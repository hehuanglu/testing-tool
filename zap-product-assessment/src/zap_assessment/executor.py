import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from .contracts import Blocked,Plan,Scope,canonical,check_authority,utcnow,validate,validate_locked_plan
from .evidence import EvidenceInvalid,SecretLeak,decide,publish,read_report,write_file
from .journal import Journal,Ownership
from .transport import LostAck

def implementation_digest():
    from .contracts import ROOT,digest
    files=sorted([*ROOT.glob('src/**/*.py'),*ROOT.glob('src/**/*.java'),*ROOT.glob('schemas/**/*.json'),*ROOT.glob('profiles/*.json')])
    return 'sha256:'+digest({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})

class InjectedCrash(BaseException): pass

class Executor:
    def __init__(self,run_root,runtime_factory,scanner_factory,clock=time.monotonic,sleep=time.sleep,safety_factory=None):
        self.root=Path(run_root); self.runtime_factory=runtime_factory; self.scanner_factory=scanner_factory
        self.clock=clock; self.sleep=sleep; self.safety_factory=safety_factory
    def run(self,plan,run_id=None,interrupt_after_start=False):
        validate_locked_plan(plan)
        from .evidence import secret_check
        secret_check(plan.encoded)
        p=plan.data['product']; w=plan.data['workflow']; a=plan.data['authority']
        # No directory, lock, scanner or network for invalid/expired plans.
        check_authority(a,p,w)
        run_id=run_id or 'r'+uuid.uuid4().hex
        if not run_id.replace('-','').isalnum() or len(run_id)>90: raise Blocked('invalid run ID')
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        folder=self.root/run_id; folder.mkdir(mode=0o700)
        stage=folder/'staging'; stage.mkdir(mode=0o700)
        write_file(stage,'plan.json',plan.encoded)
        j=Journal(folder/'journal.jsonl',run_id,plan.hash)
        lock=Ownership(folder/'ownership.lock',run_id); lock.acquire()
        from .safety_io import ReservedStop
        reserve=ReservedStop(folder/'stop-reserve.bin',run_id,plan.hash)
        rt=None
        safety=None; provision_attempted=False
        source_digest=implementation_digest()
        start=utcnow().isoformat(); total=self.clock()+w['budgets']['total']; operation_ids=[]; owned_operations=[]; observed=[]
        provenance={}; evidence='incomplete'; execution='running'; cleanup='pending'; warnings=[]; coverage=False; untriaged=False; result_artifacts=[]
        scope=Scope(p['attackOrigins'],a['resolvedAddresses']); target=p['attackOrigins'][0]
        def budget(phase): return min(total,self.clock()+w['budgets'][phase])
        def check(deadline):
            if safety is not None:safety.checkpoint()
            check_authority(a,p,w)
            if hasattr(rt,'assert_binding'): rt.assert_binding()
            if self.clock()>=deadline: raise TimeoutError('phase/total deadline exceeded')
        def intent(action,data):
            if hasattr(rt,'set_phase'):rt.set_phase({'start-crawl':'crawl','start-active':'active','import-openapi':'import','report-generate':'report'}.get(action,action))
            check(total); return j.append('intent',{'action':action,'attemptId':uuid.uuid4().hex,**data})
        try:
            rt=self.runtime_factory(run_id,folder,j);rt.plan=plan;rt.stop_reserve=reserve
            if w['active']:
                from .observed import ObservedDockerRuntime
                if not isinstance(rt,ObservedDockerRuntime):raise Blocked('active fixture observer required')
            rt.stop_timeout=w['budgets']['stop'];rt.runtime_baseline=plan.data['runtime']
            for state in ['PROFILE_VALIDATED','PLAN_LOCKED']: j.transition(state)
            if self.safety_factory is not None:
                safety=self.safety_factory(rt,j);safety.preflight()
            if hasattr(rt,'preflight'): rt.preflight()
            j.transition('PREFLIGHT_PASSED')
            intent('provision',{'createdByRun':run_id});provision_attempted=True
            provenance=rt.provision(); rt.wait_health(min(120,w['budgets']['total']))
            scanner=self.scanner_factory(rt)
            provenance.update(scanner.initialize() if hasattr(scanner,'initialize') else {})
            provenance['engine']=scanner.health()
            if provenance['engine'].get('version') not in ('fake',plan.data['runtime']['zapVersion']): raise Blocked('engine version drift')
            write_file(folder,'capabilities.json',canonical(provenance))
            intent('rate-policy',{}); provenance['rateLimit']=rt.configure_rate(w['maxRate'])
            if safety is not None:safety.start()
            j.transition('RESOURCES_READY'); j.transition('RUNNING')
            scope.check(target+p['healthPath']); intent('health',{'path':p['healthPath']})
            health=(rt.target_request if hasattr(rt,'target_request') else rt.request)(target+p['healthPath'])
            health_data=json.loads(health['body'])
            if p['schemaVersion']=='1.1':
                from .binding import assertions_match
                if health['status']!=200: raise Blocked('target health status mismatch')
                health_data={'status':200,'bodySha256':hashlib.sha256(health['body'].encode()).hexdigest(),'assertions':assertions_match(health_data,p['healthAssertions'])}
            elif health['status']!=200 or health_data.get('build')!=p['targetBuildRef'] or health_data.get('productId')!=p['productId']: raise Blocked('target identity/build/health mismatch')
            result_artifacts.append(write_file(stage,'health.json',canonical(health_data)))
            for kind in ['crawl']+(['active'] if w['active'] else []):
                check(total); crawl_target=target+p.get('crawlPath',''); scope.check(crawl_target); intent('start-'+kind,{'target':crawl_target})
                # Direct upstream ignores idempotency keys; never retry this call.
                op=scanner.start(kind,crawl_target); operation_ids.append(op); owned_operations.append((kind,op)); j.append('ack',{'action':'start-'+kind,'operationId':op})
                if interrupt_after_start: raise InjectedCrash(run_id)
                deadline=budget(kind)
                while True:
                    check(deadline)
                    if scanner.status(kind,op): break
                    self.sleep(w['budgets']['poll'])
                j.append('terminal',{'kind':kind,'operationId':op})
            intent('import-openapi',{'schemaHash':plan.data['schemaHash']})
            if p['schemaVersion']=='1.1': scanner.import_content(canonical(plan.data['schema']).decode(),target)
            else:
                scope.check(target+'/openapi.json'); scanner.import_schema(target+'/openapi.json',target)
            j.append('ack',{'action':'import-openapi'})
            for op in p['expectedOperations']:
                url=target+op['path']; scope.check(url); intent('seed',{'method':op['method'],'path':op['path']})
                response=scanner.seed(url)
                # Response assertion belongs to this seed request through this session.
                try:
                    message=response['sendRequest'][0]; status=int(message['responseHeader'].splitlines()[0].split()[1])
                except (KeyError,IndexError,ValueError,TypeError) as e: raise Blocked('seed response contract') from e
                observed.append({**op,'status':status,'actor':'anonymous','phase':'seed','assertion':status==op['status']})
                j.append('ack',{'action':'seed','path':op['path'],'status':status})
            coverage=len(observed)==len(p['expectedOperations']) and all(x['assertion'] for x in observed)
            if not coverage: raise Blocked('required operation assertion failed')
            if hasattr(rt,'set_phase'):rt.set_phase('settle')
            j.transition('SETTLING'); deadline=budget('settle'); stable=0
            while stable<w['stableObservations']:
                check(deadline); complete=scanner.passive(); stable=stable+1 if complete else 0
                j.append('passive-observation',{'complete':complete,'stableCount':stable})
                if stable<w['stableObservations']: self.sleep(w['budgets']['poll'])
            j.transition('VERIFYING')
            # All producers are terminal; exclusive namespace/session remains held during export.
            intent('report-generate',{'scope':target}); path=scanner.report(target)
            def bounded_chunk(path,offset,sha):
                check(total); return scanner.chunk(path,offset,sha)
            report=read_report(bounded_chunk,path,w['maxArtifactBytes'])
            from .evidence import secret_check
            secret_check(report); report_data=json.loads(report)
            # Structured JSON report contains alert risk codes. Unknown parser shape blocks success.
            sites=report_data.get('site')
            if not isinstance(sites,list): raise EvidenceInvalid('report site contract')
            if not sites: raise EvidenceInvalid('report lacks scoped site')
            for site in sites:
                if not isinstance(site,dict) or not isinstance(site.get('alerts'),list): raise EvidenceInvalid('report alerts contract')
                if 'name' not in site and '@name' not in site: raise EvidenceInvalid('report site identity absent')
                site_url=site.get('@name',site.get('name'))
                from .contracts import origin
                if origin(site_url)!=target or urlsplit(site_url).path not in ('','/'): raise EvidenceInvalid('report belongs to another target')
                for alert in site['alerts']:
                    risk=alert.get('riskcode')
                    if str(risk) not in {'0','1','2','3'}: raise EvidenceInvalid('unknown alert risk')
                    if int(risk)>=2: untriaged=True
            observations=rt.observations()
            if observations['forbiddenRequests']!=0: raise Blocked('forbidden egress observed')
            for name,data in [('report.json',report),('coverage.json',canonical({'expected':p['expectedOperations'],'observed':observed,'phases':['seed'],'limitations':['No authenticated or active-rule coverage claim']})),('findings.json',canonical(scanner.findings(target+p.get('crawlPath','')))),('network.json',canonical(observations)),('report-readback.json',canonical({'bytes':len(report),'sha256':hashlib.sha256(report).hexdigest(),'pages':getattr(scanner,'chunk_observations',[])}))]: result_artifacts.append(write_file(stage,name,data))
            for artifact in result_artifacts: secret_check((stage/artifact['path']).read_bytes())
            secret_check(plan.encoded); secret_check(j.path.read_bytes())
            if safety is not None:
                safety_result=safety.finish()
                write_file(folder,'pre-cleanup-safety.json',canonical(safety_result))
                provenance['runtimeSafety']={'contractHash':safety.expected_hash,**safety_result}
            evidence='complete'; execution='completed'
            # Cleanup is part of the outcome, and is recorded before manifest publication.
            rt.cleanup(); cleanup='clean'
            if safety is not None:
                if hasattr(safety,'cleanup_complete'):safety.cleanup_complete()
                write_file(folder,'runtime-safety.json',canonical(safety_result))
            if hasattr(rt,'closure_evidence'):result_artifacts.append(write_file(stage,'traffic-closure.json',canonical(rt.closure_evidence)))
            if hasattr(rt,'binding_evidence'): result_artifacts.append(write_file(stage,'binding.json',canonical(rt.binding_evidence())))
            lock.release()
            j.transition('EVIDENCE_READY')
            result_artifacts.extend([{'path':'plan.json','bytes':len(plan.encoded),'sha256':plan.hash},write_file(stage,'journal.jsonl',j.path.read_bytes())])
            verdict,gate,exit_code=decide(execution,evidence,cleanup,coverage,untriaged=untriaged)
            statuses={'executionStatus':execution,'evidenceStatus':evidence,'securityVerdict':verdict,'cleanupStatus':cleanup,'gateDecision':gate}
            tracks=[{'track':t,**statuses,'expected':p['expectedOperations'],'observed':observed,'warnings':warnings} for t in w['requiredTracks']]
            if implementation_digest()!=source_digest: raise Blocked('orchestration source drift during run')
            manifest={'initiator':a['approvalRef'],'schemaVersion':p['schemaVersion'],'runId':run_id,'planHash':plan.hash,'startedAt':start,'endedAt':utcnow().isoformat(),'targetBuildRef':p['targetBuildRef'],'sourceRefs':{'orchestrator':source_digest,'mcp':plan.data['runtime']['mcpSourceRef']},'provenance':provenance,'scope':p['attackOrigins'],'ownership':{'createdByRun':run_id,'borrowed':[p['binding']] if p['schemaVersion']=='1.1' else [],'cleanupVerified':True},'operationIds':operation_ids,'tracks':tracks,**statuses,'artifacts':result_artifacts,'retentionDays':p['retentionDays'],'reviewReferences':[],'limitations':plan.data['limitations']}
            publish(stage,folder/'bundle',manifest)
            j.transition('FINALIZED')
            reserve.record({'state':'finalized','cleanupStatus':cleanup,'stopUnconfirmed':False});reserve.close()
            return {**statuses,'runId':run_id,'exitCode':exit_code,'bundle':str(folder/'bundle')}
        except InjectedCrash:
            if safety is not None:safety.close()
            reserve.record({'state':'interrupted','cleanupStatus':'pending','stopUnconfirmed':True});reserve.close()
            raise
        except (Exception,KeyboardInterrupt) as error:
            execution='timed_out' if isinstance(error,TimeoutError) else 'cancelled' if isinstance(error,KeyboardInterrupt) else 'failed'
            evidence='invalid' if isinstance(error,(EvidenceInvalid,json.JSONDecodeError)) else 'incomplete'
            # Persist only error type; raw exceptions/tool data can contain target-controlled text.
            j.emergency=True
            journal_append=j.append
            def emergency(kind,data):
                try:return journal_append(kind,data)
                except (OSError,ValueError):j.io_failed=True;return None
            j.append=emergency
            if safety is not None:
                try:safety.close()
                except Exception:pass
            emergency('failure',{'type':type(error).__name__})
            if 'scanner' in locals() and hasattr(scanner,'mcp') and hasattr(scanner.mcp,'last_response'):
                from .evidence import secret_check
                diagnostic=canonical(scanner.mcp.last_response)
                try:
                    secret_check(diagnostic); write_file(folder,'fixture-tool-diagnostic.json',diagnostic)
                except (EvidenceInvalid,OSError): pass
            if j.state!='STOPPING':
                emergency('state',{'state':'STOPPING'});j.state='STOPPING'
            try:
                if not provision_attempted and not getattr(rt,'created',[]):
                    cleanup='clean';lock.release()
                elif safety is not None and (safety.stop_confirmed is False or (safety.thread is not None and safety.thread.is_alive())):
                    raise Blocked('safety stop unconfirmed; retain owned resources')
                elif isinstance(error,SecretLeak) and cleanup!='clean':
                    rt.terminate(); cleanup='retained_by_policy'; lock.quarantine(); j.append('quarantine',{'secretIntegrity':False,'publicExport':False})
                elif cleanup!='clean':
                    stop_deadline=time.monotonic()+w['budgets']['stop']
                    for kind,op in owned_operations:
                        if time.monotonic()>=stop_deadline:break
                        emergency('intent',{'action':'cancel-own-operation','kind':kind,'operationId':op})
                        try:
                            scanner.stop(kind,op); emergency('ack',{'action':'cancel-own-operation','operationId':op})
                        except Exception:
                            emergency('cancel-unconfirmed',{'operationId':op,'fallback':'stop-dedicated-engine'})
                    # Runtime ownership/stop must work even if its own journal
                    # append call keeps failing; original intents remain in memory.
                    rt.stop_timeout=max(.1,stop_deadline-time.monotonic())
                    rt.cleanup(); cleanup='clean'; lock.release()
            except Exception:
                cleanup='incomplete'
                try:lock.quarantine()
                except (OSError,ValueError):pass
                emergency('quarantine',{'stopUnconfirmed':True,'retainedOwnership':True})
            emergency('state',{'state':'FINALIZED_WITH_ERROR'});j.state='FINALIZED_WITH_ERROR'
            result={'runId':run_id,'executionStatus':execution,'evidenceStatus':evidence,'securityVerdict':'inconclusive','cleanupStatus':cleanup,'gateDecision':'block','exitCode':2,'reason':type(error).__name__}
            if j.io_failed: result['evidenceStatus']='invalid'; result['reason']='journal-write-failure'
            # A failure after the publication rename must not leave a complete
            # namespace that the caller could mistake for a successful result.
            if (folder/'bundle').exists():
                try:os.rename(folder/'bundle',folder/'quarantined-publication')
                except OSError:result['publicationStatus']='quarantine-unconfirmed'
            try:reserve.record({'state':'failed','cleanupStatus':cleanup,'stopUnconfirmed':cleanup!='clean','reason':result['reason'],'secretIntegrity':not isinstance(error,SecretLeak)})
            except OSError:result['reservedStopRecord']='write-unconfirmed'
            finally:reserve.close()
            try: write_file(folder,'failure.json',canonical(result))
            except OSError: pass
            try:
                partial=folder/'partial-evidence';partial.mkdir(mode=0o700)
                write_file(partial,'status.json',canonical(result))
                write_file(partial,'journal-prefix.jsonl',b''.join(canonical(e)+b'\n' for e in j.events))
            except OSError:pass
            return result

    def recover(self,folder):
        """Conservative recovery: reconcile deterministic resource IDs and stop own namespace.

        Never resume/reissue a scan or schema import without direct idempotency support.
        """
        folder=Path(folder); raw=(folder/'staging'/'plan.json').read_bytes(); plan=Plan(raw); p=plan.data['product']; w=plan.data['workflow']
        validate('normalized-plan',plan.data)
        original=Journal(folder/'journal.jsonl',folder.name,plan.hash,allow_partial_tail=True)
        lock=Ownership(folder/'ownership.lock',folder.name); lock.check()
        if any(e['kind']=='quarantine' and e['data'].get('secretIntegrity') is False for e in original.events): raise Blocked('secret-integrity quarantine requires owner incident disposition')
        from .safety_io import atomic_bytes
        from .safety_io import ReservedStop
        if (folder/'stop-reserve.bin').exists():
            record=ReservedStop.read(folder/'stop-reserve.bin')
            if record['runId']!=folder.name or record['planHash']!=plan.hash:raise Blocked('reserved recovery identity mismatch')
            if record['data'].get('secretIntegrity') is False:raise Blocked('secret-integrity quarantine requires owner incident disposition')
        recovery_path=folder/('recovery-journal-'+uuid.uuid4().hex+'.jsonl')
        atomic_bytes(recovery_path,b''.join(canonical(e)+b'\n' for e in original.events))
        j=Journal(recovery_path,folder.name,plan.hash)
        j.append('recovery-source',{'originalJournalSha256':hashlib.sha256(original.path.read_bytes()).hexdigest(),'partialTailDiscardedForRecoveryOnly':original.partial_tail})
        rt=self.runtime_factory(folder.name,folder,j); rt.plan=plan; rt.stop_timeout=w['budgets']['stop']
        j.transition('STOPPING',recovery=True)
        j.append('reconcile',{'mode':'stop-only','scanReplay':False,'planHash':plan.hash})
        try: rt.cleanup(); lock.release(verified_cleanup=True); cleanup='clean'
        except Exception: lock.quarantine(); cleanup='incomplete'; j.append('quarantine',{'stopUnconfirmed':True})
        j.transition('FINALIZED_WITH_ERROR')
        result={'runId':folder.name,'executionStatus':'cancelled','evidenceStatus':'incomplete','securityVerdict':'inconclusive','cleanupStatus':cleanup,'gateDecision':'block','exitCode':2,'reason':'interrupted-run-reconciled-stop-only'}
        name='recovery.json' if not (folder/'recovery.json').exists() else 'recovery-'+uuid.uuid4().hex+'.json'
        write_file(folder,name,canonical(result)); return result
