"""W6 offline verification with existing safe BundleReader and pure state replay.

The target implementation is independent. The external plan pin anchors fixture,
source and image; local receipts are synthetic evidence, not signed attestation.
"""
import hashlib
from .business import VERSION, validate_manifest, expected_states, digest, indexed, transition
from .contracts import canonical
from .evidence import EvidenceInvalid
from .product_adapter import ProductAdapter
from .verification import BundleReader, strict_json


def audit_business(plan, fixture, observations, arrivals, cleanup):
    validate_manifest(fixture)
    if (plan.get('contractVersion') != VERSION or plan.get('mode') != 'owned-synthetic-business'
            or plan.get('fixtureHash') != digest(fixture) or plan.get('runId') != fixture['runId']
            or plan.get('securityApproval') is not False or not plan.get('sourcePins')):
        raise EvidenceInvalid('business_plan_binding')
    runtime=observations['runtime']
    if (runtime['name'] != plan['containerName'] or runtime['image'] != plan['image']
            or runtime['runId'] != plan['runId'] or runtime['networkMode'] != 'none'
            or not runtime['id'] or runtime['readOnlyRoot'] is not True):
        raise EvidenceInvalid('business_runtime_binding')
    if (cleanup['runtime'] != runtime or cleanup['cleanupStatus'] != 'clean' or cleanup['removed'] is not True):
        raise EvidenceInvalid('business_cleanup_binding')
    cases={c['caseId']:c for c in fixture['transitions']}
    if len(observations['cases']) != len(cases) or [r['caseId'] for r in observations['cases']] != list(cases):
        raise EvidenceInvalid('business_case_inventory_or_order')
    receipts={a['requestId']:a for a in arrivals}
    if len(receipts)!=len(arrivals) or [a['sequence'] for a in arrivals] != list(range(1,len(arrivals)+1)):
        raise EvidenceInvalid('business_arrival_identity_or_order')
    used=set();adapter=ProductAdapter(fixture);actors,resources=indexed(fixture)
    results=[];prior={};last_sequence=0

    def exchange(row, actor, request, identity=False):
        nonlocal last_sequence
        rid=row['requestId'];receipt=receipts.get(rid)
        if not receipt or rid in used or receipt['sequence']<=last_sequence:
            raise EvidenceInvalid('business_missing_reused_or_reordered_arrival')
        used.add(rid);last_sequence=receipt['sequence']
        if (row['actorRef']!=actor or row['request']!=request or receipt['actorRef']!=actor
                or receipt['request']!=request or receipt['status']!=row['status'] or receipt['body']!=row['body']):
            raise EvidenceInvalid('business_actor_resource_or_wire_binding')
        if identity and (row['status'] != 200 or row['body'] != {'actorRef':actor,'subject':actors[actor]['subject']}):
            raise EvidenceInvalid('business_identity_unconfirmed')
        return receipt

    for row, (c,status,before,after) in zip(observations['cases'],expected_states(fixture),strict=True):
        reasons=[];missing=[];r=resources[c['resourceRef']]
        identity_req={'method':'GET','path':'/__w6/identity','body':None}
        exchange(row['ownerIdentity'],r['ownerActorRef'],identity_req,True)
        probe=adapter.owner_probe(c)
        # Absent create fixtures have owner list/absence positive controls.
        if not before['resources'][c['resourceRef']]['exists']:
            probe['operation']=r['kind']+'.list'
        control=row.get('ownerPositive')
        if control is None: missing.append('missing_owner_positive')
        else:
            ex=exchange(control,r['ownerActorRef'],adapter.request(probe))
            expected_control,_=transition(fixture,before,probe)
            if control['status'] != 200 or expected_control != 200:
                missing.append('owner_positive_unsuccessful')
            else:
                if adapter.check_response(probe,control['status'],control['body'],200,before):missing.append('owner_positive_not_confirmed')
            if ex['preStateSha256'] != digest(row['preState']) or ex['postStateSha256'] != digest(row['preState']):
                reasons.append('owner_control_changed_state')
        exchange(row['identity'],c['actorRef'],identity_req,True)
        main=exchange(row['exchange'],c['actorRef'],adapter.request(c))
        # independent file readbacks must agree with target arrival snapshots.
        if main['preStateSha256'] != digest(row['preState']) or main['postStateSha256'] != digest(row['postState']):
            raise EvidenceInvalid('business_readback_arrival_disagreement')
        if digest(row['preState']) != digest(before):reasons.append('initial_or_transition_pre_state_violated')
        if digest(row['postState']) != digest(after):reasons.append('post_state_oracle_violated')
        if row['exchange']['status'] != status:reasons.append('response_status_violated')
        reasons.extend(adapter.check_response(c,row['exchange']['status'],row['exchange']['body'],status,after))
        # Every rejected main request needs a previous successful same-operation control.
        # Destructive delete and implicit-owner create use an explicit same-owner sibling;
        # the requested resource still has a fresh resource-specific owner probe above.
        if status >= 400:
            pos=prior.get(c.get('positiveCaseId'))
            if not pos or pos['outcome']!='pass' or pos['status']>=400:
                missing.append('missing_successful_operation_positive')
            elif (pos['case']['operation']!=c['operation'] or pos['case']['actorRef']!=r['ownerActorRef']
                    or c['operation'] not in ('account.create','account.delete') and pos['case']['resourceRef']!=c['resourceRef']):
                raise EvidenceInvalid('business_operation_positive_binding')
        if row['expectedPostStateSha256'] != digest(after):
            raise EvidenceInvalid('business_declared_delta_disagrees_with_replay')
        # Observed violations survive incomplete controls and remain fail.
        outcome='fail' if reasons else 'inconclusive' if missing else 'pass'
        result={'caseId':c['caseId'],'operation':c['operation'],'actorRef':c['actorRef'],
                'resourceRef':c['resourceRef'],'outcome':outcome,'proofComplete':not missing,'reasons':sorted(set(reasons+missing))}
        results.append(result);prior[c['caseId']]={'case':c,'status':status,'outcome':outcome}
    if used != receipts.keys():raise EvidenceInvalid('business_unreferenced_arrival')
    counts={k:sum(r['outcome']==k for r in results) for k in ('pass','fail','inconclusive')}
    verdict='fail' if counts['fail'] else 'inconclusive'  # product/bills gaps stay visible
    return {'contractVersion':VERSION,'runId':fixture['runId'],'executionStatus':'completed',
            'evidenceStatus':'complete' if all(r['proofComplete'] for r in results) else 'incomplete',
            'securityVerdict':verdict,'cleanupStatus':'clean','gateDecision':'block',
            'syntheticContractStatus':'fail' if counts['fail'] else 'inconclusive' if counts['inconclusive'] else 'pass',
            'applicationOracleCounts':counts,'skippedUnsupportedCount':len(fixture['coverageGaps']),
            'coverageGaps':fixture['coverageGaps'],'assertions':results,'securityApproval':False,
            'productRuntimeVerified':False,'R1Admitted':False}


def verify_business_bundle(root, expected_plan_hash):
    if not isinstance(expected_plan_hash,str) or len(expected_plan_hash)!=64:
        raise EvidenceInvalid('external_business_plan_pin_required')
    with BundleReader(root) as reader:
        manifest=strict_json(reader.read('manifest.json'))
        if reader.read('manifest.sha256') != (hashlib.sha256(reader.read('manifest.json')).hexdigest()+'\n').encode():
            raise EvidenceInvalid('business_manifest_checksum')
        paths={a['path']:a for a in manifest['artifacts']}
        if len(paths)!=len(manifest['artifacts']) or set(reader.initial)!=set(paths)|{'manifest.json','manifest.sha256'}:
            raise EvidenceInvalid('business_bundle_inventory')
        required={'plan.json','fixture.json','observations.json','arrivals.json','cleanup.json','result.json'}
        if set(paths)!=required:raise EvidenceInvalid('business_document_inventory')
        for name,a in paths.items():
            raw=reader.read(name)
            if len(raw)!=a['bytes'] or hashlib.sha256(raw).hexdigest()!=a['sha256']:raise EvidenceInvalid('business_artifact_digest')
        raw=reader.read('plan.json')
        if hashlib.sha256(raw).hexdigest()!=expected_plan_hash:raise EvidenceInvalid('external_business_plan_pin_mismatch')
        plan=strict_json(raw)
        if canonical(plan)!=raw:raise EvidenceInvalid('business_plan_not_canonical')
        result=audit_business(plan,strict_json(reader.read('fixture.json')),strict_json(reader.read('observations.json')),
                              strict_json(reader.read('arrivals.json')),strict_json(reader.read('cleanup.json')))
        if result!=strict_json(reader.read('result.json')):raise EvidenceInvalid('business_claim_disagrees_with_replay')
        reader.unchanged()
        return {'verified':True,'integrityVerified':True,'semanticRecomputed':True,'planHash':expected_plan_hash,
                'verificationScope':'owned-synthetic-business-only',**result}
