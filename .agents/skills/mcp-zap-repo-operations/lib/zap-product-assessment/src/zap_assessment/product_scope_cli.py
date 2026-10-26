"""Offline task reconciliation and guarded continuation through existing CLIs."""
import argparse,json
from pathlib import Path
from .product_scope import reconcile,continue_work,apply_completion,validate_inventory
from .journal import Journal
from .discovery import canonical_hash


def load(path):return json.loads(Path(path).read_bytes())


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    for command in ('reconcile','continue','report'):
        p=sub.add_parser(command)
        for key in ('inventory','observations','prerequisites','output'):p.add_argument('--'+key,type=Path,required=True)
        if command=='continue':
            p.add_argument('--actions',type=Path,required=True);p.add_argument('--previous',type=Path,action='append',default=[])
        if command=='report':
            p.add_argument('--run',type=Path,required=True);p.add_argument('--alerts',type=Path,required=True)
    a=parser.parse_args(argv);inv=validate_inventory(load(a.inventory));obs=load(a.observations);pre=load(a.prerequisites)
    if a.output.exists():raise ValueError('fresh output required; preserve prior allocation and history')
    if a.command!='report':a.output.mkdir(parents=True,mode=0o700)
    from .bola_research import save
    if a.command=='continue':
        actions=load(a.actions);handlers={};attempts=list(actions.get('_attempts',[]))
        for prior in a.previous:
            previous=load(prior/'RUN.json')
            if previous['scope']!={k:inv[k] for k in ('productLocation','track','environment','origin') if k in inv}:raise ValueError('continuation scope changed')
            if not {c['caseId'] for c in previous['inventory']['cases']}<={c['caseId'] for c in inv['cases']}:raise ValueError('prior responsibility omitted')
            attempts.extend(previous.get('actionHistory',previous['actionsPerformed']))
            prior_obs=previous['observations']
            for cid,row in prior_obs.items():
                if row.get('outcomeUnknown') and not obs.get(cid,{}).get('stateReconciled'):obs[cid]=row
                elif cid not in obs:obs[cid]=row
            pre={**previous['prerequisites'],**pre}
        # Intent/ACK survives controller loss. No user-supplied code or shell is run.
        journal=Journal(a.output/'journal.jsonl',a.output.name,canonical_hash(inv))
        for cid,descriptor in actions.items():
            if cid=='_attempts':continue
            def execute(action,d=descriptor):
                args=d['arguments']
                command=args[1] if args[0] in ('fe-anonymous','fe-authenticated') else args[0]
                if command not in ('run','prepare','import-actor','business-fixtures'):
                    raise ValueError('continuation only dispatches existing admitted execution/preparation entries')
                from .product_cli import main as product_main
                # Validate the plan belongs to this task BEFORE any setup or traffic.
                plan=load(args[args.index('--plan')+1]);disc=plan['discovery']
                location=disc.get('productLocation',disc.get('product',{}).get('location'))
                if Path(location).resolve()!=Path(inv['productLocation']).resolve() or plan['track']!=inv['track']:
                    raise ValueError('continuation task/plan mismatch')
                selection=plan.get('selection',{})
                environment=selection.get('environment',disc.get('product',{}).get('environment'))
                origin=selection.get('origin')
                if inv.get('environment') and inv['environment']!=environment:raise ValueError('continuation environment mismatch')
                if inv.get('origin') and inv['origin']!=origin:raise ValueError('continuation origin mismatch')
                if '--output' not in args:raise ValueError('new execution output required')
                out=Path(args[args.index('--output')+1])
                if out.exists():raise ValueError('allocation already exists; read/reconcile, never replay')
                if out.resolve()==a.output.resolve():raise ValueError('executor output must be separate from continuation journal')
                # Impact comes from the compiled workload as well as the action descriptor.
                w=plan.get('workload',{});j=plan.get('journeys',{})
                requests=w.get('requests',[])+w.get('cases',[])
                hazardous=command in ('prepare','business-fixtures') or bool(plan.get('campaigns') or j.get('campaigns') or w.get('execution',{}).get('attacks'))
                hazardous=hazardous or any(r.get('method',r.get('request',{}).get('method','GET')) not in ('GET','HEAD','OPTIONS') for r in requests)
                hazardous=hazardous or any(r.get('effect')=='mutation' for r in j.get('journeys',[]))
                if hazardous and action['effect']=='read':raise ValueError('action impact understates compiled mutation/start')
                # The entry performs all current authority, pins, ownership and resource checks.
                product_main(args)
                # Exit code is intentionally ignored for scope. Read actual checker observations.
                return read_action_result(out,d,plan=plan,command=command)
            handlers[cid]=execute
        result=continue_work(inv,obs,pre,handlers,persist=lambda row:journal.append(row['state'],row),
            attempts=attempts)
    else:
        result=reconcile(inv,obs,pre)
        if a.command=='report':
            from .product_scope import compact_results
            result=compact_results(a.output,load(a.run),load(a.alerts),result)
    if a.command!='report':save(a.output,'RUN.json',result)
    print(json.dumps({'taskCompletion':result['taskCompletion'],'output':str(a.output/'RUN.json')}))
    return 0  # command success is not task completion


def read_action_result(out,descriptor,*,plan=None,command='run'):
    """Bind an existing independent checker result to responsibility evidence units.

    Mappings are reviewed task allocations, not arbitrary claimed output statuses.
    A failed product assertion (violated) is a valid observation. Unknown stays open.
    """
    out=Path(out)
    plan=plan or load(out/'PLAN.json')
    if command=='business-fixtures':
        value=load(out/'BUSINESS.json')
        if not value.get('ledger') or not value.get('checks') or any(not [k for k in c if k.endswith('Matched')] or not all(v is True for k,v in c.items() if k.endswith('Matched')) for c in value['checks']):raise ValueError('business fixture readback incomplete')
        actual={r['kind'] for r in value['ledger'] if r.get('wireId') and r.get('creationEvidence')}
        return {'prerequisites':{key:True for key,kind in descriptor.get('prerequisiteBindings',{}).items() if kind in actual}}
    if command in ('prepare','import-actor'):
        from .product_prepare import verify_actor
        actors=load(out/('actors.json' if command=='prepare' else 'actor.json'))
        if command=='import-actor':actors={'actor':actors}
        for actor in actors.values():verify_actor(actor)
        return {'prerequisites':{key:True for key,ref in descriptor.get('prerequisiteBindings',{}).items() if ref in actors}}
    if plan.get('track')=='fe-anonymous':
        from .fe_anonymous_verify import verify
        result=verify(out,canonical_hash(plan))
        if any('unknown' in str(g).lower() for g in result['responsibilityReconciliation'].get('executionGaps',[])):raise ValueError('unknown allocation outcome requires reconciliation')
        return {'observations':result['responsibilityReconciliation'].get('observations',{})}
    if plan.get('track')=='fe-authenticated':
        from .fe_authenticated_verify import verify
        result=verify(out,canonical_hash(plan))
        if any('unknown' in str(g).lower() for g in result['responsibilityReconciliation'].get('executionGaps',[])):raise ValueError('unknown allocation outcome requires reconciliation')
        return {'observations':result['responsibilityReconciliation'].get('observations',{})}
    if plan.get('track')=='bola-ownership' and any('active' in u.lower() or 'native' in u.lower() for b in descriptor.get('resultBindings',[]) for u in b['evidenceUnits']):
        raise ValueError('UI/direct case checks cannot satisfy native active evidence')
    if plan.get('track')=='bola-ownership':
        from .product_bola import verify
        verify(out)
    if plan.get('track')=='be-authenticated':return native_readback(out,plan,descriptor)
    if plan.get('track')=='be-anonymous':return anonymous_readback(out,plan,descriptor)
    checks=load(out/'CHECKS.json')
    if not isinstance(checks,list):raise ValueError('independent case checks required')
    lookup={r.get('caseId',r.get('journeyId')):r for r in checks};updates={}
    for binding in descriptor.get('resultBindings',[]):
        if any('active' in unit.lower() or 'native' in unit.lower() for unit in binding['evidenceUnits']):
            raise ValueError('UI/direct case checks cannot satisfy native active evidence')
        row=lookup.get(binding['checkId'],{});outcome=row.get('outcome')
        if outcome not in ('matched','violated','pass','assertion-mismatch'):continue
        updates[binding['caseId']]={'outcome':'violated' if outcome in ('violated','assertion-mismatch') else 'matched',
            'evidenceUnits':binding['evidenceUnits'],'resultRead':True,**binding_context(plan,binding)}
    return {'observations':updates}


def native_readback(out,workflow,descriptor):
    """Read existing native history/scan attribution; seeds and terminal alone fail."""
    from .research import verify_manifest
    from .fe_authenticated_semantics import request
    from urllib.parse import urlsplit,parse_qsl
    verify_manifest(out)
    p=load(out/'PLAN.json');history=load(out/'raw-history.json');ops=load(out/'operations.json')
    identity=load(out/'IDENTITY_STRATEGY.json')
    if not identity.get('nativeValidated'):raise ValueError('native identity readback absent')
    updates={}
    for b in descriptor.get('resultBindings',[]):
        if b.get('kind')!='active':continue
        i=b['attackIndex'];a=p['execution']['attacks'][i]
        attribution=load(out/('active-attribution-'+str(i)+'.json'))
        terminal=any(o.get('terminal') and str(o.get('nativeScanId'))==str(attribution['nativeScanId']) for o in ops)
        ids={str(mid) for mid in attribution['messageIds']['messagesIds']};delivered=False;changed_fields=set();vector='query'
        baseline=dict(parse_qsl(urlsplit(a['path']).query,keep_blank_values=True))
        for raw in history:
            if str(raw['id']) not in ids:continue
            m=request(raw,p['origin'])
            if not m or m['method']!=a['method'] or urlsplit(m['url']).netloc!=urlsplit(p['origin']).netloc:continue
            if not m['headers'].get('authorization') or m['headers'].get('x-zap-scan-id') not in {str(r) for r in p['ruleIds']} or m['status'] in (401,403,None):continue
            if a.get('body') is not None:
                proof=load(out/('transition-'+str(i)+'.json'));vector='json-body'
                try:candidate=json.loads(m['body'])
                except ValueError:continue
                changed_fields={k for k in a['body'] if candidate.get(k)!=a['body'][k]}
                delivered=bool(proof.get('deliveredBodyMessages') and proof.get('finalStateMatched') and changed_fields)
            elif i in workflow['workload'].get('pathAttackIndices',[]):
                delivered=bool(load(out/('path-delivery-'+str(i)+'.json')).get('deliveredPathMessages'));vector='path';changed_fields=set(b.get('vectorFields',[]))
            elif urlsplit(m['url']).path==urlsplit(a['path']).path:
                candidate=dict(parse_qsl(urlsplit(m['url']).query,keep_blank_values=True))
                changed_fields={k for k,v in baseline.items() if candidate.get(k)!=v}
                delivered=bool(set(candidate)==set(baseline) and changed_fields)
            if delivered:break
        required=[u.split(':',2) for u in b['evidenceUnits'] if u.startswith('active:')]
        compatible=all(len(parts)==3 and parts[1]==vector and parts[2] in changed_fields for parts in required)
        if terminal and delivered and compatible:updates[b['caseId']]={'outcome':'matched','resultRead':True,'evidenceUnits':b['evidenceUnits'],**({'role':identity['role']} if identity.get('role') else {})}
    return {'observations':updates}


def anonymous_readback(out,workflow,descriptor):
    from .anonymous_runner import verify
    verify(out);ops=load(out/'OPERATIONS.json');checks=load(out/'COVERAGE.json')['cases'];updates={}
    p=load(out/'PLAN.json');messages=load(out/'messages.json')['messages']
    for b in descriptor.get('resultBindings',[]):
        if b.get('kind')=='active':
            matched=anonymous_active_units(out,p,messages,ops,b)
        else:
            if any('active' in u.lower() for u in b['evidenceUnits']):raise ValueError('baseline is not active coverage')
            matched=any(c['caseId']==b['checkId'] and c['observed']['matched'] for c in checks)
        if matched:updates[b['caseId']]={'outcome':'matched','resultRead':True,'evidenceUnits':b['evidenceUnits']}
    return {'observations':updates}


def binding_context(plan,binding):
    """Roles/relations from the locked case; don't substitute metadata from reports."""
    case=next((c for c in plan.get('workload',{}).get('cases',[]) if c.get('id')==binding.get('checkId')),None)
    if case is None:return {}
    context={k:case[k] for k in ('actorRef','role','state','relation') if k in case}
    actors=plan.get('workload',{}).get('actors',{})
    actor=actors.get(case.get('actorRef'),{})
    if actor.get('role'):context['role']=actor['role']
    return context


def anonymous_active_units(out,plan,messages,operations,binding):
    """Changed app input, exact native campaign and field; baseline/guard never count."""
    from .fe_authenticated_semantics import request
    from urllib.parse import urlsplit,parse_qsl
    campaign=next((c for c in plan['campaigns'] if c['id']==binding['checkId']),None)
    op=next((o for o in operations if o.get('campaignId')==binding['checkId'] and o.get('terminal')),None)
    if not campaign or not op:return False
    seed=load(Path(out)/('http/'+campaign['caseId']+'.json'))
    baseline=request(seed,plan['origin']);vector={'JSON-body':'json-body','query':'query','path':'path'}[campaign['vectors'][0]]
    ids={str(i) for i in op['messageIds']['messagesIds']};fields=set()
    for raw in messages:
        if str(raw['id']) not in ids or 'x-zpa-response-origin: app' not in raw.get('responseHeader','').lower():continue
        m=request(raw,plan['origin'])
        if not m or m['method']!=baseline['method'] or m['headers'].get('x-zap-scan-id') not in {str(r) for r in campaign['ruleIds']}:continue
        if vector=='json-body':
            try:a,b=json.loads(baseline['body']),json.loads(m['body'])
            except ValueError:continue
        elif vector=='query':a,b=dict(parse_qsl(urlsplit(baseline['url']).query,keep_blank_values=True)),dict(parse_qsl(urlsplit(m['url']).query,keep_blank_values=True))
        else:
            a={'path':urlsplit(baseline['url']).path};b={'path':urlsplit(m['url']).path}
        if vector!='path' and urlsplit(m['url']).path!=urlsplit(baseline['url']).path:continue
        changed={k for k in set(a)|set(b) if a.get(k)!=b.get(k)}
        allowed=set(campaign['mutableKeys'])
        if changed and (changed<=allowed or vector=='path'):fields.update(allowed if vector=='path' else changed)
    required=[u.split(':',2) for u in binding['evidenceUnits'] if u.startswith('active:')]
    return bool(fields) and all(len(parts)==3 and parts[1]==vector and parts[2] in fields for parts in required)
