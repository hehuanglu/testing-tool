"""W7 UI diagnostic contract. Reuses W6 manifest/decimal state oracle.

A browser functional pass never enables protected execution or G8 operational.
The available native-style browser session path is tested with synthetic canaries.
"""
import json
import re
from jsonschema import Draft202012Validator
from .business import digest, indexed, transition, initial_state, validate_manifest, money
from .product_adapter import ProductAdapter
from .evidence import EvidenceInvalid

VERSION='w7-owned-ui-diagnostic-1'


def ui_steps(fixture, spike=False):
    _,resources=indexed(fixture);account=next(r for r in resources.values() if r['kind']=='account' and r['ownerActorRef']=='A' and not r['initial']['exists'])
    category=next(r for r in resources.values() if r['kind']=='category' and r['ownerActorRef']=='A')
    def operation(step,action,actor,op,values=None):
        return {'stepId':step,'action':action,'actorRef':actor,'case':{'caseId':step,'actorRef':actor,
                'operation':op,'resourceRef':account['resourceRef'],'input':values or {}}}
    steps=[{'stepId':'login-A','action':'login','actorRef':'A'}]
    if spike:return steps
    steps += [operation('create-account','create','A','account.create'),
              operation('owner-positive','read','A','account.read'),
              operation('ui-expense','expense','A','expense',{'categoryRef':category['resourceRef'],'amount':'7.1234'}),
              operation('balance-before-reload','read','A','account.read'),
              operation('balance-after-reload','reload','A','account.read'),
              {'stepId':'logout-A','action':'logout','actorRef':'anonymous'},
              {'stepId':'login-B','action':'login','actorRef':'B'},
              operation('denied-read-B','read','B','account.read'),
              operation('denied-write-B','update','B','account.update',{'name':'Unauthorized W7 change','balance':'999.0001'}),
              {'stepId':'logout-B','action':'logout','actorRef':'anonymous'},
              {'stepId':'login-A-again','action':'login','actorRef':'A'},
              operation('owner-final-state','read','A','account.read')]
    return steps


def public_config(fixture):
    actors,resources=indexed(fixture);steps=ui_steps(fixture);target=resources[steps[1]['case']['resourceRef']]
    cat=resources[steps[3]['case']['input']['categoryRef']]
    return {'runId':fixture['runId'],'alternate':fixture['adapter']=='alternate-ledger',
            'accountId':target['wireId'],'categoryId':cat['wireId'],'accountName':target['initial']['name'],
            'openingBalance':money(target['initial']['balanceMinor']),
            'actors':{a:{'subject':actors[a]['subject'],'email':a+'@w7.invalid'} for a in ('A','B')}}


def audit_ui(plan,fixture,observations,arrivals,secret_audit,cleanup):
    from .contracts import ROOT
    schema=json.loads((ROOT/'schemas/remediation/ui-plan.schema.json').read_text())
    if list(Draft202012Validator(schema).iter_errors(plan)):raise EvidenceInvalid('invalid_ui_plan_schema')
    validate_manifest(fixture)
    if (plan.get('contractVersion')!=VERSION or plan.get('mode')!='owned-synthetic-ui-diagnostic'
            or plan.get('fixtureHash')!=digest(fixture) or plan.get('runId')!=fixture['runId']
            or plan.get('steps')!=ui_steps(fixture,plan['scope']=='session-spike')
            or plan.get('fidelity')!='owned-synthetic-source-derived-ui'
            or plan.get('securityApproval') is not False):
        raise EvidenceInvalid('ui_plan_or_fixture_binding')
    if observations['evidenceKind']!=plan['evidenceKind']:raise EvidenceInvalid('ui_evidence_kind_binding')
    actual_browser=plan['evidenceKind']=='actual-webdriver'
    runtime=observations['runtime']
    if (runtime['name']!=plan['containerName'] or runtime['image']!=plan['image']
            or runtime['runId']!=plan['runId'] or runtime['networkMode']!='none'
            or runtime['readOnlyRoot'] is not True or runtime['profileVolume']!=plan['profileVolume']
            or runtime['memoryBytes']!=768*1024**2 or runtime['memorySwapBytes']!=768*1024**2
            or runtime['capDrop']!=['ALL'] or runtime['pidsLimit']!=256):
        raise EvidenceInvalid('ui_runtime_binding')
    if (observations['browserCleanupError'] is not False or observations['browser']['browserName']!='firefox'
            or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)*',observations['browser']['browserVersion'])
            or not re.fullmatch('[0-9a-f]{64}',observations['driverPin']['driverSha256'])):
        raise EvidenceInvalid('ui_browser_execution_or_cleanup_proof')
    if cleanup['runtime']!=runtime or cleanup['containerRemoved'] is not True or cleanup['volumeRemoved'] is not True:
        raise EvidenceInvalid('ui_cleanup_binding')
    if cleanup['rawProfileRetention']!='private-outside-workspace' or not cleanup['privateProfileIndexSha256']:
        raise EvidenceInvalid('ui_profile_quarantine_not_preserved')
    if (secret_audit['scope']!='browser-profile-diagnostic-only' or secret_audit['sourceValuesIncluded'] is not False
            or secret_audit['requiredOperationalPairs']!=143 or secret_audit['operationalG3']!='blocked'
            or not secret_audit['fingerprints'] or secret_audit['sourceControlMisses']!=0
            or secret_audit['browserClosedBeforeAudit'] is not True):
        raise EvidenceInvalid('ui_secret_scope_or_source_controls')
    from .opaque_canary import OpaqueCanaryAuditor
    OpaqueCanaryAuditor(secret_audit['fingerprints'])
    if actual_browser and (type(secret_audit['profileMatches']) is not int
            or secret_audit['profileMatches']!=sum(r['matched'] is True for r in secret_audit['profileFiles'])):
        raise EvidenceInvalid('ui_profile_match_inventory')
    persistence=secret_audit['profileMatches']>0
    if secret_audit['profileVerdict']!=('fail' if persistence else 'blocked'):
        raise EvidenceInvalid('ui_secret_verdict_disagrees_with_profile_readback')
    receipts={r['requestId']:r for r in arrivals}
    if len(receipts)!=len(arrivals) or [r['sequence'] for r in arrivals]!=list(range(1,len(arrivals)+1)):
        raise EvidenceInvalid('ui_arrival_inventory')
    planned={s['stepId']:s for s in plan['steps']};rows=observations['steps']
    if len(rows)>len(planned) or [r['stepId'] for r in rows]!=list(planned)[:len(rows)]:
        raise EvidenceInvalid('ui_step_inventory_or_order')
    actors,resources=indexed(fixture);adapter=ProductAdapter(fixture)
    state=initial_state(fixture);results=[];used=set();last_seq=0;owner_positive=False;app_violation=False;epochs={}
    for row in rows:
        spec=planned[row['stepId']];reasons=[];missing=[];security=[]
        if row['actorRef']!=spec['actorRef'] or row['action']!=spec['action']:
            raise EvidenceInvalid('ui_actor_or_action_binding')
        expected_commands=command_kinds(spec['action'])
        if row['commandKinds']!=expected_commands:
            if not row['errorCode'] or row['commandKinds']!=expected_commands[:len(row['commandKinds'])]:raise EvidenceInvalid('ui_missing_semantic_browser_actions')
            missing.append('ui_action_incomplete')
        dom=row['dom']
        if dom['alertPresent']:reasons.append('visible_ui_error')
        if row['errorCode']:missing.append(row['errorCode'])
        if digest(row['preState'])!=digest(state):security.append('ui_pre_state_violated')
        found=[]
        for rid in row['requestIds']:
            rec=receipts.get(rid)
            if not rec or rid in used or rec['sequence']<=last_seq:raise EvidenceInvalid('ui_missing_reused_or_reordered_arrival')
            used.add(rid);last_seq=rec['sequence'];found.append(rec)
            if (rec['runId']!=plan['runId'] or rec['source']!='target' or 'Firefox/' not in rec['userAgent']
                    or rec['origin']!='http://127.0.0.1:18080'):
                raise EvidenceInvalid('ui_target_or_browser_provenance')
        action=spec['action']
        if action=='login':
            if len(found)!=2:missing.append('login_and_identity_requests_missing')
            else:
                login,identity=found
                if (login['action']!='login' or login['actorRef']!=spec['actorRef'] or login['status']!=200
                        or login['request']!={'method':'POST','path':'/api/auth/login','body':{'credentialRef':spec['actorRef']}}
                        or identity['action']!='identity' or identity['actorRef']!=spec['actorRef'] or identity['status']!=200
                        or identity['request']!={'method':'GET','path':'/__w7/identity','body':None}
                        or identity['body']['subject']!=actors[spec['actorRef']]['subject']
                        or identity['body']['actorRef']!=spec['actorRef'] or login['body']!=identity['body']):
                    raise EvidenceInvalid('ui_login_identity_binding')
                epoch=identity['body']['authEpoch']
                if type(epoch) is not int or epoch<=epochs.get(spec['actorRef'],0):raise EvidenceInvalid('ui_auth_epoch_not_advanced')
                epochs[spec['actorRef']]=epoch
                if dom['requestId']!=identity['requestId']:raise EvidenceInvalid('ui_dom_request_correlation')
            if dom['actorRef']!=spec['actorRef'] or dom['subject']!=str(actors[spec['actorRef']]['subject']) or not dom['passwordCleared']:
                reasons.append('ui_login_identity_or_password_clear_failed')
        elif action=='logout':
            if found:raise EvidenceInvalid('unexpected_logout_network_request')
            if dom['actorRef']!='anonymous' or not dom['loginVisible']:reasons.append('ui_actor_switch_not_observed')
        else:
            c=spec['case'];status,expected=transition(fixture,state,c)
            if action=='reload':
                if len(found)==2:
                    identity,operation=found
                    if (identity['action']!='identity' or identity['actorRef']!=spec['actorRef'] or identity['status']!=200
                            or identity['request']!={'method':'GET','path':'/__w7/identity','body':None}
                            or identity['body']!={'actorRef':spec['actorRef'],'subject':actors[spec['actorRef']]['subject'],
                                                 'authEpoch':epochs.get(spec['actorRef'])}
                            or identity['authEpoch']!=epochs.get(spec['actorRef'])
                            or identity['preStateSha256']!=digest(row['preState'])
                            or identity['postStateSha256']!=digest(row['preState'])):
                        raise EvidenceInvalid('ui_reload_identity_binding')
                    found=[operation]
                else:missing.append('ui_reload_identity_and_read_missing')
            if len(found)!=1:missing.append('ui_operation_not_sent')
            else:
                rec=found[0]
                if (rec['request']!=adapter.request(c) or rec['actorRef']!=spec['actorRef']
                        or rec['action']!=('read' if action=='reload' else action)
                        or rec['authEpoch']!=epochs.get(spec['actorRef'])):
                    raise EvidenceInvalid('ui_wire_actor_resource_binding')
                if dom['requestId']!=rec['requestId'] or dom['status']!=rec['status']:
                    raise EvidenceInvalid('ui_dom_response_correlation')
                if rec['status']!=status:security.append('ui_response_status_violated')
                security.extend(adapter.check_response(c,rec['status'],rec['body'],status,expected))
                if status>=400 and not owner_positive:missing.append('missing_ui_owner_positive')
                if c['operation']=='account.read' and spec['actorRef']=='A' and rec['status']==200:
                    if dom['accountId']!=str(resources[c['resourceRef']]['wireId']) or dom['balance']!=money(expected['resources'][c['resourceRef']]['balanceMinor']):
                        reasons.append('ui_balance_or_resource_render_mismatch')
                    else:owner_positive=True
                if spec['actorRef']=='B' and (dom['accountId'] or dom['balance']):security.append('ui_denial_disclosed_account')
                if action=='reload' and row['navigation']!='webdriver-refresh':raise EvidenceInvalid('ui_reload_not_executed')
                if rec['preStateSha256']!=digest(row['preState']) or rec['postStateSha256']!=digest(row['postState']):
                    raise EvidenceInvalid('ui_independent_readback_disagreement')
            if len(found)==1:state=expected
        if action in ('login','logout'):
            expected=state
            for rec in found:
                if rec['preStateSha256']!=digest(row['preState']) or rec['postStateSha256']!=digest(row['postState']):
                    raise EvidenceInvalid('ui_identity_readback_disagreement')
        if digest(row['postState'])!=digest(state):security.append('ui_post_state_violated')
        app_violation|=bool(security)
        outcome='fail' if reasons or security else 'inconclusive' if missing else 'pass'
        results.append({'stepId':spec['stepId'],'outcome':outcome,'proofComplete':not missing,
                        'reasons':sorted(set(reasons+security+missing))})
    if used!=receipts.keys():raise EvidenceInvalid('ui_unreferenced_arrival')
    complete=len(rows)==len(planned) and all(r['proofComplete'] for r in results)
    counts={x:sum(r['outcome']==x for r in results) for x in ('pass','fail','inconclusive')}
    functional='not_run' if plan['scope']=='session-spike' else 'fail' if counts['fail'] else 'inconclusive' if not complete else 'pass'
    return {'contractVersion':VERSION,'runId':plan['runId'],'scope':plan['scope'],
            'executionStatus':'completed' if len(rows)==len(planned) and not any(r['errorCode'] for r in rows) else 'timed_out' if any(r['errorCode']=='ui_deadline' for r in rows) else 'failed',
            'evidenceStatus':'complete' if complete else 'incomplete','evidenceKind':plan['evidenceKind'],
            'browserRuntimeVerified':actual_browser,'oracleContractVerdict':functional,
            'functionalVerdict':functional if actual_browser else 'not_run',
            'applicationVerdict':'fail' if app_violation else 'inconclusive' if not complete else 'pass',
            'secretVerdict':('fail' if persistence else 'inconclusive') if actual_browser else 'not_evaluated',
            'securityVerdict':('fail' if persistence or app_violation else 'inconclusive') if actual_browser else 'not_evaluated',
            'cleanupStatus':'clean-private-evidence-retained','gateDecision':'block','G8Operational':'blocked',
            'fidelity':plan['fidelity'],'canonicalOriginVerified':False,'productRuntimeVerified':False,
            'securityApproval':False,'R1Admitted':False,'R2Admitted':False,'stepCounts':counts,
            'requiredSteps':len(planned),'observedSteps':len(rows),'assertions':results,
            'limitations':['Browser profile canary diagnosis does not cover all 143 required operational sink/lifecycle pairs.',
                           'Owned source-derived UI only; finalsource runtime and canonical TLS/CORS/cookie/CSRF remain unverified.',
                           'Client logout is a UI actor-switch control, not server revocation.']}


def command_kinds(action):
    return {'login':['fill-email','fill-password-private','click-sign-in'],
            'create':['fill-account-name','fill-opening-balance','click-create'],
            'expense':['fill-account-id','fill-amount','click-expense'],
            'read':['fill-account-id','click-read'],
            'update':['fill-account-id','fill-update-name','fill-update-balance','click-update'],
            'reload':['webdriver-refresh'],'logout':['click-logout']}[action]
