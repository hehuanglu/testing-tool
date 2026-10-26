#!/usr/bin/env python3
"""Delete only accounts owned by fresh fixture actors in a verified research bundle.

No user/category/goal delete API exists; those rows are retained. No DB mutation,
reset, target restart or retry after uncertain DELETE ACK. Evidence stays intact.
"""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from zap_assessment.research import manifest,write_json,verify_manifest
from zap_assessment.research_product import Product,binding,admit_adapter,observe_transport
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--evidence-root',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
a=p.parse_args();a.output.mkdir(mode=0o700,parents=True,exist_ok=False)
rows=[];live=binding()
for run in sorted(a.evidence_root.iterdir()):
    if not run.is_dir() or not (run/'credentials.json').exists():continue
    verify_manifest(run)
    if (run/'target-binding.json').exists() and json.loads((run/'target-binding.json').read_text())!=live:
        raise ValueError('target binding drift; cleanup refused')
    discovery=json.loads((run/'PRODUCT_DISCOVERY.json').read_text()) if (run/'PRODUCT_DISCOVERY.json').exists() else None
    if discovery is not None:admit_adapter(discovery,live,observe_transport())
    product=Product(a.output/run.name,discovery=discovery)
    credentials=json.loads((run/'credentials.json').read_text())['actors']
    for actor,c in credentials.items():
        if not c['email'].startswith('research-') or not c['email'].endswith('@example.test'):
            raise ValueError('actor does not belong to generated research fixture namespace')
        provenance=[json.loads(x.read_text()) for x in (run/'direct').glob('*response.json')]
        if not any(x['label']=='register-'+actor and x['status']==201 and x['response']['data']['user']['id']==c['userId']
                   and x['response']['data']['user']['email']==c['email'] for x in provenance):
            raise ValueError('fresh actor registration provenance missing')
        login=product.request('POST','/api/auth/login',{'email':c['email'],'password':c['password']},expected=[200],label='cleanup-login')
        token=login['data']['accessToken']
        accounts=product.request('GET','/api/v1/accounts',token=token,expected=[200],label='cleanup-identity')['data']
        if accounts['user_id']!=c['userId']:raise ValueError('cleanup protected subject mismatch')
        deleted=[]
        for account in accounts['accounts']:
            result=product.request('DELETE',f'/api/v1/accounts/{account["id"]}',token=token,expected=[200],label='cleanup-owned-account')
            deleted.append(account['id'])
        after=product.request('GET','/api/v1/accounts',token=token,expected=[200],label='cleanup-empty-poststate')['data']
        if after['user_id']!=c['userId'] or after['accounts']:raise ValueError('cleanup poststate mismatch')
        rows.append({'run':run.name,'actor':actor,'userId':c['userId'],'deletedAccountIds':deleted,'poststateEmpty':True,
                     'usersCategoriesGoals':'retained; no deletion API; no existing-row DB changes'})
write_json(a.output/'CLEANUP.json',{'cleanupStatus':'fixture-accounts-cleaned-other-fixture-rows-retained','actors':rows,'targetBinding':live})
manifest(a.output);print('owned fixture account cleanup complete: '+str(len(rows))+' actors')
