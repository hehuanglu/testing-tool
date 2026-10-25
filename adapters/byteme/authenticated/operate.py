import os,sys,json,time,secrets,re,subprocess,hashlib,copy,urllib.request,urllib.error,base64
from pathlib import Path
from urllib.parse import urlsplit
from types import SimpleNamespace
CODE_ROOT=Path(__file__).resolve().parent;BASE=CODE_ROOT.parents[2];PKG=BASE/'zap-product-assessment';ROOT=Path(os.environ.get('BYTEME_AUTH_ROOT',str(BASE/'operations/byteme/authenticated'))).resolve();SOURCE=Path('/Users/hahoangloc/Working/UET/SA/ByteMe')
ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
sys.path.insert(0,str(PKG/'src'))
from zap_assessment.anonymous_runtime import AnonymousRuntime,inspect_binding
from zap_assessment.runtime import DockerRuntime,docker,engine_bool
from zap_assessment.journal import Journal
from zap_assessment.transport import MCP,field
from zap_assessment.anonymous_runner import AnonymousRun
from zap_assessment.result_readers import read_jsonl,collect_alerts

def save(n,v):
 p=ROOT/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2));p.chmod(0o600)
def load(n):return json.loads((ROOT/n).read_bytes())
def direct(method,path,body=None,role=None,label='discovery'):
 a=load('actors.json') if (ROOT/'actors.json').exists() else {};h={'Accept':'application/json'}
 if role:h['Authorization']='Bearer '+a[role]['token']
 if body is not None:h['Content-Type']='application/json'
 row={'at':time.time(),'method':method,'path':path,'role':role,'technique':'direct setup/readback','label':label}
 with (ROOT/'direct-journal.jsonl').open('a') as f:f.write(json.dumps({**row,'phase':'intent'})+'\n')
 req=urllib.request.Request('http://127.0.0.1:8081'+path,data=None if body is None else json.dumps(body).encode(),method=method,headers=h)
 try:r=urllib.request.urlopen(req,timeout=12)
 except urllib.error.HTTPError as e:r=e
 with r:blob=r.read(2*1024*1024);s=r.status
 try:v=json.loads(blob) if blob else None
 except ValueError:v=blob.decode()
 with (ROOT/'direct-journal.jsonl').open('a') as f:f.write(json.dumps({**row,'phase':'ack','status':s})+'\n')
 return s,v

def build_responsibilities(spec,operations):
 """Source denominator, built before execution cases or campaign selection."""
 def resolve(value):
  while '$ref' in value:
   node=spec
   for key in value['$ref'].removeprefix('#/').split('/'):node=node[key]
   value=node
  if 'allOf' in value:
   value={**value,**resolve(value['allOf'][0])}
  return value
 result=[]
 for op in operations:
  if not op['protected']:continue
  vectors=[]
  if op.get('requestBody'):
   body=resolve(op['requestBody']);schema=resolve(body['content']['application/json']['schema'])
   if op['id']=='createOrder':
    branches={'DINE_IN':['orderType','tableNumber','paymentMethod','note'],'DELIVERY':['orderType','recipientName','shippingPhone','shippingAddress','paymentMethod','note']}
    assert set().union(*map(set,branches.values()))==set(schema['properties']),'new order input must remain in source inventory'
    vectors.extend((branch,{f:schema['properties'][f] for f in fields}) for branch,fields in branches.items())
   else:vectors.append(('JSON-body',schema['properties']))
  query={resolve(p)['name']:resolve(p)['schema'] for p in op['parameters'] if resolve(p)['in']=='query'}
  if query:vectors.append(('query',query))
  if '{' in op['pathTemplate']:vectors.append(('path',{'selector':{'type':'integer'}}))
  if not vectors:vectors.append(('header',{'header':{'type':'string','enum':[]}}))
  for role in op['roles']:
   for vector,fields in vectors:
    for field,raw in fields.items():
     schema=resolve(raw);processing=vector in ('JSON-body','DINE_IN','DELIVERY') and schema.get('type')=='string' and 'enum' not in schema
     result.append({'caseId':'::'.join([op['id'],role,vector,field]),'operationId':op['id'],'method':op['method'],'path':op['pathTemplate'],'role':role,'vector':vector,'field':field,'goal':'accepted mutation with independent API persistence readback' if processing else 'authenticated input/response boundary; fixture conflicts do not prove processing','requiresAcceptedMutation':processing})
 save('responsibilities.json',result)

def discover():
 import yaml
 from zap_assessment.signed_identity import verify_token
 assert not (ROOT/'actors.json').exists(),'discovery already dispatched; reconcile'
 b,proof=inspect_binding('byteme-backend-1','byteme',8080)
 labels=json.loads(docker(['inspect','--format','{{json .Config.Labels}}','byteme-backend-1']))
 assert labels['com.docker.compose.project.working_dir']==str(SOURCE)
 spec=yaml.safe_load((SOURCE/'src/main/resources/static/openapi.yaml').read_bytes());s,live=direct('GET','/openapi.yaml');assert s==200 and yaml.safe_load(live)==spec
 ops=[]
 for path,item in spec['paths'].items():
  for m,o in item.items():
   if m.upper() not in ['GET','POST','PUT','DELETE','PATCH','HEAD','OPTIONS']:continue
   protected=bool(o.get('security',spec.get('security',[])))
   roles=(['ADMIN'] if path.startswith('/api/foods') else ['CUSTOMER','EMPLOYEE'] if m=='get' and path.startswith('/api/orders') else ['EMPLOYEE'] if path.endswith('/confirm') or path.endswith('/status') else ['CUSTOMER']) if protected else []
   ops.append({'id':o['operationId'],'method':m.upper(),'pathTemplate':path,'protected':protected,'roles':roles,'parameters':item.get('parameters',[])+o.get('parameters',[]),'requestBody':o.get('requestBody')})
 assert len(ops)==18 and sum(o['protected'] for o in ops)==13
 save('discovery.json',{'source':str(SOURCE),'sourceHead':subprocess.check_output(['git','-C',str(SOURCE),'rev-parse','HEAD'],text=True).strip(),'sourceDirty':bool(subprocess.check_output(['git','-C',str(SOURCE),'status','--porcelain'],text=True).strip()),'binding':b,'bindingProof':proof,'operations':ops,'liveOpenApiMatches':True})
 build_responsibilities(spec,ops)
 # Legitimate seeded logins, extracted privately from this product's documented seed.
 seed=(SOURCE/'src/main/resources/db/seed.sql').read_text();pw=re.search(r'-- Synthetic accounts; password ([^,]+),',seed)[1]
 records=re.findall(r"\(\d+, '[^']+', '([^']+)', '[^']+', '[^']+', '(ADMIN|EMPLOYEE)', 'ACTIVE'",seed)
 actors={}
 traffic=Path(os.environ.get('BYTEME_ANON_ROOT',str(BASE/'operations/byteme/anonymous')))/'guard-private/traffic.jsonl'
 rows=read_jsonl(traffic)
 registered=next(json.loads(x['actualBody']) for x in rows if x.get('path')=='/api/auth/register' and x.get('status')==201 and x.get('field')=='fullName')
 customer={k:registered[k] for k in ('email','password')}
 creds={'CUSTOMER':customer}
 for email,role in records:
  if role not in creds:creds[role]={'email':email,'password':pw}
 # Key must match the current deployed public key; never read private signing material.
 mounts=json.loads(docker(['inspect','--format','{{json .Mounts}}','byteme-backend-1']))
 pubs=[m for m in mounts if m['Destination']=='/run/auth' and m['Type']=='bind'];assert len(pubs)==1
 keybytes=(Path(pubs[0]['Source'])/'public.pem').read_bytes();(ROOT/'public.pem').write_bytes(keybytes)
 trust={'publicKey':{'path':str(ROOT/'public.pem'),'sha256':hashlib.sha256(keybytes).hexdigest()}}
 for role,c in creds.items():
  s,v=direct('POST','/api/auth/token',c,label='real-login-'+role);assert s==200
  token=v['accessToken'];parts=token.split('.');claims=json.loads(base64.urlsafe_b64decode(parts[1]+'='*((-len(parts[1]))%4)))
  verify_token(token,trust,{'issuer':'sa-local-dev','audience':'sa-mock-api','roleClaim':'role'},str(v['user']['id']),role)
  assert claims['role']==role and claims['iss']=='sa-local-dev' and 'sa-mock-api' in claims['aud'] and claims['exp']>time.time()
  assert str(v['user']['id'])==claims['sub'] and v['user']['role']==role
  actors[role]={**c,'subject':claims['sub'],'role':role,'token':token,'expiresAt':claims['exp']};save('actors.json',actors)
 s,cart=direct('GET','/api/cart',role='CUSTOMER',label='customer-native-probe-candidate');assert s==200 and str(cart['userId'])==actors['CUSTOMER']['subject'] and not cart['items']
 s,v=direct('GET','/api/orders',role='EMPLOYEE',label='employee-protected-probe');assert s==200 and v['page']==0
 s,v=direct('GET','/api/orders',role='ADMIN',label='admin-distinct-role-control');assert s==403 and v['code']=='FORBIDDEN'
 save('actor-validation.json',{r:{'subject':a['subject'],'role':r,'realLogin':True,'signatureVerified':True,'expiresAt':a['expiresAt']} for r,a in actors.items()})
 save('resources-host.json',{'at':time.time(),'hostFree':os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize})
 print(json.dumps({'sourceVerified':True,'protectedOperations':13,'authorizedRoleOperations':15,'actors':list(actors),'bindingAddress':b['address']}))

class AuthRuntime(AnonymousRuntime):
 def owned_names(self):
  allocated=[e['data']['resource'] for e in self.journal.events if e['kind']=='intent' and e['data'].get('action')=='container-create' and e['data'].get('createdByRun')==self.run_id]
  return list(dict.fromkeys([*super().owned_names(),*allocated]))
 def create(self,name,image,args):
  args=list(args)
  if name==self.anchor:self.commands[name]=['sleep','14400']
  if name==self.names[1]:
   args=[x.replace(str(PKG/'src/zap_assessment/anonymous_guard.py')+':/guard.py:ro',str(CODE_ROOT/'guard.py')+':/guard.py:ro') for x in args]
   args+=['-v',str(PKG/'src/zap_assessment/anonymous_guard.py')+':/anonymous_guard.py:ro']
  if name==self.names[3]:
   env=self.config/'private-mcp.env';v=env.read_text();v+='SPRING_CONFIG_ADDITIONAL_LOCATION=file:/research/auth.yml\n';env.write_text(v);env.chmod(0o600)
   args+=['-v',str(ROOT/'candidate.jar')+':/app/app.jar:ro','-v',str(self.config)+':/research:ro']
  return super().create(name,image,args)

def init():
 import yaml
 assert not (ROOT/'plan.json').exists(),'allocation exists; resume'
 d=load('discovery.json');a=load('actors.json');b,proof=inspect_binding('byteme-backend-1','byteme',8080);assert b==d['binding']
 marker=secrets.token_hex(5);p={'runId':'byteme-auth-'+marker,'origin':'http://'+b['address']+':8080','targetBinding':b,'discovery':{'operations':d['operations']},'notAfter':time.time()+14400,'anonymousState':{'cookies':[]},'limits':{'requestBytes':16384,'responseBytes':1048576,'requestTimeoutSeconds':12,'maxForwarded':6000,'maxMutations':2000,'requestsPerSecond':2,'artifactBytes':180*1024*1024},'cases':[],'campaigns':[],'actors':a,'authority':{'secretPersistenceAccepted':True},'marker':'ZAP-auth-'+marker}
 save('plan.json',p);j=Journal(ROOT/'journal.jsonl',p['runId'],hashlib.sha256((ROOT/'plan.json').read_bytes()).hexdigest());rt=AuthRuntime(p,ROOT,j)
 jar=BASE/'mcp-zap-server/build/libs/mcp-zap-server-0.16.0.jar';os.link(jar,ROOT/'candidate.jar')
 profiles=[]
 for role,v in a.items():
  f=rt.config/('password-'+role);f.write_text(v['password']);f.chmod(0o444)
  prof={'id':'byteme-'+role,'kind':'json-bearer','allowed-origin':p['origin'],'credential-reference':'file:/research/password-'+role,'login-url':p['origin']+'/api/auth/token','username':v['email'],'zap-user-name':'actor-'+role,'username-json-field':'email','password-json-field':'password','token-json-pointer':'/accessToken','header-name':'Authorization','header-prefix':'Bearer ','verification-url':p['origin']+('/api/cart' if role=='CUSTOMER' else '/api/orders'),'logged-in-indicator-regex':'.*','logged-out-indicator-regex':'"(?:status|statusCode)"\\s*:\\s*401','expected-subject':v['subject']}
  if role=='CUSTOMER':prof['subject-json-pointer']='/userId'
  else:prof['signed-jwt-identity']={'public-key-file':'/research/public.pem','public-key-sha256':hashlib.sha256((ROOT/'public.pem').read_bytes()).hexdigest(),'issuer':'sa-local-dev','audience':'sa-mock-api','role-claim':'role','expected-role':role,'expected-status':403 if role=='ADMIN' else 200,'response-pointer':'/code' if role=='ADMIN' else '/page','response-value':'FORBIDDEN' if role=='ADMIN' else '0'}
  profiles.append(prof)
 (rt.config/'public.pem').write_bytes((ROOT/'public.pem').read_bytes());(rt.config/'public.pem').chmod(0o444)
 (rt.config/'auth.yml').write_text(yaml.safe_dump({'zap':{'auth':{'experimental-json-bearer-enabled':True}},'mcp':{'server':{'auth':{'bootstrap':{'profiles':profiles}}}}}));(rt.config/'auth.yml').chmod(0o444)
 rt.provision();rt.wait_health(120)
 m=MCP(rt.request);schema=m.initialize();save('tools.json',schema)
 assert {'method','postData','authSessionId'}<=schema['tools']['zap_attack_start']['properties'].keys(),'candidate exact-body capability absent'
 for args in [('network','action','setHttpProxy',{'host':'127.0.0.1','port':18888}),('network','action','setHttpProxyAuthEnabled',{'enabled':'false'}),('network','action','setHttpProxyEnabled',{'enabled':'true'}),('ascan','action','setOptionThreadPerHost',{'Integer':1}),('ascan','action','setOptionHostPerScan',{'Integer':1}),('ascan','action','setOptionMaxScanDurationInMins',{'Integer':3}),('ascan','action','setOptionAddQueryParam',{'Boolean':'false'}),('core','action','setOptionHttpStateEnabled',{'Boolean':'false'}),('ascan','action','setOptionScanHeadersAllRequests',{'Boolean':'true'}),('ascan','action','setOptionInjectPluginIdInHeader',{'Boolean':'true'})]:rt.engine(*args)
 for x in rt.engine('network','view','getHttpProxyExclusions',{}).get('getHttpProxyExclusions',[]):rt.engine('network','action','setHttpProxyExclusionEnabled',{'host':x['host'],'enabled':'false'})
 save('boundary.json',rt.boundary());save('resources-before.json',rt.sample())
 sessions={}
 for role in a:
  text=mcall(m,'zap_auth_session_prepare',{'profileId':'byteme-'+role,'targetUrl':p['origin']+('/api/cart' if role=='CUSTOMER' else '/api/orders')},'prepare-'+role)
  ss={k:field(text,label) for k,label in [('sessionId','Session ID'),('contextId','Context ID'),('userId','User ID')]};sessions[role]=ss;save('sessions.json',sessions)
  text=mcall(m,'zap_auth_session_validate',{'sessionId':ss['sessionId']},'validate-'+role);assert '\nValid: true\n' in '\n'+text+'\n','native session invalid '+role
 save('runtime-ready.json',{'at':time.time(),'nativeProfilesValidated':list(sessions),'jarSha256':hashlib.sha256(jar.read_bytes()).hexdigest(),'version':rt.engine('core','view','version',{})})
 print('Owned runtime ready; all three native sessions validated.',flush=True)

def mcall(m,name,args,label):
 from jsonschema import Draft202012Validator
 Draft202012Validator(m.contracts[name]).validate(args)
 v=m.rpc('tools/call',{'name':name,'arguments':args});save('mcp/'+label+'.json',v)
 if v.get('isError'):raise RuntimeError('MCP rejected '+name+'; private response saved')
 text='\n'.join(x['text'] for x in v['content']);return json.loads(text) if text.startswith('"') else text

def resume():
 p=load('plan.json');j=Journal(ROOT/'journal.jsonl',p['runId'],hashlib.sha256((ROOT/'plan.json').read_bytes()).hexdigest());rt=object.__new__(AuthRuntime);DockerRuntime.__init__(rt,p['runId'],ROOT,j);rt.locked=p;rt.config=ROOT/'config';rt.work=ROOT/'workspace';rt.capture=ROOT/'guard';rt.stop_timeout=60
 rt.mcp_key=next(x.split('=',1)[1] for x in (rt.config/'private-mcp.env').read_text().splitlines() if x.startswith('MCP_API_KEY='))
 for name in rt.names:rt.check_owner(name)
 if (ROOT/'runtime-state.json').exists():
  state=load('runtime-state.json');rt.capture=ROOT/state['capture'];rt.check_owner(state['extraGuard'])
 return p,j,rt

if __name__=='__main__':
 if sys.argv[1]=='discover':discover()
 if sys.argv[1]=='init':init()

def fixtures():
 p=load('plan.json');assert not (ROOT/'fixtures.json').exists(),'fixture setup already dispatched; reconcile'
 ledger={'foods':[],'orders':[],'startedAt':time.time()};save('fixtures.json',ledger)
 for purpose,stock in [('checkout',1000),('edit',50),('deactivate',0)]:
  body={'categoryId':1,'name':p['marker']+'-'+purpose,'description':'owned authenticated baseline','price':10000,'stockQuantity':stock,'status':'ACTIVE','imageUrl':'https://example.test/'+p['marker']+'.png'}
  s,v=direct('POST','/api/foods',body,'ADMIN','create-dedicated-'+purpose);assert s==201
  ledger['foods'].append({'purpose':purpose,'id':v['id'],'body':body,'initial':v});save('fixtures.json',ledger)
 fid=ledger['foods'][0]['id']
 for purpose in ['read','cancel','confirm','status','status-selector']:
  s,cart=direct('POST','/api/cart/items',{'foodId':fid,'quantity':1},'CUSTOMER','setup-cart-'+purpose);assert s==200
  s,v=direct('POST','/api/orders',{'orderType':'DINE_IN','tableNumber':'ZAP-'+purpose,'paymentMethod':'CASH','note':p['marker']},'CUSTOMER','setup-order-'+purpose);assert s==201
  ledger['orders'].append({'purpose':purpose,'id':v['id'],'initial':v});save('fixtures.json',ledger)
  if purpose in ('status','status-selector'):
   s,x=direct('POST','/api/orders/'+str(v['id'])+'/confirm',role='EMPLOYEE',label='prepare-status-confirmed');assert s==200 and x['status']=='CONFIRMED'
 s,cart=direct('POST','/api/cart/items',{'foodId':fid,'quantity':1},'CUSTOMER','prepare-populated-cart');assert s==200 and len(cart['items'])==1
 ledger['cartItemId']=cart['items'][0]['id'];ledger['readyAt']=time.time();save('fixtures.json',ledger)
 print('Dedicated foods/orders and populated CUSTOMER cart ready.',flush=True)

def allocate():
 p,j,rt=resume();assert not (ROOT/'execution.json').exists(),'allocation already written'
 f=load('fixtures.json');a=load('actors.json');q=copy.deepcopy(p);q['checkoutFoodId']=f['foods'][0]['id']
 cases=[];campaigns=[]
 def case(cid,oid,role,path,body=None,statuses=[200]):
  op=next(x for x in p['discovery']['operations'] if x['id']==oid);assert role in op['roles']
  c={'id':cid,'operationId':oid,'method':op['method'],'path':path,'body':body,'role':role,'category':'protected-success','expected':{'statuses':statuses}}
  cases.append(c);return c
 def camp(c,vector,keys,rules,cap=180):
  fields=keys if vector in ('JSON-body','query') else ['selector' if vector=='path' else 'header']
  texts=[k for k in fields if isinstance((c.get('body') or {}).get(k),str) and k not in ('status','orderType','paymentMethod')]
  questions=[{'id':c['id']+'-'+vector+'-rule-'+str(r),'ruleIds':[r],'minimumStage':'processing' if r==40012 else 'boundary','fields':texts if r==40012 else fields,'basis':'JSON reflection on textual fields, with native LOW alert threshold; no browser execution claim.' if r==40012 else 'Native header-splitting canary/reflection and response-boundary; typed rejection does not imply successful header injection.' if r==40003 else 'Authenticated typed input and response boundary; fixture conflicts do not satisfy this question.'} for r in rules]
  campaigns.append({'id':c['id']+'-'+vector,'caseId':c['id'],'vectors':[vector],'mutableKeys':keys,'ruleIds':rules,'maxForwarded':cap,'strength':'LOW','alertThreshold':'LOW' if 40012 in rules else 'MEDIUM','questions':questions})
 create={**f['foods'][1]['body'],'name':p['marker']+'-active-create','stockQuantity':0}
 c=case('admin-create','createFood','ADMIN','/api/foods',create,[201]);camp(c,'JSON-body',['name','description','imageUrl','categoryId','price','stockQuantity','status'],[40012,40018],360)
 c=case('admin-update','updateFood','ADMIN','/api/foods/'+str(f['foods'][1]['id']),f['foods'][1]['body']);camp(c,'JSON-body',['name','description','imageUrl','categoryId','price','stockQuantity','status'],[40012,40018],360);camp(c,'path',[],[40018,40003],130)
 c=case('admin-delete','deactivateFood','ADMIN','/api/foods/'+str(f['foods'][2]['id']),statuses=[204]);camp(c,'path',[],[40018,40003],130)
 c=case('customer-cart','getCurrentCart','CUSTOMER','/api/cart');camp(c,'header',[],[40003],60)
 c=case('customer-cart-add','addCartItem','CUSTOMER','/api/cart/items',{'foodId':f['foods'][0]['id'],'quantity':1});camp(c,'JSON-body',['quantity','foodId'],[40018],130)
 c=case('customer-cart-update','updateCartItem','CUSTOMER','/api/cart/items/'+str(f['cartItemId']),{'quantity':1});camp(c,'JSON-body',['quantity'],[40018],110);camp(c,'path',[],[40018,40003],130)
 c=case('customer-cart-remove','removeCartItem','CUSTOMER','/api/cart/items/'+str(f['cartItemId']));camp(c,'path',[],[40018,40003],130)
 # Mutable note reaches order persistence because the guard's explicit fixture
 # hook repopulates only this actor's cart with one owned item before checkout.
 for typ,body in [('dinein',{'orderType':'DINE_IN','tableNumber':'ZAP-test','paymentMethod':'CASH','note':'baseline'}),('delivery',{'orderType':'DELIVERY','recipientName':'ZAP Test','shippingPhone':'0900000099','shippingAddress':'ZAP local fixture','paymentMethod':'COD','note':'baseline'})]:
  c=case('customer-create-'+typ,'createOrder','CUSTOMER','/api/orders',body,[201]);camp(c,'JSON-body',list(body),[40012,40018],300)
 orders={o['purpose']:o['id'] for o in f['orders']}
 for role in ['CUSTOMER','EMPLOYEE']:
  c=case(role.lower()+'-orders','listOrders',role,'/api/orders?status=PENDING&orderType=DINE_IN&page=0&size=20');camp(c,'query',['status','orderType','page','size'],[40018,40003],200)
  c=case(role.lower()+'-detail','getOrder',role,'/api/orders/'+str(orders['read']));camp(c,'path',[],[40018,40003],130)
 c=case('customer-cancel','cancelOrder','CUSTOMER','/api/orders/'+str(orders['cancel']));camp(c,'path',[],[40018,40003],130)
 c=case('employee-confirm','confirmOrder','EMPLOYEE','/api/orders/'+str(orders['confirm'])+'/confirm');camp(c,'path',[],[40018,40003],130)
 c=case('employee-status','updateOrderStatus','EMPLOYEE','/api/orders/'+str(orders['status'])+'/status',{'status':'PROCESSING'});camp(c,'JSON-body',['status'],[40018],100)
 c=case('employee-status-selector','updateOrderStatus','EMPLOYEE','/api/orders/'+str(orders['status-selector'])+'/status',{'status':'PROCESSING'});camp(c,'path',[],[40018,40003],130)
 q['cases']=cases;q['campaigns']=campaigns;save('execution.json',q)
 fn=rt.config/'guard-plan-auth.json';fn.write_text(json.dumps(q));fn.chmod(0o444)
 cap=ROOT/'guard-execution';cap.mkdir(mode=0o777);cap.chmod(0o777)
 name=rt.names[1]+'-execution';j.append('intent',{'action':'guard-allocation-rollover','prior':rt.names[1],'new':name});docker(['stop','--time','5',rt.names[1]])
 rt.commands={name:['python','/guard.py','/config/guard-plan-auth.json','/config/mode.json','/evidence']}
 pin=json.loads((PKG/'profiles/runtime-baseline.json').read_bytes())['boundary']
 rt.create(name,pin,['--no-healthcheck','--network','container:'+rt.anchor,'--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256','--user','1003:1003','--memory','128m','-v',str(CODE_ROOT/'guard.py')+':/guard.py:ro','-v',str(PKG/'src/zap_assessment/anonymous_guard.py')+':/anonymous_guard.py:ro','-v',str(rt.config)+':/config:ro','-v',str(cap)+':/evidence'])
 save('runtime-state.json',{'capture':'guard-execution','extraGuard':name});j.append('ack',{'action':'guard-allocation-rollover','extraGuard':name})
 print(json.dumps({'cases':len(cases),'campaigns':len(campaigns),'roleOperations':len({(c['operationId'],c['role']) for c in cases})}),flush=True)

if __name__=='__main__':
 if sys.argv[1]=='fixtures':fixtures()
 if sys.argv[1]=='allocate':allocate()

def mode(rt,c,camp=None,native=None):
 v={'caseId':c['id'],'campaignId':camp['id'] if camp else None,'producer':'active' if camp else 'seed','nativeOperationId':native}
 fn=rt.config/'mode.pending';fn.write_text(json.dumps(v));fn.chmod(0o444);os.replace(fn,rt.config/'mode.json')
class Zap:
 def __init__(self,rt):self.rt=rt
 def call(self,c,k,n,**args):return self.rt.engine(c,k,n,args)

def seed(rt,c,session,index):
 from zap_assessment.research_product import seed_as_user
 res=seed_as_user(Zap(rt),rt.names[2],session,c,ROOT,index,origin=load('plan.json')['origin']);save('seeds/'+c['id']+'-result.json',res)
 msg=rt.engine('core','view','message',{'id':str(res['historyId'])})['message'];save('http/'+c['id']+'.json',msg)
 s=int(msg['responseHeader'].split()[1]);assert s in c['expected']['statuses'],'baseline status '+str(s)+' '+c['id']
 assert 'X-Zpa-Response-Origin: app' in msg['responseHeader'],'guard response not baseline'
 print(json.dumps({'case':c['id'],'role':c['role'],'method':c['method'],'path':c['path'],'baselineStatus':s}),flush=True);return msg

def campaign(cid):
 p,j,rt=resume();q=load('execution.json');camp=next(x for x in q['campaigns'] if x['id']==cid);c=next(x for x in q['cases'] if x['id']==camp['caseId']);session=load('sessions.json')[c['role']]
 assert not any(e['data'].get('campaignId')==cid and e['data'].get('action')=='active-start' for e in j.events),'start already attempted; reconcile'
 m=MCP(rt.request);m.initialize();text=mcall(m,'zap_auth_session_validate',{'sessionId':session['sessionId']},'before-'+cid);assert '\nValid: true\n' in '\n'+text+'\n'
 b,_=inspect_binding('byteme-backend-1','byteme',8080);assert b==p['targetBinding'],'binding drift'
 sample=rt.sample();save('resources/'+cid+'.json',sample);assert sample['hostFree']>=2*1024**3 and sample['ramAvailable']>=1024**3,'resource reserve'
 policy='auth-'+cid;v=camp['vectors'][0]
 rt.engine('ascan','action','setOptionTargetParamsInjectable',{'Integer':{'path':16,'query':1,'JSON-body':2,'header':8}[v]});rt.engine('ascan','action','setOptionTargetParamsEnabledRPC',{'Integer':4 if v=='JSON-body' else 0})
 rt.engine('ascan','action','addScanPolicy',{'scanPolicyName':policy,'attackStrength':camp['strength'],'alertThreshold':camp['alertThreshold']});rt.engine('ascan','action','disableAllScanners',{'scanPolicyName':policy});rt.engine('ascan','action','enableScanners',{'scanPolicyName':policy,'ids':','.join(map(str,camp['ruleIds']))})
 rules=rt.engine('ascan','view','scanners',{'scanPolicyName':policy})['scanners'];assert {int(x['id']) for x in rules if engine_bool(x['enabled'])}==set(camp['ruleIds']);save('policies/'+cid+'.json',rules)
 mode(rt,c,camp);msg=seed(rt,c,session,len(list((ROOT/'seeds').glob('*.json'))))
 binder=SimpleNamespace(rt=rt,out=ROOT,j=j,engine=lambda co,ki,na,args=None:rt.engine(co,ki,na,args or {}));AnonymousRun.bind_baseline(binder,msg,cid,expected_method=c['method'])
 args={'targetUrl':p['origin']+c['path'],'recurse':'false','policy':policy,'authSessionId':session['sessionId'],'method':c['method']}
 if c['body'] is not None:args['postData']=json.dumps(c['body'],separators=(',',':'))
 known={str(x['id']) for x in rt.engine('ascan','view','scans',{})['scans']};j.append('intent',{'action':'active-start','campaignId':cid,'knownNativeIds':sorted(known)})
 try:
  text=mcall(m,'zap_attack_start',args,'start-'+cid);native=field(text,'Scan ID');op=field(text,'Operation ID')
 except Exception:
  save('uncertain/'+cid+'.json',rt.engine('ascan','view','scans',{}));raise
 save('operations/'+cid+'.json',{'operationId':op,'nativeScanId':native,'campaignId':cid});j.append('ack',{'action':'active-start','campaignId':cid,'nativeScanId':native,'operationId':op});mode(rt,c,camp,native)
 begin=time.monotonic();lastcheck=begin;checks=[];reason=None
 while True:
  status=int(rt.engine('ascan','view','status',{'scanId':native})['status'])
  if status>=100:break
  accounting=json.loads((rt.capture/'accounting.json').read_bytes());count=accounting.get('campaigns',{}).get(cid,0)
  if count>=camp['maxForwarded']:reason='allocation-cap'
  if time.monotonic()-begin>210:reason='allocation-duration'
  if time.monotonic()-lastcheck>=12:
   txt=mcall(m,'zap_auth_session_validate',{'sessionId':session['sessionId']},'during-'+cid+'-'+str(len(checks)));valid='\nValid: true\n' in '\n'+txt+'\n';checks.append({'at':time.time(),'valid':valid});lastcheck=time.monotonic()
   if not valid:reason='authentication-loss'
   if rt.sample()['hostFree']<2*1024**3:reason='resource-reserve'
  if reason:
   mcall(m,'zap_attack_stop',{'operationId':op},'stop-'+cid);break
  time.sleep(2)
 terminal=mcall(m,'zap_attack_status',{'operationId':op},'terminal-'+cid)
 txt=mcall(m,'zap_auth_session_validate',{'sessionId':session['sessionId']},'after-'+cid);after='\nValid: true\n' in '\n'+txt+'\n'
 rows=[json.loads(x.read_bytes()) for x in rt.capture.glob('[0-9]*.json')];rows=[x for x in rows if x.get('campaignId')==cid]
 from collections import Counter
 changed=[]
 for x in rows:
  if x.get('producer')!='active':continue
  if x['url']!=p['origin']+c['path'] or (json.loads(x['body']) if x['body'] else None)!=c['body'] or any(k.lower() in ('user-agent','referer') and val not in ('','Mozilla/5.0') for k,val in x['headers'].items()):changed.append(x)
 result={'campaignId':cid,'operationId':c['operationId'],'role':c['role'],'method':c['method'],'path':c['path'],'vector':v,'nativeScanId':native,'guidedOperationId':op,'guidedTerminal':terminal,'nativeProgress':rt.engine('ascan','view','scanProgress',{'scanId':native}),'status':rt.engine('ascan','view','status',{'scanId':native}),'stopReason':reason,'seconds':time.monotonic()-begin,'forwarded':len(rows),'changedInputRequests':len(changed),'byRule':dict(Counter(str(x.get('ruleId')) for x in rows)),'statuses':dict(Counter(str(x['status']) for x in rows)),'sessionChecksDuring':checks,'sessionValidAfter':after}
 save('campaigns/'+cid+'.json',result);j.append('terminal',{'action':'active-terminal','campaignId':cid,'nativeScanId':native,'stopReason':reason,'forwarded':len(rows),'sessionValidAfter':after})
 print(json.dumps({k:result[k] for k in ['campaignId','status','stopReason','forwarded','changedInputRequests','statuses','sessionValidAfter']}),flush=True)
 if reason or not after:raise RuntimeError('allocation needs reconciliation '+str(reason))

def run_all():
 for camp in load('execution.json')['campaigns']:
  if (ROOT/'campaigns'/ (camp['id']+'.json')).exists():
   previous=load('campaigns/'+camp['id']+'.json')
   if previous['status']['status']!='100' or previous.get('stopReason') or not previous.get('sessionValidAfter'):
    raise RuntimeError('existing allocation requires readback/new continuation; never replay or silently skip '+camp['id'])
   continue
  campaign(camp['id'])
if __name__=='__main__':
 if sys.argv[1]=='campaign':campaign(sys.argv[2])
 if sys.argv[1]=='all':run_all()

def collect():
 p,j,rt=resume();q=load('execution.json');assert len(list((ROOT/'campaigns').glob('*.json')))==len(q['campaigns']),'unfinished campaigns'
 assert all(s['state'] in ('FINISHED','STOPPED') for s in rt.engine('ascan','view','scans',{})['scans'])
 m=MCP(rt.request);m.initialize();wait=mcall(m,'zap_passive_scan_wait',{'timeoutSeconds':30,'pollIntervalMs':1000},'passive-wait');save('passive-readback.json',{'text':wait})
 text=mcall(m,'zap_report_generate',{'format':'json'},'report-generate');save('report-generation.json',{'text':text});path=field(text,'Path')
 from zap_assessment.evidence import read_report
 def page(path,offset,sha):
  args={'reportPath':path,'offset':offset,'maxChars':100000}
  if sha:args['expectedSha256']=sha
  return json.loads(mcall(m,'zap_report_read_chunk',args,'report-chunk-'+str(offset)))
 report=read_report(page,path,12*1024*1024);save('native-report.json',json.loads(report))
 summary=mcall(m,'zap_findings_summary',{'baseUrl':p['origin']+'/api/orders'},'findings-summary');save('findings-summary.json',{'text':summary})
 total=int(rt.engine('core','view','numberOfAlerts',{'baseurl':p['origin']})['numberOfAlerts'])
 alerts=collect_alerts(lambda start,size:rt.engine('core','view','alerts',{'baseurl':p['origin'],'start':start,'count':size})['alerts'],total)
 assert total==int(rt.engine('core','view','numberOfAlerts',{'baseurl':p['origin']})['numberOfAlerts'])
 save('native-alerts.json',alerts)
 # Captured application rows already contain every delivered input/result.
 # Read the specific native messages needed to attribute actual alerts, rather
 # than duplicating all request bodies a second time in a report-only reader.
 history=[rt.engine('core','view','message',{'id':mid})['message'] for mid in dict.fromkeys(str(a['messageId']) for a in alerts)]
 save('native-history.json',history)
 save('terminal-readback.json',rt.engine('ascan','view','scans',{}));save('resources-after.json',rt.sample());save('collection-status.json',{'completed':True,'at':time.time(),'nativeAlertRecords':len(alerts),'nativeMessages':len(history),'historyReadScope':'distinct messages associated with current alert records; all delivered input/results remain in guard captures'})
 print(json.dumps({'collection':'complete','alerts':len(alerts),'messages':len(history),'passive':wait}),flush=True)

def state_cleanup():
 p,j,rt=resume();q=load('execution.json');f=load('fixtures.json')
 assert (ROOT/'collection-status.json').exists(),'collect before cleanup'
 assert not (ROOT/'target-cleanup.json').exists(),'cleanup already attempted; reconcile'
 rows=[json.loads(x.read_bytes()) for dr in ('guard-execution','guard-status-path') for x in (ROOT/dr).glob('[0-9]*.json')]
 foods={x['id'] for x in f['foods']};orders={x['id'] for x in f['orders']}
 for r in rows:
  if r['method']=='POST' and r['status']==201:
   v=json.loads(r['responseBody']);path=urlsplit(r['url']).path
   if path=='/api/foods':foods.add(v['id'])
   if path=='/api/orders':orders.add(v['id'])
 # Reconcile every acknowledged successful native create; do not replay creates.
 result={'startedAt':time.time(),'foodsCreated':sorted(foods),'ordersCreated':sorted(orders),'orderStatesBefore':{},'ordersAfter':{},'foodsAfter':{},'errors':[]}
 save('target-cleanup.json',result)
 for oid in sorted(orders):
  s,v=direct('GET','/api/orders/'+str(oid),role='CUSTOMER',label='owned-order-poststate');assert s==200
  result['orderStatesBefore'][str(oid)]=v['status'];save('target-cleanup.json',result)
  if v['status'] not in ('CANCELLED','COMPLETED'):
   if v['status']=='PENDING':s,v=direct('DELETE','/api/orders/'+str(oid),role='CUSTOMER',label='cancel-owned-pending-order')
   else:s,v=direct('PUT','/api/orders/'+str(oid)+'/status',{'status':'CANCELLED'},'EMPLOYEE','cancel-owned-progressed-order')
   assert s==200 and v['status']=='CANCELLED'
  s,v=direct('GET','/api/orders/'+str(oid),role='EMPLOYEE',label='owned-order-cleanup-readback');assert s==200
  result['ordersAfter'][str(oid)]={'status':v['status'],'itemCount':len(v['items'])};save('target-cleanup.json',result)
 s,cart=direct('GET','/api/cart',role='CUSTOMER',label='owned-cart-poststate');assert s==200
 for item in cart['items']:
  assert item['food']['id'] in foods
  s,v=direct('DELETE','/api/cart/items/'+str(item['id']),role='CUSTOMER',label='remove-owned-cart-leftover');assert s==200
 s,cart=direct('GET','/api/cart',role='CUSTOMER',label='owned-cart-cleanup-readback');assert s==200 and not cart['items'];result['cartEmpty']=True
 # Stock of the dedicated checkout fixture returns exactly to its starting value.
 checkout=f['foods'][0];s,v=direct('GET','/api/foods/'+str(checkout['id']),label='dedicated-stock-after-cancellation');assert s==200
 result['checkoutStockBefore']=checkout['initial']['stockQuantity'];result['checkoutStockAfter']=v['stockQuantity'];assert v['stockQuantity']==checkout['initial']['stockQuantity']
 for fid in sorted(foods):
  s,v=direct('DELETE','/api/foods/'+str(fid),role='ADMIN',label='deactivate-owned-test-food');assert s==204
  s,v=direct('GET','/api/foods/'+str(fid),label='food-deactivation-readback');assert s==404
  result['foodsAfter'][str(fid)]='deactivated; public detail 404';save('target-cleanup.json',result)
 result['completedAt']=time.time();result['status']='complete';result['retained']='Order records retained CANCELLED; food records retained INACTIVE. No hard-delete/account deletion API exists. Reused prior CUSTOMER; no new accounts created.';save('target-cleanup.json',result)
 print(json.dumps({'targetCleanup':'complete','foodsDeactivated':len(foods),'ordersRetained':len(orders),'cartEmpty':True,'stockRestored':True}),flush=True)

def cleanup():
 p,j,rt=resume();assert load('target-cleanup.json')['status']=='complete'
 rt.cleanup();ROOT.chmod(0o700);save('cleanup.json',{'status':'complete','ownedContainersRemoved':rt.owned_names(),'at':time.time()});print('Owned scanner removed; target remains running.',flush=True)
if __name__=='__main__':
 if sys.argv[1]=='collect':collect()
 if sys.argv[1]=='state-cleanup':state_cleanup()
 if sys.argv[1]=='cleanup':cleanup()
