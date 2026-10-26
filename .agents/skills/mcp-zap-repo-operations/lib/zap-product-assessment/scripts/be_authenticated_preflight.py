#!/usr/bin/env python3
"""Read back an owned W5 diagnostic and enumerate exact BE secret-proof gaps.

Offline only: this is a proof inventory, not a product runtime attestor. No URL,
credential, admission override or execution command is accepted. Output is new and
outside the sealed bundle; G3 and product G4 remain blocked.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from zap_assessment.contracts import canonical
from zap_assessment.errors import Blocked
from zap_assessment.safety_io import atomic_bytes
from zap_assessment.secret_inventory import SINKS,LIFECYCLE


def source_classification(plan,current_pins):
    pins=plan.get('sourcePins')
    if (not isinstance(pins,dict) or set(pins)!=set(current_pins)
            or any(not isinstance(value,str) or not value for value in pins.values())):
        raise Blocked('source pin comparison unavailable')
    same=pins==current_pins
    return {'evidenceClass':'owned-synthetic-'+('current' if same else 'historical')+'-source-readback',
            'sourcePinsMatchCurrent':same,'recordedSourcePins':pins,'currentSourcePins':current_pins}


def matrix(gate,*,private_db_proof=None):
    """Summarize observations without treating collector labels as acceptance."""
    if (gate.get('schemaVersion')!='w5-scanner-campaign/1.0'
            or gate.get('operationalG3')!='blocked' or gate.get('productG4')!='blocked'
            or gate.get('gateDecision')!='block' or gate.get('securityApproval') is not False):
        raise Blocked('owned diagnostic cannot grant operational admission')
    history=gate.get('actualHistoryAudits',[])
    names=[r.get('caseId') for r in history]
    if len(names)!=len(set(names)):raise Blocked('duplicate history lifecycle observation')
    histories={r['caseId']:i for i,r in enumerate(history)}
    db_controls={}
    if private_db_proof is not None:
        expected={'contract':'private-hsql-source/1.0','controlLifecycleCases':14,
            'sourceEncodingTextBinaryDetections':140,'savedSessionAuditedInHolder':True,
            'channelNegativeControls':4,'rawCellsExportedToController':False,'operationalG3':'blocked'}
        if private_db_proof!=expected or gate.get('privateDbContract')!=expected['contract']:
            raise Blocked('private DB verifier proof mismatch')
        values=gate.get('privateDbAudits',[])
        names=[r.get('caseId') for r in values]
        if len(values)!=14 or len(set(names))!=14:raise Blocked('private DB reader control inventory invalid')
        db_controls={r['caseId']:i for i,r in enumerate(values)}
    rows=[]
    for sink in sorted(SINKS):
        for case in sorted(LIFECYCLE):
            refs=[]
            if sink=='zap-history' and case in histories:
                refs.append('/actualHistoryAudits/'+str(histories[case]))
            if sink=='zap-session-db' and case in ('cleanup','crash') and gate.get('databaseReadback'):
                refs.append('/databaseReadback')
            if sink=='zap-session-db' and case in db_controls:
                refs.append('/privateDbAudits/'+str(db_controls[case]))
            if sink in ('command-arguments','logs','repository') and gate.get('containerSinkAudits'):
                refs.append('/containerSinkAudits')
            if sink in ('prompt-tool-output','reports','exports') and gate.get('envelopeAudits'):
                refs.append('/envelopeAudits')
            if sink in ('bundle','journal') and gate.get('artifactAudit'):
                refs.append('/artifactAudit')
            if sink=='credential-copy' and gate.get('sourceBoundary'):
                refs.append('/sourceBoundary')
            reasons=['actual_private_source_seeded_control_not_proven_for_pair',
                     'per_sink_lifecycle_access_and_decoder_acceptance_missing']
            if sink=='browser-profile':reasons.append('locked_browser_absence_or_storage_proof_missing')
            if sink=='crash-restart':reasons.append('mid_scan_crash_and_platform_dump_boundaries_unaccepted')
            if sink=='zap-session-db' and case in db_controls:
                reasons.append('verified_private_source_reader_control_uses_separate_HSQL_control_DB_not_live_ZAP_sink_seeding')
            rows.append({'sinkId':sink,'lifecycle':case,'proofStatus':'blocked',
                         'observationRefs':refs,'observationScope':'partial owned diagnostic only',
                         'reasonCodes':reasons})
    return {'requiredPairs':len(SINKS)*len(LIFECYCLE),'completePairs':0,
            'pairsWithPartialObservationRefs':sum(bool(r['observationRefs']) for r in rows),
            'pairs':rows,'g3Status':'blocked','platformAcceptance':'unproven',
            'privateDbReaderControls':private_db_proof,
            'limitation':'References show observations, not actual seeded/access/lifecycle acceptance; no pair is silently waived.'}


def evaluate(work,expected_hash,output):
    work=Path(work).absolute();output=Path(output).absolute()
    if output.resolve().is_relative_to(work.resolve()):raise Blocked('output must be outside sealed bundle')
    if output.exists() or output.is_symlink():raise Blocked('output already exists')
    spec=importlib.util.spec_from_file_location('be_w5_verify',ROOT/'scripts/remediation_w5_scanner.py')
    scanner=importlib.util.module_from_spec(spec);spec.loader.exec_module(scanner)
    verified=scanner.verify(work,expected_hash)  # actual bytes/pins/semantic replay, no Docker/HTTP
    if verified.get('readbackStatus')!='pass':raise Blocked('diagnostic readback failed')
    raw=(work/'gate-results.json').read_bytes();gate=json.loads(raw)
    plan=json.loads((work/'w5-plan.json').read_bytes())
    classification=source_classification(plan,scanner.source_pin())
    result={'schemaVersion':'be-authenticated-readiness/1.0','runId':gate['runId'],
        'planHash':expected_hash,**classification,
        'gateResultSha256':hashlib.sha256(raw).hexdigest(),'verifier':verified,
        'diagnosticExecutionStatus':gate['executionStatus'],
        'diagnosticEvidenceStatus':gate['evidenceStatus'],
        'secretMatrix':matrix(gate,private_db_proof=verified.get('privateDbProof')),'productRequests':0,
        'productIdentityStatus':'not_runtime_verified','operationalAttestorStatus':'not_implemented_for_product',
        'executionStatus':'not_started','evidenceStatus':'incomplete',
        'securityVerdict':'fail' if gate['canaryLeakDetected'] else 'inconclusive',
        'cleanupStatus':gate['cleanupStatus'],'gateDecision':'block','securityApproval':False,
        'blockers':['G3 actual sink/lifecycle and platform boundaries unaccepted',
                    'Product identity/epoch adapter and current operational admission contract absent',
                    'No authorized equivalent fixed-build authenticated regression baseline selected']}
    atomic_bytes(output,canonical(result))
    return {'output':str(output),'readbackStatus':'pass','requiredPairs':result['secretMatrix']['requiredPairs'],
            'completePairs':0,'gateDecision':'block','productRequests':0}


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work-dir',required=True,type=Path)
    ap.add_argument('--expect-plan-hash',required=True)
    ap.add_argument('--output',required=True,type=Path)
    a=ap.parse_args(argv)
    try:result=evaluate(a.work_dir,a.expect_plan_hash,a.output)
    except Exception as exc:
        print(json.dumps({'status':'blocked','reason':str(exc) if isinstance(exc,Blocked) else 'readback_unavailable',
                          'gateDecision':'block','productRequests':0}));return 2
    print(json.dumps(result));return 0  # consistency only; operational gate remains block


if __name__=='__main__':sys.exit(main())
