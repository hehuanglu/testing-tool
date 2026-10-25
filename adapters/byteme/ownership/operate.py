"""Finite ByteMe ownership adapter; uses existing bounded HTTP/checker/reconciliation."""
import sys, os, json, re, time, secrets, hashlib, subprocess, copy, traceback
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit
import urllib.request
CODE_ROOT = Path(__file__).resolve().parent
BASE = CODE_ROOT.parents[2]
ROOT = Path(os.environ.get('BYTEME_BOLA_ROOT', str(BASE/'operations/byteme/ownership'))).resolve()
SOURCE = Path('/Users/hahoangloc/Working/UET/SA/ByteMe')
sys.path.insert(0, str(BASE/'zap-product-assessment/src'))
from zap_assessment.bola_http import exchange
from zap_assessment.product_checks import check_case, check_pages, check_checkout, check_cancel
from zap_assessment.product_scope import reconcile, compact_results
from zap_assessment.signed_identity import verify_token
ORIGIN = 'http://127.0.0.1:8081'
ROLES = ['anonymous', 'CUSTOMER', 'EMPLOYEE', 'ADMIN']
OUT = BASE/'handoffs/byteme-bola-ownership-local-8081'
os.umask(0o077)
ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
ROOT.chmod(0o700)
def now(): return datetime.now(timezone.utc).isoformat()
def save(name, value):
    p=ROOT/name; p.parent.mkdir(parents=True, exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp'); tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)); tmp.chmod(0o600); tmp.replace(p)
def load(name): return json.loads((ROOT/name).read_text())
def cmd(*args): return subprocess.check_output(args,text=True).strip()
def binding():
    d=json.loads(cmd('docker','inspect','byteme-backend-1'))[0]
    labels=d['Config']['Labels']
    assert labels['com.docker.compose.project']=='byteme'
    assert labels['com.docker.compose.project.working_dir']==str(SOURCE)
    assert labels['com.docker.compose.project.config_files']==str(SOURCE/'compose.yaml')
    assert d['State']['Running']
    assert d['NetworkSettings']['Ports']['8080/tcp']==[{'HostIp':'127.0.0.1','HostPort':'8081'}]
    return {'containerId':d['Id'],'imageId':d['Image'],'startedAt':d['State']['StartedAt'],
            'composeProject':'byteme','composeFile':str(SOURCE/'compose.yaml'),'origin':ORIGIN},d
def actor_role(actor): return 'anonymous' if actor=='anonymous' else load('actors.json')[actor]['role']
LAST=0
def request(label,method,path,body=None,actor='anonymous',purpose='direct ownership'):
    global LAST
    state=load('state.json'); assert label not in state['dispatched'], 'Never replay an intent: '+label
    assert time.time()<state['deadline'] and len(state['dispatched'])<1600
    assert path.startswith('/') and not path.startswith('//') and '\r' not in path and '\n' not in path
    # Frozen route allowlist comes from product spec, including supporting health.
    pth=urlsplit(path).path
    assert any(method==o['method'] and re.fullmatch(re.sub(r'\{[^}]+\}',r'[^/]+',o['path']),pth) for o in load('discovery.json')['operations'])
    if len(state['dispatched'])%40==0: assert binding()[0]==load('discovery.json')['deployment']
    assert os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize>2*1024**3
    headers={'Accept':'application/json','Content-Type':'application/json'}
    role='anonymous'
    if actor!='anonymous':
        a=load('actors.json')[actor]; assert a['expiresAt']>time.time()+30
        role=a['role'];headers['Authorization']='Bearer '+a['token']
    delay=max(0,LAST+0.16-time.monotonic())
    if delay:time.sleep(delay)
    state['dispatched'].append(label);save('state.json',state)
    row={'id':label,'startedAt':now(),'method':method,'path':path,'actor':actor,'role':role,'technique':purpose,'state':'intent'}
    save('http/'+label+'.json',row);LAST=time.monotonic()
    try:
        status,v,size=exchange(ORIGIN,method,path,headers,None if body is None else json.dumps(body).encode(),12,state['deadline'],allow_empty=True)
    except Exception as e:
        row.update(state='unknown',error=type(e).__name__,retry=False);save('http/'+label+'.json',row);raise
    public=v
    if pth.startswith('/api/auth/'):
        public=({'subject':str(v.get('user',v).get('id')),'role':v.get('user',v).get('role')} if status in (200,201) else {'code':v.get('code'),'status':v.get('status')})
    row.update(finishedAt=now(),state='acknowledged',status=status,bytes=size,result=public)
    save('http/'+label+'.json',row)
    with (ROOT/'progress.jsonl').open('a') as f:f.write(json.dumps({k:row[k] for k in ('id','method','path','actor','status')})+'\n')
    return status,v

def discover():
    import yaml
    assert not (ROOT/'state.json').exists()
    b,d=binding();spec=yaml.safe_load((SOURCE/'src/main/resources/static/openapi.yaml').read_text())
    with urllib.request.urlopen(ORIGIN+'/openapi.yaml',timeout=12) as r:
        live=r.read(200000);assert r.status==200 and yaml.safe_load(live)==spec
    ops=[]
    for path,item in spec['paths'].items():
        for method,o in item.items():
            if method not in ('get','post','put','delete','patch'):continue
            protected=bool(o.get('security',spec.get('security',[])))
            allowed=ROLES if not protected else ['ADMIN'] if path.startswith('/api/foods') else ['CUSTOMER','EMPLOYEE'] if method=='get' and path.startswith('/api/orders') else ['EMPLOYEE'] if path.endswith(('/confirm','/status')) else ['CUSTOMER']
            ops.append({'id':o['operationId'],'method':method.upper(),'path':path,'protected':protected,'allowedRoles':allowed})
    assert len(ops)==18
    refs=['README.md','src/main/resources/static/openapi.yaml','src/main/java/org/example/config/SecurityConfiguration.java','src/main/java/org/example/cart/service/CartService.java','src/main/java/org/example/order/service/OrderService.java']
    cases=[]
    for o in ops:
        for role in ROLES:
            units=['policy-response']
            if role=='CUSTOMER' and o['id'] in ('getCurrentCart','addCartItem'):units+=['two-owner-isolation','client-owner-override']
            if role=='CUSTOMER' and o['id'] in ('updateCartItem','removeCartItem'):units+=['owner-positive','cross-owner-both-directions','state-unchanged-after-denial']
            if role=='CUSTOMER' and o['id']=='createOrder':units+=['two-owner-checkout','client-owner-override','related-stock-cart-state']
            if role=='CUSTOMER' and o['id']=='listOrders':units+=['populated-pages-both-owners','status-type-filter-isolation','client-owner-override']
            if role=='EMPLOYEE' and o['id']=='listOrders':units+=['populated-pages-cross-owner','default-queue-and-filters']
            if role=='CUSTOMER' and o['id']=='getOrder':units+=['owner-positive','cross-owner-both-directions','all-relevant-states']
            if role=='EMPLOYEE' and o['id']=='getOrder':units+=['two-employees-cross-owner','all-relevant-states']
            if role=='CUSTOMER' and o['id']=='cancelOrder':units+=['owner-positive','cross-owner-both-directions','non-pending-denial','stock-restored-once']
            if role=='EMPLOYEE' and o['id'] in ('confirmOrder','updateOrderStatus'):units+=['two-employees-cross-owner','transition-and-poststate','terminal-state-denial']
            cases.append({'caseId':o['id']+':'+role,'operationId':o['id'],'method':o['method'],'path':o['path'],'role':role,'requiredEvidence':units,'evidenceRefs':refs,'question':'Check declared role policy, owner isolation or authorized cross-owner action, response and relevant post-state.'})
    save('inventory.json',{'productLocation':str(SOURCE),'environment':'local Docker Compose byteme, host loopback 8081','origin':ORIGIN,'track':'bola-ownership','complete':True,'cases':cases})
    save('discovery.json',{'startedAt':now(),'deployment':b,'sourceHead':cmd('git','-C',str(SOURCE),'rev-parse','HEAD'),'sourceDirty':bool(cmd('git','-C',str(SOURCE),'status','--porcelain')),'liveSpecMatchesSource':True,'sourceRouteReview':'Auth/Food/Cart/Order controllers agree with the 18 spec method-routes; no additional business controller found. Framework health/docs are supporting public surfaces, without owner selectors.','operations':ops,'policyBasis':'README role/ownership rules and matching OpenAPI/security/service source; no independent business-policy approval.','routing':'Native MCP has no ownership oracle/fixture matrix tool. Existing common BOLA compiler requires a different product recipe. This finite ByteMe adapter reuses bola_http.exchange, product_checks and product_scope; no scanner changes or gate modifications.','preflight':{'hostFreeBytes':os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize,'workload':'bounded direct HTTP; no build/provision/scan allocation'},'supportOperations':[{'method':'GET','path':'/openapi.yaml','actor':'anonymous','status':200,'result':'matches source spec'}]})
    mounts=[m for m in d['Mounts'] if m['Destination']=='/run/auth'];assert len(mounts)==1
    (ROOT/'public.pem').write_bytes((Path(mounts[0]['Source'])/'public.pem').read_bytes())
    save('state.json',{'startedAt':now(),'deadline':time.time()+7200,'marker':'BOLA-'+secrets.token_hex(5),'dispatched':[]})
    save('observations.json',{});save('cases.json',[]);save('fixtures.json',{'foods':[],'orders':[]})
    print('Verified local ByteMe; 18 method-routes, 72 endpoint-role responsibilities; existing product transport/checkers selected.',flush=True)

def mark(oid,role,unit,label,checks):
    cid=oid+':'+role;rows=load('cases.json');assert checks
    reasons=[name for name,ok in checks.items() if not ok]
    labels=[label] if isinstance(label,str) else label;operation_ids=[]
    for value in labels:
        exact=ROOT/'http'/(value+'.json')
        children=[exact] if exact.exists() else sorted((ROOT/'http').glob(value+'-page-*.json'),key=lambda p:int(p.stem.rsplit('-page-',1)[1]))
        if not children:raise ValueError('operation/group reference has no recorded requests')
        operation_ids.extend(json.loads(p.read_text())['id'] for p in children)
    rows.append({'caseId':cid,'unit':unit,'operationIds':list(dict.fromkeys(operation_ids)),'operationGroups':labels,'checks':checks,'outcome':'violated' if reasons else 'matched','reasons':reasons,'resultRead':True});save('cases.json',rows)
    obs=load('observations.json');old=obs.get(cid,{'role':role,'evidenceUnits':[],'resultRead':True,'outcome':'matched'})
    if unit not in old['evidenceUnits']:old['evidenceUnits'].append(unit)
    if reasons:old['outcome']='violated'
    obs[cid]=old;save('observations.json',obs)
    if reasons:print('Discrepancy:',cid,unit,','.join(reasons),flush=True)
def must(status,value,wanted):
    if status!=wanted:raise RuntimeError('Fixture/probe precondition failed: HTTP '+str(status))
    return value
def actors():
    assert not (ROOT/'actors-ready.json').exists()
    seed=(SOURCE/'src/main/resources/db/seed.sql').read_text();pw=re.search(r'-- Synthetic accounts; password ([^,]+),',seed)[1]
    records=re.findall(r"\(\d+, '[^']+', '([^']+)', '[^']+', '[^']+', '(ADMIN|EMPLOYEE)', 'ACTIVE'",seed)
    a=load('actors.json') if (ROOT/'actors.json').exists() else {};marker=load('state.json')['marker']
    for idx,alias in enumerate(('A','B')):
        if alias in a:continue
        password=secrets.token_urlsafe(18)+'!aA1';c={'fullName':marker+' '+alias,'email':marker.lower()+'-'+alias.lower()+'@example.test','phone':'+84'+str(secrets.randbelow(899999999)+100000000),'password':password,'confirmPassword':password}
        save('credentials-'+alias+'.json',c)
        s,v=request('register-'+alias,'POST','/api/auth/register',c,purpose='actor setup: real registration')
        must(s,v,201);assert v['role']=='CUSTOMER'
        a[alias]={'email':c['email'],'password':password,'subject':str(v['id']),'role':'CUSTOMER'};save('actors.json',a)
    n=0
    for email,role in records:
        alias='ADMIN' if role=='ADMIN' else 'E'+str(n+1)
        if role=='EMPLOYEE':n+=1
        if alias not in a:a[alias]={'email':email,'password':pw,'role':role}
    assert 'E1' in a and 'E2' in a
    save('actors.json',a)
    trust={'publicKey':{'path':str(ROOT/'public.pem'),'sha256':hashlib.sha256((ROOT/'public.pem').read_bytes()).hexdigest()}}
    for alias,x in a.items():
        s,v=request('login-'+alias,'POST','/api/auth/token',{'email':x['email'],'password':x['password']},purpose='actor setup: real credential login')
        must(s,v,200);x.update(subject=str(v['user']['id']),token=v['accessToken'])
        claims=json.loads(__import__('base64').urlsafe_b64decode(x['token'].split('.')[1]+'=='));x['expiresAt']=claims['exp']
        verify_token(x['token'],trust,{'issuer':'sa-local-dev','audience':'sa-mock-api','roleClaim':'role'},x['subject'],x['role']);assert v['user']['role']==x['role'];save('actors.json',a)
    for alias in ('A','B'):
        s,c=request('identity-'+alias,'GET','/api/cart',actor=alias,purpose='actor identity protected probe');assert s==200 and str(c['userId'])==a[alias]['subject'] and not c['items']
    for alias in ('E1','E2','ADMIN'):
        s,v=request('identity-'+alias,'GET','/api/orders?size=1',actor=alias,purpose='actor role protected probe');assert s==(403 if alias=='ADMIN' else 200)
    save('actors-ready.json',{k:{'subject':x['subject'],'role':x['role'],'realLogin':True,'signatureVerified':True,'protectedProbeRead':True} for k,x in a.items()})
    print('Fresh customers A/B and seeded E1/E2/ADMIN logged in; signed identities and role probes verified.',flush=True)

def food(label,fid):return must(*request(label,'GET','/api/foods/'+str(fid),purpose='related state readback'),200)
def cart(label,actor):return must(*request(label,'GET','/api/cart',actor=actor,purpose='owner cart readback'),200)
def cart_identity_state(value):
    return {'id':value['id'],'userId':value['userId'],'items':sorted([{'id':x['id'],'foodId':x['food']['id'],'quantity':x['quantity']} for x in value['items']],key=lambda x:x['id'])}
def foreign_cart_checkout_checks(before,after,food_id,quantity):
    expected=copy.deepcopy(before)
    for item in expected['items']:
        if item['food']['id']==food_id:item['food']['stockQuantity']-=quantity
    def ordered(value):
        value=copy.deepcopy(value);value['items']=sorted(value['items'],key=lambda x:x['id']);return value
    return {'foreign-cart-unchanged':cart_identity_state(before)==cart_identity_state(after),
            'only-expected-shared-stock-change':quantity>0 and ordered(expected)==ordered(after)}
def order(label,oid,actor='E1'):return must(*request(label,'GET','/api/orders/'+str(oid),actor=actor,purpose='order state readback'),200)
def add(label,actor,fid,quantity=1,extra=None):
    return request(label,'POST','/api/cart/items',{'foodId':fid,'quantity':quantity,**(extra or {})},actor)
def create(label,actor,fid,typ='DINE_IN',quantity=1,extra=None):
    must(*add(label+'-add',actor,fid,quantity),200)
    before=food(label+'-stock-before',fid);cb=cart(label+'-cart-before',actor)
    body={'orderType':typ,'paymentMethod':'CASH' if typ=='DINE_IN' else 'COD','note':load('state.json')['marker']+' '+label}
    body.update({'tableNumber':'BOLA'} if typ=='DINE_IN' else {'recipientName':'BOLA Test','shippingPhone':'0900000099','shippingAddress':'Local fixture'})
    body.update(extra or {})
    s,v=request(label,'POST','/api/orders',body,actor);must(s,v,201)
    f=load('fixtures.json');f['orders'].append({'id':v['id'],'owner':actor,'type':typ,'foodId':fid,'quantity':quantity});save('fixtures.json',f)
    after=food(label+'-stock-after',fid);ca=cart(label+'-cart-after',actor);read=order(label+'-read',v['id'])
    expected_owner=int(load('actors.json')[actor]['subject'])
    ok=check_checkout({'stock':before['stockQuantity']},{'stock':after['stockQuantity'],'cart':ca,'order':read},food_id=fid,quantity=quantity,owner=expected_owner,food_name=before['name'],unit_price=before['price'])
    checks={'created-201':s==201,'owner-from-auth':v['userId']==expected_owner,'readback-same-order':read==v,'checkout-stock-cart-snapshot':ok}
    mark('createOrder','CUSTOMER','two-owner-checkout',label,checks)
    mark('createOrder','CUSTOMER','policy-response',label,checks)
    mark('createOrder','CUSTOMER','related-stock-cart-state',label,{'checkout-state':ok})
    return v

def execute():
    assert not (ROOT/'execution-started.json').exists(),'Resume by remaining labels, never replay this batch'
    save('execution-started.json',{'at':now()});a=load('actors.json');marker=load('state.json')['marker']
    # Public auth controllers have no existing-object selector. Strict injected role/id
    # rejection and credential identity are checked for each inbound bearer role.
    for role,alias in [('anonymous','anonymous'),('CUSTOMER','A'),('EMPLOYEE','E1'),('ADMIN','ADMIN')]:
        c=load('credentials-A.json');bad={**c,'role':'ADMIN','userId':a['B']['subject']}
        s,v=request('auth-register-role-'+role,'POST','/api/auth/register',bad,alias)
        mark('registerCustomer',role,'policy-response','auth-register-role-'+role,{'strict-owner-role-input-rejected':s==400,'no-account-disclosed':not any(k in v for k in ('id','user','accessToken'))})
        s,v=request('auth-login-role-'+role,'POST','/api/auth/token',{'email':a['A']['email'],'password':a['A']['password']},alias)
        mark('issueAccessToken',role,'policy-response','auth-login-role-'+role,{'login-200':s==200,'credential-identity-over-inbound-bearer':str(v.get('user',{}).get('id'))==a['A']['subject'] and v.get('user',{}).get('role')=='CUSTOMER'})
    s,foods=request('catalog-baseline','GET','/api/foods');must(s,foods,200);assert foods
    category=foods[0]['categoryId']
    for purpose in ('checkout','editable'):
        body={'categoryId':category,'name':marker+'-'+purpose,'description':'Dedicated BOLA ownership fixture','price':12345,'stockQuantity':200,'status':'ACTIVE','imageUrl':'https://example.test/bola.png'}
        s,v=request('food-create-'+purpose,'POST','/api/foods',body,'ADMIN');must(s,v,201)
        f=load('fixtures.json');f['foods'].append({'id':v['id'],'body':body,'purpose':purpose});save('fixtures.json',f)
        mark('createFood','ADMIN','policy-response','food-create-'+purpose,{'admin-created':s==201,'body-matches':all(v.get(k)==z for k,z in body.items())})
    f=load('fixtures.json');fid=f['foods'][0]['id'];edit=f['foods'][1]['id'];fb=f['foods'][1]['body']
    for role,alias in [('anonymous','anonymous'),('CUSTOMER','A'),('EMPLOYEE','E1'),('ADMIN','ADMIN')]:
        for oid,path in [('listActiveFoods','/api/foods?categoryId='+str(category)),('searchActiveFoods','/api/foods/search?'+urlencode({'q':marker,'categoryId':category})),('getActiveFood','/api/foods/'+str(fid))]:
            # operationId for detail is read from product spec, not assumed.
            if oid=='getActiveFood':oid=next(o['id'] for o in load('discovery.json')['operations'] if o['method']=='GET' and o['path']=='/api/foods/{id}')
            label='public-'+oid+'-'+role;s,v=request(label,'GET',path,actor=alias)
            found=(v.get('id')==fid) if isinstance(v,dict) else any(x['id']==fid for x in v)
            mark(oid,role,'policy-response',label,{'public-access':s==200,'fixture-visible':found,'active-only':all(x['status']=='ACTIVE' for x in (v if isinstance(v,list) else [v]))})
    # Populate both carts before ID substitution. All writes refer to owned fixtures.
    carts={}
    for alias in ('A','B'):
        other='B' if alias=='A' else 'A'
        other_before=cart('cart-other-before-add-'+alias,other)
        s,v=add('cart-add-'+alias,alias,fid,2,{'userId':int(a[other]['subject']),'cartId':other_before['id']})
        must(s,v,200);carts[alias]=v
        other_after=cart('cart-other-after-add-'+alias,other)
        checks={'own-cart':str(v['userId'])==a[alias]['subject'],'other-unchanged':other_before==other_after,'populated':len(v['items'])==1 and v['items'][0]['quantity']==2}
        for unit in ('policy-response','two-owner-isolation','client-owner-override'):mark('addCartItem','CUSTOMER',unit,'cart-add-'+alias,checks)
    for alias in ('A','B'):
        other='B' if alias=='A' else 'A';path='/api/cart?'+urlencode({'userId':a[other]['subject'],'cartId':carts[other]['id']})
        s,v=request('cart-selector-'+alias,'GET',path,actor=alias)
        checks={'own-cart-only':s==200 and v==carts[alias],'no-foreign-item-id':all(x['id']!=carts[other]['items'][0]['id'] for x in v['items'])}
        for unit in ('policy-response','two-owner-isolation','client-owner-override'):mark('getCurrentCart','CUSTOMER',unit,'cart-selector-'+alias,checks)
    for method,oid in [('PUT','updateCartItem'),('DELETE','removeCartItem')]:
        for alias in ('A','B'):
            other='B' if alias=='A' else 'A';target=carts[other]['items'][0]['id'];before={k:cart('cross-'+method+'-'+alias+'-before-'+k,k) for k in ('A','B')}
            label='cross-cart-'+method+'-'+alias;s,v=request(label,method,'/api/cart/items/'+str(target),{'quantity':7} if method=='PUT' else None,alias)
            after={k:cart('cross-'+method+'-'+alias+'-after-'+k,k) for k in ('A','B')}
            result=check_case({'access':'deny','denialStatuses':[404]}, {'response':{'status':s,'body':v},'disclosed':not (v.get('code')=='CART_ITEM_NOT_FOUND' and 'items' not in v),'before':before,'after':after,'captureComplete':True})
            for unit in ('cross-owner-both-directions','state-unchanged-after-denial'):mark(oid,'CUSTOMER',unit,label,{'denial-and-state-check':result['outcome']=='matched'})
        for alias in ('A','B'):
            label='own-cart-'+method+'-'+alias;target=carts[alias]['items'][0]['id'];s,v=request(label,method,'/api/cart/items/'+str(target),{'quantity':3} if method=='PUT' else None,alias)
            read=cart(label+'-read',alias)
            checks={'owner-allowed':s==200,'poststate-read':read==v,'poststate-correct':len(v['items'])==0 if method=='DELETE' else v['items'][0]['quantity']==3}
            for unit in ('policy-response','owner-positive'):mark(oid,'CUSTOMER',unit,label,checks)
    print('Public/catalog and two-owner cart checks read; preparing order/state fixtures.',flush=True)
    orders={}
    for alias in ('A','B'):
        for typ in ('DINE_IN','DELIVERY'):
            other='B' if alias=='A' else 'A';other_before=cart('checkout-other-before-'+alias+'-'+typ,other)
            o=create('checkout-'+alias+'-'+typ,alias,fid,typ,extra={'userId':int(a[other]['subject']),'cartId':carts[other]['id'],'items':[{'foodId':edit,'quantity':99}],'status':'COMPLETED'})
            other_after=cart('checkout-other-after-'+alias+'-'+typ,other)
            orders[alias+'-'+typ]=o
            mark('createOrder','CUSTOMER','client-owner-override','checkout-'+alias+'-'+typ,{'owner-is-caller':str(o['userId'])==a[alias]['subject'],'foreign-cart-unchanged':cart_identity_state(other_before)==cart_identity_state(other_after),'server-cart-only':len(o['items'])==1 and o['items'][0]['foodId']==fid,'client-status-ignored':o['status']=='PENDING'})
    save('order-fixtures.json',orders)
    s,role_cart=add('role-matrix-populated-cart','A',fid);must(s,role_cart,200);carts['A']=role_cart
    # Full denied role matrix, each mutation surrounded by owner/related readback.
    targets={'createFood':('POST','/api/foods',{**fb,'name':marker+'-denied-create'}), 'updateFood':('PUT','/api/foods/'+str(edit),{**fb,'description':'unauthorized-change'}),'deactivateFood':('DELETE','/api/foods/'+str(edit),None),'getCurrentCart':('GET','/api/cart',None),'addCartItem':('POST','/api/cart/items',{'foodId':fid,'quantity':1}),'updateCartItem':('PUT','/api/cart/items/'+str(carts['A']['items'][0]['id']),{'quantity':9}),'removeCartItem':('DELETE','/api/cart/items/'+str(carts['A']['items'][0]['id']),None),'createOrder':('POST','/api/orders',{'orderType':'DINE_IN','tableNumber':'BOLA','paymentMethod':'CASH'}),'listOrders':('GET','/api/orders?size=1',None),'getOrder':('GET','/api/orders/'+str(orders['A-DINE_IN']['id']),None),'cancelOrder':('DELETE','/api/orders/'+str(orders['A-DINE_IN']['id']),None),'confirmOrder':('POST','/api/orders/'+str(orders['A-DINE_IN']['id'])+'/confirm',None),'updateOrderStatus':('PUT','/api/orders/'+str(orders['A-DINE_IN']['id'])+'/status',{'status':'CONFIRMED'})}
    for op in load('discovery.json')['operations']:
        if op['id'] not in targets:continue
        for role,alias in [('anonymous','anonymous'),('CUSTOMER','A'),('EMPLOYEE','E1'),('ADMIN','ADMIN')]:
            if role in op['allowedRoles']:continue
            label='role-denial-'+op['id']+'-'+role;method,path,body=targets[op['id']]
            before={'food':food(label+'-food-before',edit),'stock':food(label+'-stock-before',fid),'order':order(label+'-order-before',orders['A-DINE_IN']['id']),'cart':cart(label+'-cart-before','A')}
            s,v=request(label,method,path,body,alias)
            after={'food':food(label+'-food-after',edit),'stock':food(label+'-stock-after',fid),'order':order(label+'-order-after',orders['A-DINE_IN']['id']),'cart':cart(label+'-cart-after','A')}
            code='UNAUTHENTICATED' if role=='anonymous' else 'FORBIDDEN'
            res=check_case({'access':'deny','denialStatuses':[401 if role=='anonymous' else 403]}, {'response':{'status':s,'body':v},'disclosed':not (v.get('code')==code and not any(k in v for k in ('items','userId','content','accessToken'))),'before':before,'after':after,'captureComplete':True})
            mark(op['id'],role,'policy-response',label,{'role-denial-no-disclosure-no-side-effect':res['outcome']=='matched'})
    must(*request('role-matrix-cart-remove','DELETE','/api/cart/items/'+str(carts['A']['items'][0]['id']),actor='A'),200)
    # Admin shared catalog mutations are functional authorization, no per-admin owner.
    label='admin-food-update';s,v=request(label,'PUT','/api/foods/'+str(edit),{**fb,'description':'authorized catalog edit'},'ADMIN');read=food(label+'-read',edit)
    mark('updateFood','ADMIN','policy-response',label,{'admin-200':s==200,'persisted':read==v and read['description']=='authorized catalog edit'})
    label='admin-food-deactivate';s,v=request(label,'DELETE','/api/foods/'+str(edit),actor='ADMIN');s2,v2=request(label+'-read','GET','/api/foods/'+str(edit))
    mark('deactivateFood','ADMIN','policy-response',label,{'admin-204':s==204,'inactive-hidden':s2==404 and v2.get('code')=='FOOD_NOT_FOUND'})
    print('All protected endpoint-role denial controls read; checking cross-owner orders and state transitions.',flush=True)
    for alias in ('A','B'):
        other='B' if alias=='A' else 'A';own=orders[alias+'-DINE_IN']['id'];foreign=orders[other+'-DINE_IN']['id']
        label='own-order-read-'+alias;s,v=request(label,'GET','/api/orders/'+str(own),actor=alias)
        for unit in ('policy-response','owner-positive'):mark('getOrder','CUSTOMER',unit,label,{'owner-read':s==200 and str(v['userId'])==a[alias]['subject']})
        label='foreign-order-read-'+alias;s,v=request(label,'GET','/api/orders/'+str(foreign),actor=alias)
        mark('getOrder','CUSTOMER','cross-owner-both-directions',label,{'foreign-denied':s==403 and v.get('code')=='FORBIDDEN','no-order-disclosed':'userId' not in v and 'items' not in v})
        label='foreign-order-cancel-'+alias;before=order(label+'-before',foreign);stock=food(label+'-stock-before',fid)
        s,v=request(label,'DELETE','/api/orders/'+str(foreign),actor=alias);after=order(label+'-after',foreign);stock_after=food(label+'-stock-after',fid)
        mark('cancelOrder','CUSTOMER','cross-owner-both-directions',label,{'403':s==403 and v.get('code')=='FORBIDDEN','no-side-effects':before==after and stock==stock_after})
    # Employee scope is shared across customers; confirmedBy is attribution, not owner.
    for alias in ('E1','E2'):
        for owner in ('A','B'):
            label='employee-read-'+alias+'-'+owner;o=order(label,orders[owner+'-DINE_IN']['id'],alias)
            for unit in ('policy-response','two-employees-cross-owner'):mark('getOrder','EMPLOYEE',unit,label,{'allowed-across-owner':str(o['userId'])==a[owner]['subject']})
    # Keep one pending order per customer for positive cancellation and one per type for flows.
    for alias in ('A','B'):
        extra=create('cancel-fixture-'+alias,alias,fid,quantity=2)
        label='owner-cancel-'+alias;before={'order':extra,'stock':food(label+'-stock-before',fid)['stockQuantity']}
        s,v=request(label,'DELETE','/api/orders/'+str(extra['id']),actor=alias);after={'order':order(label+'-read',extra['id']),'stock':food(label+'-stock-after',fid)['stockQuantity']}
        s2,v2=request(label+'-repeat','DELETE','/api/orders/'+str(extra['id']),actor=alias);repeat={'order':order(label+'-repeat-read',extra['id']),'stock':food(label+'-stock-repeat',fid)['stockQuantity']}
        checks={'cancelled-owner':s==200 and v==after['order'],'stock-restored-once':check_cancel(before,after,2,repeat),'repeat-conflict':s2==409 and v2.get('code')=='INVALID_ORDER_TRANSITION'}
        for unit in ('policy-response','owner-positive','stock-restored-once'):mark('cancelOrder','CUSTOMER',unit,[label,label+'-repeat'],checks)
    states=['PENDING','CONFIRMED','PROCESSING','SHIPPING','COMPLETED','CANCELLED']
    def state_reads(label,oid,owner):
        other='B' if owner=='A' else 'A'
        s,v=request(label+'-owner','GET','/api/orders/'+str(oid),actor=owner);s2,v2=request(label+'-foreign','GET','/api/orders/'+str(oid),actor=other)
        mark('getOrder','CUSTOMER','all-relevant-states',[label+'-owner',label+'-foreign'],{'owner-read-current-state':s==200 and str(v.get('userId'))==a[owner]['subject'],'foreign-still-denied':s2==403 and v2.get('code')=='FORBIDDEN' and 'items' not in v2})
        for employee in ('E1','E2'):
            s3,v3=request(label+'-'+employee,'GET','/api/orders/'+str(oid),actor=employee)
            mark('getOrder','EMPLOYEE','all-relevant-states',label+'-'+employee,{'authorized-current-state':s3==200 and v3==v})
    for owner in ('A','B'):
        for typ in ('DINE_IN','DELIVERY'):
            oid=orders[owner+'-'+typ]['id'];state_reads('state-pending-'+owner+'-'+typ,oid,owner)
            flow=['CONFIRMED','PROCESSING']+(['SHIPPING'] if typ=='DELIVERY' else [])+['COMPLETED']
            for idx,nxt in enumerate(flow):
                employee='E1' if (idx+(owner=='B'))%2==0 else 'E2';label='transition-'+owner+'-'+typ+'-'+nxt
                before=order(label+'-before',oid);stock=food(label+'-stock-before',fid)
                if nxt=='CONFIRMED':method,path,body,op='POST','/api/orders/'+str(oid)+'/confirm',None,'confirmOrder'
                else:method,path,body,op='PUT','/api/orders/'+str(oid)+'/status',{'status':nxt},'updateOrderStatus'
                s,v=request(label,method,path,body,employee);after=order(label+'-after',oid);stock_after=food(label+'-stock-after',fid)
                checks={'allowed-transition':s==200 and v==after and after['status']==nxt,'owner-stable':str(after['userId'])==a[owner]['subject'],'stock-unchanged':stock==stock_after,'confirmer-attribution':after['confirmedBy']==int(a[employee]['subject']) if nxt=='CONFIRMED' else after['confirmedBy']==before['confirmedBy']}
                for unit in ('policy-response','two-employees-cross-owner','transition-and-poststate'):mark(op,'EMPLOYEE',unit,label,checks)
                state_reads('state-'+nxt+'-'+owner+'-'+typ,oid,owner)
                if nxt in ('CONFIRMED','PROCESSING','SHIPPING','COMPLETED'):
                    label2='customer-cancel-nonpending-'+owner+'-'+typ+'-'+nxt;s2,v2=request(label2,'DELETE','/api/orders/'+str(oid),actor=owner);r=order(label2+'-read',oid)
                    mark('cancelOrder','CUSTOMER','non-pending-denial',label2,{'409-state-rule':s2==409 and v2.get('code')=='INVALID_ORDER_TRANSITION','unchanged':r==after})
            for employee in ('E1','E2'):
                for op,method,suffix,body in [('confirmOrder','POST','/confirm',None),('updateOrderStatus','PUT','/status',{'status':'PROCESSING'})]:
                    label='terminal-denial-'+owner+'-'+typ+'-'+employee+'-'+op;before=order(label+'-before',oid)
                    s,v=request(label,method,'/api/orders/'+str(oid)+suffix,body,employee);after=order(label+'-after',oid)
                    mark(op,'EMPLOYEE','terminal-state-denial',label,{'terminal-conflict':s==409 and v.get('code')=='INVALID_ORDER_TRANSITION','unchanged':before==after})
    for item in load('fixtures.json')['orders']:
        if item['id'] not in [x['id'] for x in orders.values()]:state_reads('state-cancelled-'+str(item['id']),item['id'],item['owner'])
    save('business-execution-finished.json',{'at':now()})
    print('Owner/cross-owner order detail/cancel and DINE_IN/DELIVERY transitions read through terminal states.',flush=True)

def supplement():
    assert (ROOT/'business-execution-finished.json').exists()
    assert not (ROOT/'supplement-finished.json').exists()
    inv=load('inventory.json')
    for c in inv['cases']:
        if c['operationId']=='createOrder' and c['role']=='CUSTOMER' and 'populated-foreign-cart-override' not in c['requiredEvidence']:c['requiredEvidence'].append('populated-foreign-cart-override')
        if c['operationId']=='updateOrderStatus' and c['role']=='EMPLOYEE' and 'cancel-and-restock' not in c['requiredEvidence']:c['requiredEvidence'].append('cancel-and-restock')
    save('inventory.json',inv)
    a=load('actors.json');fid=load('fixtures.json')['foods'][0]['id']
    # Give the foreign cart real contents: an empty foreign cart cannot show
    # whether checkout would consume another customer's items.
    for owner in ('A','B'):
        other='B' if owner=='A' else 'A'
        s,foreign=add('populated-foreign-add-'+owner,other,fid,3);must(s,foreign,200)
        o=create('populated-foreign-checkout-'+owner,owner,fid,extra={'userId':int(a[other]['subject']),'cartId':foreign['id']})
        after=cart('populated-foreign-after-'+owner,other)
        mark('createOrder','CUSTOMER','populated-foreign-cart-override','populated-foreign-checkout-'+owner,{'foreign-had-real-items':len(foreign['items'])==1 and foreign['items'][0]['quantity']==3,**foreign_cart_checkout_checks(foreign,after,fid,1),'own-cart-only-checkout':str(o['userId'])==a[owner]['subject'] and len(o['items'])==1 and o['items'][0]['quantity']==1})
        must(*request('populated-foreign-remove-'+owner,'DELETE','/api/cart/items/'+str(foreign['items'][0]['id']),actor=other),200)
    for i,start in enumerate(('PENDING','CONFIRMED','PROCESSING')):
        owner='A' if i%2==0 else 'B';other='B' if owner=='A' else 'A';o=create('employee-cancel-fixture-'+start,owner,fid,quantity=2)
        for nxt in (['CONFIRMED'] if start=='CONFIRMED' else ['CONFIRMED','PROCESSING'] if start=='PROCESSING' else []):
            s,v=request('employee-cancel-setup-'+start+'-'+nxt,'PUT','/api/orders/'+str(o['id'])+'/status',{'status':nxt},'E1');must(s,v,200)
        label='employee-cancel-'+start;before=order(label+'-before',o['id']);stock=food(label+'-stock-before',fid)
        s,v=request(label,'PUT','/api/orders/'+str(o['id'])+'/status',{'status':'CANCELLED'},'E2');after=order(label+'-after',o['id']);stock2=food(label+'-stock-after',fid)
        s2,v2=request(label+'-repeat','PUT','/api/orders/'+str(o['id'])+'/status',{'status':'CANCELLED'},'E1');read2=order(label+'-repeat-read',o['id']);stock3=food(label+'-stock-repeat',fid)
        mark('updateOrderStatus','EMPLOYEE','cancel-and-restock',[label,label+'-repeat'],{'authorized-cancel-from-state':s==200 and before['status']==start and after['status']=='CANCELLED','owner-stable':str(after['userId'])==a[owner]['subject'],'restocked-once':stock2['stockQuantity']-stock['stockQuantity']==2 and stock2==stock3,'repeat-denied-no-side-effect':s2==409 and v2.get('code')=='INVALID_ORDER_TRANSITION' and read2==after})
        s3,v3=request(label+'-owner','GET','/api/orders/'+str(o['id']),actor=owner);s4,v4=request(label+'-foreign','GET','/api/orders/'+str(o['id']),actor=other)
        mark('getOrder','CUSTOMER','all-relevant-states',[label+'-owner',label+'-foreign'],{'cancelled-owner-readable':s3==200 and v3==after,'foreign-denied':s4==403 and v4.get('code')=='FORBIDDEN' and 'items' not in v4})
        for employee in ('E1','E2'):
            for op,method,suffix,body in [('confirmOrder','POST','/confirm',None),('updateOrderStatus','PUT','/status',{'status':'PROCESSING'})]:
                lab=label+'-terminal-'+employee+'-'+op;s5,v5=request(lab,method,'/api/orders/'+str(o['id'])+suffix,body,employee);r=order(lab+'-read',o['id'])
                mark(op,'EMPLOYEE','terminal-state-denial',lab,{'cancelled-is-terminal':s5==409 and v5.get('code')=='INVALID_ORDER_TRANSITION','unchanged':r==after})
    # Known live fixtures at all employee queue states before pagination/filtering.
    for owner,typ,st in [('A','DINE_IN','CONFIRMED'),('B','DELIVERY','PROCESSING'),('A','DELIVERY','SHIPPING')]:
        o=create('active-state-fixture-'+st,owner,fid,typ)
        for nxt in ['CONFIRMED','PROCESSING','SHIPPING']:
            s,v=request('active-state-setup-'+st+'-'+nxt,'PUT','/api/orders/'+str(o['id'])+'/status',{'status':nxt},'E1');must(s,v,200)
            if nxt==st:break
        r=order('active-state-verify-'+st,o['id']);assert r['status']==st
    # Read shared catalog after deactivation for every caller role.
    inactive=load('fixtures.json')['foods'][1]['id'];marker=load('state.json')['marker']
    for role,alias in [('anonymous','anonymous'),('CUSTOMER','A'),('EMPLOYEE','E1'),('ADMIN','ADMIN')]:
        for op,path in [('listActiveFoods','/api/foods'),('searchActiveFoods','/api/foods/search?'+urlencode({'q':marker}))]:
            lab='inactive-catalog-'+op+'-'+role;s,v=request(lab,'GET',path,actor=alias)
            mark(op,role,'policy-response',lab,{'public-active-catalog':s==200 and all(x['status']=='ACTIVE' for x in v),'inactive-fixture-absent':all(x['id']!=inactive for x in v)})
    save('supplement-finished.json',{'at':now()})
    print('Populated foreign-cart checkout, employee cancellation/restock and all live queue states verified.',flush=True)

def collections():
    assert not (ROOT/'collections-finished.json').exists()
    a=load('actors.json');fixtures=load('fixtures.json')['orders'];states=['PENDING','CONFIRMED','PROCESSING','SHIPPING','COMPLETED','CANCELLED']
    # Known fixtures currently all terminal; add one live order for each owner so the
    # default employee queue and each customer's status filter are populated.
    fid=load('fixtures.json')['foods'][0]['id']
    for owner in ('A','B'):create('queue-fixture-'+owner,owner,fid,'DELIVERY' if owner=='B' else 'DINE_IN')
    fixtures=load('fixtures.json')['orders'];snap={x['id']:order('collection-fixture-read-'+str(x['id']),x['id']) for x in fixtures}
    def pages(prefix,alias,params,size=2):
        result=[];ids=[];page=0
        while True:
            label=prefix+'-page-'+str(page);s,v=request(label,'GET','/api/orders?'+urlencode({**params,'size':size,'page':page}),actor=alias);must(s,v,200)
            result.append(v);ids += [x['id'] for x in v['content']]
            if not v['content']:break
            page+=1;assert page<160,'pagination allocation needs continuation'
        return result,ids
    for owner in ('A','B'):
        own=[x['id'] for x in fixtures if x['owner']==owner];other='B' if owner=='A' else 'A'
        p,ids=pages('customer-pages-'+owner,owner,{})
        ok=check_pages(p,rows='/content',page='/page',size='/size',total='/totalElements',identity='/id',expected_ids=own,owner='/userId',expected_owner=int(a[owner]['subject']),terminal=True)
        for unit in ('policy-response','populated-pages-both-owners'):mark('listOrders','CUSTOMER',unit,'customer-pages-'+owner,{'populated-exact-owner-pagination':ok and len(own)>2})
        p2,ids2=pages('customer-owner-override-'+owner,owner,{'userId':a[other]['subject'],'customerId':a[other]['subject']})
        mark('listOrders','CUSTOMER','client-owner-override','customer-owner-override-'+owner,{'cannot-change-owner-filter':set(ids2)==set(own) and all(str(x['userId'])==a[owner]['subject'] for pg in p2 for x in pg['content'])})
        for st in states:
            for typ in ('DINE_IN','DELIVERY'):
                p3,ids3=pages('customer-filter-'+owner+'-'+st+'-'+typ,owner,{'status':st,'orderType':typ})
                expected=[i for i in own if snap[i]['status']==st and snap[i]['orderType']==typ]
                mark('listOrders','CUSTOMER','status-type-filter-isolation','customer-filter-'+owner+'-'+st+'-'+typ,{'exact-filtered-owner-pagination':check_pages(p3,rows='/content',page='/page',size='/size',total='/totalElements',identity='/id',expected_ids=expected,owner='/userId',expected_owner=int(a[owner]['subject']),terminal=True),'filters':all(x['status']==st and x['orderType']==typ for pg in p3 for x in pg['content'])})
    for employee in ('E1','E2'):
        p,ids=pages('employee-default-'+employee,employee,{},20)
        active=[i for i,x in snap.items() if x['status'] in ('PENDING','CONFIRMED','PROCESSING','SHIPPING')]
        checks={'valid-pagination':check_pages(p,rows='/content',page='/page',size='/size',total='/totalElements',identity='/id',expected_ids=ids,terminal=True),'both-owner-fixtures-in-queue':set(active)<=set(ids),'default-active-states':all(x['status'] in ('PENDING','CONFIRMED','PROCESSING','SHIPPING') for pg in p for x in pg['content'])}
        for unit in ('policy-response','populated-pages-cross-owner'):mark('listOrders','EMPLOYEE',unit,'employee-default-'+employee,checks)
        for st in states:
            for typ in ('DINE_IN','DELIVERY'):
                p2,ids2=pages('employee-filter-'+employee+'-'+st+'-'+typ,employee,{'status':st,'orderType':typ},20)
                expected=[i for i,x in snap.items() if x['status']==st and x['orderType']==typ]
                mark('listOrders','EMPLOYEE','default-queue-and-filters','employee-filter-'+employee+'-'+st+'-'+typ,{'pagination':check_pages(p2,rows='/content',page='/page',size='/size',total='/totalElements',identity='/id',expected_ids=ids2,terminal=True),'known-both-owner-fixtures-present':set(expected)<=set(ids2),'filter-values-correct':all(x['status']==st and x['orderType']==typ for pg in p2 for x in pg['content'])})
    save('collections-finished.json',{'at':now()});print('Customer exact known-object pagination and both employees queue/status/type filters read.',flush=True)

def review():
    assert (ROOT/'collections-finished.json').exists()
    assert not (ROOT/'review-finished.json').exists()
    rows=load('cases.json')
    # Oracles run at observation time. Never turn a discrepancy into matched
    # merely because it resembles a past adapter bug.
    save('interpretation-corrections.json',[])
    obs={}
    for c in rows:
        role=c['caseId'].split(':')[1];old=obs.setdefault(c['caseId'],{'role':role,'evidenceUnits':[],'resultRead':True,'outcome':'matched'})
        if c['unit'] not in old['evidenceUnits']:old['evidenceUnits'].append(c['unit'])
        if c['outcome']=='violated':old['outcome']='violated'
    save('observations.json',obs)
    fid=load('fixtures.json')['foods'][0]['id'];seen={}
    # Send cross-owner DELETE against real fixtures in all represented states.
    for x in load('fixtures.json')['orders']:
        other='B' if x['owner']=='A' else 'A';lab='review-foreign-cancel-'+str(x['id'])
        before=order(lab+'-before',x['id']);stock=food(lab+'-stock-before',fid)
        s,v=request(lab,'DELETE','/api/orders/'+str(x['id']),actor=other)
        after=order(lab+'-after',x['id']);stock2=food(lab+'-stock-after',fid)
        mark('cancelOrder','CUSTOMER','cross-owner-both-directions',lab,{'foreign-denied-in-state':s==403 and v.get('code')=='FORBIDDEN','no-order-disclosed':'items' not in v and 'userId' not in v,'order-and-stock-unchanged':before==after and stock==stock2})
        seen.setdefault(before['status'],[]).append(x['owner'])
    expected_states={'PENDING','CONFIRMED','PROCESSING','SHIPPING','COMPLETED','CANCELLED'};assert set(seen)==expected_states
    # Readback validates real actor/direction/state, beyond a unit-label match.
    for owner in ('A','B'):
        for method in ('PUT','DELETE'):
            r=load('http/cross-cart-'+method+'-'+owner+'.json');assert r['status']==404 and r['result']['code']=='CART_ITEM_NOT_FOUND'
        assert load('http/foreign-order-read-'+owner+'.json')['status']==403
        assert load('http/populated-foreign-checkout-'+owner+'.json')['status']==201
        actual_states=set()
        for p in (ROOT/'http').glob('state-*-owner.json'):
            r=json.loads(p.read_text())
            if r['actor']==owner and r['status']==200:actual_states.add(r['result']['status'])
        assert actual_states==expected_states
    for employee in ('E1','E2'):
        for owner in ('A','B'):assert load('http/employee-read-'+employee+'-'+owner+'.json')['status']==200
    unknown=[p.name for p in (ROOT/'http').glob('*.json') if json.loads(p.read_text())['state']!='acknowledged'];assert not unknown
    rec=reconcile(load('inventory.json'),load('observations.json'),{});assert not rec['openResponsibilities'],str(rec['openResponsibilities'])
    save('review-finished.json',{'at':now(),'crossOwnerCancellationStates':seen,'allOwnerStatesRead':True,'bothCustomerDirectionsAndBothEmployeesChecked':True,'unknownOutcomes':unknown,'scopeReconciliation':rec['taskCompletion']})
    print('Actual readback reviewed: six states, both customer directions and employees. Ownership/stock predicates and empty-page contract applied at observation time; no automatic verdict correction.',flush=True)

def cleanup():
    assert not (ROOT/'cleanup-finished.json').exists()
    f=load('fixtures.json');clean=[];final_orders=[]
    for x in f['orders']:
        label='cleanup-order-'+str(x['id']);o=order(label+'-before',x['id'])
        if o['status'] in ('PENDING','CONFIRMED','PROCESSING','SHIPPING'):
            nxt='COMPLETED' if o['status']=='SHIPPING' else 'CANCELLED'
            if o['status']=='PENDING':s,v=request(label,'DELETE','/api/orders/'+str(x['id']),actor=x['owner'])
            else:s,v=request(label,'PUT','/api/orders/'+str(x['id'])+'/status',{'status':nxt},'E1')
            must(s,v,200);r=order(label+'-after',x['id']);assert r['status']==nxt
            clean.append({'orderId':x['id'],'action':'close owned fixture by authorized '+('owner cancellation' if o['status']=='PENDING' else 'employee transition'),'status':s,'readbackStatus':r['status']})
            final_orders.append(r)
        else:
            clean.append({'orderId':x['id'],'action':'retained terminal test order','status':o['status']});final_orders.append(o)
    for owner in ('A','B'):
        c=cart('cleanup-cart-'+owner,owner)
        for x in c['items']:must(*request('cleanup-item-'+str(x['id']),'DELETE','/api/cart/items/'+str(x['id']),actor=owner),200)
        assert not cart('cleanup-cart-final-'+owner,owner)['items']
    checkout=next(x for x in f['foods'] if x['purpose']=='checkout')
    remaining=food('cleanup-final-stock',checkout['id'])['stockQuantity']
    completed_quantity=sum(i['quantity'] for o in final_orders if o['status']=='COMPLETED' for i in o['items'] if i['foodId']==checkout['id'])
    assert remaining==checkout['body']['stockQuantity']-completed_quantity
    assert all(o['status'] in ('COMPLETED','CANCELLED') for o in final_orders)
    save('cleanup-stock.json',{'initial':checkout['body']['stockQuantity'],'final':remaining,'completedQuantity':completed_quantity,'conservationMatched':True,'terminalOrders':len(final_orders)})
    for x in f['foods']:
        label='cleanup-food-'+str(x['id']);s,v=request(label,'DELETE','/api/foods/'+str(x['id']),actor='ADMIN');assert s==204
        s2,v2=request(label+'-read','GET','/api/foods/'+str(x['id']));assert s2==404 and v2['code']=='FOOD_NOT_FOUND'
    assert binding()[0]==load('discovery.json')['deployment']
    save('cleanup-finished.json',{'at':now(),'orders':clean,'carts':'both empty','foods':'both deactivated and public 404 read','accounts':'Two dedicated test customers retained; product exposes no account delete API. Real tokens/credentials stay private local.','infrastructure':'No containers/builds/scanner sessions created, restarted, stopped or modified.'})
    print('Pending owned orders cancelled; carts empty; fixture foods deactivated; deployment unchanged.',flush=True)

def report():
    d=load('discovery.json');inv=load('inventory.json');obs=load('observations.json');cases=load('cases.json');rec=reconcile(inv,obs,{})
    operations=[json.loads(p.read_text()) for p in sorted((ROOT/'http').glob('*.json'))]
    unknown=[r for r in operations if r['state']!='acknowledged']
    if unknown:rec.update(taskCompletion='partial',handoffClosesTask=False,executionGaps=['Unknown request outcomes need reconciliation: '+','.join(x['id'] for x in unknown)])
    findings=[]
    for c in cases:
        if c['outcome']=='violated':findings.append({'name':'Authorization or ownership expectation discrepancy','severity':'Medium','confidence':'Medium','source':'direct','track':'bola-ownership','caseId':c['caseId'],'question':c['unit'],'operationIds':c['operationIds'],'reasons':c['reasons'],'assessment':'Discrepancy against documented/source policy; inspect concrete responses and state before asserting exploit impact.'})
    alerts={'product':'ByteMe','track':'bola-ownership','origin':ORIGIN,'summary':{'groups':len(findings),'bySeverity':{s:sum(f['severity']==s for f in findings) for s in ('High','Medium','Low','Informational')},'bySource':{'direct':len(findings),'ZAP':0},'instances':len(findings)},'alerts':findings,'interpretation':'No discrepancy is scoped to performed ownership cases and policy basis; it does not certify overall product safety. No ZAP scan executed in this track.'}
    clean=load('cleanup-finished.json') if (ROOT/'cleanup-finished.json').exists() else {'status':'pending'}
    coverage=[]
    for c in inv['cases']:
        matches=[x for x in cases if x['caseId']==c['caseId']]
        missing=sorted(set(c['requiredEvidence'])-set(obs.get(c['caseId'],{}).get('evidenceUnits',[])))
        coverage.append({'operationId':c['operationId'],'method':c['method'],'path':c['path'],'role':c['role'],'questions':c['requiredEvidence'],'performed':matches,'missing':missing,'applicability':'Public auth binds supplied credentials/new registration and has no existing-object selector; tested role/id injection or credential binding.' if c['operationId'] in ('registerCustomer','issueAccessToken') else 'Shared catalog: functional role authorization; food/category have no personal owner.' if 'Food' in c['operationId'] or 'Foods' in c['operationId'] else 'Cart/order owner isolation or documented employee cross-owner permission; forbidden roles checked separately.'})
    # Minimize responses in shareable operations: never include unrelated customer data.
    for r in operations:
        v=r.pop('result',None)
        if isinstance(v,dict):
            r['resultSummary']={k:v[k] for k in ('id','userId','status','code','page','size','totalElements','subject','role') if k in v}
            if 'content' in v:r['resultSummary']['ownedFixtureIds']=[x['id'] for x in v['content'] if x['id'] in {i['id'] for i in load('fixtures.json')['orders']}]
            if 'items' in v:r['resultSummary']['itemCount']=len(v['items'])
        elif isinstance(v,list):r['resultSummary']={'count':len(v)}
    run={'product':'ByteMe','environment':inv['environment'],'origin':ORIGIN,'track':'bola-ownership','startedAt':d['startedAt'],'finishedAt':now(),'executionStatus':'finished' if (ROOT/'collections-finished.json').exists() and (ROOT/'cleanup-finished.json').exists() else 'partial','deployment':d['deployment'],'source':{'location':str(SOURCE),'head':d['sourceHead'],'dirty':d['sourceDirty'],'runtimeSpecMatches':True,'runtimeBinarySourceIdentity':'Image/container identity and matching deployed spec verified; binary byte-for-byte correspondence to source not independently established.'},'scope':{'operations':d['operations'],'roles':ROLES,'businessMethodRoutes':18,'endpointRolePairs':72,'supportingSurfaces':'health/docs serve no owned business object; used only for discovery','technique':'direct ownership requests, role denials, owner/non-owner substitutions, body/query owner override attempts, state/related-state readback, populated collection pagination/filtering','policyBasis':d['policyBasis']},'adapterDecision':d['routing'],'preflight':d['preflight'],'actors':load('actors-ready.json'),'operations':d['supportOperations']+operations,'coverage':coverage,'semanticCaseResults':len(cases),'limitations':['Expected policy comes from current README/OpenAPI/source; no independent business policy approval.','Employee global collection completeness is checked structurally across all returned pages and against both owners known fixtures; no independent DB census of historical orders.','Runtime binary/source correspondence was not independently attested.','Finite role/ownership/state cases do not establish absence of every possible authorization defect.'],'cleanup':clean,'alertsSummary':alerts['summary'],'historicalResults':'Earlier other-track results retained in place and not counted as new ownership observations.','continuationLocation':str(OUT)}
    run['resultInterpretationCorrections']=load('interpretation-corrections.json')
    run['semanticReadbackReview']=load('review-finished.json')
    run['cleanup']['stockConservation']=load('cleanup-stock.json')
    run['executionNotes']=['Initial system Python lacked jsonschema before discovery or traffic; switched to existing zap-product-assessment/.venv with required dependencies. No package installation or scanner changes.','Two analysis issues were diagnosed using captured responses: shared FoodDto stock is not cart ownership state, and an empty filtered page needs no redundant second empty page. Original HTTP and original analysis values retained in the working journal; corrected derived observations are recorded above.']
    compact_results(OUT,run,alerts,rec)
    print(json.dumps({'taskCompletion':rec['taskCompletion'],'open':[(x['caseId'],x.get('missingEvidence')) for x in rec['openResponsibilities']],'requests':len(operations),'semanticCaseResults':len(cases),'findings':len(findings),'output':str(OUT)},ensure_ascii=False),flush=True)

if __name__=='__main__':
    fn=globals()[sys.argv[1]]
    try:fn()
    except Exception as e:
        save('last-error.json',{'at':now(),'phase':sys.argv[1],'type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()})
        print('Phase failed; private diagnostic saved:',type(e).__name__,str(e),flush=True);sys.exit(1)
