"""W9 plan and conservative aggregation. No credentials, Docker or product IO."""
from copy import deepcopy
import re
from .contracts import digest
from .business_fixture import generate_manifest
from .active_fixture import fixture as active_fixture
from .evidence import EvidenceInvalid

VERSION = 'w9-owned-unified-diagnostic-1'
TRACKS = ('session', 'api', 'ui', 'active-vulnerable', 'active-fixed')
REQUIRED = (*TRACKS, 'post-state', 'verification')
EPOCH_POLICY = 'fresh-memory-only-stop-on-restart'
ZAP_IMAGE = 'sha256:5ccfff9a411743ab2615136a2edd7416bec9ce41572fa94e935df38c14adb2b6'


def require(v, reason):
    if not v: raise EvidenceInvalid('unified_' + reason)


def specs(assessment_id, seed, adapter, reverse, image):
    ident = assessment_id.removeprefix('w9-'); result = []
    for i, phase in enumerate(TRACKS):
        active = phase.startswith('active-')
        run_id = ('w8-' if active else 'w6-w7-') + ident + '-' + phase
        f = active_fixture(seed) if active else generate_manifest(run_id, seed, adapter, reverse)
        scope = {'kind': 'owned-anonymous-query-sinks' if active else 'owned-business-phase-clone',
                 'actors': ['anonymous'] if active else f['actors'],
                 'resources': f['vectors'] if active else [{'resourceRef': r['resourceRef'], 'wireId': r['wireId'], 'ownerActorRef': r['ownerActorRef']} for r in f['resources']],
                 'stateBranch': phase}
        name = run_id + ('-active' if active else '-fixture') if phase == 'api' or active else 'w7-ui-' + run_id.removeprefix('w6-w7-')
        result.append({'phase': phase, 'required': True, 'childRunId': run_id, 'fixtureHash': digest(f), 'scopeHash': digest(scope),
                       'scope': scope, 'image': image if phase == 'api' else ZAP_IMAGE, 'containerName': name,
                       'profileVolume': name + '-profile' if phase in ('session', 'ui') else None,
                       'dependsOn': list(TRACKS[:i])})
    return result


def make_plan(assessment_id, seed, adapter, reverse, image, source_pins, api_fault='fixed', ui_fault='fixed'):
    p = {'contractVersion': VERSION, 'assessmentId': assessment_id, 'mode': 'owned-synthetic-unified-diagnostic',
         'seed': seed, 'adapter': adapter, 'reverse': reverse, 'apiImage': image, 'sourcePins': source_pins,
         'requiredTracks': list(REQUIRED), 'tracks': specs(assessment_id, seed, adapter, reverse, image),
         'stateModel': 'declared-phase-isolated-clones-shared-logical-identities', 'epochPolicy': EPOCH_POLICY,
         'diagnosticContinuation': 'record-security-failures-without-admitting-operational-mode',
         'faults': {'api': api_fault, 'ui': ui_fault}, 'securityApproval': False, 'productRequestsPermitted': False,
         'resourceBudget': {'estimatedHostGrowthBytes': 192 * 1024**2, 'reserveBytes': 2 * 1024**3},
         'limitations': ['Phase clones are separate state branches, never a claim of one live product DB across tracks.',
                         'Browser remains required and its G3/G8 failure blocks operational G10/R2.',
                         'Active fixtures have explicit anonymous scope; A/B business identity is not an active auth proof.']}
    validate_plan(p); return p


def validate_plan(p):
    expected = {'contractVersion', 'assessmentId', 'mode', 'seed', 'adapter', 'reverse', 'apiImage', 'sourcePins', 'requiredTracks', 'tracks',
                'stateModel', 'epochPolicy', 'diagnosticContinuation', 'faults', 'securityApproval', 'productRequestsPermitted', 'resourceBudget', 'limitations'}
    require(isinstance(p, dict) and set(p) == expected, 'plan_fields')
    require(p['contractVersion'] == VERSION and p['mode'] == 'owned-synthetic-unified-diagnostic', 'contract')
    require(isinstance(p['assessmentId'], str) and re.fullmatch('w9-[0-9a-f]{32}', p['assessmentId']), 'assessment_id')
    require(type(p['seed']) is int and 0 <= p['seed'] < 2**32 and type(p['reverse']) is bool, 'seed_or_order')
    require(p['adapter'] in ('finalsource-shaped', 'alternate-ledger') and re.fullmatch('sha256:[0-9a-f]{64}', p['apiImage']), 'adapter_image')
    require(p['requiredTracks'] == list(REQUIRED) and p['tracks'] == specs(p['assessmentId'], p['seed'], p['adapter'], p['reverse'], p['apiImage']), 'required_track_graph')
    require(p['stateModel'] == 'declared-phase-isolated-clones-shared-logical-identities' and p['epochPolicy'] == EPOCH_POLICY, 'state_epoch_contract')
    require(p['diagnosticContinuation'] == 'record-security-failures-without-admitting-operational-mode', 'diagnostic_scope')
    require(p['securityApproval'] is False and p['productRequestsPermitted'] is False, 'admission_ceiling')
    require(p['resourceBudget'] == {'estimatedHostGrowthBytes': 192 * 1024**2, 'reserveBytes': 2 * 1024**3}, 'resource_budget')
    require(isinstance(p['sourcePins'], dict) and bool(p['sourcePins']) and all(isinstance(k, str) and re.fullmatch('[0-9a-f]{64}', v) for k, v in p['sourcePins'].items()), 'source_pins')
    require(set(p['faults']) == {'api', 'ui'} and p['faults']['api'] in ('fixed', 'denied-mutated', 'denied-disclosure', 'list-leak')
            and p['faults']['ui'] in ('fixed', 'wrong-balance', 'error-page', 'denied-mutated', 'denied-disclosure', 'no-submit'), 'fault_scope')
    return p


def binding_for(p, phase):
    spec = next(t for t in p['tracks'] if t['phase'] == phase)
    return {'assessmentId': p['assessmentId'], 'planHash': digest(p), 'phase': phase, 'childRunId': spec['childRunId'],
            'fixtureHash': spec['fixtureHash'], 'scopeHash': spec['scopeHash'], 'epochPolicy': p['epochPolicy']}


def functional(phase, result):
    if phase == 'api': return result['syntheticContractStatus'] == 'pass'
    if phase == 'session': return result['executionStatus'] == 'completed' and result['scope'] == 'session-spike'
    if phase == 'ui': return result['functionalVerdict'] == 'pass' and result['requiredSteps'] == result['observedSteps'] == 13
    return result['G9Synthetic'] == 'pass'


def aggregate(p, rows, post_state, *, interrupted=False, cleanup_clean=True):
    phases = [r['phase'] for r in rows]
    require(len(phases) == len(set(phases)) and all(x in TRACKS for x in phases), 'duplicate_or_unknown_track')
    present = {r['phase']: r for r in rows}; complete = set(present) == set(TRACKS) and post_state
    observed_fail = any(r['result']['securityVerdict'] == 'fail' for r in rows)
    missing = [t for t in REQUIRED if (t in TRACKS and t not in present) or t == 'post-state' and not post_state or t == 'verification' and not complete]
    good = complete and all(functional(t, present[t]['result']) for t in TRACKS) and not interrupted and cleanup_clean
    return {'executionStatus': 'interrupted' if interrupted else 'completed' if complete else 'incomplete',
            'evidenceStatus': 'complete' if complete and not interrupted else 'incomplete',
            'securityVerdict': 'fail' if observed_fail else 'inconclusive',
            'cleanupStatus': 'clean' if cleanup_clean else 'quarantined', 'gateDecision': 'block',
            'orchestrationVerdict': 'verified' if good else 'blocked', 'missingRequiredTracks': missing,
            'failedFunctionalTracks': [r['phase'] for r in rows if not functional(r['phase'], r['result'])],
            'G10Operational': 'blocked', 'R1R2Admission': False, 'securityApproval': False,
            'requiredTrackCount': len(REQUIRED), 'functionalTrackCount': sum(functional(r['phase'], r['result']) for r in rows),
            'productRuntimeVerified': False, 'stateModel': p['stateModel']}
