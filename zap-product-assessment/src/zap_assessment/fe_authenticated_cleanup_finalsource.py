"""Exact owned account cleanup after complete product readback; unsupported objects retain ledgers."""
from pathlib import Path
from .fe_authenticated_fixture_finalsource import FixtureClient
from .fe_authenticated_contract import load,save

def cleanup(plan,root,actors):
    root=Path(root);result={'accounts':{},'retained':[],'replay':False}
    for ref,actor in actors.items():
        result['retained'].append({'actorRef':ref,'kind':'principal','ids':[actor['subject']],'reason':'No supported user DELETE endpoint'})
        goals=[actor.get('fixtures',{}).get(k) for k in ('ownedGoalId','expenseGoalId') if actor.get('fixtures',{}).get(k) is not None]
        if goals:result['retained'].append({'actorRef':ref,'kind':'goal','ids':sorted(goals),'reason':'No supported goal DELETE endpoint; owned browser readback retained'})
        ledger=root/'private/fixtures'/ref/'FIXTURE_DAG.json'
        if not ledger.exists():
            continue
        data=load(ledger)
        if data['subject']!=actor['subject']:raise ValueError('cleanup actor ledger mismatch')
        ids=[a['id'] for a in data['accounts']]
        if len(set(ids))!=len(ids) or len(ids)>data['maxNewAccounts']:raise ValueError('cleanup owned ledger row budget')
        if not ids:continue
        folder=root/'private/cleanup'/ref;folder.mkdir(mode=0o700,parents=True,exist_ok=False)
        client=FixtureClient(plan['selection'],folder,max_requests=len(ids)+2);token=actor['setupToken']
        before=client.send('GET','/api/v1/accounts',token=token)['data']
        if before['user_id']!=actor['subject']:raise ValueError('cleanup collection owner proof absent')
        present=set(ids)&{a['id'] for a in before['accounts']}
        intent={'actorRef':ref,'subject':actor['subject'],'exactAccountIds':ids,'cascade':'only transactions related to these exact owned test accounts','state':'intent','replay':False};save(folder,'CLEANUP_INTENT.json',intent)
        for identifier in ids:
            if identifier not in present:continue  # already absent, confirmed by current protected readback
            response=client.send('DELETE','/api/v1/accounts/'+str(identifier),token=token)
            if response['data']['deleted_account_id']!=identifier:raise ValueError('cleanup exact DELETE acknowledgement mismatch')
        after=client.send('GET','/api/v1/accounts',token=token)['data']
        if after['user_id']!=actor['subject'] or set(ids)&{a['id'] for a in after['accounts']}:raise ValueError('cleanup absence proof failed')
        intent.update(state='acknowledged',absenceVerified=True);save(folder,'CLEANUP_INTENT.json',intent);result['accounts'][ref]=ids
        for kind,field in (('category','categoryId'),('bill','billId')):
            if data.get('database',{}).get(field) is not None:result['retained'].append({'actorRef':ref,'kind':kind,'ids':[data['database'][field]],'reason':'Setup-only INSERT adapter has no qualified DELETE path; exact owned row retained'})
    save(root,'FIXTURE_CLEANUP.json',result);return result
