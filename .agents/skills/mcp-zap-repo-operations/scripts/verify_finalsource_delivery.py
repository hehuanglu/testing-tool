#!/usr/bin/env python3
"""Offline evidence verification. Exit0 means integrity, never security approval."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import urlsplit

WORKSPACE=Path('/Users/hahoangloc/Working/testing tool')
sys.path.insert(0,str(WORKSPACE/'zap-product-assessment/src'))
sys.dont_write_bytecode=True


def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_bytes())
def require(value,message):
    if not value:raise ValueError(message)


def checked_files(root):
    m=read(root/'manifest.json')
    require(sha((root/'manifest.json').read_bytes())==(root/'manifest.sha256').read_text().strip(),'manifest hash')
    for item in m['artifacts']:
        rel=PurePosixPath(item['path'])
        require(not rel.is_absolute() and '..' not in rel.parts,'artifact path')
        p=root/str(rel)
        require(not p.is_symlink() and p.resolve().is_relative_to(root.resolve()),'artifact symlink/boundary')
        require(all(not q.is_symlink() for q in p.parents if q!=root.parent),'artifact parent symlink')
        b=p.read_bytes();require(len(b)==item['bytes'] and sha(b)==item['sha256'],'artifact bytes/hash: '+str(rel))
    return m


def tool_text(response):
    text='\n'.join(x['text'] for x in response['content'] if x.get('type')=='text')
    return json.loads(text) if text.startswith('"') else text


def verify(root):
    from zap_assessment.evidence import verify_bundle
    from zap_assessment.contracts import digest
    from jsonschema import Draft202012Validator
    root=root.resolve();top=checked_files(root);native=root/'native-r3';nm=checked_files(native)
    result=read(native/'result.json')
    require(result['executionStatus']=='completed' and result['evidenceStatus']=='complete' and result['cleanupStatus']=='clean'
            and result['borrowedTargetBindingUnchanged'] is True,'native run completion/cleanup')
    plan=read(native/'plan.json')
    require(sha((root/'operator-sources/run_finalsource_native.py').read_bytes())==plan['wrapperSourceSha256'],'executed native wrapper source')
    catalog=read(native/'mcp-discovery.json')['tools'];index=read(native/'tool-index.json');pages={};passive=[]
    for event in index:
        prefix=f"{event['index']:04d}-{event['tool']}"
        request=read(native/'tools'/(prefix+'-request.json'));response=read(native/'tools'/(prefix+'-response.json'))
        require(request['tool']==event['tool'] and not response.get('isError'),'MCP tool transcript')
        Draft202012Validator(catalog[event['tool']]).validate(request['arguments'])
        text=tool_text(response)
        if event['tool']=='zap_report_read_chunk':
            page=json.loads(text);pages.setdefault(page['reportPath'],[]).append(page)
        if event['tool']=='zap_passive_scan_status':passive.append(text)
    require(len(passive)>=2 and all('Completed: yes' in x and 'Records remaining: 0' in x for x in passive[-2:]),'passive stable observations')
    operations=read(native/'operations.json')
    require(len(operations)==4 and sum(x['kind']=='active' for x in operations)==2
            and all('Completed: yes' in x['status'] for x in operations),'terminal crawl/active tool observations')
    report_results=[]
    for label in ('frontend','backend'):
        for kind in ('json','html'):
            b=(native/'reports'/(label+'.'+kind)).read_bytes();rb=read(native/'reports'/(label+'-'+kind+'-readback.json'))
            pp=pages[rb['reportPath']];offset=0;parts=[]
            for n,page in enumerate(pp):
                require(page['offset']==offset and page['artifactSha256']==rb['sha256'],'page continuity/hash')
                require(page['charactersReturned']==len(page['content']),'Unicode codepoint page length')
                parts.append(page['content']);offset+=len(page['content'])
                if n<len(pp)-1:require(not page['endOfFile'] and page['nextOffset']==offset,'page next offset')
            require(pp[-1]['endOfFile'] and offset==pp[-1]['totalCharacters'],'report EOF/total length')
            require(''.join(parts).encode()==b and len(b)==rb['bytes'] and sha(b)==rb['sha256'],'full report readback')
            report_results.append({'report':label+'.'+kind,'bytes':len(b),'pages':len(pp),'sha256':sha(b)})
    guard=read(native/'config/guard.json');forwarded=denied=0
    for line in (native/'guard/proxy.jsonl').read_text().splitlines():
        e=json.loads(line)
        if e['action']=='forwarded':
            u=urlsplit(e['url']);require(e['method']=='GET' and u.netloc==guard['backendAuthority'] and u.path in guard['allowedPaths'],'backend forwarded scope')
            forwarded+=1
        elif e['action']=='denied':denied+=1
        else:require(False,'backend guard upstream failure')
    bm=verify_bundle(root/'bola-bundle');fixture=read(root/'fixture/fixture-manifest.json');bp=read(root/'bola-bundle/plan.json')
    require(bp['config']['fixture']['accountId']==fixture['accountId'] and fixture['createdAccount']['user_id']==fixture['ownerId'],'actual created account binding')
    require(bp['config']['fixture']['provenanceRef']=='sha256:'+digest(fixture),'fixture provenance digest')
    probe=read(root/'auth-probes/result.json');register=read(root/'auth-probes/04-weak-register-response.json');login=read(root/'auth-probes/05-weak-login-response.json')
    require(register['status']==201 and login['status']==200 and register['body']['data']['user']['id']==login['body']['data']['user']['id'],'weak-password creation/login evidence')
    require(len(read(root/'auth-probes/test-credentials-input.json')['password'])==1,'one-character test password')
    normalized=read(root/'auth-probes/login-failure-normalized-comparison.json')
    require(normalized['semanticsEqual'] and normalized['rawArtifactsUnchanged'],'login failure interpretation')
    # Do not mistake a public scan that never used credentials for an
    # authenticated ZAP secret-gate proof. Check only the stated no-secret claim.
    credentials=read(root/'fixture/test-credentials.json')
    secrets=[v for actor in credentials['actors'].values() for k,v in actor.items() if k in ('password','registrationToken')]
    for file in native.rglob('*'):
        if file.is_file():
            b=file.read_bytes();require(not any(v.encode() in b for v in secrets),'generated target credential entered native evidence')
    return {'verified':True,'artifactCount':len(top['artifacts']),'nativeArtifactCount':len(nm['artifacts']),
        'nativeToolCalls':len(index),'reports':report_results,'backendForwardedGETs':forwarded,'backendGuardDeniedRequests':denied,
        'bolaStatuses':{k:bm[k] for k in ('executionStatus','evidenceStatus','securityVerdict','cleanupStatus','gateDecision')},
        'weakPasswordAcceptanceVerified':True,'generatedABCredentialsAbsentFromNativeEvidence':True,
        'repoChecks':read(root/'repo-checks/summary.json'),
        'securityApproval':False,'limits':['Checksums and internally consistent recorded observations; not signed independent attestation',
           'No HTTP/Docker/test replay','BOLA client dispatch is not target-side wire observation','Confirmed findings require remediation/triage; verification is not security pass']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('bundle',type=Path);args=p.parse_args()
    print(json.dumps(verify(args.bundle),ensure_ascii=False,indent=2))
