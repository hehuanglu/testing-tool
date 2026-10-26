"""Finalsource adapter: source-derived recipes, API-only fixtures, exact poststate.

Reuses discovery and tiny BE-auth fixture input primitives. No DB helper, ZAP
lifecycle or raw login capture. Only the verified local test deployment is bound.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path
import ssl
import time
import uuid
from . import bola_research as br
from .anonymous_product import discover as shared_discover
from .research_product import (binding,observe_transport,registration_input,
    account_input,saving_goal_input,WORKSPACE,TARGET,docker)
from .discovery import validate_discovery,verify_local_sources,canonical_hash,verify_identity
from .business import minor

# Closed response fields from the pinned account/goal/transaction DTOs and app
# envelope. Register/login capture is separately limited to protected subject.
CAPTURE_FIELDS=frozenset('data success statusCode message error timestamp path account accountId account_id account_number_last_4 account_type accounts balance bank_name branch_name deleted_account_id end_date expenseGoals goal_id goal_type hasMore id recent_transactions savingGoal start_date target_achieved target_amount total updated_at updated_goal user_id date amount description status receipt_id type transactionId transactionDate itemDescription shopName paymentMethod createdAt'.split())


def inspect():
    wd=docker('inspect','--format','{{index .Config.Labels "com.docker.compose.project.working_dir"}}',TARGET)
    if Path(wd).resolve()!=(WORKSPACE/'finalsource').resolve():raise ValueError('test deployment not bound to selected checkout')
    b=binding();p=observe_transport()
    return b,p


def authority(receipt,doc):
    if receipt.get('environment')!=doc['product']['environment'] or receipt.get('productLocation')!=str(WORKSPACE/'finalsource') or receipt.get('permissions')!=list(br.PERMISSIONS) or not receipt.get('source'):
        raise ValueError('explicit API-only BOLA receipt required')
    return copy.deepcopy(receipt)


def discover(output):
    inspect() # checkout binding BEFORE even authorized documentation traffic
    d=shared_discover(output);d=copy.deepcopy(d)
    ops={(o['method'],o['pathTemplate']):o for o in d['operations']}
    # Nest's live Swagger omits @Query DTO fields. Supplement only from the
    # already pinned controller + DTO; do not broaden the shared compiler.
    dto=next(s for s in d['sources'] if s['location'].endswith('dto/list-transactions-query.dto.ts'))
    text=Path(dto['location']).read_text()
    if not all('readonly '+name+':' in text for name in ('type','limit','offset')):raise ValueError('unsupported transaction query DTO')
    op=ops[('GET','/api/v1/transactions')]
    if op['input']['query'] not in ([],['type','limit','offset']):raise ValueError('query source/spec disagreement')
    op['input']['query']=['type','limit','offset'];op['evidenceRefs'].append(dto['id'])
    d['gaps'].append({'status':'unknown','description':'Live Swagger omits transaction Query DTO parameters; type/limit/offset supplemented from pinned controller and DTO source, runtime readback still required.','evidenceRefs':[dto['id']]})
    for path,names in [('/api/v1/expenses/summary',['userId']),('/api/v1/expenses/breakdown',['month']),('/api/v1/savings/summary',['year'])]:
        op=ops[('GET',path)]
        op['input']['query']=names
    refs=ops[('POST','/api/auth/login')]['evidenceRefs']
    d['auth']={'kind':'json-bearer','loginOperationId':ops[('POST','/api/auth/login')]['id'],'usernameField':'email','passwordField':'password',
        'tokenPointer':'/data/accessToken','headerName':'Authorization','headerPrefix':'Bearer ','credentialRef':'private:in-memory-fresh-slots',
        'identity':{'operationId':ops[('GET','/api/v1/accounts')]['id'],'subjectPointer':'/data/user_id',
        'actorSource':{'operationId':ops[('POST','/api/auth/register')]['id'],'subjectPointer':'/data/user/id'},'expectedStatus':200,'contentType':'application/json'},
        'evidenceRefs':refs,'confidence':'high'}
    d['tracks']['bola-ownership']={'status':'candidate','reason':'API-only A/B fixtures; account detail/list/update/delete and saving-goal list/update policy from pinned services; category dependency blocked','evidenceRefs':refs}
    validate_discovery(d);br.save(output,'BOLA_DISCOVERY.json',d)
    inv=inventory(d);br.save(output,'BOLA_INVENTORY.json',inv)
    return d,inv


def inventory(d):
    def source(suffix):
        found=[s['id'] for s in d['sources'] if s['location'].endswith(suffix)]
        if len(found)!=1:raise ValueError('policy source missing '+suffix)
        return found[0]
    ar=source('accounts/accounts.service.ts');gr=source('goals/goals.service.ts');tr=source('transactions/transactions.service.ts')
    policies=[{'id':'account-owner','relation':'owner-only','semantics':'list where userId; detail/update/remove compare account.userId to authenticated subject before disclosure/write','evidenceRefs':[ar]},
              {'id':'goal-owner','relation':'owner-only','semantics':'list where userId; update checks goal.userId; Saving fixture has no category dependency','evidenceRefs':[gr]}]
    rows=[]
    for o in d['operations']:
        method,path=o['method'],o['pathTemplate'];kind=None;typ=None;policy=None;extra={};slots=[];body=None
        if path=='/api/v1/accounts/{id}' and method in ('GET','PUT','DELETE'):
            kind={'GET':'detail','PUT':'update','DELETE':'delete'}[method];typ='account';policy='account-owner';slots=[{'location':'path','name':'id'}]
            if method=='PUT':body={'bank_name':'bola-cross-attempt','account_type':'Checking','branch_name':'fixture','balance':7654}
        elif method=='GET' and path in ('/api/v1/accounts','/api/v1/accounts/options'):
            kind='collection';typ='account';policy='account-owner';extra={'collectionPointers':['/data/accounts'] if path.endswith('accounts') else ['/data'],
                'collectionIdField':'id' if path.endswith('accounts') else 'accountId'}
        elif method=='GET' and path=='/api/v1/goals':
            kind='collection';typ='goal';policy='goal-owner';extra={'collectionPointers':['/data/savingGoal'],'collectionIdField':'goal_id'}
        elif method=='PUT' and path=='/api/v1/goals/{goalId}':
            kind='update';typ='goal';policy='goal-owner';slots=[{'location':'path','name':'goalId'}];body={'target_amount':'7654'}
        reason='Bounded policy-aware BOLA cases + owner and anonymous controls' if kind else 'Public authentication/bootstrap or health/documentation/protocol; no owned product object is disclosed or mutated'
        disposition='candidate' if kind else 'not-applicable'
        if path=='/api/v1/transactions' or path in ('/api/v1/expenses/summary','/api/v1/expenses/breakdown','/api/v1/savings/summary','/api/v1/categories/options'):
            disposition='blocked';reason='Populated transaction/category nested/reference/filter/pagination coverage needs fresh category; no API create-category. Historical API-only preparation lacked fresh prerequisites; a separate currently authorized, bound DB provisioning step is required. Empty owned transaction readback is related-state evidence only.'
        if path=='/api/v1/bills':disposition='blocked';reason='No API create-bill observed; populated fixture/policy oracle absent'
        if method=='POST' and path in ('/api/v1/goals','/api/v1/accounts'):
            disposition='not-run';reason='Create owner is assigned by authenticated subject; owner-field whitelist and Expense category reference require branch-specific execution'
        rows.append({'operationRef':o['id'],'disposition':disposition,'reason':reason,'evidenceRefs':o['evidenceRefs']+([ar] if typ=='account' else [gr] if typ=='goal' else []),
            'objectType':typ,'kind':kind,'policyRef':policy,'idLocations':slots,
            'request':{'operationRef':o['id'],'method':method,'path':path,'body':body},**extra})
    result={'schemaVersion':'bola-inventory/1.1','discoverySha256':canonical_hash(d),'policies':policies,'operations':rows,
        'dependencies':[{'reference':'transaction.accountId (body), category_id (body), transaction list type/limit/offset (query), goals Expense.category_id (body)',
                         'policySource':tr,'disposition':'blocked','reason':'fresh category API unavailable; explicit bound DB prerequisite provisioning required'},
                        {'reference':'account.recent_transactions[].receipt_id; bills','disposition':'blocked','reason':'populated fixture prerequisite provisioning required; not an absence of authorization relevance'},
                        {'reference':'search/export/goal detail/goal DELETE/user DELETE','disposition':'not-applicable','reason':'not observed in complete source/live OpenAPI inventory'}]}
    # Branches express applicability separately from the legacy case engine's supported recipes.
    for row in rows:
        path=row['request']['path'];method=row['request']['method']
        names=['Saving','Expense'] if path=='/api/v1/goals' else ['Saving','Expense'] if path=='/api/v1/goals/{goalId}' else (['All','Revenue','Expense'] if method=='GET' else ['Revenue','Expense']) if path=='/api/v1/transactions' else ['default']
        relevant=path.startswith('/api/v1/')
        policy=gr if '/goals' in path else ar if '/accounts' in path else tr
        if '/bills' in path:policy=source('bills/bills.service.ts')
        if '/savings' in path:policy=source('savings/savings.service.ts')
        row['branches']=[]
        for name in names:
            refs=[]
            if method=='POST' and path=='/api/v1/transactions':refs=[{'location':'body','name':'accountId','objectType':'account'},{'location':'body','name':'category_id','objectType':'category'}]
            if method=='POST' and path=='/api/v1/goals' and name=='Expense':refs=[{'location':'body','name':'category_id','objectType':'category'}]
            if not refs:refs=copy.deepcopy(row['idLocations'])
            if relevant and not refs:refs=[{'location':'implicit-subject','name':'authenticated user','objectType':row['objectType'] or 'owned dataset'}]
            deps=['fresh-A/B'] if relevant else []
            if '/transactions' in path or name=='Expense' or '/expenses' in path or '/categories' in path:deps+=['fresh-owner-categories','populated-transactions']
            if '/bills' in path:deps+=['fresh-owner-bills']
            row['branches'].append({'operationRef':row['operationRef'],'branchRef':row['operationRef']+':'+name,
                'predicate':('goal_type = '+name if '/goals' in path else 'type = '+name if '/transactions' in path else 'all requests'),
                'relevant':relevant,'objectReferences':refs,'policyRefs':[policy] if relevant else [],'evidenceRefs':list(dict.fromkeys(row['evidenceRefs']+([policy] if relevant else []))),
                'fixtureDependencies':deps,'disposition':('blocked' if name=='Expense' and method=='POST' and path=='/api/v1/goals' else row['disposition']),
                'reason':row['reason']})
    br.validate_inventory(d,result);return result


def req(doc,method,path,body=None,template=None):
    op=next(o for o in doc['operations'] if o['method']==method and o['pathTemplate']==(template or path))
    return {'operationRef':op['id'],'method':method,'path':path,'body':body}


def run(doc,inv,out,receipt,interrupt_after=None):
    out=Path(out);out.mkdir(parents=True,mode=0o700,exist_ok=False)
    br.validate_inventory(doc,inv);verify_local_sources(doc);b,proof=inspect();a=authority(receipt,doc)
    br.direct_binding(doc,b,proof)
    # Narrow, explicit adapter; a changed inventory cannot silently broaden setup.
    expected={(o['method'],o['pathTemplate']) for o in doc['operations']}
    from .research_product import SURFACE
    if expected!=SURFACE|{('GET','/docs-json'),('HEAD','/api/health'),('OPTIONS','/api/auth/login')}:raise ValueError('unsupported finalsource recipe extension')
    if inventory(doc)!=inv:raise ValueError('policy/inventory not derived from selected source')
    # All static related reads must admit before registration/fixture mutation.
    br.validate_request(doc,req(doc,'GET','/api/v1/transactions?type=All&limit=100&offset=0',template='/api/v1/transactions'))
    tls=ssl.create_default_context(cafile=str(WORKSPACE/'finalsource/.local-tls/localhost.crt'))
    client=br.DirectClient(doc,b,inspect,out,a,tls,capture_fields=CAPTURE_FIELDS);actors={};resources=[];controls=[];ledger=[];prefix='bola-'+uuid.uuid4().hex[:16]
    br.save(out,'AUTHORITY_RECEIPT.json',a);br.save(out,'BOLA_INVENTORY.json',inv);br.save(out,'PRODUCT_DISCOVERY.json',doc)
    br.save(out,'RESOURCE_PREFLIGHT.json',{'hostFreeBytes':__import__('shutil').disk_usage(out).free,'reserveBytes':br.LIMITS['reserveBytes'],
      'workload':'bounded host direct-client; no Docker create/build/ZAP workload; <=32MiB artifacts; memory max response64KiB',
      'binding':b,'transport':proof,'at':time.time()})
    def send(label,actor,method,path,body=None,permission='setup',template=None,token=None,sensitive=False):
        return client.request(label,actor,req(doc,method,path,body,template),permission,token=token,sensitive=sensitive)
    def add_ledger(value):
        ledger.append(value);br.save(out,'fixture-events/'+str(len(ledger))+'.json',value)
    def detail(label,actor,r):return send(label,actor,'GET',r['readRequest']['path'],permission='poststate',template='/api/v1/accounts/{id}' if r['objectType']=='account' else None)
    def make_account(actor,role):
        marker=prefix+'-'+actor+'-'+role;body=account_input(marker)
        s,v,ref=send('create-'+actor+'-'+role,actor,'POST','/api/v1/accounts',body)
        if s!=201:raise ValueError('fresh account creation failed, no retry')
        value=v['data']['account']
        if value['user_id']!=actors[actor]['subject']:raise ValueError('fixture owner mismatch')
        rid=value['id'];r={'id':actor+'-account-'+role,'wireId':rid,'objectType':'account','owner':actor,'sharedWith':[],
           'role':role,'runId':out.name,'createdByRun':True,'preparationEvidence':[ref],'statePointer':'/data','idField':'id',
           'expectedFields':{'/bank_name':marker,'/balance':1000},'markers':[marker],
           'readRequest':req(doc,'GET','/api/v1/accounts/'+str(rid),template='/api/v1/accounts/{id}'),
           'relatedRequests':[req(doc,'GET','/api/v1/transactions?type=All&limit=100&offset=0',template='/api/v1/transactions')],
           'relatedPointers':['/data'],
           'cleanup':'owner API DELETE, verify absence; no DB reset'}
        add_ledger(r);return r
    def make_goal(actor,role):
        s,v,ref=send('create-goal-'+actor+'-'+role,actor,'POST','/api/v1/goals',saving_goal_input('500'))
        if s!=201:raise ValueError('fresh goal creation failed, no retry')
        r={'id':actor+'-goal-'+role,'wireId':v['data']['goal_id'],'objectType':'goal','owner':actor,'sharedWith':[],
           'role':role,'runId':out.name,'createdByRun':True,'preparationEvidence':[ref],'statePointer':'/data/savingGoal','idField':'goal_id',
           'expectedFields':{'/target_amount':500},'markers':[],'readRequest':req(doc,'GET','/api/v1/goals'),
           'relatedRequests':[req(doc,'GET','/api/v1/accounts')],'cleanup':'retained; no goal DELETE API'}
        r['relatedPointers']=['/data']
        add_ledger(r);return r
    def positive(actor,r,method,body):
        before_s,before,bref=detail('positive-before-'+actor+'-'+r['objectType']+'-'+method,actor,r)
        template='/api/v1/accounts/{id}' if r['objectType']=='account' else '/api/v1/goals/{goalId}'
        path=template.replace('{id}',str(r['wireId'])).replace('{goalId}',str(r['wireId']))
        s,v,ref=send('positive-'+actor+'-'+r['objectType']+'-'+method,actor,method,path,body,template=template)
        after_s,after,aref=detail('positive-after-'+actor+'-'+r['objectType']+'-'+method,actor,r)
        old=br.extract_snapshot(r,before,before_s);new=br.extract_snapshot(r,after,after_s,False)
        ok=old is not None and s==200 and (after_s==404 if method=='DELETE' else new is not None and (minor(str(new['balance' if r['objectType']=='account' else 'target_amount']))==6000000))
        control={'operationRef':req(doc,method,path,body,template)['operationRef'],'owner':actor,'resource':copy.deepcopy(r),
          'beforeRef':bref,'attemptRef':ref,'afterRef':aref,'request':req(doc,method,path,body,template),
          'expectedPost':None if method=='DELETE' else {'/balance' if r['objectType']=='account' else '/target_amount':600},'verified':ok}
        controls.append(control)
        if not ok:raise ValueError('dedicated positive control failed')
    result=None;failure=None;cleanup=[]
    try:
        # Fresh registration subject and independent login/subject continuity. Values stay only in memory.
        raw_actors={}
        for actor in ('A','B'):
            credentials,body=registration_input(prefix,actor)
            client.secret_values.extend(credentials.values())
            s,v,ref=send('register-'+actor,actor,'POST','/api/auth/register',body,sensitive={'subjectPointer':'/data/user/id'})
            if s!=201:raise ValueError('fresh registration failed, no retry')
            subject=v['data']['user']['id'];add_ledger({'kind':'user','owner':actor,'subject':subject,'runId':out.name,'preparationEvidence':[ref],'cleanup':'retained; no user DELETE API'})
            s,v,lref=send('login-'+actor,actor,'POST','/api/auth/login',{'email':credentials['email'],'password':credentials['password']},permission='login',sensitive={'subjectPointer':'/data/user/id'})
            if s!=200 or v['data']['user']['id']!=subject:raise ValueError('login subject differs from registration')
            raw_actors[actor]={**credentials,'subject':subject,'token':v['data']['accessToken']}
            actors[actor]={'subject':subject,'credentialRef':'private:memory/'+actor,'runId':out.name,'sourceOperationRef':req(doc,'POST','/api/auth/register')['operationRef'],'evidenceRefs':[ref,lref]}
        client.set_tokens(raw_actors)
        for actor in ('A','B'):
            s,v,ref=send('protected-identity-'+actor,actor,'GET','/api/v1/accounts',permission='read')
            verify_identity(s,'application/json',v,actors[actor]['subject'],'/data/user_id')
            actors[actor]['evidenceRefs'].append(ref)
        raw_actors.clear()
        for actor in ('A','B'):
            pos=make_account(actor,'positive-update');positive(actor,pos,'PUT',{'bank_name':prefix+'-positive','account_type':'Checking','branch_name':'fixture','balance':600})
            # Delete positive uses a distinct fresh sibling, never the negative target.
            sibling=make_account(actor,'positive-delete');positive(actor,sibling,'DELETE',None)
            # Remove update sibling before exact collection cases.
            s,v,ref=send('cleanup-positive-'+actor,actor,'DELETE',pos['readRequest']['path'],permission='cleanup',template='/api/v1/accounts/{id}')
            s,v,absref=detail('cleanup-positive-absence-'+actor,actor,pos)
            if s!=404:raise ValueError('positive account cleanup unconfirmed')
            pg=make_goal(actor,'positive');positive(actor,pg,'PUT',{'target_amount':'600'})
            resources.extend([make_account(actor,'target'),make_goal(actor,'target')])
        br.save(out,'ACTORS.json',actors);br.save(out,'FIXTURES.json',{'resources':resources,'ledger':ledger,'positiveControls':controls})
        plan=br.compile_plan(doc,inv,actors,resources,a,b,proof,out.name,controls)
        runner=br.BolaRun(plan,client,out);result=runner.run(interrupt_after)
    except (Exception,KeyboardInterrupt) as error:
        failure=type(error).__name__;client.stopped=True
        br.save(out,'FAILURE.json',{'phase':'setup-or-executor','error':failure,'retry':False,'retention':'fixture-events retain every acknowledged ID; uncertain creates not replayed'})
        raise
    finally:
        # API cleanup only IDs acknowledged by this run, with actor identity and owner detail first.
        for r in ledger:
            if r.get('objectType')!='account':continue
            label='final-cleanup-'+r['id']
            entry={'resource':r['id'],'wireId':r['wireId'],'owner':r['owner'],'runId':out.name,'status':'incomplete'}
            try:
                s,v,iref=send(label+'-identity',r['owner'],'GET','/api/v1/accounts',permission='poststate')
                verify_identity(s,'application/json',v,actors[r['owner']]['subject'],'/data/user_id')
                s,v,dref=detail(label+'-before',r['owner'],r)
                if s==404:entry.update(status='already-absent',evidenceRefs=[iref,dref])
                elif s==200 and br.extract_snapshot(r,v,s,False) is not None:
                    s,v,ref=send(label+'-delete',r['owner'],'DELETE',r['readRequest']['path'],permission='cleanup',template='/api/v1/accounts/{id}')
                    s,v,afterref=detail(label+'-after',r['owner'],r)
                    entry.update(status='deleted' if s==404 else 'incomplete',evidenceRefs=[iref,dref,ref,afterref])
                else:entry.update(status='retained-ownership-unconfirmed',evidenceRefs=[iref,dref])
            except Exception as error:entry.update(error=type(error).__name__)
            cleanup.append(entry)
        retained=[r for r in ledger if r.get('objectType')=='goal' or r.get('kind')=='user']
        br.save(out,'CLEANUP_RETENTION.json',{'accounts':cleanup,'retained':retained,'reason':'No user/goal API DELETE; retain dedicated test fixtures, no DB helper/reset','failure':failure})
    result['cleanupStatus']='retained-documented' if all(x['status'] in ('deleted','already-absent') for x in cleanup) else 'incomplete'
    result['requests']=client.count
    result['gateDecision']='allow' if result['executionStatus']=='completed' and result['securityVerdict']=='pass' and result['cleanupStatus']=='retained-documented' else 'block'
    br.save(out,'RUN.json',result);br.save(out,'ALERTS.json',br.alerts(plan,runner.rows))
    br.save(out,'technical/TESTER_REPORT_VI.md',('''# BOLA direct-client — finalsource test\nChỉ fresh fixtures A/B của run; account detail/list/options hai chiều, anonymous và owner controls; account PUT/DELETE và saving-goal PUT trên dedicated target. Owner positives dùng sibling riêng trước target creation. Mỗi case kiểm subject trước/sau, owner before/after và related readbacks.\nALERTS.json giữ chi tiết từng finding, phân loại do agent; không native ZAP alert/reviewer approval. Client captures không continuous wire attestation hoặc source-to-image proof. Secret response register/login bị bỏ, protected subject được lưu; verifier không tự chứng minh password/owner credential trên wire.\nCollection membership kiểm exact set fresh targets, không suy pagination transaction khi category fixture thiếu. Transaction/category/Expense-goal/bills populated bị blocked; không dùng DB helper hay ID lịch sử. Update/delete related transactions readback hiện rỗng: không là populated cascade proof.\nUsers/goals retained theo CLEANUP_RETENTION.json vì không có DELETE API. Fixed product build regression và natural expiry/refresh chưa có proof lượt này. Controlled interruption giữ not-run cases, không resume mutations.\n''').encode())
    br.save(out,'REPRODUCE.md',('''Từ workspace: `zap-product-assessment/.venv/bin/python zap-product-assessment/scripts/bola_research.py --help`.\nOffline readback: `zap-product-assessment/.venv/bin/python zap-product-assessment/scripts/bola_research.py verify --run RUN_DIRECTORY`; không target traffic.\nFresh execution cần local test binding không đổi và receipt đúng scope: `zap-product-assessment/.venv/bin/python zap-product-assessment/scripts/bola_research.py product-run --discovery BOLA_DISCOVERY.json --inventory BOLA_INVENTORY.json --receipt AUTHORITY_RECEIPT.json --output NEW_DIRECTORY`. Không replay action files; không reuse credentials/fixture IDs.\n''').encode())
    br.seal(out);verification=br.verify(out);br.save(out,'VERIFICATION.json',verification)
    return result
