"""Stdlib-only in-container driver. Origin fixed to this network-none fixture."""
import json
from pathlib import Path
import sys
from .bola_http import exchange


def collect(jobs, state_path, run_id):
    rows=[];seq=0
    def call(job,case):
        nonlocal seq
        seq+=1;ident=run_id+'-request-'+str(seq);request=job['request']
        headers={'X-W6-Request':ident,'X-W6-Case':case,'Content-Type':'application/json'}
        if job['subject'] is not None:headers['X-W6-Subject']=str(job['subject'])
        payload=json.dumps(request['body']).encode() if request['body'] is not None else None
        status,body,_=exchange('http://127.0.0.1:18080',request['method'],request['path'],headers,payload,3)
        return {'requestId':ident,'actorRef':job['actorRef'],'request':request,'status':status,'body':body}
    for job in jobs:
        row={'caseId':job['caseId'],'preState':json.loads(Path(state_path).read_text())}
        for field in ('ownerIdentity','ownerPositive','identity','exchange'):row[field]=call(job[field],job['caseId'])
        row['postState']=json.loads(Path(state_path).read_text());row['expectedPostStateSha256']=job['expectedPostStateSha256']
        rows.append(row)
    return rows


if __name__=='__main__':
    payload=json.load(sys.stdin)
    result={'cases':collect(payload['jobs'],'/state/state.json',payload['runId'])}
    if payload.get('unifiedBinding'):result['unifiedBinding']=payload['unifiedBinding']
    print(json.dumps(result))
