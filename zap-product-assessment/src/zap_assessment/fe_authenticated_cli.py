"""Explicit FE authenticated research entry. Read-only commands stay offline."""
import argparse,json,uuid
from pathlib import Path
from .fe_authenticated_contract import load,save,canonical,compile_plan

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    d=s.add_parser('discover');d.add_argument('--product',type=Path,required=True);d.add_argument('--recipe',required=True);d.add_argument('--observations',type=Path);d.add_argument('--inventory',type=Path);d.add_argument('--output',type=Path,required=True)
    a=s.add_parser('status');a.add_argument('--discovery',type=Path,required=True)
    a=s.add_parser('plan')
    for flag in ('discovery','journeys','selection','authority','output'):a.add_argument('--'+flag,type=Path,required=True)
    a.add_argument('--run-id',default=None)
    a=s.add_parser('run')
    for flag in ('plan','selection','actors','output'):a.add_argument('--'+flag,type=Path,required=True)
    a.add_argument('--interrupt-after',type=int)
    a=s.add_parser('verify');a.add_argument('--run',type=Path,required=True);a.add_argument('--expected-plan-hash',required=True)
    a=s.add_parser('handoff');a.add_argument('--lineage',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('controls')
    for flag in ('jar','jar-pin','authority','output'):a.add_argument('--'+flag,type=Path,required=True)
    a.add_argument('--variant',choices=('vulnerable','fixed'),default='vulnerable')
    a.add_argument('--calibration',type=Path)
    a.add_argument('--fault',choices=('wrong-password','wrong-actor','stale-credential','browser-loss','native-loss','pre-send','commit-drop','broker-crash','controller-crash','resource','cancel','lost-ack','native-restart','scope','tls-ca','tls-hostname','tls-pin'))
    args=p.parse_args(argv)
    if args.command=='discover':
        from .fe_authenticated_discovery import discover
        v=discover(args.product,args.recipe,args.observations)
        if args.inventory:
            from .product_scope import validate_inventory
            inv=validate_inventory(load(args.inventory))
            if Path(inv['productLocation']).resolve()!=args.product.resolve() or inv['track']!='fe-authenticated':raise ValueError('task inventory mismatch')
            original=v.get('responsibilityInventory') or {'cases':[]}
            if not {c['caseId'] for c in original['cases']}<={c['caseId'] for c in inv['cases']}:raise ValueError('product obligations omitted from reviewed inventory')
            v['responsibilityInventory']=inv
        args.output.mkdir(parents=True,mode=0o700,exist_ok=False);save(args.output,'DISCOVERY.json',v);save(args.output,'FE_JOURNEYS.json',v['journeys']);result={'stage':'source-only','executionStatus':'not-run','responsibilities':len(v['journeys']['responsibilities'])}
    elif args.command=='status':
        d=load(args.discovery)
        from .fe_authenticated_contract import validate_journeys
        validate_journeys(d['journeys']);result={'stage':d['stage'],'executionStatus':'not-run','taskCompletion':'partial','responsibilities':len(d['journeys']['responsibilities']),'runtimeObservation':'not requested'}
    elif args.command=='plan':
        from .fe_authenticated_binding import inspect
        d=load(args.discovery);selection=load(args.selection);inspect(selection);d['selection']=selection;d['stage']='runtime-bound'
        v=compile_plan(d,load(args.journeys),selection,load(args.authority),args.run_id or 'fea-'+uuid.uuid4().hex[:12])
        if args.output.exists():raise ValueError('plan output exists')
        save(args.output.parent,args.output.name,v);result={'planHash':canonical(v),'runId':v['runId']}
    elif args.command=='run':
        from .fe_authenticated_runner import AuthenticatedRun
        from .fe_authenticated_auth import private_actors
        v=load(args.plan)
        if v['selection']!=load(args.selection):raise ValueError('selection drift')
        result=AuthenticatedRun(v,args.output,private_actors(args.actors)).execute(args.interrupt_after)
    elif args.command=='verify':
        from .fe_authenticated_verify import verify
        result=verify(args.run,args.expected_plan_hash)
    elif args.command=='handoff':
        from .fe_authenticated_handoff import handoff
        result=handoff(load(args.lineage),args.output)
    elif args.command=='controls':
        from .fe_authenticated_controls import control
        result=control(args.output,args.jar,args.jar_pin,load(args.authority),args.variant,args.fault,args.calibration)
    print(json.dumps(result,ensure_ascii=False));return 0 if result.get('executionStatus') not in ('failed','interrupted') else 2
