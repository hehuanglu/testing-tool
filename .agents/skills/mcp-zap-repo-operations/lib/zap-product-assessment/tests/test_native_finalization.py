"""Offline fault checks: native cleanup survives journal finalization failure."""
from contextlib import ExitStack
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from zap_assessment import product_native


class NativeFinalizationTests(unittest.TestCase):
    def run_fault(self, output, rebound=False):
        workflow={'discovery':{},'workload':{},'runId':'owned-test'}
        actor={'role':'reader','subject':'1','username':'owned','password':'private','provenance':{}}
        compiled={'targetBinding':{},'origin':'http://owned'}
        resources={'mcp':'owned-mcp','zap':'owned-zap','mcpContainerId':'mcp-id',
                   'zapContainerId':'zap-id','runLabel':'owned-label'}
        run=Mock()
        run.prepare.side_effect=RuntimeError('synthetic preparation failure')
        run.finish.side_effect=OSError('synthetic finalization IO failure')
        calls=[]
        def docker(*args):
            calls.append(args)
            if args[0]=='inspect':
                if args[2]=='{{.Id}}':
                    return 'foreign-id' if rebound else resources[('mcp' if args[3]=='owned-mcp' else 'zap')+'ContainerId']
                return 'owned-label'
            return ''
        with ExitStack() as stack:
            for target,value in (
                ('product_native.validate_workflow',SimpleNamespace()),
                ('product_identity.strategy',{'version':'offline-test'}),
                ('product_native.compile_track',compiled),
                ('product_resources.preflight',{}),
                ('product_native.profile',{'id':'offline-profile'}),
                ('product_native.provision',(resources,Mock(),Mock(),Mock())),
                ('product_native.ResearchRun',run),
                ('product_native.cleanup_images',[]),
                ('product_scope.task_readback',{}),
            ):
                stack.enter_context(patch('zap_assessment.'+target,return_value=value))
            stack.enter_context(patch('zap_assessment.product_workflow.archive_sources'))
            stack.enter_context(patch('zap_assessment.product_native.manifest'))
            stack.enter_context(patch('zap_assessment.product_scope.apply_completion',side_effect=lambda result,scope:result))
            stack.enter_context(patch('zap_assessment.product_native.docker',side_effect=docker))
            result=product_native.execute(workflow,lambda:None,output,actor,'unused.jar')
        return result,calls,run

    def test_owned_cleanup_runs_when_finish_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,calls,run=self.run_fault(Path(tmp)/'run')
        self.assertEqual([c for c in calls if c[0]=='rm'],[('rm','-f','owned-mcp'),('rm','-f','owned-zap')])
        self.assertEqual(result['cleanupStatus'],'clean')
        self.assertEqual(result['finalizationError'],'OSError')
        self.assertEqual((result['executionStatus'],result['evidenceStatus'],result['gateDecision']),('failed','incomplete','block'))
        run.finish.assert_called_once()
        run.tool.assert_not_called()

    def test_finish_failure_never_bypasses_cleanup_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,calls,_=self.run_fault(Path(tmp)/'run',rebound=True)
        self.assertFalse(any(c[0]=='rm' for c in calls))
        self.assertEqual(result['cleanupStatus'],'incomplete')
        self.assertEqual(result['gateDecision'],'block')


if __name__=='__main__':unittest.main()
