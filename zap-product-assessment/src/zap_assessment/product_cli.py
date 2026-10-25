"""Product location -> source discovery -> explicit recipe -> frozen plan -> existing executors."""
import argparse
import json
import os
from pathlib import Path
import stat
from .bola_research import save
from .discovery import canonical_hash,validate_discovery
from .product_source import source_inventory,validate_candidate,materialize
from .product_workflow import admission,compile_workflow,validate_workflow,compile_track
from .product_binding import verify_binding
from .recipes import select,REGISTRY


def load(path):return json.loads(Path(path).read_bytes())
def private(path):
    p=Path(path)
    if p.is_symlink() or not stat.S_ISREG(p.stat().st_mode) or p.stat().st_mode & 0o077:raise ValueError('private actor file must be regular mode 0600')
    return load(p)


def main(argv=None):
    # FE has its own contract/transport. Never fall through to backend/BOLA else branches.
    import sys
    args=list(sys.argv[1:] if argv is None else argv)
    if args and args[0]=='fe-authenticated':
        from .fe_authenticated_cli import main as fe_main
        return fe_main(args[1:])
    if args and args[0]=='fe-anonymous':
        from .fe_anonymous_cli import main as fe_main
        return fe_main(args[1:])
    if args and args[0]=='run' and '--plan' in args:
        candidate=load(args[args.index('--plan')+1])
        if candidate.get('track')=='fe-authenticated':
            from .fe_authenticated_cli import main as fe_main
            return fe_main(args)
        if candidate.get('track')=='fe-anonymous':
            from .fe_anonymous_cli import main as fe_main
            return fe_main(args)
    if args and args[0]=='scope':
        from .product_scope_cli import main as scope_main
        return scope_main(args[1:])
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    d=sub.add_parser('discover',help='Source-assisted facts; no runtime/environment fabrication')
    d.add_argument('--product',required=True,type=Path);d.add_argument('--recipe')
    d.add_argument('--observations',type=Path,help='Reviewed source observations with file hashes; generic provider')
    d.add_argument('--output',required=True,type=Path)
    m=sub.add_parser('materialize',help='Resolve source candidate with independently inspectable deployment')
    m.add_argument('--candidate',required=True,type=Path);m.add_argument('--deployment',required=True,type=Path);m.add_argument('--output',required=True,type=Path)
    for name in ('status','plan','continue-plan','templates'):
        p=sub.add_parser(name);p.add_argument('--product',required=True,type=Path);p.add_argument('--discovery',required=True,type=Path);p.add_argument('--recipe',required=True);p.add_argument('--track',required=True)
        if name in ('plan','continue-plan'):
            p.add_argument('--inventory',type=Path);p.add_argument('--selection',required=True,type=Path);p.add_argument('--authority',required=True,type=Path);p.add_argument('--workload',required=name=='plan',type=Path);p.add_argument('--run-id',required=True);p.add_argument('--output',required=True,type=Path)
        if name=='continue-plan':p.add_argument('--continuation',required=True,type=Path);p.add_argument('--allocation',required=True)
    rec=sub.add_parser('reconcile');rec.add_argument('--responsibilities',required=True,type=Path);rec.add_argument('--observations',required=True,type=Path);rec.add_argument('--prerequisites',required=True,type=Path);rec.add_argument('--output',required=True,type=Path)
    handoff=sub.add_parser('handoff',help='Compose pinned retained/continuation lineage; no execution')
    handoff.add_argument('--lineage',required=True,type=Path);handoff.add_argument('--output',required=True,type=Path)
    imp=sub.add_parser('import-actor');imp.add_argument('--plan',required=True,type=Path);imp.add_argument('--selection',required=True,type=Path);imp.add_argument('--credentials',required=True,type=Path);imp.add_argument('--output',required=True,type=Path)
    setup=sub.add_parser('prepare');setup.add_argument('--plan',required=True,type=Path);setup.add_argument('--selection',required=True,type=Path);setup.add_argument('--output',required=True,type=Path)
    business=sub.add_parser('business-fixtures');business.add_argument('--plan',required=True,type=Path);business.add_argument('--selection',required=True,type=Path);business.add_argument('--output',required=True,type=Path);business.add_argument('--actors',required=True,type=Path);business.add_argument('--catalog',required=True,type=Path)
    r=sub.add_parser('run');r.add_argument('--plan',required=True,type=Path);r.add_argument('--selection',required=True,type=Path);r.add_argument('--output',required=True,type=Path)
    r.add_argument('--actors',type=Path);r.add_argument('--jar',type=Path);r.add_argument('--jar-pin',type=Path);r.add_argument('--interrupt-after',type=float)
    a=parser.parse_args(argv)
    if a.command=='handoff':
        from .product_handoff import compose_handoff
        result=compose_handoff(load(a.lineage),a.output);print(json.dumps(result['summary']));return 0
    if a.command=='reconcile':
        from .product_workflow import reconcile_responsibilities
        result=reconcile_responsibilities(load(a.responsibilities),load(a.observations),load(a.prerequisites))
        if a.output.exists():raise ValueError('continuation output exists')
        save(a.output.parent,a.output.name,result);print(json.dumps({'nextEligibleCaseIds':result['nextEligibleCaseIds'],'taskCompletion':result['taskCompletion']}));return 0
    if a.command=='discover':
        if a.observations:c=source_inventory(a.product,load(a.observations))
        elif a.recipe and hasattr(recipe:=select(a.recipe),'discover'):c=recipe.discover(a.product)
        else:parser.error('recipe needs source-assisted observations; no implicit product parser or legacy runtime discovery')
        if a.output.exists():raise ValueError('output exists; preserve source candidate')
        save(a.output.parent,a.output.name,c);print(json.dumps({'stage':c['stage'],'operations':len(c['operations']),'sha256':canonical_hash(c),'executionStatus':'not-run'}));return 0
    if a.command=='materialize':
        c=validate_candidate(load(a.candidate));d=load(a.deployment)
        doc=materialize(c,d['source'],d['environment'],d['binding'],d['origins'])
        verify_binding(doc,d['selection'],require_direct=False)
        if a.output.exists():raise ValueError('output exists')
        save(a.output.parent,a.output.name,doc);print(json.dumps({'stage':'runtime-bound','sha256':canonical_hash(doc),'executionStatus':'not-run'}));return 0
    if a.command in ('status','plan','continue-plan','templates'):
        select(a.recipe);doc=load(a.discovery)
        location=doc.get('productLocation') if doc.get('stage')=='source-only' else doc['product']['location']
        if Path(a.product).resolve()!=Path(location).resolve():raise ValueError('requested product/source candidate mismatch')
        if a.command=='templates':
            r=select(a.recipe)
            if not hasattr(r,'workload_templates'):raise ValueError('templates require recipe helper; agent supplies reviewed workload')
            if doc.get('stage')=='source-only':validate_candidate(doc)
            print(json.dumps(r.workload_templates(doc),ensure_ascii=False,indent=2));return 0
        if doc.get('stage')=='source-only':
            c=validate_candidate(doc);supported=select(a.recipe).admit({'operations':c['operations'],'auth':c['auth']},track=a.track)
            if not supported:raise ValueError('source recipe incompatible; inventory retained')
            print(json.dumps({'stage':'source-only','executionStatus':'not-run','evidenceStatus':'source-only','securityVerdict':'inconclusive','cleanupStatus':'not-applicable','gateDecision':'block',
                              'operations':len(c['operations']),'sourceSupportedOperationIds':supported,'dependencies':['runtime deployment binding','authority and operation scope','owned fixtures/role credentials as required'],'recipe':a.recipe}));return 0 if a.command=='status' else 2
        if a.command=='templates':
            r=select(a.recipe)
            if not hasattr(r,'workload_templates'):raise ValueError('templates require recipe helper; agent may supply reviewed workload')
            print(json.dumps(r.workload_templates(doc),ensure_ascii=False,indent=2));return 0
        recipe,cap=admission(a.product,doc,a.recipe,a.track)
        if a.command=='status':print(json.dumps({**cap,'executionStatus':'not-run','runtimeObservation':'not requested; status-only'}));return 0
        selection=load(a.selection);inspection=lambda:verify_binding(doc,selection,require_direct=a.track!='be-anonymous')
        if a.command=='continue-plan':
            allocations=[r for r in load(a.continuation)['nextAllocations'] if r['id']==a.allocation]
            if len(allocations)!=1:raise ValueError('continuation allocation not eligible')
            workload=allocations[0]['workload']
        else:workload=load(a.workload)
        p=compile_workflow(a.product,doc,a.recipe,a.track,load(a.authority),workload,inspection,a.run_id)
        if a.inventory:
            from .product_scope import validate_inventory
            inv=validate_inventory(load(a.inventory))
            if Path(inv['productLocation']).resolve()!=a.product.resolve() or inv['track']!=a.track:raise ValueError('task inventory mismatch')
            if not {c['caseId'] for c in p['responsibilityInventory']['cases']}<={c['caseId'] for c in inv['cases']}:raise ValueError('source operation responsibility omitted')
            p['responsibilityInventory']=inv
        # Fail on unsupported workload before any fixture preparation.
        if 'actorRefs' not in p['workload'] and a.track!='be-authenticated':compile_track(p)
        if a.output.exists():raise ValueError('plan output exists')
        save(a.output.parent,a.output.name,p);print(json.dumps({'stage':'frozen','sha256':canonical_hash(p),'executionStatus':'not-run','capability':cap}));return 0
    p=load(a.plan);selection=load(a.selection);plan_hash=canonical_hash(p);selection_hash=canonical_hash(selection)
    def inspection():
        if canonical_hash(load(a.plan))!=plan_hash or canonical_hash(load(a.selection))!=selection_hash:raise ValueError('frozen plan/selection file drift')
        return verify_binding(p['discovery'],selection,require_direct=p['track']!='be-anonymous')
    validate_workflow(p,inspection)
    if a.command=='import-actor':
        from .product_identity import import_actor
        print(json.dumps(import_actor(p,inspection,a.output,private(a.credentials))));return 0
    if a.command=='business-fixtures':
        from .product_prepare import business
        result=business(p,inspection,a.output,private(a.actors),load(a.catalog))
        print(json.dumps({'executionStatus':'prepared','checks':result['checks'],'cleanupStatus':result['cleanupStatus']}));return 0
    if a.command=='prepare':
        from .product_prepare import prepare
        print(json.dumps(prepare(p,inspection,a.output)));return 0
    if p['track']=='be-anonymous':
        from .anonymous_runner import AnonymousRun
        def guarded_inspection():
            validate_workflow(p,inspection);return inspection()
        run=AnonymousRun(compile_track(p),a.output,guarded_inspection)
        from .product_workflow import archive_sources
        archive_sources(p,a.output)
        result=run.execute(a.interrupt_after)
        from .product_handoff import anonymous_handoff
        anonymous_handoff(p,a.output)
    elif p['track']=='be-authenticated':
        if not a.actors or not a.jar or not a.jar_pin:parser.error('native execution requires private actor provenance and compatible pinned JAR')
        from .product_native import execute
        from .product_resources import verify_jar
        verify_jar(a.jar,load(a.jar_pin))
        from .product_prepare import verify_actor
        native_actor=private(a.actors);verify_actor(native_actor)
        result=execute(p,inspection,a.output,native_actor,a.jar,interrupt_after=a.interrupt_after)
    else:
        if not a.actors:parser.error('BOLA requires private actors with protected subject provenance')
        from .product_bola import execute
        result=execute(p,inspection,a.output,private(a.actors),interrupt_after=a.interrupt_after)
    print(json.dumps(result));return 0 if result['executionStatus']=='completed' else 2

if __name__=='__main__':raise SystemExit(main())
