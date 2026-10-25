"""Offline independent W8 oracle. Checksums/Complete/empty alerts cannot verify depth."""
import hashlib
import html
from html.parser import HTMLParser
import sqlite3
from urllib.parse import parse_qs, urlsplit
from .active_fixture import ORIGIN, RULES, WITNESSES, fixture
from .contracts import canonical, digest
from .evidence import EvidenceInvalid
from .traffic import correlate
from .verification import BundleReader, strict_json

VERSION = 'w8-owned-active-1'
IMAGE = 'sha256:5ccfff9a411743ab2615136a2edd7416bec9ce41572fa94e935df38c14adb2b6'


def require(value, reason):
    if not value: raise EvidenceInvalid('active_' + reason)


def sha(value): return hashlib.sha256(value).hexdigest()


def sql_effect(row, config):
    # Compare the same input against parameter binding, not against the seed's
    # rows. A harmless value absent from the table legitimately returns zero.
    safe_rows = [name for name in config['names'] if name == row['input']]
    return row['sink']['error'] is not None or row['sink']['rows'] != safe_rows


class ExecutableHTML(HTMLParser):
    def __init__(self): super().__init__(); self.active = False
    def handle_starttag(self, tag, attrs):
        if tag == 'script' or any(k.startswith('on') for k, _ in attrs): self.active = True


def oracle(row, config, variant):
    """Replay SQLite independently; inspect the resulting HTML parsing context."""
    t = row['technique']; value = row['input']; sink = row['sink']
    require(row['fixtureTag'] == config['tag'] and row['variant'] == variant, 'arrival_build_binding')
    require(row['responseBodySha256'] == sha(row['response'].encode()), 'response_bytes')
    require(t in RULES and row['method'] == 'GET', 'arrival_vector')
    parameter = 'name' if t == 'sqli' else 'q'
    require(urlsplit(row['url']).path == '/' + t and row['parameter'] == parameter, 'arrival_vector')
    query = parse_qs(urlsplit(row['url']).query, keep_blank_values=True)
    valid = set(query) == {parameter} and len(query[parameter]) == 1
    require(type(row['valid']) is bool and row['valid'] == valid, 'seed_validation')
    if not valid:
        require(value is None and sink is None and row['status'] == 400 and row['response'] == 'invalid seed', 'invalid_seed_response')
        return False
    require(query == {row['parameter']: [value]}, 'received_input')
    if sink is None or sink.get('kind') == 'missing': return False
    if t == 'sqli':
        require(sink['kind'] == 'sqlite-select', 'sql_sink_kind')
        connection = sqlite3.connect(':memory:')
        connection.execute('CREATE TABLE items (name TEXT)')
        for name in config['names']: connection.execute('INSERT INTO items VALUES (?)', (name,))
        if variant == 'fixed':
            statement = 'SELECT name FROM items WHERE name = ?'; params = [value]
        else:
            statement = "SELECT name FROM items WHERE name = '" + value + "'"; params = []
        rows = []; error = None
        try: rows = [r[0] for r in connection.execute(statement, params).fetchall()]
        except sqlite3.Error as exc: error = str(exc)
        finally: connection.close()
        require(sink == {'kind': 'sqlite-select', 'statement': statement, 'parameters': params, 'rows': rows, 'error': error}, 'sql_execution_replay')
        # Exact response bytes are independently derived, including error rendering.
        import json
        body = 'SQLite error: ' + error if error else json.dumps({'items': rows})
        require(row['response'] == body and row['status'] == (500 if error else 200), 'sql_response_replay')
    elif t == 'xss':
        require(sink['kind'] == 'html-body-text' and row['contentType'].startswith('text/html'), 'html_sink_context')
        rendered = value if variant == 'vulnerable' else html.escape(value, quote=True)
        require(sink == {'kind': 'html-body-text', 'rendered': rendered}, 'html_render_replay')
        require(row['response'] == '<!doctype html><html><body><main id="result">' + rendered + '</main></body></html>' and row['status'] == 200, 'html_response_replay')
    else: raise EvidenceInvalid('active_unknown_technique')
    return True


def plugin_rows(progress):
    found = []
    def walk(v):
        if isinstance(v, dict):
            for k, item in v.items():
                if k == 'Plugin': found.append(item)
                else: walk(item)
        elif isinstance(v, list):
            for item in v: walk(item)
    walk(progress)
    return found


def _audit_active(plan, config, observations, cleanup):
    require(plan['contractVersion'] == VERSION and plan['mode'] == 'owned-synthetic-active', 'contract')
    require(plan['image'] == IMAGE and plan['productRequestsPermitted'] is False and plan['securityApproval'] is False, 'scope')
    require(plan['fixtureHash'] == digest(config) and config == fixture(plan['seed']), 'fixture_pin')
    require(plan['variant'] in ('vulnerable', 'fixed'), 'variant')
    require(observations['evidenceKind'] == 'actual-zap-native', 'runtime_kind')
    require(observations['fixtureBuild'] == plan['sourcePins']['src/zap_assessment/active_fixture.py'], 'source_build')
    require(plan['targetBuildHash'] == observations['targetBuildHash'] == digest({'source': observations['fixtureBuild'], 'variant': plan['variant']}), 'variant_build_pin')
    require(observations['scannerStopped'] and observations['fixtureStopped'], 'producer_stop')
    require(cleanup['containerRemoved'] is True and cleanup['oomKilled'] is False and cleanup['id'] and cleanup['runId'] == plan['runId'] and cleanup['image'] == IMAGE, 'cleanup')
    require(cleanup['name'] == plan['containerName'] and cleanup['networkMode'] == 'none' and cleanup['readOnlyRoot'] is True, 'runtime_binding')
    samples = observations['resourceSamples']
    require(len(samples) >= 2 and not observations['resourceErrors'], 'resource_samples')
    require(all(0 <= b['at'] - a['at'] <= 5 for a, b in zip(samples, samples[1:])), 'sampling_gap')
    require(all(s['ramAvailable'] >= 4 * 1024**3 and s['dockerFree'] >= 2 * 1024**3 and s['peakBytes'] > 0 and s['events'].get('oom', 0) == 0 and s['events'].get('oom_kill', 0) == 0 for s in samples), 'resource_threshold')
    try: traffic = correlate(observations['sender'], observations['boundary'], observations['arrivals'], terminal=True)
    except ValueError as exc: raise EvidenceInvalid('active_traffic_correlation') from exc
    require(traffic == observations['traffic'], 'traffic_claim')
    requests = {r['requestId']: r for r in observations['sender'] if r['kind'] == 'request'}
    arrivals = {r['requestId']: r for r in observations['arrivals']}
    require(len(arrivals) == len(observations['arrivals']), 'duplicate_arrival')
    require(all(r['requestId'].startswith(plan['runId'] + '-') for r in requests.values()), 'run_binding')
    require(all(r['initiator'] in (2, 3, 6, 7) and (r['initiator'] != 2 or r.get('ruleId') in RULES.values() or r.get('activeControl') is True) for r in requests.values()), 'unexpected_native_producer')
    for ident, row in arrivals.items():
        require(row['url'].startswith(ORIGIN + '/') and sha(row['url'].encode()) == requests[ident]['urlSha256'], 'wire_url')
        oracle(row, config, plan['variant'])
    scans = observations['scans']
    require(len(scans) == 2 and {s['technique'] for s in scans} == set(RULES), 'required_techniques')
    assertions = []; confirmed = False
    for vector in config['vectors']:
        t = vector['technique']; rule = vector['ruleId']; s = next(s for s in scans if s['technique'] == t); reasons = []; oracle_vulnerable = None
        require(s['ruleId'] == rule and s['before'] == s['after'], 'effective_policy_drift')
        enabled = {str(r['id']) for r in s['before']['rules'] if r['enabled'] in (True, 'true')}
        if enabled != {rule}: reasons.append('selected_rule_not_enabled')
        selected = [r for r in s['before']['rules'] if str(r['id']) == rule]
        require(len(selected) == 1 and selected[0]['attackStrength'] == 'LOW' and selected[0]['alertThreshold'] == 'MEDIUM', 'small_policy')
        proxy = s['before']['proxy']
        require(proxy['enabled'] is True and proxy['host'] == '127.0.0.1' and proxy['port'] == 18888, 'mandatory_proxy')
        require(all(e['enabled'] is False for e in proxy['exclusions']), 'proxy_exclusion')
        require(s['before']['vectors'] == {'optionTargetParamsInjectable': {'TargetParamsInjectable': '1'}, 'optionTargetParamsEnabledRPC': {'TargetParamsEnabledRPC': '0'}, 'optionAddQueryParam': {'AddQueryParam': 'false'}}, 'query_only_vectors')
        seed = [r for r in arrivals.values() if r['url'] == s['seedUrl'] and requests[r['requestId']]['initiator'] == 6]
        valid_seed = [r for r in seed if r['valid'] and r['status'] == 200 and r['input'] == vector['baseline'] and oracle(r, config, plan['variant'])]
        if not valid_seed: reasons.append('invalid_or_missing_baseline_seed')
        elif t == 'sqli': require(valid_seed[0]['sink']['rows'] == [config['names'][0]], 'baseline_business_rows')
        require(bool(seed) and urlsplit(s['seedUrl']).path == vector['path'] and s['seedResponse']['responseBody'] == seed[0]['response'], 'seed_correlation')
        native = [r for r in requests.values() if r['initiator'] == 2 and r.get('ruleId') == rule]
        plugins = plugin_rows(s['progress'])
        require(all(isinstance(p, list) and len(p) == 7 and str(p[5]).isdecimal() for p in plugins), 'progress_shape')
        count = sum(int(p[5]) for p in plugins if str(p[1]) == rule)
        require(count == len(native), 'native_progress_request_counts')
        if s['status'] != '100' or not any(str(p[1]) == rule and p[3] == 'Complete' for p in plugins): reasons.append('rule_not_complete')
        exercised = [arrivals[r['requestId']] for r in native if r['requestId'] in arrivals and arrivals[r['requestId']]['valid'] and arrivals[r['requestId']]['technique'] == t and arrivals[r['requestId']]['input'] != vector['baseline'] and oracle(arrivals[r['requestId']], config, plan['variant'])]
        if not exercised: reasons.append('zero_valid_payload_to_sink_exercise')
        if any(r.get('phase') != 'active' for r in native): reasons.append('rule_outside_active_phase')
        witness = [r for r in arrivals.values() if r['technique'] == t and r['input'] == WITNESSES[t] and requests[r['requestId']]['initiator'] == 6]
        if len(witness) != 1 or not oracle(witness[0], config, plan['variant']): reasons.append('missing_witness_sink')
        else:
            w = witness[0]
            if t == 'sqli': vulnerable = w['sink']['rows'] == config['names']
            else:
                parser = ExecutableHTML(); parser.feed(w['response']); vulnerable = parser.active
            oracle_vulnerable = vulnerable
            confirmed = confirmed or vulnerable
            if vulnerable != (plan['variant'] == 'vulnerable'): reasons.append('witness_oracle_mismatch')
            require(s['witnessResponse']['responseBody'] == w['response'], 'witness_response_correlation')
        correlated_alerts = []
        require(set(s['messages']) == {a['messageId'] for a in s['alerts']}, 'alert_message_inventory')
        for alert in s['alerts']:
            require(str(alert['pluginId']) == rule and alert['param'] == vector['parameter'] and alert['attack'], 'alert_rule_vector')
            message = s['messages'][alert['messageId']]
            header = message['requestHeader']; ids = [h.split(':', 1)[1].strip() for h in header.splitlines() if h.lower().startswith('x-zpa-correlation:')]
            require(len(ids) == 1 and ids[0] in arrivals and ids[0] in {r['requestId'] for r in native}, 'alert_native_sink_correlation')
            arrival = arrivals[ids[0]]
            require(arrival['technique'] == t and arrival['input'] == alert['attack'] and message['responseBody'] == arrival['response'], 'alert_attack_response_binding')
            require(alert['url'] == arrival['url'] and message['id'] == alert['messageId'] and int(message['responseHeader'].splitlines()[0].split()[1]) == arrival['status'], 'alert_message_binding')
            require(isinstance(alert['evidence'], str) and bool(alert['evidence']) and alert['evidence'] in message['responseHeader'] + message['responseBody'], 'alert_evidence')
            require(oracle(arrival, config, plan['variant']), 'alert_sink_missing')
            if t == 'xss':
                parser = ExecutableHTML(); parser.feed(arrival['response'])
                require(parser.active and alert['evidence'] in arrival['response'], 'alert_html_executable_context')
            else:
                require(sql_effect(arrival, config), 'alert_sql_effect')
            correlated_alerts.append(alert['id'])
        if plan['variant'] == 'vulnerable' and not correlated_alerts: reasons.append('vulnerable_not_detected')
        if plan['variant'] == 'fixed' and correlated_alerts: reasons.append('fixed_still_detected')
        assertions.append({'technique': t, 'ruleId': rule, 'verified': not reasons, 'reasons': reasons, 'oracleVulnerable': oracle_vulnerable,
                           'nativeRequests': len(native), 'validSinkExercises': len(exercised), 'alertIds': correlated_alerts})
    complete = all(a['verified'] for a in assertions)
    return {'executionStatus': 'completed', 'evidenceStatus': 'complete', 'cleanupStatus': 'clean',
            'securityVerdict': 'fail' if confirmed or any(a['alertIds'] for a in assertions) else 'inconclusive',
            'gateDecision': 'review_required' if complete and plan['variant'] == 'fixed' and not confirmed else 'block',
            'techniqueVerdict': 'verified' if complete else 'blocked', 'assertions': assertions,
            'G9Synthetic': 'pass' if complete else 'blocked', 'G9Product': 'unverified', 'R1R2Admission': False,
            'scope': 'GET query SQLite SQLi and reflected HTML body XSS; anonymous owned fixture only'}


def audit_active(plan, config, observations, cleanup):
    try: return _audit_active(plan, config, observations, cleanup)
    except EvidenceInvalid: raise
    except (KeyError, TypeError, IndexError, AttributeError, OverflowError, ValueError) as exc:
        raise EvidenceInvalid('active_malformed_contract') from exc


def verify_active_bundle(root, expected_plan_hash):
    require(isinstance(expected_plan_hash, str) and len(expected_plan_hash) == 64, 'external_plan_pin_required')
    with BundleReader(root) as reader:
        raw = reader.read('manifest.json'); manifest = strict_json(raw)
        require(manifest['contractVersion'] == VERSION and reader.read('manifest.sha256') == (sha(raw) + '\n').encode(), 'manifest_checksum')
        required = {'plan.json', 'fixture.json', 'observations.json', 'cleanup.json', 'result.json'}
        rows = manifest['artifacts']; inventory = {r['path']: r for r in rows}
        require(len(rows) == len(inventory) and set(inventory) == required and set(reader.initial) == required | {'manifest.json', 'manifest.sha256'}, 'artifact_inventory')
        for name, meta in inventory.items():
            blob = reader.read(name); require(len(blob) == meta['bytes'] and sha(blob) == meta['sha256'], 'artifact_digest')
        plan_raw = reader.read('plan.json'); plan = strict_json(plan_raw)
        require(sha(plan_raw) == expected_plan_hash and canonical(plan) == plan_raw, 'external_plan_pin_mismatch')
        result = audit_active(plan, strict_json(reader.read('fixture.json')), strict_json(reader.read('observations.json')), strict_json(reader.read('cleanup.json')))
        require(result == strict_json(reader.read('result.json')), 'claim_disagrees_with_recomputation')
        reader.unchanged()
        return {'verified': True, 'planHash': expected_plan_hash, **result}


def compare_active(vulnerable_root, vulnerable_pin, fixed_root, fixed_pin):
    a = verify_active_bundle(vulnerable_root, vulnerable_pin); b = verify_active_bundle(fixed_root, fixed_pin)
    with BundleReader(vulnerable_root) as ra, BundleReader(fixed_root) as rb:
        pa = strict_json(ra.read('plan.json')); pb = strict_json(rb.read('plan.json'))
        require(pa['variant'] == 'vulnerable' and pb['variant'] == 'fixed' and pa['runId'] != pb['runId'], 'pair_variants')
        require(pa['sourcePins'] == pb['sourcePins'] and pa['image'] == pb['image'] and pa['fixtureHash'] == pb['fixtureHash'] and pa['fault'] == pb['fault'] == 'none', 'pair_equivalence')
        oa = strict_json(ra.read('observations.json')); ob = strict_json(rb.read('observations.json'))
        require([s['before'] for s in oa['scans']] == [s['before'] for s in ob['scans']], 'pair_policy_equivalence')
        ra.unchanged(); rb.unchanged()
    return {'contractVersion': VERSION, 'G9Synthetic': 'pass' if a['G9Synthetic'] == b['G9Synthetic'] == 'pass' else 'blocked',
            'vulnerableSecurityVerdict': a['securityVerdict'], 'fixedSecurityVerdict': b['securityVerdict'],
            'vulnerablePlanHash': vulnerable_pin, 'fixedPlanHash': fixed_pin,
            'productCapability': 'unverified', 'securityApproval': False, 'R1R2Admission': False}
