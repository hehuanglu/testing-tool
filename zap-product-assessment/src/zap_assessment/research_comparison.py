"""Conservative repeatability comparison; never invent product A->B remediation."""
import json
import hashlib
from pathlib import Path
from .research import digest, verify_manifest


def compare_runs(before,after,image_equivalence=None):
    roots=[Path(before),Path(after)]
    def read(root,name):return json.loads((root/name).read_text())
    result={'comparisonKind':'same-build-research-repeatability','decision':'inconclusive',
            'productFixedBuildRegression':'pending-selected-build-B','reasons':[]}
    for root in roots:
        try:verify_manifest(root)
        except (ValueError,OSError):result['reasons'].append('missing/truncated/changed evidence: '+root.name)
    if result['reasons']:return result
    try:
        runs=[read(r,'RUN.json') for r in roots]
        for r in runs:
            if r['executionStatus']!='completed' or r['evidenceStatus']!='complete' or r['orchestration']['authLost']:
                result['reasons'].append('run incomplete or authentication lost')
        for root in roots:
            if not all(row['pass'] is not False for row in read(root,'CASES.json')):result['reasons'].append('failed operation/route')
            if read(root,'actual-rule-disposition.json')['unexpected']:result['reasons'].append('unexpected active rule')
        resources=[read(r,'resources.json') for r in roots]
        equivalent=False
        if image_equivalence is not None:
            proof=read(Path(image_equivalence).parent,Path(image_equivalence).name)
            images=proof['images']
            expected={r['mcpImageId'] for r in resources}
            actual={r['imageId'] for r in images}
            signatures=[hashlib.sha256(json.dumps(r['signature'],sort_keys=True).encode()).hexdigest() for r in images]
            equivalent=(len(images)==2 and expected==actual and signatures[0]==signatures[1]
                        and all(r['sha256']==s for r,s in zip(images,signatures))
                        and all(r['signature']['layers'] for r in images))
            result['imageEquivalence']={'accepted':equivalent,'evidenceSha256':digest(image_equivalence),
                'distinctImageIds':[r['mcpImageId'] for r in resources],
                'basis':'identical complete filesystem layer digests, OS/architecture and runtime config hash; local Docker observation'}
        for key in ('jarSha256','mcpImageId','zapImageId'):
            if resources[0][key]!=resources[1][key] and not (key=='mcpImageId' and equivalent):
                result['reasons'].append('scanner drift: '+key)
        if resources[0]['targetBinding']['imageId']!=resources[1]['targetBinding']['imageId']:
            result['reasons'].append('target build differs; requires explicit product regression contract')
        for filename in ('addons.json','rules.json','OPERATIONS.json','actual-rule-disposition.json'):
            values=[read(r,filename) for r in roots]
            if values[0]!=values[1]:result['reasons'].append('inventory/rule drift: '+filename)
        if not result['reasons']:
            result['decision']='repeatability-compatible'
            result['counts']=[read(r,'COVERAGE.json') for r in roots]
            result['note']='Dynamic fixture IDs and request counts may differ. No fixed-build resolved/new security verdict implied.'
    except (OSError,KeyError,ValueError):result['reasons'].append('required comparison evidence absent or invalid')
    return result
