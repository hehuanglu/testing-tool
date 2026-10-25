"""Independent selected-state checker. No runner/oracle/evaluate imports.

Expected state is derived from declared API inputs, not from DB observations.
This is same-repository corroboration, not external/server attestation.
"""
import json,datetime as dt
from decimal import Decimal
from pathlib import Path

def money(x):return Decimal(str(x))
def check_state(manifest,observed):
    problems=[];actors=manifest['actors'];subjects={a:v['subject'] for a,v in actors.items()}
    for table,keys in {'accounts':['id','user_id','bank_name','balance'],'categories':['id','user_id','name'],'transactions':['id','account_id','category_id','type','amount','status','item_description','transaction_date'],'goals':['id','user_id','goal_type','category_id','target_amount','start_date','end_date'],'bills':['id','user_id','item_description','amount','due_date']}.items():
        expected=manifest[table];actual=observed.get(table)
        if not isinstance(actual,list):problems.append(table+':missing projection');continue
        if {r['id'] for r in expected}!={r['id'] for r in actual} or len(actual)!=len(expected):problems.append(table+':exact ID/count mismatch')
        byid={r['id']:r for r in actual}
        for row in expected:
            other=byid.get(row['id'],{})
            for k in keys:
                if k not in other or k not in row:problems.append(table+':missing '+k);continue
                same=money(row[k])==money(other[k]) if k in ('balance','amount','target_amount') else dt.datetime.fromisoformat(row[k])==dt.datetime.fromisoformat(other[k]) if k=='transaction_date' else row[k]==other[k]
                if not same:problems.append(table+':'+str(row['id'])+':'+k)
    accounts={r['id']:r for r in observed.get('accounts',[])};cats={r['id']:r for r in observed.get('categories',[])}
    for t in observed.get('transactions',[]):
        a=accounts.get(t.get('account_id'));c=cats.get(t.get('category_id'))
        if not a or not c or a['user_id']!=c['user_id']:problems.append('orphan/foreign transaction relation')
    for g in observed.get('goals',[]):
        if g['category_id'] is not None and (g['category_id'] not in cats or cats[g['category_id']]['user_id']!=g['user_id']):problems.append('orphan/foreign goal relation')
    if len(set(subjects.values()))!=2:problems.append('actor identity collision')
    return problems

def check_pages(expected,pages,actor,subject):
    errors=[];seen=[];offset=0
    for page in pages:
        if page['actorRef']!=actor or page['subject']!=subject:errors.append('wrong actor')
        b=page['body'];data=b.get('data',{});rows=data.get('data',[]) if isinstance(data,dict) else []
        # Product envelope data is {data,total,hasMore}.
        if not isinstance(data,dict) or not {'data','total','hasMore'}<=data.keys():errors.append('unknown page projection');continue
        if page['offset']!=offset:errors.append('incomplete pages')
        ids=[r['transactionId'] for r in rows];seen+=ids;offset+=len(ids)
        if data['total']!=len(expected) or data['hasMore']!=(offset<len(expected)):errors.append('pagination total/terminal')
    if seen!=[r['id'] for r in expected] or len(seen)!=len(set(seen)):errors.append('foreign/missing/order IDs')
    if not pages or pages[-1]['body'].get('data',{}).get('hasMore') is not False:errors.append('incomplete pages')
    return errors

def verify(root):
    root=Path(root);plan=json.loads((root/'PLAN.json').read_text());rows=json.loads((root/'RESULTS.json').read_text());errors=[]
    if set(r['caseId'] for r in rows)!=set(c['id'] for c in plan['cases']):errors.append('omitted planned case/branch')
    for row in rows:
        c=next((c for c in plan['cases'] if c['id']==row['caseId']),None)
        if c is None or row['actorRef']!=c['actorRef']:errors.append(row['caseId']+':wrong actor')
        if not row.get('afterRef'):
            if row.get('attemptRef') and next(c for c in plan['cases'] if c['id']==row['caseId'])['request']['method']=='GET':continue
            errors.append(row['caseId']+':missing observation');continue
        m=json.loads((root/row['expectedRef']).read_text());o=json.loads((root/row['afterRef']).read_text())
        errors.extend(row['caseId']+':'+s for s in check_state(m,o))
    for group in json.loads((root/'PAGINATION.json').read_text()):
        errors.extend(check_pages(group['expected'],group['pages'],group['actorRef'],plan['actors'][group['actorRef']]['subject']))
    if (root/'READ_PLAN.json').exists():
        read_plan=json.loads((root/'READ_PLAN.json').read_text());read_ids={c['id'] for c in read_plan['cases']}
        for row in rows:
            c=next(c for c in plan['cases'] if c['id']==row['caseId'])
            if c['id'] in read_ids:
                errors.extend(row['caseId']+':'+e for e in check_read(read_plan['expected'],c,json.loads((root/row['attemptRef']).read_text()),read_plan['window']))
            for ref in row.get('apiOwnerReadbacks',[]):
                h=json.loads((root/ref).read_text());action=json.loads((root/h['actionRef']).read_text());uid=plan['actors'][action['actorRef']]['subject']
                if h['body'].get('data',{}).get('user_id')!=uid:errors.append(row['caseId']+':owner read wrong subject')
    declared={b['branchRef'] for op in plan['inventory']['operations'] for b in op['branches']}
    catalog={op['operationRef']:{b['branchRef'].rsplit(':',1)[1] for b in op['branches']} for op in plan['inventory']['operations']}
    for op in ('GoalsController_create','GoalsController_list','GoalsController_update'):
        if op in catalog and catalog[op]!={'Saving','Expense'}:errors.append('omitted goal business branch')
    if any(c['branchRef'] not in declared for c in plan['cases']):errors.append('unknown branch')
    if (root/'READ_STATE_CHECK.json').exists():
        r=json.loads((root/'READ_STATE_CHECK.json').read_text())
        errors.extend('after-read:'+e for e in check_state(read_plan['expected'],json.loads((root/r['afterRef']).read_text())))
    if (root/'FAILURE_MODE_RESULTS.json').exists():errors.extend(check_faults(root))
    return {'checker':'selected state and page invariants; separate implementation, no evaluate import','errors':errors,'evidenceStatus':'consistent' if not errors else 'inconsistent','cases':len(rows),'securitySignOff':False}

def check_faults(root):
    """Corroborate fault claims against durable dispatch and actual app/readback."""
    root=Path(root);load=lambda p:json.loads((root/p).read_text());errors=[]
    events=[json.loads(line) for line in (root/'journal.jsonl').read_text().splitlines()]
    results=load('FAILURE_MODE_RESULTS.json')['results']
    if {r['mode'] for r in results}!={'lost-response','hard-kill-inflight','lost-response-denied'} or len(results)!=3:errors.append('fault corpus incomplete')
    for r in results:
        mode=r['mode'];base='faults/'+mode+'/';locked=load(base+'LOCKED_REQUEST.json');proxy=load(r['proxyRef']);action_ref='actions/fault-'+mode+'.json';action=load(action_ref)
        intents=[e for e in events if e['kind']=='intent' and e['data']['actionRef']==action_ref]
        acks=[e for e in events if e['kind']=='ack' and e['data']['actionRef']==action_ref]
        recovery=[e for e in events if e['kind'] in ('unknown-outcome','recovery-observation-only') and e['data']['actionRef']==action_ref]
        if len(intents)!=1 or acks or len(recovery)!=1:errors.append(mode+':dispatch/unknown accounting')
        if action['request']!=locked['request'] or action['actorRef']!=locked['actorRef'] or proxy['request']!=locked['request'] or proxy['actorRef']!=locked['actorRef']:errors.append(mode+':request/actor mismatch')
        if r['forwardCount']!=1 or proxy['forwardCount']!=1 or proxy['captureComplete'] is not True or r['runnerReceivedResponse'] is not False or r['replayedMutation'] is not False:errors.append(mode+':forward/ACK/projection mismatch')
        model=load(base+'EXPECTED.json');after=load(r['afterRef']);errors.extend(mode+':'+e for e in check_state(model,after))
        before=load(r['beforeRef']);marker=locked['request']['body']['itemDescription'];created=[t for t in after['transactions'] if t['item_description']==marker]
        if any(t['item_description']==marker for t in before['transactions']):errors.append(mode+':marker not fresh')
        if [t['id'] for t in created]!=r['createdIds']:errors.append(mode+':reconciliation IDs')
        if locked['expected']=='allow':
            if len(created)!=1 or proxy['status']!=201 or proxy['body'].get('data',{}).get('transactionId')!=created[0]['id'] or r['reconciliation']!='succeeded-once':errors.append(mode+':success not uniquely reconciled')
        elif created or proxy['status'] not in (400,401,403,404) or r['reconciliation']!='denied-no-effect':errors.append(mode+':denial not reconciled')
        if mode=='hard-kill-inflight' and (r['hardKillConfirmed'] is not True or not any(e['data'].get('signal')=='SIGKILL' for e in recovery)):errors.append(mode+':hard kill missing')
        if r['status']!='proved' or r['problems']:errors.append(mode+':qualification failed')
    return errors

def check_read(model,case,http,window):
    """Separately coded subset: subject, membership, sums and disclosure markers."""
    errors=[];a=case['actorRef'];path=case['request']['path'].split('?')[0];body=http.get('body',{});d=body.get('data');status=http.get('status')
    markers=[r[k] for table,k in [('accounts','bank_name'),('categories','name'),('transactions','item_description'),('bills','item_description')] for r in model[table]]
    if case['expected']=='deny':
        if status not in (400,401,403,404) or any(m in json.dumps(body) for m in markers):errors.append('unauthorized read/disclosure')
        return errors
    if status!=200 or a not in model['actors']:return ['owner read/actor missing']
    uid=model['actors'][a]['subject'];accounts=[r for r in model['accounts'] if r['user_id']==uid];ids={r['id'] for r in accounts};transactions=[t for t in model['transactions'] if t['account_id'] in ids]
    expense=sum((money(t['amount']) for t in transactions if t['type']=='Expense'),Decimal(0));net=sum((money(t['amount'])*(1 if t['type']=='Revenue' else -1) for t in transactions),Decimal(0))
    try:
        if path=='/api/v1/accounts':
            if d['user_id']!=uid or {r['id']:money(r['balance']) for r in d['accounts']}!={r['id']:money(r['balance']) for r in accounts}:errors.append('account subject/IDs/balance')
        elif path.endswith('/accounts/options'):
            if {r['accountId'] for r in d}!=ids:errors.append('account options foreign/missing')
        elif path.endswith('/categories/options'):
            if {r['category_id'] for r in d}!={r['id'] for r in model['categories'] if r['user_id']==uid}:errors.append('category options foreign/missing')
        elif path.endswith('/expenses/summary'):
            if sum((money(r['totalExpense']) for r in d['data']),Decimal(0))!=expense or len(d['data'])!=1:errors.append('expense arithmetic')
        elif path.endswith('/expenses/breakdown'):
            expected={t['item_description']:money(t['amount']) for t in transactions if t['type']=='Expense'};actual={i['item_description']:money(i['amount']) for cat in d['data'] for i in cat['subCategories']}
            if actual!=expected or sum((money(cat['Total']) for cat in d['data']),Decimal(0))!=expense:errors.append('breakdown membership/arithmetic')
        elif path.endswith('/savings/summary'):
            if d['user_id']!=uid or len(d['summary']['this_year'])!=12 or len(d['summary']['last_year'])!=12 or sum((money(r['amount']) for r in d['summary']['this_year']),Decimal(0))!=net or any(money(r['amount']) for r in d['summary']['last_year']):errors.append('savings subject/arithmetic')
        elif path=='/api/v1/goals':
            gs=[g for g in model['goals'] if g['user_id']==uid and g['start_date'][:7]<=window and g['end_date'][:7]>=window]
            if case['branchRef'].endswith(':Expense'):
                if {g['goal_id']:money(g['target_amount']) for g in d['expenseGoals']}!={g['id']:money(g['target_amount']) for g in gs if g['goal_type']=='Expense'}:errors.append('expense goal foreign/missing/value')
            else:
                saving=max((g for g in gs if g['goal_type']=='Saving'),key=lambda g:(g['start_date'],g['id']));expected=sum((money(t['amount'])*(1 if t['type']=='Revenue' else -1) for t in transactions if t['status']=='Complete'),Decimal(0))
                if d['savingGoal']['goal_id']!=saving['id'] or money(d['savingGoal']['target_achieved'])!=expected or money(d['savingGoal']['target_amount'])!=money(saving['target_amount']):errors.append('saving goal subject/arithmetic/value')
        elif path=='/api/v1/bills':
            if {b['billId']:money(b['Amount']) for b in d['data']}!={b['id']:money(b['amount']) for b in model['bills'] if b['user_id']==uid} or any(b['userId']!=uid for b in d['data']):errors.append('bill ownership/membership/value')
        elif path.startswith('/api/v1/accounts/'):
            rid=int(path.rsplit('/',1)[1]);r=next(r for r in accounts if r['id']==rid)
            if d['id']!=rid or money(d['balance'])!=money(r['balance']):errors.append('detail membership/balance')
    except (KeyError,TypeError,ValueError,StopIteration):errors.append('unknown projection')
    return errors
