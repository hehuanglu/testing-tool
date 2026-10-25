"""W3 admission and claims tests; no target credentials or runtime required."""
import copy
import contextlib
import importlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from zap_assessment.contracts import Blocked, ROOT
from zap_assessment.capabilities import load_registry, validate_registry, require_p0_mode, check_readiness, render_summary, check

sys.path.insert(0, str(ROOT/'scripts'))

class CapabilityTests(unittest.TestCase):
    def test_registry_readback_and_generated_docs(self):
        result = check()
        self.assertEqual('pass', result['registryStatus'])
        self.assertEqual('blocked', result['g3Status'])
        self.assertFalse(result['securityApproval'])
        self.assertEqual(0, result['targetRequests'])
        self.assertEqual((ROOT/'docs/remediation/CAPABILITIES_GENERATED.md').read_text(), render_summary(load_registry()))

    def test_every_p0_mode_denied(self):
        for mode in ('native','delegated','business','unknown','',None,[]):
            with self.subTest(mode=mode), self.assertRaises(Blocked): require_p0_mode(mode)

    def test_every_generated_evidence_link_resolves_to_workspace_file(self):
        import re
        base=ROOT/'docs/remediation'
        links=re.findall(r'\]\(([^)]+)\)',render_summary(load_registry()))
        self.assertGreater(len(links),0)
        for link in links:
            with self.subTest(link=link):
                target=(base/link).resolve()
                self.assertTrue(target.is_relative_to(ROOT.parent))
                self.assertTrue(target.is_file())

    def test_pilot_denied_before_files_metadata_or_docker(self):
        pilot = importlib.import_module('finalsource_p0')
        with tempfile.TemporaryDirectory() as t:
            for mode in ('native','delegated','business'):
                dest = Path(t)/mode
                with patch.object(pilot,'metadata',side_effect=AssertionError('Docker observed')), \
                     patch.object(pilot.Path,'read_text',side_effect=AssertionError('file read')), \
                     self.assertRaises(Blocked):
                    pilot.Pilot(dest,'A',mode,Path('/missing-secret'),[1])
                self.assertFalse(dest.exists())

    def test_cli_denied_before_receipt_credentials_or_output(self):
        pilot = importlib.import_module('finalsource_p0')
        with tempfile.TemporaryDirectory() as t:
            for mode in ('native','delegated','business'):
                args=['pilot','--mode',mode,'--output',str(Path(t)/mode),'--credentials','/missing-secret','--receipt','/missing-receipt']
                with patch.object(sys,'argv',args), patch.object(pilot.Path,'read_text',side_effect=AssertionError('file read')), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(2,pilot.main())
                self.assertFalse((Path(t)/mode).exists())

    def test_serve_denied_before_state_secrets_or_socket(self):
        guard=importlib.import_module('finalsource_p0_guard')
        for mode in ('native','delegated','business'):
            with patch.object(guard,'State',side_effect=AssertionError('credential read')), \
                 patch.object(guard,'ThreadingHTTPServer',side_effect=AssertionError('socket')), self.assertRaises(Blocked):
                guard.serve({'mode':mode})

    def test_execute_provision_recheck_mode(self):
        pilot=importlib.import_module('finalsource_p0')
        p=object.__new__(pilot.Pilot);p.mode='native'
        for f in (p.execute,p.provision):
            with self.assertRaises(Blocked):f()

    def test_offline_coverage_route_kept(self):
        pilot=importlib.import_module('finalsource_p0')
        collector=importlib.import_module('finalsource_p0_coverage')
        with patch.object(sys,'argv',['pilot','coverage','historical','--output','fresh']), patch.object(collector,'main',return_value=0) as run:
            self.assertEqual(0,pilot.main());run.assert_called_once_with(['historical','--output','fresh'])

    def test_registry_cannot_grant_permission_or_enable_historical_pilot(self):
        for change in ('authority','policy','current','gates','duplicate','unknown'):
            r=load_registry(); c=next(c for c in r['capabilities'] if c['capabilityId']=='p0-delegated')
            if change=='authority':r['grantsAuthority']=True
            elif change=='policy':c['executionPolicy']='existing-contract'
            elif change=='current':c['evidenceLevel']='current-runtime-verified'
            elif change=='gates':c['gateStatus']='pass'
            elif change=='duplicate':r['capabilities'].append(copy.deepcopy(c))
            else:c['evidenceRefs']=['missing']
            with self.subTest(change=change),self.assertRaises(Blocked):validate_registry(r)

    def test_bad_reference_paths_and_checksums_rejected(self):
        for path in ('../secret.json','/tmp/secret.json','.zap-auth/private.json','foo/../../bar','a\\b'):
            r=load_registry();r['references'][0]['path']=path
            with self.subTest(path=path),self.assertRaises(Blocked):validate_registry(r)
        r=load_registry();r['references'][0]['sha256']='0'*64
        with self.assertRaises(Blocked):validate_registry(r,readback=True)

    def test_reference_symlink_hardlink_and_directory_alias_rejected(self):
        from zap_assessment import capabilities as c
        with tempfile.TemporaryDirectory() as t, patch.object(c,'WORKSPACE',Path(t)):
            root=Path(t);d=root/'test-artifacts';d.mkdir()
            f=d/'credential-audit.json';f.write_bytes(b'{}')
            (d/'alias.json').symlink_to(f)
            (root/'alias').symlink_to(d,target_is_directory=True)
            for path in ('test-artifacts/alias.json','alias/credential-audit.json'):
                with self.subTest(path=path),self.assertRaises(Blocked):c._read_relative(path)
            import os
            os.link(f,d/'hard.json')
            with self.assertRaises(Blocked):c._read_relative('test-artifacts/hard.json')

    def test_registry_check_is_offline_and_does_not_modify_files(self):
        import hashlib
        import socket
        import subprocess
        paths=[ROOT/'profiles/capability-registry.json',ROOT/'profiles/secret-sink-inventory.json',
               ROOT/'docs/remediation/CAPABILITIES_GENERATED.md']
        before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        with patch.object(socket,'socket',side_effect=AssertionError('network')), \
             patch.object(subprocess,'Popen',side_effect=AssertionError('process')):
            self.assertEqual('pass',check()['registryStatus'])
        self.assertEqual(before,[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths])

    def test_schema_versions_and_extra_claims_rejected(self):
        for change in ('version','extra','missing','policy'):
            r=load_registry()
            if change=='version':r['schemaVersion']='capability-registry/9.0'
            elif change=='extra':r['securityApproval']=True
            elif change=='missing':r['capabilities'][0].pop('limitations')
            else:r['capabilities'][1]['gateStatus']='blocked'
            with self.subTest(change=change),self.assertRaises(Blocked):validate_registry(r)

    def test_missing_unknown_and_duplicate_sink_or_lifecycle_rejected(self):
        m=json.loads((ROOT/'profiles/secret-sink-inventory.json').read_text())
        for change in ('sink','case','encoding','duplicate','unreadable','unknown'):
            d=copy.deepcopy(m)
            if change=='sink':d['sinks'].pop()
            elif change=='case':d['requiredLifecycle'].pop()
            elif change=='encoding':d['encodings'].pop()
            elif change=='duplicate':d['sinks'].append(copy.deepcopy(d['sinks'][0]))
            elif change=='unreadable':d['sinks'][0]['auditStatus']='pass'
            else:d['sinks'][0]['sinkId']='unknown'
            with self.subTest(change=change),self.assertRaises(Blocked):check_readiness(d)

    def test_readiness_never_claims_g3_from_inventory_or_partial_audit(self):
        m=json.loads((ROOT/'profiles/secret-sink-inventory.json').read_text())
        result=check_readiness(m)
        self.assertEqual('pass',result['inventoryStatus'])
        self.assertEqual('blocked',result['g3Status'])
        self.assertGreater(len(result['missingProof']),0)
        self.assertEqual([], result['operationalModesEnabled'])

if __name__=='__main__': unittest.main()
