"""Offline dependency-selection probe; no product data or effects."""
import copy
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
library = root / '.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment'
sys.path[:0] = [str(library / 'src'), str(library / 'tests')]
from test_criteria_workflow import working, approve
from zap_assessment.criteria_resume import resume_next

run = working(None)
workflow = run['criteriaWorkflow']
first = workflow['plan']['cases'][0]
second = copy.deepcopy(first)
second['id'] = 'T2'
first['dependsOnCases'] = ['T2']
workflow['plan']['cases'].append(second)
workflow['criteria'][0]['caseIds'].append('T2')
approve(run)
result = resume_next(run)
print('T1 depends on unfinished T2. Candidate:', result['nextAction'])
assert result['nextAction']['caseId'] == 'T1', 'Behavior changed; reassess F06'
