"""ByteMe-only authenticated boundary, using the existing exact request guard."""
import sys,json,time,base64,re,os,hashlib,threading
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0,'/')
import anonymous_guard as a
original=a.authorize
original_conn=a.http.client.HTTPConnection
OUT=Path(sys.argv[3]);PLAN=json.loads(Path(sys.argv[1]).read_bytes())
def claims(headers):
 token=headers.get('Authorization',headers.get('authorization',''))
 if not token.startswith('Bearer '):raise ValueError('native-bearer-missing')
 try:
  p=token[7:].split('.')[1];c=json.loads(base64.urlsafe_b64decode(p+'='*((-len(p))%4)))
 except Exception:raise ValueError('native-bearer-shape') from None
 actor=next((x for x in PLAN['actors'].values() if x['subject']==c.get('sub') and x['role']==c.get('role')),None)
 if not actor or c.get('exp',0)<=time.time() or c.get('iss')!='sa-local-dev':raise ValueError('actor-scope')
 # Backend verifies the signature. Native prepared profiles additionally verify
 # the customer subject or signed subject/role + protected response.
 return actor

def authorize(p,mode,method,url,headers,body,now):
 u=urlsplit(url);base=urlsplit(p['origin']);h={k.lower():v for k,v in headers.items()}
 if now>=p['notAfter'] or u.scheme!=base.scheme or u.netloc!=base.netloc or h.get('host')!=base.netloc or u.fragment or u.username:raise ValueError('origin-deadline')
 if method=='POST' and u.path=='/api/auth/token' and not u.query:
  v=json.loads(body);actor=next((x for x in p['actors'].values() if v=={'email':x['email'],'password':x['password']}),None)
  if not actor or 'authorization' in h or 'cookie' in h:raise ValueError('exact-auth-login')
  cid='auth-login-'+actor['role'];return {'id':cid,'method':method,'path':u.path,'category':'setup','expected':{'statuses':[200]}},{'id':cid,'maxForwarded':100}
 actor=claims(headers)
 c=next((c for c in p['cases'] if c['id']==mode.get('caseId')),None)
 # Verification is a separate, fixed read path, even while another operation runs.
 probe=('/api/cart' if actor['role']=='CUSTOMER' else '/api/orders')
 if method=='GET' and u.path==probe and not u.query and (not c or c['role']!=actor['role'] or c['method']!='GET' or c['path']!=u.path):
  cid='auth-probe-'+actor['role'];return {'id':cid,'method':method,'path':u.path,'category':'probe','expected':{'statuses':[200,403]}},{'id':cid,'maxForwarded':500}
 if not c or c['role']!=actor['role']:raise ValueError('case-actor')
 clean={k:v for k,v in headers.items() if k.lower()!='authorization'}
 camp=next((x for x in p['campaigns'] if x['id']==mode.get('campaignId') and x['caseId']==c['id']),None)
 md=dict(mode)
 if camp and camp['vectors']==['header']:md.pop('campaignId',None)
 if camp and camp['vectors']==['path'] and body:
  if json.loads(body)!=c['body']:raise ValueError('frozen-path-body')
  cc,returned=original(p,md,method,url,clean,b'',now)
 else:cc,returned=original(p,md,method,url,clean,body,now)
 if camp and camp['vectors']==['header']:returned=camp
 if body:
  v=json.loads(body)
  for key in ('foodId','categoryId'):
   if key in v and key in (c.get('body') or {}) and str(v[key]).strip()!=str(c['body'][key]) and re.fullmatch(r'[+-]?\d+',str(v[key]).strip()):raise ValueError('foreign-reference')
  if 'name' in v and v['name'] is not None and p['marker'] not in str(v['name']):raise ValueError('fixture-name-scope')
 return cc,returned

def fixture_call(method,path,headers,body=None,purpose='direct fixture maintenance before native checkout request'):
 c=original_conn(PLAN['targetBinding']['address'],urlsplit(PLAN['origin']).port,timeout=12)
 try:
  b=None if body is None else json.dumps(body).encode();h={k:v for k,v in headers.items() if k.lower() in ('authorization','host')};h['Accept']='application/json'
  if b:h['Content-Type']='application/json'
  c.request(method,path,body=b,headers=h);r=c.getresponse();raw=r.read(1048576);v=json.loads(raw) if raw else None
  row={'at':time.time(),'method':method,'path':path,'status':r.status,'body':body,'response':v,'technique':purpose}
  with (OUT/'fixture-maintenance.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
  if r.status not in (200,201):raise ValueError('fixture-maintenance-failed')
  return v
 finally:c.close()
class ReadbackResponse:
 def __init__(self,response,request):self.response=response;self.request=request;self.recorded=False
 def __getattr__(self,name):return getattr(self.response,name)
 def read(self,*args):
  raw=self.response.read(*args)
  if self.recorded:return raw
  self.recorded=True;req=self.request;path=urlsplit(req['url']).path
  if self.response.status not in (200,201) or not (req['method']=='PUT' and path.startswith('/api/foods/') or req['method']=='POST' and path in ('/api/foods','/api/orders')):return raw
  result={'sequence':req['sequence'],'at':time.time(),'method':req['method'],'path':path,'technique':'immediate independent API read before next native mutation','matched':False}
  try:
   ack=json.loads(raw);read_path=('/api/orders/' if path=='/api/orders' else '/api/foods/')+str(ack['id'])
   value=fixture_call('GET',read_path,req['headers'],purpose='independent variant persistence readback before next mutation')
   fields=json.loads(req['body']);result.update(objectId=ack['id'],readPath=read_path,apiReadStatus=200,ack=ack,readback=value,matched=all(value.get(k)==ack.get(k) for k in fields))
  except Exception as exc:result['readbackErrorType']=type(exc).__name__
  with (OUT/'variant-readback.jsonl').open('a') as f:f.write(json.dumps(result)+'\n')
  return raw
class Connection(original_conn):
 def request(self,method,url,body=None,headers={},**kw):
  seq=max(int(x.name.split('.')[0]) for x in OUT.glob('[0-9]*.json.intent'))
  self.current_request={'sequence':seq,'method':method,'url':url,'body':body.decode() if isinstance(body,bytes) else body,'headers':dict(headers)}
  if method=='POST' and urlsplit(url).path=='/api/foods':
   native=json.loads(body);value=dict(native)
   value['name']=str(native['name'])+'-'+str(seq)
   body=json.dumps(value).encode()
   headers=dict(headers);headers['Content-Length']=str(len(body))
   with (OUT/'fresh-create-map.jsonl').open('a') as f:f.write(json.dumps({'sequence':seq,'nativeBody':native,'actualBody':value,'technique':'ByteMe-only fresh name fixture; target payload preserved'})+'\n')
  if method=='POST' and urlsplit(url).path=='/api/orders':
   actor=claims(headers)
   if actor['role']!='CUSTOMER':raise ValueError('checkout-actor')
   fid=PLAN.get('checkoutFoodId')
   if not fid:raise ValueError('checkout-fixture-unavailable')
   cart=fixture_call('GET','/api/cart',headers)
   if cart['items']:
    assert len(cart['items'])==1 and cart['items'][0]['food']['id']==fid
    if cart['items'][0]['quantity']!=1:fixture_call('PUT','/api/cart/items/'+str(cart['items'][0]['id']),headers,{'quantity':1})
   else:fixture_call('POST','/api/cart/items',headers,{'foodId':fid,'quantity':1})
  return super().request(method,url,body=body,headers=headers,**kw)
 def getresponse(self):return ReadbackResponse(super().getresponse(),self.current_request)
a.authorize=authorize;a.http.client.HTTPConnection=Connection
a.serve(*sys.argv[1:4]).serve_forever()
