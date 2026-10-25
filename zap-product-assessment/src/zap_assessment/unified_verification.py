"""W9 offline readback: recompute every required child and cross-phase linkage."""
import hashlib
from pathlib import Path
from .contracts import canonical, digest
from .evidence import EvidenceInvalid
from .verification import BundleReader, strict_json
from .business import initial_state, expected_states, transition
from .business_verification import verify_business_bundle
from .ui_contract import ui_steps
from .ui_verification import verify_ui_bundle
from .active_verification import verify_active_bundle, compare_active
from .journal import Journal
from .unified_contract import VERSION, TRACKS, REQUIRED, validate_plan, binding_for, aggregate, require


def identity_shape(fixture):
    return {'adapter': fixture['adapter'], 'actors': fixture['actors'],
            'resources': [{k: r[k] for k in ('resourceRef', 'wireId', 'kind', 'ownerActorRef', 'initial')} for r in fixture['resources']]}


def child_result(phase, folder, pin):
    if phase == 'api': return verify_business_bundle(folder, pin)
    if phase in ('session', 'ui'): return verify_ui_bundle(folder, pin)
    return verify_active_bundle(folder, pin)


def check_child(parent, phase, folder, pin):
    expected = next(s for s in parent['tracks'] if s['phase'] == phase)
    with BundleReader(folder) as reader:
        p = strict_json(reader.read('plan.json')); observations = strict_json(reader.read('observations.json'))
        fixture = strict_json(reader.read('fixture.json'))
        require(hashlib.sha256(reader.read('plan.json')).hexdigest() == pin, 'child_external_pin')
        require(p.get('unifiedBinding') == observations.get('unifiedBinding') == binding_for(parent, phase), 'child_parent_phase_binding')
        require(p['runId'] == expected['childRunId'] and p['image'] == expected['image'] and p['containerName'] == expected['containerName'], 'child_identity_image')
        require(digest(fixture) == expected['fixtureHash'] == p['fixtureHash'], 'child_fixture')
        require(all(parent['sourcePins'].get(k) == v for k, v in p['sourcePins'].items()), 'child_source')
        if phase in ('session', 'ui'):
            require(p['scope'] == ('session-spike' if phase == 'session' else 'ui-business-flow') and observations['evidenceKind'] == 'actual-webdriver', 'actual_browser_required')
            require(p['fault'] == ('fixed' if phase == 'session' else parent['faults']['ui']), 'declared_ui_mode')
        if phase == 'api': require(p['fault'] == parent['faults']['api'], 'declared_api_mode')
        if phase.startswith('active-'):
            require(p['variant'] == phase.removeprefix('active-') and p['fault'] == 'none', 'selected_active_variants')
            arrivals = observations['arrivals']
        else: arrivals = strict_json(reader.read('arrivals.json'))
        require(bool(arrivals) and all(r['requestId'].startswith(expected['childRunId'] + '-') for r in arrivals), 'arrival_run_binding')
        reader.unchanged()
    result = child_result(phase, folder, pin)
    row = {'phase': phase, 'binding': binding_for(parent, phase), 'childPlanHash': pin,
           'childManifestSha256': hashlib.sha256((Path(folder) / 'manifest.json').read_bytes()).hexdigest(), 'result': result}
    return row


def post_state(children):
    """No claim of continuity between two explicitly separate DB branches."""
    data = {}
    for phase in ('session', 'api', 'ui'):
        with BundleReader(children / phase) as reader:
            data[phase] = {k: strict_json(reader.read(k + '.json')) for k in ('plan', 'fixture', 'observations')}
            reader.unchanged()
    shapes = [identity_shape(data[t]['fixture']) for t in ('session', 'api', 'ui')]
    require(shapes[0] == shapes[1] == shapes[2], 'logical_actor_resource_mapping')
    api = data['api']; ui = data['ui']
    expected_api = list(expected_states(api['fixture']))[-1][3]
    actual_api = api['observations']['cases'][-1]['postState']
    state = initial_state(ui['fixture'])
    for step in ui_steps(ui['fixture']):
        if 'case' in step: _, state = transition(ui['fixture'], state, step['case'])
    actual_ui = ui['observations']['steps'][-1]['postState']
    require(actual_api == expected_api and actual_ui == state, 'post_state_branch_oracle')
    return {'stateModel': 'declared-phase-isolated-clones-shared-logical-identities',
            'logicalIdentityHash': digest(shapes[0]),
            'branches': [{'phase': phase, 'childRunId': data[phase]['plan']['runId'], 'fixtureHash': digest(data[phase]['fixture']),
                          'postStateHash': digest(actual_api if phase == 'api' else actual_ui), 'oracleVerified': True}
                         for phase in ('api', 'ui')],
            'sameLiveProductDatabase': False}


def expected_journal_kinds():
    return ['plan_locked', 'preflight_passed', *[kind for _ in TRACKS for kind in ('track_intent', 'track_recorded')], 'namespace_clean', 'post_state_recorded', 'verifying']


def verify_journal(path, plan, rows, post):
    j = Journal(path, plan['assessmentId'], digest(plan))
    require([e['kind'] for e in j.events] == expected_journal_kinds(), 'journal_state_graph')
    require(j.events[0]['data'] == {'planHash': digest(plan)}, 'journal_plan_binding')
    budget = plan['resourceBudget']; pre = j.events[1]['data']
    require(pre['hostFreeBytes'] >= 2 * budget['estimatedHostGrowthBytes'] + budget['reserveBytes'], 'preflight_threshold')
    for i, row in enumerate(rows):
        spec = plan['tracks'][i]; intent, ack = j.events[2 + i * 2:4 + i * 2]
        require(intent['data'] == {'phase': row['phase'], 'bindingHash': digest(row['binding']), 'containerName': spec['containerName'],
                                  'image': spec['image'], 'childRunId': spec['childRunId'], 'profileVolume': spec['profileVolume']}, 'journal_intent')
        require(ack['data'] == {'phase': row['phase'], 'childPlanHash': row['childPlanHash'],
                               'resultHash': digest(row['result']), 'childManifestSha256': row['childManifestSha256']}, 'journal_track_ack')
    require(j.events[-3]['data'] == {'assessmentId': plan['assessmentId'], 'dockerStateObserved': True, 'containers': [], 'volumes': []}, 'namespace_cleanup_closure')
    require(j.events[-2]['data'] == {'sha256': digest(post)} and j.events[-1]['data'] == {'requiredTracks': list(REQUIRED)}, 'journal_post_state_verifier')


def _verify_unified_bundle(root, expected_plan_hash):
    require(isinstance(expected_plan_hash, str) and len(expected_plan_hash) == 64, 'external_plan_pin_required')
    root = Path(root)
    with BundleReader(root) as reader:
        raw = reader.read('manifest.json'); m = strict_json(raw)
        require(m['contractVersion'] == VERSION and reader.read('manifest.sha256') == (hashlib.sha256(raw).hexdigest() + '\n').encode(), 'manifest')
        inventory = {r['path']: r for r in m['artifacts']}
        require(len(inventory) == len(m['artifacts']) and set(reader.initial) == set(inventory) | {'manifest.json', 'manifest.sha256'}, 'artifact_inventory')
        required = {'plan.json', 'journal.jsonl', 'track-matrix.json', 'post-state.json', 'result.json', 'active-pair.json'}
        require(required <= inventory.keys() and all(n in required or n.startswith(tuple('children/' + p + '/' for p in TRACKS)) for n in inventory), 'required_documents')
        for name, row in inventory.items():
            blob = reader.read(name)
            require(len(blob) == row['bytes'] and hashlib.sha256(blob).hexdigest() == row['sha256'], 'artifact_hash')
        plan_raw = reader.read('plan.json'); plan = validate_plan(strict_json(plan_raw))
        require(canonical(plan) == plan_raw and hashlib.sha256(plan_raw).hexdigest() == expected_plan_hash, 'external_plan_pin_mismatch')
        declared_rows = strict_json(reader.read('track-matrix.json'))
        require([r['phase'] for r in declared_rows] == list(TRACKS), 'required_tracks_order')
        rows = [check_child(plan, r['phase'], root / 'children' / r['phase'], r['childPlanHash']) for r in declared_rows]
        require(rows == declared_rows, 'track_claim_disagrees_with_child_readback')
        with BundleReader(root / 'children/ui') as ui:
            require(strict_json(ui.read('plan.json'))['spikePlanHash'] == rows[0]['childPlanHash'], 'fresh_session_spike_link')
            ui.unchanged()
        pair = compare_active(root / 'children/active-vulnerable', rows[3]['childPlanHash'], root / 'children/active-fixed', rows[4]['childPlanHash'])
        require(pair == strict_json(reader.read('active-pair.json')) and pair['G9Synthetic'] == 'pass', 'active_pair_equivalence')
        post = post_state(root / 'children'); require(post == strict_json(reader.read('post-state.json')), 'post_state_claim')
        verify_journal(root / 'journal.jsonl', plan, rows, post)
        result = aggregate(plan, rows, True)
        require(result == strict_json(reader.read('result.json')), 'aggregate_claim_disagrees_with_recomputation')
        reader.unchanged()
        return {'verified': True, 'semanticRecomputed': True, 'assessmentId': plan['assessmentId'], 'planHash': expected_plan_hash, **result}


def verify_unified_bundle(root, expected_plan_hash):
    try: return _verify_unified_bundle(root, expected_plan_hash)
    except EvidenceInvalid: raise
    except (KeyError, TypeError, IndexError, AttributeError, ValueError, OSError) as exc:
        raise EvidenceInvalid('unified_malformed_or_missing_evidence') from exc
