"""Fresh local SQLite/XSS controls through the same native scanner and guard."""
import datetime as dt
import hashlib,json
from pathlib import Path
import uuid
from .anonymous import compile_plan
from .anonymous_product import save
from .anonymous_runner import AnonymousRun,verify
from .journal import Journal
from .runtime import DockerRuntime,docker


def controls(output,*,path_only=False):
 out=Path(output).resolve();out.mkdir(mode=0o700,parents=True,exist_ok=False);rid='ancontrol-'+uuid.uuid4().hex[:12]
 baseline=json.loads((Path(__file__).resolve().parents[2]/'profiles/runtime-baseline.json').read_bytes())
 j=Journal(out/'bootstrap-journal.jsonl',rid,'0'*64);rt=DockerRuntime(rid,out,j);fixture=Path(__file__).with_name('anonymous_control_fixture.py')
 rt.commands={rt.anchor:['python','/control.py']}
 try:
  selector=str(int(uuid.uuid4().hex[:6],16)+1)
  rt.create(rt.anchor,baseline['boundary'],['--network','none','--cap-add','NET_ADMIN','--memory','64m','-e','ZPA_CONTROL_OBJECT_ID='+selector,'-v',str(fixture)+':/control.py:ro'])
  info=rt.check_owner(rt.anchor);none=next(iter(info['NetworkSettings']['Networks'].values()))
  b={'containerId':info['Id'],'imageId':info['Image'],'startedAt':info['State']['StartedAt'],'networkId':none['NetworkID'],'address':'127.0.0.1'}
  proof={'environment':'owned-anonymous-control','targetBinding':b,'scannerOrigins':['http://127.0.0.1:18080'],'directOrigins':[]}
  src={'id':'fixture','kind':'source','location':str(fixture),'sha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),'observedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'confidence':'high'}
  ops=[{'id':v,'method':'POST','pathTemplate':'/control/'+v,'protected':False,'semantics':'Owned '+v+' SQLite query and HTML reflection control, not product','input':{'query':[]},'evidenceRefs':['fixture'],'confidence':'high'} for v in ('vulnerable','fixed')]
  if path_only:ops=[{**ops[0],'id':'path','method':'GET','pathTemplate':'/control/path/{id}','semantics':'Owned numeric selector parser and scope control; no product data'}]
  doc={'schemaVersion':'product-discovery/1.1','product':{'location':str(fixture),'environment':'owned-anonymous-control','binding':b,'environmentEvidenceRefs':['fixture'],'origins':[{'url':proof['scannerOrigins'][0],'role':'scanner','accessFrom':'scanner-network','authorized':True,'bindingVerified':True,'evidenceRefs':['fixture'],'confidence':'high'}]},'sources':[src],'operations':ops,'auth':None,'fixtures':[],'tracks':{t:{'status':'candidate' if t=='be-anonymous' else 'not-applicable','reason':'Run-owned technique controls only','evidenceRefs':['fixture']} for t in ('fe-anonymous','be-anonymous','fe-authenticated','be-authenticated','bola-ownership')},'ui':[],'conflicts':[],'gaps':[]}
  cases=[{'id':v,'operationId':v,'method':'POST','path':'/control/'+v,'body':{'input':'marker'},'category':'public-success','fixtureRefs':['owned-control'],'expected':{'statuses':[200],'contentType':'text/html','equals':{},'present':['/rows']}} for v in ('vulnerable','fixed')]
  campaigns=[{'id':v,'caseId':v,'ruleIds':[40012,40018],'vectors':['JSON-body'],'mutableKeys':['input'],'maxForwarded':120,'strength':'LOW','baselineSeed':True} for v in ('vulnerable','fixed')]
  if path_only:
   cases=[{'id':'path','operationId':'path','method':'GET','path':'/control/path/'+selector,'body':None,'category':'public-success','fixtureRefs':[],'expected':{'statuses':[200],'contentType':'application/json','equals':{'/id':int(selector)},'present':['/name']}}]
   campaigns=[{'id':'path','caseId':'path','ruleIds':[40018],'vectors':['path'],'mutableKeys':['id'],'maxForwarded':40,'strength':'LOW','baselineSeed':True}]
  a={'environment':'owned-anonymous-control','source':'Human user instruction: fresh vulnerable/fixed control fixtures for anonymous research','discoveryRead':True,'active':True,'publicMutation':True,'deniedMutation':False,'fixtureSetup':True}
  p=compile_plan(doc,live_binding=b,observed_transport=proof,run_id=rid,cases=cases,campaigns=campaigns,authority=a,fixtures=[{'id':'owned-control','runId':rid,'ownership':'Exact created container ID + zpa.run label and image pin','preparationEvidence':['bootstrap-journal.jsonl'],'cleanup':'Remove owned namespace containers; SQLite DB only per-request in-memory'}],target_ownership='run-owned',dispositions=[{'operationId':o['id'],'disposition':'public-exercise','reason':'scoped numeric path native control' if path_only else 'vulnerable/fixed technique control'} for o in ops])
  def inspect():
   i=rt.check_owner(rt.anchor)
   if not i['State']['Running'] or i['State']['StartedAt']!=b['startedAt']:raise ValueError('fixture binding drift')
   return b,proof
  runner=AnonymousRun(p,out/'native',inspect);runner.rt.precreated_anchor=True
  for e in j.events:
   if e['kind'] in ('intent','ack'):runner.j.append(e['kind'],e['data'])
  result=runner.execute();alerts=json.loads((out/'native/alerts-native.json').read_bytes())['alerts'] if (out/'native/alerts-native.json').exists() else []
  counts={v:{str(rule):sum(str(a['pluginId'])==str(rule) and '/control/'+v in a.get('url','') for a in alerts) for rule in [40012,40018]} for v in ('vulnerable','fixed')}
  qualified=all(counts['vulnerable'].values()) and not any(counts['fixed'].values()) and result['evidenceStatus']=='complete' and result['cleanupStatus']=='clean'
  if path_only:
   from .anonymous_guard import path_scope,scoped_path
   from urllib.parse import urlsplit
   rows=[json.loads(path.read_bytes()) for path in (out/'native/guard').glob('[0-9]*.json')]
   scope=path_scope(ops[0]['pathTemplate'],cases[0]['path'])
   changed=[row for row in rows if row.get('ruleId')=='40018' and urlsplit(row['url']).path!=cases[0]['path']]
   qualified=bool(changed) and all(scoped_path(scope,urlsplit(row['url']).path) for row in rows) and result['executionStatus']=='completed' and result['cleanupStatus']=='clean'
   counts={'changedPathMessages':len(changed),'forwardedMessages':len(rows),'noForeignNumericSelector':all(scoped_path(scope,urlsplit(row['url']).path) for row in rows)}
  record={'functionalQualification':qualified,'ruleAlertCounts':counts,'run':result,'productFixedBuildRegression':False,'sourceSha256':src['sha256'],'evidenceVerification':verify(out/'native')}
  save(out,'CONTROL_RESULT.json',record);return record
 finally:
  # Idempotent ownership cleanup also covers bootstrap/setup exceptions.
  rt.cleanup()
