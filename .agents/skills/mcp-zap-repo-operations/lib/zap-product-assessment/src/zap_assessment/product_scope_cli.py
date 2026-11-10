"""Offline task reconciliation and guarded continuation through existing CLIs."""
import argparse,json,sys
from pathlib import Path
from .product_scope import reconcile,continue_work,apply_completion,validate_inventory
from .journal import Journal
from .discovery import canonical_hash


def load(path):return json.loads(Path(path).read_bytes())


def main(argv=None):
    command_line = sys.argv[1:] if argv is None else argv

    class ScopeParser(argparse.ArgumentParser):
        def error(self, message):
            if command_line and command_line[0].startswith('state-'):
                print(json.dumps(dict(code='invalid-arguments', message='Invalid command arguments', refs=[])))
                self.exit(2)
            super().error(message)

    parser=ScopeParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    from .assessment_state_cli import add_commands, handle, managed_run_argument
    from .assessment_store import load_current, read_json
    add_commands(sub)
    for name in ('criteria-review','criteria-digest','criteria-packet','criteria-merge'):
        command=sub.add_parser(name)
        if name == 'criteria-merge':
            command.add_argument('--run',type=Path,required=True)
        else:
            managed_run_argument(command)
        if name=='criteria-digest':command.add_argument('--kind',choices=('criteria','plan'),required=True)
        if name=='criteria-packet':
            command.add_argument('--task-id',required=True);command.add_argument('--worker-id',required=True)
            command.add_argument('--case-id',action='append',required=True)
            command.add_argument('--refs',type=Path)
        if name=='criteria-merge':
            command.add_argument('--packet',type=Path,required=True);command.add_argument('--result',type=Path,required=True)
        if name in ('criteria-packet','criteria-merge'):command.add_argument('--output',type=Path,required=True)
    native=sub.add_parser('criteria-native-read',help='Execute one approved read-only native MCP action')
    managed_run_argument(native)
    native.add_argument('--packet',type=Path,required=True)
    native.add_argument('--action-id',required=True)
    native.add_argument('--history-entry-id',help='Select a candidate from the approved retained history list')
    reconcile_native=sub.add_parser('criteria-reconcile-action',help='Reconcile a leased action from reviewed RUN evidence')
    managed_run_argument(reconcile_native)
    reconcile_native.add_argument('--packet',type=Path,required=True)
    reconcile_native.add_argument('--action-id',required=True)
    reconcile_native.add_argument('--operation-id',action='append',required=True)
    reconcile_native.add_argument('--release',action='store_true')
    release_native=sub.add_parser('criteria-release-task',help='Release a retained task after reconciliation')
    managed_run_argument(release_native)
    release_native.add_argument('--packet',type=Path,required=True)
    review=sub.add_parser('review-business')
    review.add_argument('--inventory',type=Path,required=True)
    residual=sub.add_parser('review-residuals')
    for key in ('security-scope','scope-assessment','run'):
        residual.add_argument('--'+key,type=Path,required=True)
    for key in ('reconciliation','alerts'):
        residual.add_argument('--'+key,type=Path)
    closure=sub.add_parser('review-closure')
    for key in ('run','security-scope','scope-assessment'):
        closure.add_argument('--'+key,type=Path,required=True)
    closure.add_argument('--alerts',type=Path,help='Canonical findings for residual finding references')
    for key in ('inventory','observations','prerequisites'):
        closure.add_argument('--'+key,type=Path)
    next_case=sub.add_parser('resume-next',help='Select one offline v2 recovery task')
    managed_run_argument(next_case)
    next_case.add_argument('--evidence-index',type=Path,help='Private retained candidates indexed by case')
    resume=sub.add_parser('inspect-resume')
    resume.add_argument('--run',type=Path,required=True)
    for command in ('reconcile','continue','report','next-work'):
        p=sub.add_parser(command)
        for key in ('inventory','observations','prerequisites'):
            p.add_argument('--'+key,type=Path,required=command!='report')
        if command!='next-work':p.add_argument('--output',type=Path,required=True)
        if command!='report':p.add_argument('--operations',type=Path,help='Existing semantic operation readbacks; never dispatch')
        if command in ('continue','next-work'):
            p.add_argument('--actions',type=Path,required=command=='continue');p.add_argument('--previous',type=Path,action='append',default=[])
            p.add_argument('--stop',action='store_true',help='Honor a user stop; do not dispatch actions')
        if command=='next-work':
            for key in ('security-scope','scope-assessment','run'):
                p.add_argument('--'+key,type=Path,help='Optional reviewed residual context; supply all three together')
            p.add_argument('--alerts',type=Path,help='Canonical finding records when residual items reference findings')
        if command=='report':
            p.add_argument('--run',type=Path,required=True);p.add_argument('--alerts',type=Path,required=True)
            p.add_argument('--security-scope',type=Path,help='Agent-prepared user criteria/questions; not a runner workload')
            p.add_argument('--scope-assessment',type=Path,help='Reviewed observations and finding associations')
            p.add_argument('--previous-scope',type=Path,help='Prior normalized scope; retain earlier responsibilities')
            p.add_argument('--finalize-round',action='store_true',help='Recompute closure and publish only if eligible; no runtime cleanup')
            p.add_argument('--overwrite',action='store_true',help='Replace only a regular two/three-report destination')
    a=parser.parse_args(argv)
    if a.command.startswith('state-'):
        return handle(a)
    state_dir = getattr(a, 'state_dir', None)

    def working_run():
        return load_current(state_dir).run if state_dir else load(a.run)

    if a.command in ('criteria-native-read','criteria-reconcile-action','criteria-release-task'):
        from .criteria_delegation import Coordinator, coordinator_lock
        from .criteria_native_read import execute_read
        working=working_run()
        with coordinator_lock(working):
            current=working_run()
            state=current.get('coordinatorState')
            if not state or state!=working.get('coordinatorState'):
                raise ValueError('retained coordinator state required')
            packet=load(a.packet)
            coordinator=Coordinator(state['directory'],state['assessmentId'])
            if a.command=='criteria-native-read':
                result=execute_read(current,packet,a.action_id,coordinator,history_entry_id=a.history_entry_id)
                output={'dispatched':result['dispatched'],'receipt':result.get('outcome')}
            elif a.command=='criteria-release-task':
                output=coordinator.release(current,packet)
            else:
                coordinator.reconcile(current,packet,a.action_id,a.operation_id)
                output={'reconciledActionId':a.action_id}
                if a.release:
                    task=next(task for task in coordinator.status()['tasks'] if task['taskId']==packet['taskId'])
                    if task['pendingActionIds']:
                        output.update(released=False,pendingActionIds=task['pendingActionIds'])
                    else:
                        output.update(coordinator.release(current,packet))
        print(json.dumps(output))
        return 0
    if a.command.startswith('criteria-'):
        from .criteria_workflow import review_workflow,approval_digest
        working=working_run()
        if working.get('reportProjection'):raise ValueError('report projection is not executable; load private working RUN')
        if a.command=='criteria-review':
            print(json.dumps(safe_review_output(review_workflow(working))));return 0
        if a.command=='criteria-digest':
            cw=working['criteriaWorkflow']
            print(json.dumps(dict(kind=a.kind,revision=cw[a.kind+'Revision'],digest=approval_digest(cw,a.kind),
                meaning='content identity only; does not grant approval')));return 0
        from .criteria_delegation import make_packet,merge_result,coordinator_lock
        from .safety_io import atomic_bytes
        with coordinator_lock(working):
            # Reload under the canonical writer lock. A projection or pointer
            # changed by another writer must not silently select another state.
            current=working_run()
            if current.get('coordinatorState') != working.get('coordinatorState'):
                raise ValueError('coordinator state changed; reload the current private RUN')
            if a.command=='criteria-packet':
                result=make_packet(current,a.task_id,a.case_id,a.worker_id,refs=load(a.refs) if a.refs else None)
            else:result=merge_result(current,load(a.packet),load(a.result))
            a.output.parent.mkdir(parents=True,exist_ok=True)
            already_applied = False
            if a.command == 'criteria-merge' and a.output.resolve() == a.run.resolve():
                raise ValueError('merge output cannot be the input RUN')
            try:
                atomic_bytes(a.output,json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False).encode())
            except FileExistsError:
                if a.command != 'criteria-merge' or read_json(a.output) != result:
                    raise
                already_applied = True
        print(json.dumps({'output':str(a.output),'execution':'not-dispatched','alreadyApplied':already_applied}));return 0
    if a.command=='review-closure':
        from .security_scope import canonical_alerts, project_scope
        from .round_closure import review_current_round
        working,rec,pre,diagnostics=closure_work_state(a)
        scope=load(a.security_scope);assessment=load(a.scope_assessment)
        check_scope_context(scope,assessment,working,rec.get('inventory'))
        # Validates retained source pointers/text without using finding mappings.
        residual_context(scope,assessment,working,rec,load(a.alerts) if a.alerts else None,base=a.scope_assessment.parent)
        evidence_assessment=dict(assessment,mappings=[])
        projection=project_scope(scope,evidence_assessment,working,canonical_alerts(load(a.alerts) if a.alerts else {'alerts':[]}),rec)
        working=dict(working,scopeAssessment=assessment)
        result=review_current_round(working,projection,rec,pre)
        if diagnostics:
            result['diagnostics'].extend(diagnostics);result['eligibleStatus']=None
            if result['decision']!='checkpoint-required':result['decision']='review-needed'
        print(json.dumps(safe_review_output(result)));return 0
    if a.command=='resume-next':
        from .criteria_resume import resume_next
        index = load(a.evidence_index) if a.evidence_index else ()
        if state_dir:
            from .assessment_state_cli import decision_for
            result = decision_for(load_current(state_dir), evidence_index=index)
        else:
            result = resume_next(working_run(), index)
        print(json.dumps(safe_review_output(result)));return 0
    if a.command=='inspect-resume':
        print(json.dumps(inspect_resume(a.run)));return 0
    if a.command=='review-residuals':
        working=load(a.run);require_legacy_run(working);scope=load(a.security_scope);assessment=load(a.scope_assessment)
        check_scope_context(scope, assessment, working)
        rec=load(a.reconciliation) if a.reconciliation else working.get('responsibilityReconciliation') or (working if 'cases' in working else {})
        result=residual_context(scope,assessment,working,rec,load(a.alerts) if a.alerts else None,base=a.scope_assessment.parent)
        print(json.dumps(safe_review_output(result)));return 0
    if a.command=='review-business':
        from .business_discovery import review_business_coverage
        result=review_business_coverage(validate_inventory(load(a.inventory)))
        if 'limitations' in result:result['limitations']=[{'sourceId':r['sourceId']} for r in result['limitations']]
        print(json.dumps(result));return 0
    if a.command=='report':
        supplied=[a.inventory,a.observations,a.prerequisites]
        if any(supplied) and not all(supplied):parser.error('supply inventory, observations and prerequisites together')
        if a.scope_assessment and not a.security_scope:parser.error('--scope-assessment requires --security-scope')
        if a.previous_scope and not a.security_scope:parser.error('--previous-scope requires --security-scope')
        from .product_scope import compact_results
        working=load(a.run)
        if 'criteriaWorkflow' in working or working.get('workflowVersion')==2:
            if any(supplied) or a.security_scope or a.scope_assessment or a.previous_scope:
                parser.error('criteria workflow uses its approved plan; do not supply legacy scope/inventory arguments')
            from .criteria_reporting import CriteriaFinalizationError
            from .criteria_delegation import coordinator_lock
            try:
                with coordinator_lock(working):
                    current=load(a.run)
                    if current.get('coordinatorState') != working.get('coordinatorState'):
                        raise ValueError('coordinator state changed; reload the current private RUN')
                    result=compact_results(a.output,current,load(a.alerts),overwrite=a.overwrite,finalize_round=a.finalize_round)
            except CriteriaFinalizationError as error:
                print(json.dumps(safe_review_output(error.review)));return 1
            print(json.dumps({'assessmentStatus':result['assessmentStatus'],'criterionCounts':result['criterionCounts'],
                'output':str(a.output/'RUN.json')}));return 0
        from .question_evidence import pending_effects_from_run
        rec=reconcile(validate_inventory(load(a.inventory)),load(a.observations),load(a.prerequisites),
            operations=working.get('operations',[]),attempts=working.get('actionHistory',[]),
            pending_effects=pending_effects_from_run(working)) if all(supplied) else None
        if a.finalize_round or working.get('assessmentRound'):
            working,rec,pre,diagnostics=closure_work_state(a)
            if a.finalize_round and diagnostics:
                print(json.dumps(dict(decision='review-needed',eligibleStatus=None,diagnostics=diagnostics)));return 1
            effective_scope=load(a.security_scope) if a.security_scope else working.get('securityScope')
            effective_assessment=load(a.scope_assessment) if a.scope_assessment else working.get('scopeAssessment',{})
            if effective_scope:
                check_scope_context(effective_scope,effective_assessment,working,(rec or {}).get('inventory'))
                residual_context(effective_scope,effective_assessment,working,rec or {},load(a.alerts),base=(a.scope_assessment or a.run).parent)
        from .round_closure import RoundFinalizationError
        try:
            result=compact_results(a.output,working,load(a.alerts),rec or None,
                security_scope=load(a.security_scope) if a.security_scope else None,
                scope_assessment=load(a.scope_assessment) if a.scope_assessment else None,
                previous_scope=load(a.previous_scope) if a.previous_scope else None,overwrite=a.overwrite,finalize_round=a.finalize_round)
        except RoundFinalizationError as error:
            print(json.dumps(safe_review_output(error.review)));return 1
        print(json.dumps({'taskCompletion':result['taskCompletion'],'roundClosed':result.get('roundClosed',False),'roundStatus':result.get('assessmentRound',{}).get('status','undefined'),'output':str(a.output/'RUN.json')}))
        return 0
    inv=validate_inventory(load(a.inventory));obs=load(a.observations);pre=load(a.prerequisites)
    operations=load(a.operations) if a.operations else []
    actions=load(a.actions) if getattr(a,'actions',None) else {}
    obs,pre,attempts,operations=load_work_state(inv,obs,pre,actions,getattr(a,'previous',[]),operations)
    if a.command=='next-work':
        from .work_selection import select_next_work
        supplied=[a.security_scope,a.scope_assessment,a.run]
        if any(supplied) and not all(supplied):parser.error('supply security-scope, scope-assessment and run together')
        residual=None
        if all(supplied):
            working=load(a.run);scope=load(a.security_scope);assessment=load(a.scope_assessment)
            check_scope_context(scope,assessment,working,inv)
            from .question_evidence import operation_index, pending_effects_from_run
            merged=operation_index(operations)
            for oid,row in operation_index(working.get('operations',[])).items():
                if oid in merged and merged[oid]!=row:raise ValueError('residual context historical operation changed')
                merged[oid]=row
            operations=list(merged.values());attempts+=working.get('actionHistory',[])
            rec=reconcile(inv,obs,pre,operations=operations,attempts=attempts,pending_effects=pending_effects_from_run(working))
            rec.update(observations=obs,operations=operations,continuationStoppedByUser=a.stop)
            residual=residual_context(scope,assessment,{**working,'operations':operations,'actionHistory':attempts},rec,
                load(a.alerts) if a.alerts else None,base=a.scope_assessment.parent)
        else:
            rec=reconcile(inv,obs,pre,operations=operations,attempts=attempts)
            rec.update(observations=obs,operations=operations,continuationStoppedByUser=a.stop)
        result=select_next_work(inv,rec,pre,attempts,{k for k in actions if not k.startswith('_')},residual_work=residual)
        result['taskCompletion']=rec['taskCompletion']
        print(json.dumps(safe_review_output(result)));return 0
    if a.output.exists():raise ValueError('fresh output required; preserve prior allocation and history')
    if a.command!='report':a.output.mkdir(parents=True,mode=0o700)
    from .bola_research import save
    if a.command=='continue':
        handlers={}
        # Intent/ACK survives controller loss. No user-supplied code or shell is run.
        journal=Journal(a.output/'journal.jsonl',a.output.name,canonical_hash(inv))
        for cid,descriptor in actions.items():
            if cid.startswith('_'):continue
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
            attempts=attempts,operations=operations,stop=a.stop)
    else:
        result=reconcile(inv,obs,pre,operations=operations,attempts=attempts)
    if a.command!='report':save(a.output,'RUN.json',result)
    print(json.dumps({'taskCompletion':result['taskCompletion'],'output':str(a.output/'RUN.json')}))
    return 0  # command success is not task completion


def require_legacy_run(run):
    if 'criteriaWorkflow' in run or run.get('workflowVersion') == 2:
        raise ValueError('legacy scope command cannot evaluate criteria workflow v2/v3; use criteria-review with private working RUN')


def closure_work_state(args):
    """Load the executable retained inputs, never the compact inventory as a plan."""
    import copy
    from .question_evidence import pending_effects_from_run
    working=load(args.run);require_legacy_run(working);diagnostics=[];values={}
    supplied=[getattr(args,k,None) for k in ('inventory','observations','prerequisites')]
    if any(supplied) and not all(supplied):raise ValueError('supply inventory, observations and prerequisites together')
    if all(supplied):
        values={k:load(getattr(args,k)) for k in ('inventory','observations','prerequisites')}
    elif working.get('continuation',{}).get('workingInputs'):
        inspected=inspect_resume(args.run)
        if inspected['status']!='working-inputs-available':
            diagnostics.append(dict(code='missing-or-invalid-retained-inventory',details=inspected['diagnostics']))
        else:
            for row in inspected['inputs']:
                value=load(row['path']) if row.get('path') else working
                values[row['input']]=working_pointer(value,row['pointer']) if row.get('pointer') else value
    elif working.get('responsibilityInventory') or working.get('responsibilityReconciliation'):
        diagnostics.append(dict(code='missing-retained-working-inputs',nextStep='Supply inventory, observations and prerequisites or restore workingInputs'))
    if not values:return working,{}, {},diagnostics
    inv=validate_inventory(values['inventory']);obs=values['observations'];pre=values['prerequisites']
    if getattr(args,'security_scope',None):
        check_scope_context(load(args.security_scope),load(args.scope_assessment) if getattr(args,'scope_assessment',None) else working.get('scopeAssessment',{}),working,inv)
    # Preserve the common history loader and reject conflicting retained results.
    merged=copy.deepcopy(working)
    if 'operations' in values and values['operations']!=working.get('operations',[]):raise ValueError('closure retained operations mismatch')
    if 'history' in values and values['history']!=working.get('actionHistory',[]):raise ValueError('closure retained history mismatch')
    obs,pre,attempts,operations=load_work_state(inv,obs,pre,previous=(),operations=working.get('operations',[]))
    rec=reconcile(inv,obs,pre,operations=operations,attempts=working.get('actionHistory',[]),pending_effects=pending_effects_from_run(working))
    rec.update(observations=obs,operations=operations)
    return merged,rec,pre,diagnostics


def load_work_state(inventory, observations, prerequisites, actions=None, previous=(), operations=()):
    """One read-only history loader for preview and execution; never lose intent."""
    import copy
    from .question_evidence import operation_index, pending_effects_from_run
    actions=actions or {};obs=copy.deepcopy(observations);pre=copy.deepcopy(prerequisites)
    attempts=list(actions.get('_attempts',[]));ops=operation_index(operations)
    for prior in previous:
        path=Path(prior);saved=load(path/'RUN.json' if path.is_dir() else path)
        if is_report_projection(saved):
            raise ValueError('report-projection-not-executable: use scope inspect-resume --run REPORT and retained working inputs')
        if saved.get('inventory',{}).get('workflowVersion')==1 and inventory.get('workflowVersion')!=1:
            raise ValueError('continuation workflowVersion downgrade')
        if saved['scope']!={k:inventory[k] for k in ('productLocation','track','environment','origin') if k in inventory}:
            raise ValueError('continuation scope changed')
        if not {c['caseId'] for c in saved['inventory']['cases']}<={c['caseId'] for c in inventory['cases']}:
            raise ValueError('prior responsibility omitted')
        attempts.extend(saved.get('actionHistory',saved.get('actionsPerformed',[])))
        for pending in pending_effects_from_run(saved):
            attempts.append({**pending,'state':'unknown','effect':'start'})
        for cid,row in saved.get('observations',{}).items():
            if inventory.get('workflowVersion')==1:
                if cid not in obs:obs[cid]=copy.deepcopy(row)
                else:
                    obs[cid]['resolvedEffects']=copy.deepcopy(row.get('resolvedEffects',[]))+obs[cid].get('resolvedEffects',[])
                    if row.get('outcomeUnknown') and not obs[cid].get('resolvedEffects'):obs[cid]['outcomeUnknown']=True
            elif row.get('outcomeUnknown') and not obs.get(cid,{}).get('stateReconciled'):obs[cid]=copy.deepcopy(row)
            elif cid not in obs:obs[cid]=copy.deepcopy(row)
        pre={**saved.get('prerequisites',{}),**pre}
        for oid,operation in operation_index(saved.get('operations',[])).items():
            if oid in ops and ops[oid]!=operation:raise ValueError('historical operation changed')
            ops[oid]=operation
    return obs,pre,attempts,list(ops.values())


def is_report_projection(run):
    if run.get('reportGeneration') or run.get('continuation', {}).get('workingInputs', {}).get('reportIsProjection') is True:
        return True
    inv=run.get('inventory') or run.get('responsibilityInventory') or {}
    return any(not c.get('evidenceRefs') for c in inv.get('cases', []))


def safe_review_output(value):
    """CLI summaries retain semantic IDs/pointers, never raw text or credentials."""
    from .discovery_handoff import clean
    if isinstance(value, dict):
        result={}
        for key,item in value.items():
            name=key.lower().replace('_','').replace('-','')
            if name in ('raw','rawdata','requestheader','responseheader','requestbody','responsebody','credentials',
                        'originaltext','selectedtext','observation','evidencelinks','readback'):
                continue
            result[clean(key)]='[private]' if name in ('token','accesstoken','refreshtoken','setuptoken','sessiontoken','authorization','cookie','setcookie','secret','password','passwordvalue','apikey','clientsecret','privatekey') else safe_review_output(item)
        return result
    if isinstance(value, (tuple,list)):
        return [safe_review_output(v) for v in value]
    return clean(value) if isinstance(value,str) else value


def check_scope_context(scope, assessment, run, inventory=None):
    if assessment.get('scopeRevision') != scope.get('revision'):
        raise ValueError('residual context scope revision mismatch')
    context=run.get('assessmentContext', {})
    for key in ('assessmentId','product','environment'):
        values=[row[key] for row in (scope,assessment,run,context) if row.get(key) not in (None,'unknown')]
        if not values or any(v!=values[0] for v in values):
            raise ValueError('residual context '+key+' mismatch or missing')
    if context.get('scopeRevision',scope.get('revision')) != scope.get('revision'):
        raise ValueError('residual context RUN scope revision mismatch')
    if inventory is not None:
        for key,expected in (('product',scope['product']),('environment',scope['environment']),('scopeRevision',scope['revision'])):
            actual=inventory.get(key)
            if actual is None and key!='scopeRevision':
                values={c.get('coverageContext', {}).get(key) for c in inventory.get('cases', [])}
                if len(values)==1:actual=values.pop()
            if actual!=expected:
                raise ValueError('residual context inventory '+key+' mismatch or missing')
        saved=run.get('responsibilityInventory') or run.get('inventory')
        if saved and any(saved.get(k)!=inventory.get(k) for k in ('productLocation','track','environment','origin')):
            raise ValueError('residual context inventory boundary mismatch')


def residual_context(scope, assessment, working, reconciliation, alerts=None, *, base=None):
    require_legacy_run(working)
    import copy
    from .security_scope import canonical_alerts, project_scope
    from .residual_review import validate_source_texts, project_residual_work
    review=assessment.get('residualReview')
    if review:
        documents={}
        for source in review.get('sources', []):
            location=Path(source['location'])
            if not location.is_absolute():location=(base or Path.cwd())/location
            if location.is_symlink() or not location.is_file():
                raise ValueError('residual source must be a regular JSON file: '+source['id'])
            documents[source['id']]=load(location)
        validate_source_texts(review,documents)
    # Aggregate source joins use the same explicitly supplied JSON documents.
    # The pure core validates declared refs; the CLI additionally resolves their
    # paths against retained documents before any publication.
    from .question_evidence import read_pointer
    sources={row['id']:row for row in scope.get('sources',[])}
    sources.update({row['id']:row for row in (review or {}).get('sources',[])})
    documents=documents if review else {}
    for row in assessment.get('aggregateReviews',{}).get('rows',[]):
        for ref in row.get('sourceRefs',[]):
            sid=ref.get('sourceRef')
            if sid not in sources:raise ValueError('unresolved aggregate source')
            if sid not in documents:
                location=Path(sources[sid]['location'])
                location=location if location.is_absolute() else (base or Path.cwd())/location
                if location.suffix.lower()!='.json' or location.is_symlink() or not location.is_file():
                    raise ValueError('aggregate source needs an explicitly retained regular JSON representation: '+sid)
                documents[sid]=load(location)
            read_pointer(documents[sid],ref.get('sourcePointer'))
    # Finding associations are not needed to resolve question evidence. Without
    # ALERTS, do not invent finding objects to satisfy unrelated legacy mappings.
    evidence_assessment=copy.deepcopy(assessment)
    if alerts is None:evidence_assessment['mappings']=[]
    findings=canonical_alerts(alerts or {'alerts':[]})
    projection=project_scope(scope,evidence_assessment,working,findings,reconciliation)
    return project_residual_work(review,projection['securityScope'],
        {**reconciliation,'scopeQuestions':list({q['id']:q for c in projection['criteria'] for q in c['questions']}.values())},
        working.get('operations',[]),findings)


def inspect_resume(run_path):
    """Read explicitly retained references. Existence never attests live readiness."""
    from .question_evidence import operation_index
    path=Path(run_path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('resume RUN must be a regular JSON file')
    report=load(path);require_legacy_run(report);working=report.get('continuation', {}).get('workingInputs')
    diagnostics=[];rows=[];values={}
    result=dict(version=1, status='missing-inputs', inputs=rows, diagnostics=diagnostics,
        readiness='not-validated; revalidate next-action dependencies before execution')
    if is_report_projection(report):diagnostics.append(dict(code='report-projection-not-executable'))
    if working is None:
        diagnostics.append(dict(code='working-inputs-not-supplied', nextStep='Locate explicitly retained private working state; do not execute the compact report'))
        if report.get('privateWorkingDirectory'):result['privateWorkingDirectoryHint']=report['privateWorkingDirectory']
        return safe_review_output(result)
    if not isinstance(working,dict) or type(working.get('version')) is not int or working['version']!=1 or working.get('purpose')!='executable-working-inputs' or working.get('reportIsProjection') is not True:
        diagnostics.append(dict(code='invalid-working-inputs-contract'));return safe_review_output(result)
    expected={**{k:report.get(k) for k in ('assessmentId','product','environment')},**report.get('assessmentContext',{})}
    expected.setdefault('scopeRevision',report.get('securityScope',{}).get('revision'))
    for key in ('assessmentId','product','environment','scopeRevision'):
        if working.get(key) in (None,'unknown') or expected.get(key) in (None,'unknown') or working[key]!=expected[key]:
            diagnostics.append(dict(code='working-input-context-conflict', field=key))
    for key in ('inventory','observations','prerequisites','operations','history'):
        ref=working.get(key);row=dict(input=key,status='missing');rows.append(row)
        if isinstance(ref,str):ref={'path':ref}
        if not isinstance(ref,dict) or set(ref) not in ({'path'},{'pointer'},{'path','pointer'}) or any(not isinstance(v,str) or not v for v in ref.values()):
            row['status']='unavailable' if isinstance(ref,dict) and ref.get('unavailable') else 'invalid-reference';continue
        value=report
        if 'path' in ref:
            location=Path(ref['path']);location=location if location.is_absolute() else path.parent/location
            row['path']=str(location)
            if location.is_symlink() or not location.is_file():row['status']='missing-or-nonregular-file';continue
            try:value=load(location)
            except (ValueError, OSError):row['status']='invalid-json';continue
        if 'pointer' in ref:
            row['pointer']=ref['pointer']
            try:value=working_pointer(value,ref['pointer'])
            except ValueError:row['status']='unresolved-pointer';continue
        try:
            if key=='inventory':
                validate_inventory(value)
                retained=report.get('responsibilityInventory') or report.get('responsibilityReconciliation', {}).get('inventory') or report.get('inventory') or {}
                if any(retained.get(field) is not None and value.get(field)!=retained[field] for field in ('productLocation','track','environment','origin')):
                    raise ValueError('inventory-boundary-conflict')
                for field in ('product','environment','scopeRevision','assessmentId'):
                    actual=value.get(field)
                    if actual is not None and actual!=working[field]:
                        raise ValueError('context-conflict:'+field)
                retained_cases={c['caseId']:c for c in retained.get('cases', [])}
                for case in value.get('cases',[]):
                    # Coverage-context labels have their own namespace (e.g.
                    # product slug versus assessment source path). Compare the
                    # retained case boundary, never coerce labels across them.
                    old=retained_cases.get(case['caseId'])
                    if old and old.get('coverageContext')!=case.get('coverageContext'):
                        raise ValueError('context-conflict:caseBoundary')
            elif key in ('observations','prerequisites'):
                if not isinstance(value,dict):raise ValueError('object-required')
                if key=='prerequisites' and any(type(v) is not bool for v in value.values()):raise ValueError('boolean-prerequisites-required')
            elif key=='operations':operation_index(value)
            elif not isinstance(value,list) or any(not isinstance(v,dict) or not v.get('actionId') or not v.get('state') for v in value):
                raise ValueError('history-list-required')
            values[key]=value;row['status']='available'
        except (ValueError,TypeError,KeyError) as error:
            row['status']='schema-or-context-conflict'
            code=str(error)
            if code in {'context-conflict:'+field for field in ('product','environment','scopeRevision','assessmentId','caseBoundary')}:
                diagnostics.append(dict(code='working-input-file-context-conflict',input=key,field=code.split(':')[1]))
    if len(values)==5 and not any(d['code']=='working-input-context-conflict' for d in diagnostics):
        try:
            reconcile(values['inventory'],values['observations'],values['prerequisites'],operations=values['operations'],attempts=values['history'])
            result['status']='working-inputs-available'
        except (ValueError,KeyError,TypeError):diagnostics.append(dict(code='working-inputs-reconciliation-invalid'))
    if any(r['status']!='available' for r in rows):diagnostics.append(dict(code='missing-or-invalid-working-inputs'))
    return safe_review_output(result)


def working_pointer(value, pointer):
    """RFC 6901 working-data reference; empty maps/lists are legitimate inputs."""
    import re
    if not isinstance(pointer,str) or not pointer.startswith('/'):
        raise ValueError('working input JSON pointer required')
    for part in pointer[1:].split('/'):
        if re.search(r'~(?![01])',part):raise ValueError('invalid pointer escape')
        key=part.replace('~1','/').replace('~0','~')
        try:
            if isinstance(value,list):
                if not key.isdigit() or len(key)>1 and key.startswith('0'):raise ValueError('invalid pointer index')
                value=value[int(key)]
            elif isinstance(value,dict):value=value[key]
            else:raise ValueError('pointer traverses scalar')
        except (IndexError,KeyError):raise ValueError('unresolved working pointer') from None
    return value


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
