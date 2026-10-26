"""Explicit FE command router. Offline commands never provision containers or send HTTP."""
import argparse,json,time,uuid
from pathlib import Path
from .fe_anonymous_contract import load,save,canonical,compile_plan,validate_plan

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    d=sub.add_parser('discover');d.add_argument('--product',type=Path,required=True);d.add_argument('--recipe',required=True);d.add_argument('--observations',type=Path);d.add_argument('--inventory',type=Path);d.add_argument('--output',type=Path,required=True)
    p=sub.add_parser('plan');p.add_argument('--discovery',type=Path,required=True);p.add_argument('--journeys',type=Path,required=True);p.add_argument('--selection',type=Path,required=True);p.add_argument('--authority',type=Path,required=True);p.add_argument('--run-id',default=None);p.add_argument('--output',type=Path,required=True)
    r=sub.add_parser('run');r.add_argument('--plan',type=Path,required=True);r.add_argument('--selection',type=Path,required=True);r.add_argument('--output',type=Path,required=True);r.add_argument('--interrupt-after',type=int)
    v=sub.add_parser('verify');v.add_argument('--run',type=Path,required=True);v.add_argument('--expected-plan-hash',required=True)
    s=sub.add_parser('status');s.add_argument('--discovery',type=Path,required=True)
    h=sub.add_parser('handoff');h.add_argument('--lineage',type=Path,required=True);h.add_argument('--output',type=Path,required=True)
    c=sub.add_parser('controls');c.add_argument('--output',type=Path,required=True);c.add_argument('--jar',type=Path,required=True);c.add_argument('--jar-pin',type=Path,required=True)
    a=parser.parse_args(argv)
    if a.command=='discover':
        from .fe_anonymous_discovery import discover
        result=discover(a.product,a.recipe,a.observations)
        if a.inventory:
            from .product_scope import validate_inventory
            inv=validate_inventory(load(a.inventory))
            if Path(inv['productLocation']).resolve()!=a.product.resolve() or inv['track']!='fe-anonymous':raise ValueError('task inventory mismatch')
            result['responsibilityInventory']=inv
        if a.output.exists():raise ValueError('output exists; no clobber')
        a.output.mkdir(mode=0o700,parents=True);save(a.output,'DISCOVERY.json',result);save(a.output,'FE_JOURNEYS.json',result['journeys'])
        print(json.dumps({'stage':'source-only','journeys':len(result['journeys']['journeys']),'executionStatus':'not-run','output':str(a.output)}));return 0
    if a.command=='status':
        d=load(a.discovery);print(json.dumps({'stage':d['stage'],'executionStatus':'not-run','obligations':len(d['journeys']['responsibilities'])}));return 0
    if a.command=='plan':
        from .fe_anonymous_binding import inspect
        d=load(a.discovery);selection=load(a.selection);inspect(selection);d['selection']=selection;d['stage']='runtime-bound'
        result=compile_plan(d,load(a.journeys),selection,load(a.authority),a.run_id or 'fe-'+uuid.uuid4().hex[:12])
        if a.output.exists():raise ValueError('plan output exists')
        save(a.output.parent,a.output.name,result);print(json.dumps({'planHash':canonical(result),'runId':result['runId']}));return 0
    if a.command=='run':
        from .fe_anonymous_runner import FERun
        p=load(a.plan)
        if p['selection']!=load(a.selection):raise ValueError('selection file drift')
        result=FERun(p,a.output).execute(a.interrupt_after);print(json.dumps(result));return 0 if result['executionStatus']=='completed' else 2
    if a.command=='verify':
        from .fe_anonymous_verify import verify
        print(json.dumps(verify(a.run,a.expected_plan_hash)));return 0
    if a.command=='handoff':
        from .fe_anonymous_handoff import handoff
        print(json.dumps(handoff(load(a.lineage),a.output)['summary']));return 0
    if a.command=='controls':
        from .fe_anonymous_controls import transport_control
        print(json.dumps(transport_control(a.output,a.jar,a.jar_pin)));return 0
    return 2
