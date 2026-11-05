import copy
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from test_coordinator_recovery import prepared
from test_criteria_workflow import working
from zap_assessment import assessment_store as store
from zap_assessment.contracts import canonical
from zap_assessment.operator_state import default_operator


class StoreTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.root = self.base / 'state'
        self.registry = self.base / 'registry'
        self.source = self.base / 'source.json'
        self.run = working()
        self.operator = default_operator(self.run)

    def register(self, root=None):
        self.source.write_bytes(canonical(self.run))
        return store.register_store(self.registry, root or self.root, self.source, self.operator,
                                    registration_id='registration')

    def commit(self, parent, key='next', *, run=None, operator=None):
        return store.commit_snapshot(self.root, expected_generation=parent, commit_id=key,
                                     run=run or self.run, operator_state=operator or self.operator)

    def test_B01_B02_B14_registration_identity_and_artifact_base(self):
        first = self.register()
        self.assertTrue(self.register()['alreadyApplied'])
        self.assertEqual(store.resolve_store(self.registry, 'A1')['storePath'], str(self.root))
        with self.assertRaisesRegex(store.StateError, 'different registration'):
            self.register(self.base / 'other')
        snap = store.load_current(self.root)
        self.assertEqual(snap.generation_id, first['generationId'])
        self.assertEqual(snap.resolve_reference('retained/out.json'), self.base / 'retained/out.json')
        self.assertEqual(self.source.read_bytes(), canonical(self.run))

    def test_B03_genesis_exists_before_registry_publication(self):
        write = store.immutable

        def interrupt(path, data):
            if path.parent == self.registry:
                raise OSError('lost registry publication')
            return write(path, data)

        with patch.object(store, 'immutable', interrupt), self.assertRaises(OSError):
            self.register()
        self.assertTrue(self.register()['alreadyApplied'])

    def test_B04_B05_B06_B07_staged_and_committed_retries(self):
        parent = self.register()['generationId']
        write = store.immutable

        def interrupt(path, data):
            if path.name == 'OPERATOR.json':
                raise OSError('partial staged generation')
            return write(path, data)

        with patch.object(store, 'immutable', interrupt), self.assertRaises(OSError):
            self.commit(parent)
        self.assertEqual(store.load_current(self.root).generation_id, parent)
        publish = store._publish

        def lost_receipt(*args):
            publish(*args)
            raise OSError('lost response')

        with patch.object(store, '_publish', lost_receipt), self.assertRaises(OSError):
            self.commit(parent)
        first = self.commit(parent)
        self.assertTrue(first['alreadyApplied'])
        second = self.commit(first['generationId'], 'newer')
        self.assertEqual(self.commit(parent)['currentGenerationId'], second['generationId'])
        changed = dict(self.run, harmlessMetadata=True)
        with self.assertRaisesRegex(store.StateError, 'different request'):
            self.commit(parent, run=changed)
        with self.assertRaisesRegex(store.StateError, 'no longer current'):
            self.commit(parent, 'stale')

    def test_B08_competing_writers(self):
        parent = self.register()['generationId']

        def writer(key):
            try:
                return self.commit(parent, key)['generationId']
            except store.StateError as exc:
                return exc.code

        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(writer, ('one', 'two')))
        self.assertIn('stale-generation', results)
        self.assertIn(store.load_current(self.root).generation_id, results)

    def test_B09_D08_tampering_missing_symlink_escape(self):
        self.register()
        snap = store.load_current(self.root)
        original = snap.run_path.read_bytes()
        snap.run_path.write_bytes(b'{}')
        with self.assertRaises(store.StateError):
            store.load_current(self.root)
        snap.run_path.unlink()
        with self.assertRaises(store.StateError):
            store.load_current(self.root)
        snap.run_path.symlink_to(self.source)
        with self.assertRaises(store.StateError):
            store.load_current(self.root)
        snap.run_path.unlink()
        snap.run_path.write_bytes(original)
        (self.root / 'current.json').write_bytes(canonical(dict(version=1, assessmentId='A1',
            generationId='../elsewhere', manifestSha256='none')))
        with self.assertRaises(store.StateError):
            store.load_current(self.root)

    def test_B10_projection_failure_preserves_commit(self):
        from zap_assessment.assessment_state_cli import render_current

        parent = self.register()['generationId']
        with patch('zap_assessment.assessment_state_cli.render_current', side_effect=OSError('projection')):
            receipt = self.commit(parent)
        self.assertTrue(receipt['projectionsPending'])
        snap = store.load_current(self.root)
        self.assertEqual(snap.generation_id, receipt['generationId'])
        self.assertTrue(Path(render_current(snap)['checklist.md']).is_file())

    def test_B11_preserve_history_and_recheck_approval(self):
        self.run['actionHistory'] = [dict(actionId='fixture-unknown', state='intent')]
        parent = self.register()['generationId']
        operator = dict(self.operator, activeBlockId=None)
        receipt = self.commit(parent, operator=operator)
        snap = store.load_current(self.root)
        self.assertEqual(snap.run, self.run)
        for field, value in (('operations', []), ('actionHistory', []), ('coordinatorState', {})):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.commit(receipt['generationId'], field, run=dict(self.run, **{field: value}))
        changed = copy.deepcopy(self.run)
        changed['criteriaWorkflow']['planRevision'] = 'P-2'
        self.commit(receipt['generationId'], 'revision', run=changed, operator=operator)
        from zap_assessment.criteria_workflow import review_workflow
        self.assertFalse(review_workflow(store.load_current(self.root).run)['approvalStatus']['plan'])

    def test_B15_degraded_operator_only_commit(self):
        (self.base / 'coordinator').mkdir()
        self.run, packet, coordinator = prepared(self.base / 'coordinator')
        self.operator = default_operator(self.run)
        parent = self.register()['generationId']
        coordinator.acquire(self.run, packet)
        with coordinator._journal_args()[0].open('ab') as stream:
            stream.write(b'{')
        with self.assertRaisesRegex(store.StateError, 'unchanged RUN'):
            self.commit(parent, 'bad', run=dict(self.run, arbitrary='change'))
        receipt = self.commit(parent, operator=dict(self.operator, activeBlockId=None))
        self.assertEqual(store.load_current(self.root).generation_id, receipt['generationId'])
