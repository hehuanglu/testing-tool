import argparse
import json
from pathlib import Path
from .contracts import ROOT,Blocked,validate,make_plan,AuthorityRegistry,check_authority
from .evidence import verify_bundle
from .executor import InjectedCrash
from .pilot import fixture_inputs,live_executor,pilot

def product_plan(path,authority_path=None):
    source=Path(path).resolve();product=json.loads(source.read_bytes());validate('product',product)
    records={}
    if authority_path:
        record=json.loads(Path(authority_path).read_bytes());validate('authorization',record);records[record['recordId']]=record
    registry=AuthorityRegistry(records);authority=registry.get(product['authorizationRef'])
    workflow=json.loads((ROOT/'profiles/v1-exploratory.json').read_bytes());check_authority(authority,product,workflow)
    if product['schemaVersion']=='1.1':
        from .binding import validate_binding
        validate_binding(product,workflow,authority)
    # Profiles cannot redirect local schema reads to credential files or remote URLs.
    name=product['schema']['path']
    if Path(name).name!=name or not name.endswith('.json') or (source.parent/name).is_symlink():raise Blocked('schema must be adjacent plain JSON file')
    schema=source.parent/name
    if schema.stat().st_size>1048576:raise Blocked('schema exceeds limit')
    return make_plan(product,workflow,registry,schema.read_bytes())

def main():
    parser=argparse.ArgumentParser(description='Assessment workflow and read-only versioned evidence verification; product pilot requires authority')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('plan'); p.add_argument('--product',default=None);p.add_argument('--authority')
    p=sub.add_parser('pilot');p.add_argument('--product-id',default='alternate-synthetic');p.add_argument('--product');p.add_argument('--authority');p.add_argument('--expect-plan-hash');p.add_argument('--safety-contract');p.add_argument('--expect-safety-hash')
    sub.add_parser('interrupt')
    p=sub.add_parser('recover'); p.add_argument('run')
    p=sub.add_parser('verify'); p.add_argument('bundle');p.add_argument('--expect-plan-hash')
    p=sub.add_parser('validate'); p.add_argument('kind',choices=['product','workflow','authorization']); p.add_argument('file')
    args=parser.parse_args(); root=ROOT/'runs';execution_entered=False
    try:
        safety_contract=None
        if getattr(args,'safety_contract',None) or getattr(args,'expect_safety_hash',None):
            if not args.safety_contract or not args.expect_safety_hash:raise Blocked('runtime safety contract and external pin are both required')
            from .capabilities import _json
            safety_contract=_json(Path(args.safety_contract).read_bytes())
        if getattr(args,'authority',None) and not getattr(args,'product',None):raise Blocked('--authority requires --product')
        if args.command=='plan':
            plan=product_plan(args.product,args.authority) if args.product else make_plan(*fixture_inputs()); result={'planHash':plan.hash,'plan':plan.data}; code=0
        elif args.command=='validate': validate(args.kind,json.loads(Path(args.file).read_text())); result={'structurallyValid':True,'executable':False}; code=0
        elif args.command=='verify': result=verify_bundle(args.bundle,args.expect_plan_hash); code=0
        elif args.command=='recover':
            execution_entered=True;result=live_executor(root).recover(args.run);code=result['exitCode']
        elif args.command=='pilot' and args.product:
            plan=product_plan(args.product,args.authority)
            if args.expect_plan_hash and args.expect_plan_hash!=plan.hash:raise Blocked('reviewed plan hash mismatch')
            execution_entered=True;result=live_executor(root,safety_contract,args.expect_safety_hash).run(plan);code=result['exitCode']
        else:
            execution_entered=True;result=pilot(root,getattr(args,'product_id','alternate-synthetic'),args.command=='interrupt'); code=result['exitCode']
        print(json.dumps(result,indent=2)); return code
    except InjectedCrash as crash:
        print(json.dumps({'runId':str(crash),'executionStatus':'running','evidenceStatus':'incomplete','securityVerdict':'inconclusive','cleanupStatus':'pending','gateDecision':'block','next':'recover '+str(root/str(crash))})); return 2
    except (Blocked,ValueError,OSError) as e:
        detail=str(e) if isinstance(e,Blocked) else type(e).__name__
        from .evidence import secret_check
        try:secret_check(detail.encode())
        except Blocked:detail='diagnostic withheld by secret policy'
        print(json.dumps({'executionStatus':'not_started','evidenceStatus':'incomplete','securityVerdict':'inconclusive','cleanupStatus':'clean' if not execution_entered else 'incomplete','gateDecision':'block','reason':type(e).__name__,'detail':detail[:300]})); return 2
if __name__=='__main__': raise SystemExit(main())
