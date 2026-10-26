"""Continuation recipes over the existing direct client, discovery and journal.

No scanner engine or historical authority changes. DB is prerequisite/observation,
never a replacement for the API request under test.
"""
import copy,datetime as dt,json,ssl,time,uuid
from pathlib import Path
from decimal import Decimal
from . import bola_research as br
from .bola_research_product import inspect,req,CAPTURE_FIELDS
from .bola_research_db import FixtureDB
from .bola_research_branches import coverage
from .bola_research_check import check_state,check_pages,verify as independent_verify
from .research_product import WORKSPACE,registration_input,account_input,saving_goal_input
from .discovery import canonical_hash,verify_local_sources,verify_identity

FIELDS=CAPTURE_FIELDS|frozenset('category_id category name receiptId userId billId logoUrl dueDate lastChargeDate Amount summary this_year last_year month year totalExpense Total changePercent subCategories item_description'.split())

def run(doc,inv,out,receipt,failure=False):
    out=Path(out);out.mkdir(parents=True,mode=0o700,exist_ok=False)
    br.validate_inventory(doc,inv);verify_local_sources(doc);binding,transport=inspect();br.direct_binding(doc,binding,transport)
    if receipt.get('dbPrerequisitesAuthorized') is not True or receipt.get('permissions')!=list(br.PERMISSIONS) or receipt.get('environment')!=doc['product']['environment'] or receipt.get('productLocation')!=str(WORKSPACE/'finalsource') or not receipt.get('source'):raise ValueError('continuation authority required')
    if failure and receipt.get('ownedClientFaultsAuthorized') is not True:raise ValueError('owned client fault authority required')
    br.save(out,'AUTHORITY_RECEIPT.json',receipt);br.save(out,'PRODUCT_DISCOVERY.json',doc);br.save(out,'BOLA_INVENTORY.json',inv)
    br.save(out,'RESOURCE_PREFLIGHT.json',{'hostFreeBytes':__import__('shutil').disk_usage(out).free,'reserveBytes':br.LIMITS['reserveBytes'],'workload':'bounded direct HTTP+small DB queries; no build/container creation/scan','artifactBudget':br.LIMITS['artifactBytes']})
    client=br.DirectClient(doc,binding,inspect,out,receipt,ssl.create_default_context(cafile=str(WORKSPACE/'finalsource/.local-tls/localhost.crt')),capture_fields=FIELDS)
    db=FixtureDB(out,binding);actors={};raw={};ledger=[];rows=[];pages=[];cases=[];controls=[];prefix='bc-'+uuid.uuid4().hex[:14]
    now=dt.datetime.now(dt.timezone.utc);month=now.strftime('%Y-%m');future=(now.replace(day=1)+dt.timedelta(days=32)).strftime('%Y-%m');year=now.year
    model={'actors':actors,'accounts':[],'categories':[],'transactions':[],'goals':[],'bills':[]};n=0
    ledger_seq=0;plan_seq=0
    def saveledger():
        nonlocal ledger_seq
        ledger_seq+=1;br.save(out,'fixture-events/'+str(ledger_seq).zfill(4)+'.json',{'runId':out.name,'entries':ledger,'expected':model})
    def call(label,a,m,p,b=None,permission='read',template=None,sensitive=False):
        result=client.request(label,a,req(doc,m,p,b,template),permission,sensitive=sensitive)
        cap=br.load(out,result[2])
        if not cap['captureComplete']:raise ValueError('unknown projection '+label)
        return result
    def ident(a,label):
        s,v,r=call(label,a,'GET','/api/v1/accounts',permission='poststate');verify_identity(s,'application/json',v,actors[a]['subject'],'/data/user_id');return r
    def observe(label):
        v=db.call('observe',actors=raw);br.save(out,'observations/'+label+'.json',v);return v,'observations/'+label+'.json'
    def account(a,role):
        marker=prefix+'-'+a+'-'+role;body=account_input(marker);client.secret_values.append(body['account_number_full'])
        s,v,r=call('setup-account-'+a+'-'+role,a,'POST','/api/v1/accounts',body,'setup')
        if s!=201 or v['data']['account']['user_id']!=actors[a]['subject']:raise ValueError('fresh account setup')
        x=v['data']['account'];row={'id':x['id'],'user_id':actors[a]['subject'],'bank_name':marker,'balance':'1000.0000'};model['accounts'].append(row)
        ledger.append({'table':'accounts','actor':a,'id':x['id'],'role':role,'marker':marker,'evidenceRefs':[r],'cleanup':'owner API cascade exact ID'});saveledger();return x['id']
    def transaction_body(a,acc,cat,typ,tag,amount='3.1250',status='Complete'):
        return {'accountId':acc,'category_id':cat,'transactionDate':month+'-15T12:00:00.000Z','type':typ,'itemDescription':prefix+'-'+a+'-'+tag,'shopName':prefix+'-'+a,'amount':amount,'paymentMethod':'Cash','status':status}
    def goal_body(typ,cat=None,period=None):
        return {'goal_type':typ,'target_amount':'500.2500' if typ=='Saving' else '125.7500','start_date':(period or month)+'-01','end_date':(period or month)+'-28',**({'category_id':cat} if cat is not None else {})}
    def incorporate(case,status,body):
        if case['expected']!='allow':return
        p=case['request']['path'];b=case['request']['body'];a=case['actorRef'];method=case['request']['method'];uid=actors[a]['subject']
        if method=='POST' and p=='/api/v1/transactions':
            x=body['data'];tid=x['transactionId'];model['transactions'].append({'id':tid,'account_id':b['accountId'],'category_id':b['category_id'],'type':b['type'],'amount':b['amount'],'status':b['status'],'item_description':b['itemDescription'],'transaction_date':b['transactionDate'].replace('T',' ').replace('Z','')})
            r=next(r for r in model['accounts'] if r['id']==b['accountId']);r['balance']=str(Decimal(r['balance'])+Decimal(b['amount'])*(1 if b['type']=='Revenue' else -1))
            ledger.append({'table':'transactions','actor':a,'id':tid,'account_id':b['accountId'],'category_id':b['category_id'],'caseId':case['id'],'cleanup':'owner account API cascade'})
        elif method=='POST' and p=='/api/v1/goals':
            gid=body['data']['goal_id'];model['goals'].append({'id':gid,'user_id':uid,'goal_type':b['goal_type'],'category_id':b.get('category_id'),'target_amount':b['target_amount'],'start_date':b['start_date'],'end_date':b['end_date']});ledger.append({'table':'goals','actor':a,'id':gid,'caseId':case['id'],'cleanup':'retained; no API DELETE'})
        elif method=='POST' and p=='/api/v1/accounts':
            x=body['data']['account'];model['accounts'].append({'id':x['id'],'user_id':uid,'bank_name':b['bank_name'],'balance':str(b['balance'])});ledger.append({'table':'accounts','actor':a,'id':x['id'],'role':'create-control','marker':b['bank_name'],'caseId':case['id'],'cleanup':'owner API DELETE'})
        elif method=='PUT' and p.startswith('/api/v1/accounts/'):
            rid=int(p.rsplit('/',1)[1]);r=next(r for r in model['accounts'] if r['id']==rid);r.update(balance=str(b['balance']),bank_name=b['bank_name'])
        elif method=='DELETE':
            rid=int(p.rsplit('/',1)[1]);model['accounts']=[r for r in model['accounts'] if r['id']!=rid];model['transactions']=[r for r in model['transactions'] if r['account_id']!=rid]
        elif method=='PUT' and '/goals/' in p:
            next(r for r in model['goals'] if r['id']==int(p.rsplit('/',1)[1]))['target_amount']=b['target_amount']
    def add(a,m,p,b,branch,expect='deny',role='nonowner',template=None,policy=None):
        i='c'+str(len(cases)+1).zfill(3);request=req(doc,m,p,b,template);br.validate_request(doc,request)
        case={'id':i,'branchRef':request['operationRef']+':'+branch,'operationRef':request['operationRef'],'actorRef':a,'request':request,'expected':expect,'role':role,'policyRefs':policy or next(x for x in inv['operations'] if x['operationRef']==request['operationRef'])['branches'][0]['policyRefs'],'maxDispatch':1,'retry':False}
        cases.append(case);return case
    def execute(c):
        label=c['id'];before,bref=observe(label+'-before');before_errors=check_state(model,before)
        if before_errors:raise ValueError('fixture precondition mismatch '+str(before_errors[:3]))
        br.save(out,'expected/'+label+'-before.json',model)
        s,v,ref=call(label,c['actorRef'],c['request']['method'],c['request']['path'],c['request']['body'],'mutation' if c['request']['method']!='GET' else 'read',template=next(o['pathTemplate'] for o in doc['operations'] if o['id']==c['operationRef']))
        success=s==201 if c['request']['method']=='POST' else s==200
        control_ok=c['expected']!='allow' or success
        if c['expected']=='allow' and success:incorporate(c,s,v)
        expectedref='expected/'+label+'.json';br.save(out,expectedref,model);after,aref=observe(label+'-after');problems=check_state(model,after)
        api_refs=[ident(a,label+'-after-identity-'+a) for a in ('A','B')]
        verdict='fail' if problems else 'pass' if control_ok and (success if c['expected']=='allow' else s in (400,401,403,404)) else 'inconclusive'
        row={'caseId':label,'branchRef':c['branchRef'],'actorRef':c['actorRef'],'role':c['role'],'expectedAccess':c['expected'],'status':s,'verdict':verdict,'problems':problems,'beforeRef':bref,'afterRef':aref,'expectedRef':expectedref,'attemptRef':ref,'apiOwnerReadbacks':api_refs,'policyRefs':c['policyRefs']}
        rows.append(row);br.save(out,'checkpoints/results-'+str(len(rows)).zfill(3)+'.json',rows);saveledger()
        if not control_ok:raise ValueError('valid owner business control failed '+label)
        return v
    def freeze():
        nonlocal plan_seq
        plan_seq+=1
        plan={'schemaVersion':'bola-continuation-plan/1.0','runId':out.name,'actors':actors,'inventory':inv,'discoverySha256':canonical_hash(doc),'targetBinding':binding,'transportBinding':transport,'implementationPins':br.implementation_pin(),'cases':br.sanitized(cases,client.secret_values),'limits':dict(br.LIMITS),'source':'fresh finalsource fixture and source-derived branches'}
        br.save(out,'locked-plans/phase-'+str(plan_seq)+'.json',plan);return plan
    cleanup=[];plan=None
    try:
        for a in ('A','B'):
            cred,body=registration_input(prefix,a);client.secret_values.extend(cred.values());s,v,r=call('register-'+a,a,'POST','/api/auth/register',body,'setup',sensitive={'subjectPointer':'/data/user/id'})
            if s!=201:raise ValueError('fresh registration no retry')
            uid=v['data']['user']['id'];actors[a]={'subject':uid,'sourceRef':r};ledger.append({'table':'users','actor':a,'id':uid,'evidenceRefs':[r],'cleanup':'retained; no API DELETE'});saveledger()
            s,v,r=call('login-'+a,a,'POST','/api/auth/login',{'email':cred['email'],'password':cred['password']},'login',sensitive={'subjectPointer':'/data/user/id'})
            if s!=200 or uid!=v['data']['user']['id']:raise ValueError('fresh login identity')
            raw[a]={'subject':uid,'email':cred['email'],'token':v['data']['accessToken']}
        client.set_tokens(raw)
        for a in ('A','B'):ident(a,'initial-identity-'+a)
        # Intent durably precedes the single prerequisite write transaction.
        br.save(out,'DB_PROVISION_INTENT.json',{'prefix':prefix,'actors':actors,'allowlist':'DB_ALLOWLIST.json','rowBudget':4,'retry':False,'source':'user continuation DB authorization; not historical API-only authority'})
        prov=db.call('provision',actors=raw,prefix=prefix,due=(now+dt.timedelta(days=7)).strftime('%Y-%m-%d'),last=now.strftime('%Y-%m-%d'));br.save(out,'DB_PROVISION_RESULT.json',prov)
        for r in prov['created']:
            ledger.append({**r,'preparation':'DB prerequisite','evidenceRefs':['DB_PROVISION_INTENT.json','DB_PROVISION_RESULT.json'],'cleanup':'retained if category referenced; exact bills delete'})
            if r['table']=='categories':model['categories'].append({k:r[k] for k in ('id','user_id','name')})
            else:model['bills'].append({k:r[k] for k in ('id','user_id','item_description')}|{'amount':'17.2500' if r['actor']=='A' else '38.7500','due_date':(now+dt.timedelta(days=7)).strftime('%Y-%m-%d')})
        saveledger();cats={a:next(r['id'] for r in prov['created'] if r['table']=='categories' and r['actor']==a) for a in ('A','B')}
        acc={a:{role:account(a,role) for role in ('target','unrelated','owner-update','owner-delete')} for a in ('A','B')}
        # Setup populated targets through the product API, with different actor totals and a Pending record.
        for a in ('A','B'):
            for i,(role,typ,status) in enumerate([('target','Revenue','Complete'),('target','Expense','Complete'),('target','Expense','Pending'),('unrelated','Revenue','Complete'),('owner-update','Expense','Complete'),('owner-delete','Expense','Complete')]):
                b=transaction_body(a,acc[a][role],cats[a],typ,'seed'+str(i),str((Decimal('10.1250') if a=='A' else Decimal('20.3750'))+i),status)
                c={'id':'setup-tx-'+a+'-'+str(i),'actorRef':a,'expected':'allow','request':req(doc,'POST','/api/v1/transactions',b)}
                s,v,r=call(c['id'],a,'POST','/api/v1/transactions',b,'setup')
                if s!=201:raise ValueError('populated API seed rejected')
                incorporate(c,s,v)
        saveledger();baseline,base_ref=observe('baseline');br.save(out,'BASELINE_STATE_CHECK.json',{'errors':check_state(model,baseline),'ref':base_ref})
        if check_state(model,baseline):raise ValueError('populated fixture independent state mismatch')
        # Lock every request after IDs are resolved and before any assessment case.
        for typ in ('Expense','Revenue'):
            for a in ('A','B'):
                other='B' if a=='A' else 'A'
                shapes=[('owned',a,acc[a]['target'],cats[a],'allow','owner'),('foreign-account',a,acc[other]['target'],cats[a],'deny','nonowner'),('foreign-category',a,acc[a]['target'],cats[other],'deny','nonowner'),('both-foreign',a,acc[other]['target'],cats[other],'deny','nonowner'),('anonymous','anonymous',acc[a]['target'],cats[a],'deny','anonymous'),('missing-account',a,2147483647,cats[a],'deny','nonexistent'),('missing-category',a,acc[a]['target'],2147483647,'deny','nonexistent')]
                for tag,actor,aid,cid,expected,role in shapes:add(actor,'POST','/api/v1/transactions',transaction_body(a,aid,cid,typ,typ+'-'+tag),typ,expected,role)
        for a in ('A','B'):
            other='B' if a=='A' else 'A'
            add(a,'POST','/api/v1/goals',goal_body('Saving'),'Saving','allow','owner')
            add(a,'POST','/api/v1/goals',goal_body('Expense',cats[a]),'Expense','allow','owner')
            add(a,'POST','/api/v1/goals',goal_body('Expense',cats[other],future),'Expense','deny','nonowner')
            add(a,'POST','/api/v1/goals',goal_body('Expense',cats[a],future),'Expense','allow','owner')
            add('anonymous','POST','/api/v1/goals',goal_body('Saving'),'Saving','deny','anonymous')
            add('anonymous','POST','/api/v1/goals',goal_body('Expense',cats[a]),'Expense','deny','anonymous')
            body=account_input(prefix+'-'+a+'-create-control');client.secret_values.append(body['account_number_full']);add(a,'POST','/api/v1/accounts',body,'default','allow','owner')
            add('anonymous','POST','/api/v1/accounts',body,'default','deny','anonymous')
            for field in ('userId','user_id'):
                # Entity and persistence field names are sourced, not brute-forced.
                for path,body,branch in [('/api/v1/accounts',account_input(prefix+'-'+a+'-injection-'+field),'default'),('/api/v1/transactions',transaction_body(a,acc[a]['target'],cats[a],'Expense','injection-'+field),'Expense'),('/api/v1/goals',goal_body('Saving'),'Saving')]:
                    if 'account_number_full' in body:client.secret_values.append(body['account_number_full'])
                    add(a,'POST',path,{**body,field:actors[other]['subject']},branch,'deny','property-authorization')
                add(a,'PUT','/api/v1/accounts/'+str(acc[a]['unrelated']),{**account_input(prefix+'-'+a+'-update-inject'),field:actors[other]['subject']},'default','deny','property-authorization','/api/v1/accounts/{id}')
        for a in ('A','B'):
            other='B' if a=='A' else 'A'
            for method in ('PUT','DELETE'):
                for actor in (other,'anonymous'):
                    body={'bank_name':prefix+'-foreign','account_type':'Checking','branch_name':'fixture','balance':765.125} if method=='PUT' else None
                    add(actor,method,'/api/v1/accounts/'+str(acc[a]['target']),body,'default','deny','anonymous' if actor=='anonymous' else 'nonowner','/api/v1/accounts/{id}')
                role='owner-update' if method=='PUT' else 'owner-delete'
                body={'bank_name':prefix+'-'+a+'-owner-updated','account_type':'Checking','branch_name':'fixture','balance':650.125} if method=='PUT' else None
                add(a,method,'/api/v1/accounts/'+str(acc[a][role]),body,'default','allow','owner','/api/v1/accounts/{id}')
        plan=freeze()
        for c in list(cases):execute(c)
        # Goal IDs arise from executed POSTs, so freeze a second phase before issuing PUTs.
        for a in ('A','B'):
            other='B' if a=='A' else 'A'
            for typ in ('Saving','Expense'):
                target=next(g for g in model['goals'] if g['user_id']==actors[a]['subject'] and g['goal_type']==typ and g['start_date'].startswith(month))
                for actor in (other,'anonymous'):add(actor,'PUT','/api/v1/goals/'+str(target['id']),{'target_amount':'777.1250'},typ,'deny','anonymous' if actor=='anonymous' else 'nonowner','/api/v1/goals/{goalId}')
                # Non-destructive owner PUT; Saving sibling is added via API first below.
                positive=next((g for g in model['goals'] if g['user_id']==actors[a]['subject'] and g['goal_type']==typ and g['start_date'].startswith(future)),None)
                if positive is None:
                    b=goal_body('Saving',period=future);s,v,r=call('setup-positive-saving-'+a,a,'POST','/api/v1/goals',b,'setup')
                    if s!=201:raise ValueError('saving positive setup')
                    incorporate({'id':'setup-positive-saving-'+a,'actorRef':a,'expected':'allow','request':req(doc,'POST','/api/v1/goals',b)},s,v);positive=model['goals'][-1]
                add(a,'PUT','/api/v1/goals/'+str(positive['id']),{'target_amount':'600.3750'},typ,'allow','owner','/api/v1/goals/{goalId}')
                for field in ('userId','user_id'):add(a,'PUT','/api/v1/goals/'+str(target['id']),{'target_amount':'999.1250',field:actors[other]['subject']},typ,'deny','property-authorization','/api/v1/goals/{goalId}')
        done=len(rows);br.save(out,'PLAN_PHASE1.json',plan);plan=freeze()
        for c in cases[done:]:execute(c)
        read_isolation(doc,inv,out,client,db,raw,actors,model,cases,rows,pages,add,call,observe,month,year)
        plan=freeze();br.save(out,'PLAN.json',plan);br.save(out,'PLAN.sha256',(canonical_hash(plan)+'\n').encode());br.save(out,'RESULTS.json',rows);br.save(out,'PAGINATION.json',pages)
        if failure:
            from .bola_research_faults import qualify
            qualify(out,doc,client,db,raw,actors,model,acc,cats,transaction_body,incorporate,observe,ident)
        br.save(out,'FINAL_EXPECTED.json',model);saveledger()
    except BaseException as e:
        br.save(out,'FAILURE.json',{'type':type(e).__name__,'detail':str(e)[:250] if isinstance(e,ValueError) else 'diagnostic withheld','retry':False});raise
    finally:
        for r in list(ledger):
            if r['table']!='accounts':continue
            a=r['actor'];rid=r['id'];label='cleanup-account-'+str(rid)
            try:
                ident(a,label+'-identity');s,v,ref=call(label+'-before',a,'GET','/api/v1/accounts/'+str(rid),permission='poststate',template='/api/v1/accounts/{id}')
                if s==404:cleanup.append({'table':'accounts','id':rid,'status':'already-absent','evidenceRefs':[ref]});continue
                if s!=200 or v['data']['bank_name'] not in {x['bank_name'] for x in model['accounts'] if x['id']==rid and x['user_id']==actors[a]['subject']}:raise ValueError('cleanup ownership')
                s,v,ref=call(label,a,'DELETE','/api/v1/accounts/'+str(rid),permission='cleanup',template='/api/v1/accounts/{id}')
                s,v,absref=call(label+'-absence',a,'GET','/api/v1/accounts/'+str(rid),permission='poststate',template='/api/v1/accounts/{id}')
                cleanup.append({'table':'accounts','id':rid,'status':'deleted' if s==404 else 'incomplete','evidenceRefs':[ref,absref]})
            except Exception as e:cleanup.append({'table':'accounts','id':rid,'status':'retained','error':type(e).__name__})
        bills=[r for r in ledger if r['table']=='bills']
        if bills:
            try:br.save(out,'DB_CLEANUP_INTENT.json',{'rows':bills,'allowlist':'DB_ALLOWLIST.json','retry':False});cl=db.call('cleanup-bills',actors=raw,rows=bills);br.save(out,'DB_CLEANUP_RESULT.json',cl)
            except Exception as e:cleanup.append({'table':'bills','status':'retained','error':type(e).__name__})
        br.save(out,'CLEANUP_RETENTION.json',{'apiCleanup':cleanup,'retained':[r for r in ledger if r['table'] in ('users','goals','categories')],'reason':'No user/goal API DELETE; retain categories with goal FKs. No broad DB cleanup.','accountsCascade':'API deleted transactions only under exact created account IDs'})
    br.save(out,'FIXTURE_LEDGER.json',{'runId':out.name,'entries':ledger,'expectedBeforeCleanup':model})
    postclean,ref=observe('after-cleanup');br.save(out,'CLEANUP_READBACK.json',{'observationRef':ref,'accounts':len(postclean['accounts']),'transactions':len(postclean['transactions']),'bills':len(postclean['bills'])})
    proofs={}
    for row in rows:
        if row['verdict']!='inconclusive' and all(r['verdict']!='inconclusive' for r in rows if r['branchRef']==row['branchRef']):
            p=proofs.setdefault(row['branchRef'],{'caseRefs':[],'evidenceRefs':[]});p['caseRefs'].append(row['caseId']);p['evidenceRefs']+=([row['attemptRef'],row['afterRef']] if row.get('afterRef') else [row['attemptRef']])
    cov=coverage(inv,proofs);br.save(out,'BRANCH_COVERAGE.json',cov)
    br.save(out,'POST_REFERENCE_MATRIX.json',br.sanitized([{**c,'outcome':next((r for r in rows if r['caseId']==c['id']),None)} for c in cases if c['request']['method']=='POST'],client.secret_values))
    br.save(out,'POPULATED_STATE_CHECKS.json',{'baselineRef':'observations/baseline.json','casesWithExactPostState':sum('afterRef' in r for r in rows),'population':{'accounts':8,'transactions':12,'categories':2,'bills':2},'semantics':'Balances updated for every created transaction status; list and goals achieved filter Complete; expense/savings summaries/breakdown include Pending. Owner delete cascades transactions; unrelated states remain exact.','pagesRef':'PAGINATION.json','window':month})
    ver=independent_verify(out);br.save(out,'INDEPENDENT_CHECK.json',ver)
    findings=make_alerts(cases,rows)
    br.save(out,'ALERTS.json',findings)
    result={'executionStatus':'completed','evidenceStatus':'complete' if ver['evidenceStatus']=='consistent' and all(r['verdict']!='inconclusive' for r in rows) else 'partial','securityVerdict':'findings' if findings['findings'] else 'no-findings-in-executed-scope' if all(r['verdict']=='pass' for r in rows) else 'inconclusive','cleanupStatus':'retained-documented' if not postclean['accounts'] and not postclean['transactions'] and not postclean['bills'] else 'incomplete','gateDecision':'handoff-only-no-signoff','cases':len(rows),'requests':client.count,'source':'BOLA/direct-client','nativeZap':False}
    br.save(out,'RUN.json',result);br.seal(out);br.save(out,'VERIFICATION.json',verify(out));return result

def read_isolation(doc,inv,out,client,db,raw,actors,model,cases,rows,pages,add,call,observe,month,year):
    """Exact fresh dataset expectations, small real pages; no invented filters."""
    own=lambda table,a:[r for r in model[table] if r['user_id']==actors[a]['subject']]
    tx=lambda a:[r for r in model['transactions'] if r['account_id'] in {x['id'] for x in own('accounts',a)}]
    start=len(cases);checks={};groups=[]
    for a in ('A','B'):
        other='B' if a=='A' else 'A'
        aids={x['id'] for x in own('accounts',a)}
        for r in own('accounts',a)[:2]:
            for actor,expect in [(a,'allow'),(other,'deny'),('anonymous','deny')]:
                c=add(actor,'GET','/api/v1/accounts/'+str(r['id']),None,'default',expect,'owner' if actor==a else 'anonymous' if actor=='anonymous' else 'nonowner','/api/v1/accounts/{id}')
                def detail(v,r=r,a=a,expect=expect):
                    if expect!='allow':return []
                    d=v['data'];t=sorted([t for t in tx(a) if t['account_id']==r['id']],key=lambda t:(t['transaction_date'],t['id']),reverse=True)[:5]
                    expected=[{'date':t['transaction_date'][:10],'amount':float(Decimal(t['amount'])*(1 if t['type']=='Revenue' else -1)),'description':t['item_description'],'status':t['status'],'receipt_id':None,'type':t['type']} for t in t]
                    return [] if d['id']==r['id'] and Decimal(str(d['balance']))==Decimal(r['balance']) and d['recent_transactions']==expected else ['detail/recent transaction mismatch']
                checks[c['id']]=detail
        paths=[('/api/v1/accounts','default'),('/api/v1/accounts/options','default'),('/api/v1/categories/options','default'),('/api/v1/goals','Saving'),('/api/v1/goals','Expense'),('/api/v1/bills','default'),('/api/v1/expenses/summary','default'),('/api/v1/expenses/summary?userId='+str(actors[other]['subject']),'default'),('/api/v1/expenses/breakdown?month='+month,'default'),('/api/v1/savings/summary?year='+str(year),'default')]
        for p,branch in paths:
            template=p.split('?')[0];c=add(a,'GET',p,None,branch,'allow','owner',template)
            def check(v,p=p,a=a,branch=branch):
                d=v['data'];path=p.split('?')[0];transactions=tx(a);expense=sum((Decimal(t['amount']) for t in transactions if t['type']=='Expense'),Decimal(0));revenue=sum((Decimal(t['amount']) for t in transactions if t['type']=='Revenue'),Decimal(0));complete_net=sum((Decimal(t['amount'])*(1 if t['type']=='Revenue' else -1) for t in transactions if t['status']=='Complete'),Decimal(0))
                if path=='/api/v1/accounts':
                    actual={r['id']:(r['bank_name'],Decimal(str(r['balance']))) for r in d['accounts']};expected={r['id']:(r['bank_name'],Decimal(r['balance'])) for r in own('accounts',a)};ok=d['user_id']==actors[a]['subject'] and actual==expected
                elif path.endswith('/accounts/options'):ok={r['accountId'] for r in d}=={r['id'] for r in own('accounts',a)}
                elif path.endswith('/categories/options'):ok=d==[{'category_id':r['id'],'name':r['name']} for r in own('categories',a)]
                elif path=='/api/v1/goals':
                    gs=[r for r in own('goals',a) if r['start_date']<month+'-31' and r['end_date']>=month+'-01']
                    if branch=='Saving':
                        g=max((g for g in gs if g['goal_type']=='Saving'),key=lambda g:(g['start_date'],g['id']));actual=d['savingGoal'];ok=actual['goal_id']==g['id'] and Decimal(str(actual['target_amount']))==Decimal(g['target_amount']) and Decimal(str(actual['target_achieved']))==complete_net
                    else:
                        expected=[{'goal_id':g['id'],'category':next(c['name'] for c in own('categories',a) if c['id']==g['category_id']),'target_amount':float(g['target_amount'])} for g in gs if g['goal_type']=='Expense'];ok=d['expenseGoals']==expected
                elif path=='/api/v1/bills':
                    expected=[{'billId':r['id'],'userId':r['user_id'],'itemDescription':r['item_description'],'logoUrl':'https://example.test/logo','dueDate':r['due_date'],'lastChargeDate':dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d'),'Amount':float(r['amount'])} for r in own('bills',a)];ok=d['data']==expected
                elif path.endswith('/expenses/summary'):ok=d['data']==[{'month':['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(month[-2:])-1],'totalExpense':float(expense)}]
                elif path.endswith('/expenses/breakdown'):
                    cats=own('categories',a);e=sorted([t for t in transactions if t['type']=='Expense'],key=lambda t:(t['transaction_date'],t['id']),reverse=True)
                    expected=[{'category':cats[0]['name'],'Total':float(expense),'changePercent':100,'subCategories':[{'item_description':t['item_description'],'amount':float(t['amount']),'date':t['transaction_date'][:10]} for t in e]}];ok=d['data']==expected
                else:
                    this=[{'month':str(i).zfill(2),'amount':float(revenue-expense) if i==int(month[-2:]) else 0} for i in range(1,13)];last=[{'month':str(i).zfill(2),'amount':0} for i in range(1,13)];ok=d['user_id']==actors[a]['subject'] and d['year']==year and d['summary']=={'this_year':this,'last_year':last}
                return [] if ok else ['implicit subject membership/value/aggregate mismatch']
            checks[c['id']]=check
        for typ in ('All','Expense','Revenue'):
            expected=sorted([t for t in tx(a) if t['status']=='Complete' and (typ=='All' or t['type']==typ)],key=lambda t:(t['transaction_date'],t['id']),reverse=True)
            group={'actorRef':a,'type':typ,'pageSize':2,'expected':copy.deepcopy(expected),'pages':[]};groups.append(group)
            for offset in range(0,max(1,len(expected)),2):
                c=add(a,'GET','/api/v1/transactions?type='+typ+'&limit=2&offset='+str(offset),None,typ,'allow','owner','/api/v1/transactions')
                def check(v,c=c,group=group,offset=offset,expected=expected):
                    group['pages'].append({'caseId':c['id'],'actorRef':a if False else group['actorRef'],'subject':actors[group['actorRef']]['subject'],'offset':offset,'body':v})
                    expected_ids=[t['id'] for t in expected[offset:offset+2]];d=v['data'];actual=d.get('data',[])
                    ids=[t['transactionId'] for t in actual]
                    errors=[] if ids==expected_ids and d['total']==len(expected) and d['hasMore']==(offset+len(actual)<len(expected)) else ['pagination membership/terminal mismatch']
                    for r,t in zip(actual,expected[offset:offset+2]):
                        if r['accountId']!=t['account_id'] or r['itemDescription']!=t['item_description'] or Decimal(str(r['amount']))!=Decimal(t['amount']):errors.append('page relation/value mismatch')
                    return errors
                checks[c['id']]=check
    # Anonymous checks once per actual path/branch, rather than duplicate actor dataset.
    for p,branch in [('/api/v1/accounts','default'),('/api/v1/accounts/options','default'),('/api/v1/categories/options','default'),('/api/v1/goals','Saving'),('/api/v1/goals','Expense'),('/api/v1/bills','default'),('/api/v1/expenses/summary','default'),('/api/v1/expenses/breakdown?month='+month,'default'),('/api/v1/savings/summary?year='+str(year),'default')]+[('/api/v1/transactions?type='+t+'&limit=2&offset=0',t) for t in ('All','Expense','Revenue')]:
        c=add('anonymous','GET',p,None,branch,'deny','anonymous',p.split('?')[0]);checks[c['id']]=lambda v:[]
    br.save(out,'READ_PLAN.json',{'cases':cases[start:],'expected':model,'window':month,'pageSize':2,'totalPageBudget':20,'lockedAt':time.time()})
    for c in cases[start:]:
        label=c['id'];s,v,ref=call(label,c['actorRef'],'GET',c['request']['path'],permission='read',template=next(o['pathTemplate'] for o in doc['operations'] if o['id']==c['operationRef']))
        problems=[]
        if c['expected']=='allow':
            if s!=200:problems=['owned read failed']
            else:
                try:problems=checks[label](v)
                except (KeyError,TypeError,ValueError):problems=['unknown/incomplete projection']
        else:
            if s not in (401,403,404):problems=['unauthorized read response']
            # Detect fixture marker/ID-shaped disclosure even on an error response.
            if any(r[key] in json.dumps(v) for table,key in [('accounts','bank_name'),('categories','name'),('transactions','item_description'),('bills','item_description')] for r in model[table]):problems.append('foreign marker disclosure')
        rows.append({'caseId':label,'branchRef':c['branchRef'],'actorRef':c['actorRef'],'role':c['role'],'status':s,'verdict':'fail' if problems else 'pass','problems':problems,'attemptRef':ref,'policyRefs':c['policyRefs']})
    pages.extend(groups)
    for group in groups:
        errors=check_pages(group['expected'],group['pages'],group['actorRef'],actors[group['actorRef']]['subject'])
        if errors:raise ValueError('pagination independent check '+str(errors))
    _,aref=observe('after-read-isolation');br.save(out,'READ_STATE_CHECK.json',{'afterRef':aref,'errors':check_state(model,br.load(out,aref))})

def make_alerts(cases,rows):
    groups={};byid={c['id']:c for c in cases}
    for row in rows:
        if row['verdict']!='fail':continue
        c=byid[row['caseId']];source='property-authorization assessment' if c['role']=='property-authorization' else 'BOLA/direct-client'
        # A failed owner control alone is a functional issue, not authorization finding.
        if c['expected']=='allow':continue
        key=(source,c['operationRef']);g=groups.setdefault(key,{'id':'BOLA-CONT-'+str(len(groups)+1).zfill(3),'source':source,'name':'Unauthorized effect or disclosure on '+c['operationRef'],'severity':'High','severityAttribution':'agent assessment of verified fixture effect/disclosure','confidence':'High','confidenceAttribution':'fresh actor identity + source policy + before/after selected DB state and owner API reads','description':'Request from a nonowner/anonymous or injected owner field produced a verified effect/disclosure contrary to the selected source policy.','impact':'Unauthorized access or modification of another fixture owner’s financial data.','remediation':'Enforce authenticated ownership for every referenced object and ensure denied requests are atomic; reject unauthorized owner properties.','retest':'Repeat own/foreign reference pair with fresh populated A/B fixtures on an explicitly supplied fixed build.','rootCause':'Requires product investigation; instances grouped by operation and authorization surface, not counted per combination.','instances':[]})
        g['instances'].append({'caseId':row['caseId'],'branchRef':row['branchRef'],'actorRef':row['actorRef'],'method':c['request']['method'],'path':c['request']['path'],'status':row['status'],'policyRefs':row['policyRefs'],'details':row['problems'],'evidenceRefs':[row[x] for x in ('attemptRef','beforeRef','afterRef','expectedRef') if x in row]})
    return {'schemaVersion':'product-assessment-handoff/bola-1.0','source':'BOLA/direct-client and property-authorization assessment','nativeZap':False,'findings':list(groups.values()),'limitations':'No findings is not product safety. Selected exact fixture state and client captures, no full raw/server attestation; same-repo independent checker is not an external trust anchor.','securitySignOff':False}

def verify(out):
    out=Path(out);index=br.load(out,'EVIDENCE_INDEX.json');actual={str(p.relative_to(out)) for p in out.rglob('*') if p.is_file() and p.name not in ('EVIDENCE_INDEX.json','VERIFICATION.json')}
    if actual!={r['path'] for r in index['files']}:raise ValueError('evidence index mismatch')
    for r in index['files']:
        p=out/r['path']
        if br.sha(p)!=r['sha256'] or p.stat().st_size!=r['bytes']:raise ValueError('evidence hash mismatch')
    plan=br.load(out,'PLAN.json')
    if canonical_hash(plan)!=(out/'PLAN.sha256').read_text().strip():raise ValueError('plan hash mismatch')
    br.validate_inventory(br.load(out,'PRODUCT_DISCOVERY.json'),plan['inventory'],source=False)
    if plan['inventory']!=br.load(out,'BOLA_INVENTORY.json'):raise ValueError('branch inventory drift')
    rows=br.load(out,'RESULTS.json');byid={c['id']:c for c in plan['cases']}
    for row in rows:
        c=byid[row['caseId']];http=br.load(out,row['attemptRef']);action=br.load(out,http['actionRef'])
        if action['actorRef']!=c['actorRef'] or action['request']!=br.sanitized(c['request']) or row['branchRef']!=c['branchRef'] or http['captureComplete'] is not True:raise ValueError('case actor/request/branch/projection mismatch')
    from .journal import Journal
    events=Journal(out/'journal.jsonl',out.name,canonical_hash({'discovery':br.load(out,'PRODUCT_DISCOVERY.json'),'authority':br.load(out,'AUTHORITY_RECEIPT.json'),'binding':plan['targetBinding']})).events
    for e in events:
        if e['kind']=='intent':
            action=br.load(out,e['data']['actionRef'])
            if canonical_hash(action)!=e['data']['actionSha256'] or action['actorRef']!=e['data']['actorRef']:raise ValueError('intent hash/actor drift')
        if e['kind']=='ack':
            http=br.load(out,e['data']['responseRef'])
            if http['actionRef']!=e['data']['actionRef'] or http['status']!=e['data']['status']:raise ValueError('ack drift')
    intents=[e['data']['actionRef'] for e in events if e['kind']=='intent']
    if len(intents)!=len(set(intents)) or len(intents)!=br.load(out,'RUN.json')['requests']:raise ValueError('dispatch accounting or replay')
    result=independent_verify(out)
    # Findings can consistently fail selected-state expected policy; inconsistency is reported, not hidden.
    return {'evidenceStatus':'consistent' if not any('missing' in e or 'omitted' in e for e in result['errors']) else 'incomplete','stateCheck':result,'files':len(index['files']),'requests':len(intents),'securitySignOff':False,'independenceBoundary':'hash+journal local integrity and separately coded state/page checker, no external attestation'}
