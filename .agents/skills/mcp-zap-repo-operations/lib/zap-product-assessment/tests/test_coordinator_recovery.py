"""Fixture-only process interruption tests at durable lease boundaries."""
import json
import multiprocessing
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_criteria_workflow as fixtures
from zap_assessment import criteria_delegation as delegation
from zap_assessment.contracts import Blocked, canonical
from zap_assessment.journal import Journal


def prepared(directory, assessment_id='A1'):
    run, _, coordinator = fixtures.CoordinatorRecoveryTests().prepare(directory, assessment_id)
    run['criteriaWorkflow']['plan']['resourceIds'] = ['one', 'two']
    fixtures.approve(run)
    return run, delegation.make_packet(run, 'W1', ['T1'], 'worker'), coordinator


def interrupt(run, packet, coordinator, boundary):
    append = Journal.append
    publish = delegation.atomic_bytes
    unlink = Path.unlink
    count = 0

    def append_then_exit(journal, kind, row):
        event = append(journal, kind, row)
        if kind == boundary:
            os._exit(77)
        return event

    def write_then_exit(path, data):
        nonlocal count
        publish(path, data)
        if path.parent == coordinator.resources:
            count += 1
            if boundary == 'lease-' + str(count):
                os._exit(77)

    def unlink_then_exit(path, *args, **kwargs):
        unlink(path, *args, **kwargs)
        if path.parent == coordinator.resources and boundary == 'unlink':
            os._exit(77)

    with patch.object(Journal, 'append', append_then_exit), patch.object(
        delegation, 'atomic_bytes', write_then_exit
    ), patch.object(Path, 'unlink', unlink_then_exit):
        if boundary in ('lease_release_intent', 'unlink'):
            coordinator.release(run, packet)
        else:
            coordinator.acquire(run, packet)


class TransactionTests(unittest.TestCase):
    def kill_at(self, run, packet, coordinator, boundary):
        worker = multiprocessing.get_context('fork').Process(target=interrupt,
            args=(run, packet, coordinator, boundary))
        worker.start()
        worker.join(10)
        if worker.is_alive():
            worker.kill()
            worker.join()
        self.assertEqual(worker.exitcode, 77)

    def test_A01_A02_A03_A04_acquire_after_process_exit(self):
        for boundary in ('lease_acquire_intent', 'lease-1', 'lease-2'):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as temp:
                run, packet, coordinator = prepared(temp)
                self.kill_at(run, packet, coordinator, boundary)
                cold = delegation.Coordinator(temp, 'A1')
                self.assertEqual(cold.inspect_recovery()['openTransactions'][0]['kind'], 'lease_acquire_intent')
                self.assertFalse(cold.recover_transactions(run, packet)['alreadyApplied'])
                self.assertTrue(cold.acquire(run, packet)['alreadyApplied'])
                self.assertEqual([row['kind'] for row in cold._journal().events], ['lease_acquire_intent', 'leased'])

    def test_A05_lost_append_ack_does_not_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            run, packet, coordinator = prepared(temp)
            append = Journal.append

            def fail(journal, kind, data):
                result = append(journal, kind, data)
                if kind == 'leased':
                    raise OSError('lost write acknowledgment')
                return result

            with patch.object(Journal, 'append', fail), self.assertRaises(OSError):
                coordinator.acquire(run, packet)
            self.assertTrue(coordinator.acquire(run, packet)['alreadyApplied'])

    def test_A06_A14_torn_tail_forensics_block_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            run, packet, coordinator = prepared(temp)
            coordinator.acquire(run, packet)
            coordinator.dispatch(run, packet, packet['cases'][0]['actions'][0], lambda _: None)
            path = coordinator._journal_args()[0]
            valid = path.read_bytes()
            with path.open('ab') as stream:
                stream.write(b'{"partial":')
            facts = coordinator.inspect_recovery()
            self.assertEqual(facts['validPrefixBytes'], len(valid))
            self.assertEqual(facts['integrity'], 'incomplete-tail')
            self.assertIsNone(facts['pendingEffects'])
            self.assertEqual(facts['knownPendingEffects'][0]['actionId'], 'read-1')
            self.assertFalse(facts['effectsAllowed'])
            with self.assertRaises(Blocked):
                coordinator.dispatch(run, packet, packet['cases'][0]['actions'][0], self.fail)
            self.assertTrue(all(coordinator._path(r).is_file() for r in packet['resourceIds']))

    def test_A07_A08_A09_A13_release_restarts_and_cannot_reacquire(self):
        for boundary in ('lease_release_intent', 'unlink'):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as temp:
                run, packet, coordinator = prepared(temp)
                coordinator.acquire(run, packet)
                self.kill_at(run, packet, coordinator, boundary)
                cold = delegation.Coordinator(temp, 'A1')
                self.assertTrue(cold.recover_transactions(run, packet)['released'])
                other, other_packet, other_coordinator = prepared(temp, 'A2')
                other_coordinator.acquire(other, other_packet)
                self.assertTrue(cold.release(run, packet)['alreadyApplied'])
                other_coordinator._check_leases(other_packet)
                with self.assertRaises(delegation.DelegationError):
                    cold.acquire(run, packet)

    def test_A10_A16_original_packet_retained_after_stop(self):
        with tempfile.TemporaryDirectory() as temp:
            run, packet, coordinator = prepared(temp)
            coordinator.acquire(run, packet)
            coordinator.dispatch(run, packet, packet['cases'][0]['actions'][0], lambda _: None)
            run['criteriaWorkflow']['userRequest'] = dict(kind='stop', source='fixture')
            with self.assertRaises(delegation.DelegationError):
                coordinator.release(run, packet)
            with self.assertRaises(delegation.DelegationError):
                coordinator.dispatch(run, packet, packet['cases'][0]['actions'][0], self.fail)
            fixtures.CoordinatorRecoveryTests().terminal(run, packet)
            coordinator.reconcile(run, packet, 'read-1', ['terminal'])
            self.assertTrue(coordinator.release(run, packet)['released'])

    def test_A11_foreign_resource_not_deleted_on_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            run, packet, coordinator = prepared(temp)
            other, other_packet, owner = prepared(temp, 'A2')
            self.kill_at(run, packet, coordinator, 'lease_acquire_intent')
            owner.acquire(other, other_packet)
            self.assertTrue(coordinator.recover_transactions(run, packet)['aborted'])
            owner._check_leases(other_packet)

    def test_A12_legacy_leftovers_and_orphans(self):
        with tempfile.TemporaryDirectory() as temp:
            run, packet, coordinator = prepared(temp)
            binding = coordinator._binding(packet)
            for resource in packet['resourceIds']:
                delegation.atomic_bytes(coordinator._path(resource), canonical(dict(binding, resourceId=resource)))
            self.assertIn('orphan-lease-no-intent', ' '.join(coordinator.inspect_recovery()['diagnostics']))
            journal = coordinator._journal()
            journal.append('leased', dict(binding, resourceIds=packet['resourceIds']))
            journal.append('released', binding)
            coordinator._path('one').unlink()
            self.assertTrue(coordinator.recover_transactions(run, packet)['released'])
            self.assertFalse(coordinator._path('two').exists())

    def test_A15_middle_corruption_and_wrong_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            run, packet, coordinator = prepared(temp)
            coordinator.acquire(run, packet)
            path, identity, plan = coordinator._journal_args()
            self.assertEqual(Journal.inspect(path, 'foreign', plan)['integrity'], 'identity-mismatch')
            rows = path.read_bytes().splitlines()
            changed = json.loads(rows[0])
            changed['at'] = 'modified'
            path.write_bytes(canonical(changed) + b'\n' + rows[1] + b'\n')
            self.assertEqual(Journal.inspect(path, identity, plan)['validEvents'], [])
            self.assertEqual(Journal.inspect(path, identity, plan)['integrity'], 'corrupt-record')

    def test_A06_torn_lease_commit_preserves_partial_ownership(self):
        with tempfile.TemporaryDirectory() as temp:
            run, packet, coordinator = prepared(temp)
            append = Journal.append

            def tear(journal, kind, data):
                if kind == 'leased':
                    with journal.path.open('ab') as stream:
                        stream.write(b'{"seq":')
                        stream.flush()
                        os.fsync(stream.fileno())
                    raise OSError('torn lease commit')
                return append(journal, kind, data)

            with patch.object(Journal, 'append', tear), self.assertRaises(OSError):
                coordinator.acquire(run, packet)
            with self.assertRaises(Blocked):
                coordinator.recover_transactions(run, packet)
            self.assertEqual(coordinator.inspect_recovery()['integrity'], 'incomplete-tail')
            self.assertTrue(all(coordinator._path(r).is_file() for r in packet['resourceIds']))

    def test_A11_two_processes_one_resource_grant(self):
        with tempfile.TemporaryDirectory() as temp:
            first = prepared(temp)
            second = prepared(temp, 'A2')
            context = multiprocessing.get_context('fork')
            gate = context.Event()

            def acquire(arguments):
                gate.wait(10)
                run, packet, coordinator = arguments
                try:
                    coordinator.acquire(run, packet)
                except delegation.DelegationError:
                    os._exit(3)
                os._exit(0)

            children = [context.Process(target=acquire, args=(row,)) for row in (first, second)]
            try:
                for child in children:
                    child.start()
                gate.set()
                for child in children:
                    child.join(10)
                self.assertEqual(sorted(child.exitcode for child in children), [0, 3])
                winner = (first, second)[children[0].exitcode != 0]
                winner[2]._check_leases(winner[1])
            finally:
                for child in children:
                    if child.is_alive():
                        child.kill()
                        child.join()

    def test_A16_original_approved_reader_after_plan_revision(self):
        with tempfile.TemporaryDirectory() as temp:
            run, _, coordinator = prepared(temp)
            workflow = run['criteriaWorkflow']
            actions = workflow['plan']['cases'][0]['actions']
            actions.append(dict(id='read-2', caseId='T1', effect='read', readbackOf='read-1'))
            fixtures.approve(run)
            packet = delegation.make_packet(run, 'W1', ['T1'], 'worker')
            coordinator.acquire(run, packet)
            coordinator.dispatch(run, packet, actions[0], lambda _: None)
            workflow['planRevision'] = 'P-2'
            workflow['userRequest'] = dict(kind='stop', source='fixture')
            observed = []
            coordinator.dispatch(run, packet, actions[1], lambda action: observed.append(action['id']))
            self.assertEqual(observed, ['read-2'])
            with self.assertRaises(delegation.DelegationError):
                coordinator.dispatch(run, packet, actions[1], self.fail)
