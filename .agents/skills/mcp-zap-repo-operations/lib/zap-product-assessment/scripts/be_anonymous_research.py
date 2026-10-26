#!/usr/bin/env python3
"""Anonymous research entry. Direct/native POST campaigns, MCP reports; strict auth unchanged."""
import argparse,json,sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from zap_assessment.anonymous_product import discover,setup,plan,oracle,save,binding,observe_transport
from zap_assessment.anonymous_runner import AnonymousRun,verify
from zap_assessment.anonymous_runtime import inspect_binding
from zap_assessment.discovery import canonical_hash


def inspection(p):
 from urllib.parse import urlsplit
 b,proof=inspect_binding(p['targetBinding']['containerId'],p['environment'],urlsplit(p['origin']).port or 80)
 if any(x['role']=='direct' and x['authorized'] for x in p['discovery']['product']['origins']):
  if p['environment']!='finalsource-zap-test':raise ValueError('direct inspector unavailable for adapter')
  proof['directOrigins']=observe_transport()['directOrigins']
 return b,proof


def cleanup_product(doc,product,actor,f):
 if binding()!=doc['product']['binding']:raise ValueError('cleanup binding drift')
 accounts=product.request('GET','/api/v1/accounts',token=actor['token'],expected=[200],label='cleanup-owner-list')['data']
 if accounts['user_id']!=actor['userId'] or not any(a['id']==f['accountId'] for a in accounts['accounts']):raise ValueError('cleanup ownership absent')
 result=product.request('DELETE','/api/v1/accounts/'+str(f['accountId']),token=actor['token'],expected=[200],label='cleanup-account-delete')
 after=product.request('GET','/api/v1/accounts',token=actor['token'],expected=[200],label='cleanup-account-list')['data']
 if any(a['id']==f['accountId'] for a in after['accounts']):raise ValueError('cleanup absence failed')
 return {'accountDeleted':f['accountId'],'apiResult':result,'accountAbsenceVerified':True,'retained':{'userId':actor['userId'],'goalId':f['goalId'],'reason':'No supported user/goal DELETE API; no DB deletion.'}}


def product_run(args):
 doc=json.loads(args.discovery.read_bytes());out=args.output.resolve();out.mkdir(mode=0o700,parents=True,exist_ok=False);run_id='anon-'+uuid.uuid4().hex[:14];save(out,'PRODUCT_DISCOVERY.json',doc)
 actor=f=product=None;result={'executionStatus':'not-started','evidenceStatus':'incomplete','securityVerdict':'inconclusive','cleanupStatus':'pending','gateDecision':'block'}
 try:
  actor,f,product=setup(doc,out,run_id);p=plan(doc,out,run_id,actor,f);result=AnonymousRun(p,out/'native',lambda:inspection(p)).execute(args.interrupt_after)
  after=oracle(product,actor,f);save(out,'poststate-after.json',after);before=json.loads((out/'poststate-before.json').read_bytes())
  save(out,'POST_STATE_VERIFICATION.json',{'same':before==after,'beforeSha256':canonical_hash(before),'afterSha256':canonical_hash(after),'scope':'owned account/goals/transaction list only; not global DB nonmutation proof','transactionSeedLimit':'No category creation API; denial transaction body omits category_id, auth must reject before DTO validation'})
  if before!=after:result={**result,'postState':'mismatch','gateDecision':'block'}
  reg=out/'native/http/register-minimum.json'
  if reg.exists():
   try:v=json.loads(json.loads(reg.read_bytes())['responseBody']);save(out,'RETENTION_PUBLIC.json',{'userId':v['data']['user']['id'],'reason':'Public registration fixture, no delete API','tokenPropagation':False})
   except (ValueError,KeyError):pass
 except Exception as exc:
  result.update(executionStatus='failed',errorType=type(exc).__name__,detail=str(exc)[:220]);print('Wrapper stopped:',type(exc).__name__,str(exc)[:150],flush=True)
 finally:
  cleanup={'scannerStatus':result['cleanupStatus'],'dataStatus':'pending','mutationsRetried':False}
  if actor and f and product:
   try:cleanup.update(dataStatus='completed-with-retention',**cleanup_product(doc,product,actor,f))
   except Exception as exc:cleanup.update(dataStatus='incomplete',errorType=type(exc).__name__);result['gateDecision']='block'
  else:
   # A setup exception can occur after acknowledged fixture creation but before tuple return.
   if (out/'fixtures.json').exists() and (out/'private/actor.json').exists():
    from zap_assessment.anonymous_product import Product
    try:
     f=json.loads((out/'fixtures.json').read_bytes());actor=json.loads((out/'private/actor.json').read_bytes());product=Product(out,doc);product.count=len(list((out/'direct').glob('*-intent.json')))
     cleanup.update(dataStatus='completed-with-retention',**cleanup_product(doc,product,actor,f))
    except Exception as exc:cleanup.update(dataStatus='incomplete',errorType=type(exc).__name__)
   else:cleanup.update(dataStatus='unknown-setup-partial',nextAction='Reconcile direct intents/responses; no POST retry. Only exact run-owned IDs.')
  save(out,'CLEANUP_RETENTION.json',cleanup);save(out,'RESULT.json',result)
 print(json.dumps({'output':str(out),'runId':run_id,**result},ensure_ascii=False),flush=True)
 return 0 if result['executionStatus']=='completed' and result['cleanupStatus']=='clean' and result['gateDecision']=='review_required' and cleanup['dataStatus']=='completed-with-retention' else 2


def recover(root):
 from zap_assessment.journal import Journal
 from zap_assessment.runtime import DockerRuntime
 root=root.resolve();p=json.loads((root/'PLAN.json').read_bytes());j=Journal(root/'journal.jsonl',p['runId'],canonical_hash(p),allow_partial_tail=True)
 # Separate recovery journal preserves any sealed original bundle.
 recovery=root.parent/('recovery-'+uuid.uuid4().hex[:8]);recovery.mkdir(mode=0o700)
 import shutil
 shutil.copy2(root/'journal.jsonl',recovery/'journal.jsonl');j=Journal(recovery/'journal.jsonl',p['runId'],canonical_hash(p),allow_partial_tail=True)
 (root/'config/STOP').touch(exist_ok=True);rt=DockerRuntime(p['runId'],root,j);rt.stop_timeout=60;rt.cleanup()
 save(recovery,'RESULT.json',{'cleanupStatus':'clean','targetRequests':0,'pendingStartRetry':False,'oldManifestStillHistorical':True});return {'cleanupStatus':'clean','recovery':str(recovery)}


def main():
 parser=argparse.ArgumentParser(description=__doc__);subs=parser.add_subparsers(dest='command',required=True)
 p=subs.add_parser('discover');p.add_argument('--output',type=Path,required=True)
 p=subs.add_parser('product-run');p.add_argument('--discovery',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--interrupt-after',type=float)
 p=subs.add_parser('run');p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--interrupt-after',type=float)
 for name in ('verify','recover'):
  p=subs.add_parser(name);p.add_argument('path',type=Path)
 p=subs.add_parser('controls');p.add_argument('--output',type=Path,required=True)
 p=subs.add_parser('handoff');p.add_argument('--root',type=Path,required=True)
 a=parser.parse_args()
 if a.command=='discover':print(json.dumps({'operations':len(discover(a.output)['operations']),'execution':'discovery-only'}));return 0
 if a.command=='product-run':return product_run(a)
 if a.command=='run':
  p=json.loads(a.plan.read_bytes())
  if p['environment']!='finalsource-zap-test':raise ValueError('session authority limited to finalsource-zap-test')
  result=AnonymousRun(p,a.output,lambda:inspection(p)).execute(a.interrupt_after);print(json.dumps(result));return 0 if result['executionStatus']=='completed' else 2
 if a.command=='verify':print(json.dumps(verify(a.path)));return 0
 if a.command=='recover':print(json.dumps(recover(a.path)));return 0
 if a.command=='controls':
  from zap_assessment.anonymous_controls import controls
  print(json.dumps(controls(a.output)));return 0
 if a.command=='handoff':
  from zap_assessment.anonymous_handoff import handoff
  print(json.dumps(handoff(a.root),ensure_ascii=False));return 0

if __name__=='__main__':raise SystemExit(main())
