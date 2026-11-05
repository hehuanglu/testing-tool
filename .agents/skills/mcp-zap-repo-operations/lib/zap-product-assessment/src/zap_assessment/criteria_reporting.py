"""Version 2 criterion review and alert-oriented handoff; no dispatch or migration.

The private working RUN remains the executable state. Reports are sanitized
projections, never an approval source or a replacement for the executor journal.
"""
import base64
import copy
import html
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import quote, quote_plus
from uuid import uuid4

from .criteria_workflow import approval_digest, review_workflow, validate_workflow
from .question_evidence import operation_index, verified_zap_message
from .security_scope import canonical_alerts
from .safety_io import atomic_bytes


class CriteriaFinalizationError(ValueError):
    def __init__(self, review):
        super().__init__('criteria assessment is not eligible for completion')
        self.review = review


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + ' required')


def _identity(value):
    return (isinstance(value, str) and bool(value.strip())) or type(value) is int


def _zap_transport(row):
    provenance = row.get('provenance')
    return provenance.get('transport') if isinstance(provenance, dict) else None


def _occurrences(row):
    """Unknown occurrence totals stay unknown rather than becoming one alert."""
    instances = row.get('instances')
    if instances is not None and not isinstance(instances, list):
        raise ValueError('alert instances must be a list')
    count = row.get('instanceCount')
    if count is not None and (type(count) is not int or count < 1):
        raise ValueError('instanceCount must be a positive integer')
    if instances is not None:
        if not instances or (count is not None and count != len(instances)):
            raise ValueError('alert instance list/count inconsistent')
        return len(instances)
    return count


def _summary(rows, all_rows=None):
    all_rows = rows if all_rows is None else all_rows
    mapped = sum(bool(r.get('criterionMappings')) for r in all_rows)
    counts = [_occurrences(r) for r in rows]
    return dict(alertCount=len(rows), totalAlertCount=len(all_rows),
        nativeAlertCount=sum(r['recordKind'] == 'native-zap-alert' for r in rows),
        observedAlertCount=sum(r['recordKind'] == 'observed-security-alert' for r in rows),
        mappedAlertCount=mapped, unmappedAlertCount=len(all_rows)-mapped,
        mappingCount=sum(len(r.get('criterionMappings', [])) for r in all_rows),
        occurrenceCount=sum(n for n in counts if n is not None),
        unknownOccurrenceAlertCount=sum(n is None for n in counts),
        occurrenceCountMeaning='Known instance totals for this list only; unknown totals are counted separately. Mappings do not add occurrences.')


def alert_projection(run, document):
    """Explicit inclusion, stable identities and rationale-bearing criterion joins.

    Semantic classification is a tester responsibility. Ambiguous legacy mixed
    observations fail closed instead of silently becoming security alerts.
    """
    canonical = canonical_alerts(document)
    cw = validate_workflow(run['criteriaWorkflow'])
    criteria = {c['id']: c for c in cw['criteria']}
    operations = operation_index(run.get('operations', []))
    message_cases = {case['id'] for case in cw['plan']['cases'] if case.get('requireZapMessageEvidence')}
    alerts, observations = [], []
    for original in canonical['alerts']:
        row = copy.deepcopy(original)
        kind = row.get('recordKind')
        if kind in ('control-observation', 'test-uncertainty'):
            _text(row.get('basis'), 'non-alert classification basis')
            observations.append(row)
            continue
        if kind not in ('native-zap-alert', 'observed-security-alert'):
            raise ValueError('explicit alert triage required for ' + row['findingId'])
        _text(row.get('source'), 'alert source')
        transport = _zap_transport(row)
        if transport not in ('zap-proxy', 'zap-sendRequest', 'zap-native'):
            raise ValueError('alert requires explicit ZAP transport provenance')
        if kind == 'native-zap-alert':
            if transport != 'zap-native':
                raise ValueError('native alert requires native ZAP output provenance')
            if not _identity(row.get('nativeRuleId')) or not (_identity(row.get('nativeAlertId')) or row.get('instances')):
                raise ValueError('native detector and alert/instance identity required')
            if 'nativeAlertId' in row and not _identity(row['nativeAlertId']):
                raise ValueError('invalid native alert identity')
        else:
            if any(row.get(k) is not None for k in ('nativeRuleId', 'nativeAlertId', 'nativeId')):
                raise ValueError('tester observation cannot claim a native rule')
            for field in ('securitySignal', 'expectedBehavior', 'observedBehavior', 'expectationBasis'):
                _text(row.get(field), 'observed alert ' + field)
            if row.get('status') not in ('suspected', 'confirmed', 'needs-review'):
                raise ValueError('observed alert triage status required')
            refs = row.get('operationIds')
            if not isinstance(refs, list) or not refs or any(not isinstance(r, str) or r not in operations for r in refs):
                raise ValueError('observed alert requires existing operation IDs')
            if any(_zap_transport(operations[r]) not in ('zap-proxy', 'zap-sendRequest', 'zap-native') for r in refs):
                raise ValueError('observed alert requires ZAP operation provenance')
            if any((operations[r].get('caseId') in message_cases or 'zapMessageReceipt' in operations[r])
                   and not verified_zap_message(operations[r]) for r in refs):
                raise ValueError('observed alert requires a matching ZAP capture receipt')
            for field in ('severity', 'confidence'):
                if field in row and row.get(field + 'Source') != 'tester':
                    raise ValueError('observed ratings must identify tester as source')
        # Historical associations are not current mappings.
        row.pop('criterionMappings', None)
        row.pop('criterionIds', None)
        row.pop('unmappedReason', None)
        _occurrences(row)
        alerts.append(row)
    by_id = {r['findingId']: r for r in alerts}
    mappings = {}
    seen = set()
    declared_mappings = cw.get('alertMappings', [])
    if not isinstance(declared_mappings, list):
        raise ValueError('alertMappings list required')
    if declared_mappings and not any(a['kind'] == 'criteria' and a['revision'] == cw['criteriaRevision']
            and a['digest'] == approval_digest(cw, 'criteria') for a in cw.get('approvals', [])):
        raise ValueError('alert mappings require approval of the current criteria')
    for mapping in declared_mappings:
        if not isinstance(mapping, dict):
            raise ValueError('alert mapping object required')
        fid, cid = mapping.get('findingId'), mapping.get('criterionId')
        if fid not in by_id or cid not in criteria:
            raise ValueError('alert mapping references missing alert/criterion')
        _text(mapping.get('rationale'), 'alert mapping rationale')
        if (fid, cid) in seen:
            raise ValueError('unique alert mapping with rationale required')
        seen.add((fid, cid))
        criterion = criteria[cid]
        strict_cases = message_cases.intersection(criterion['caseIds'])
        alert = by_id[fid]
        if strict_cases and alert['recordKind'] == 'observed-security-alert' and not any(
                operations[oid].get('caseId') in strict_cases and verified_zap_message(operations[oid])
                for oid in alert['operationIds']):
            raise ValueError('observed alert mapping requires a matching case capture')
        mappings.setdefault(fid, []).append(dict(criterionId=cid,
            rawText=criterion['rawText'], source=copy.deepcopy(criterion['source']),
            rationale=mapping['rationale']))
    scoped = []
    for row in alerts:
        row['criterionMappings'] = mappings.get(row['findingId'], [])
        row['scopeMapping'] = 'mapped' if row['criterionMappings'] else 'unmapped'
        if row['criterionMappings']:
            scoped.append(copy.deepcopy(row))
        else:
            row.setdefault('unmappedReason', 'No supported mapping to the approved criteria was supplied')
    summary = _summary(alerts)
    grouping = canonical.get('grouping', 'One row per caller-established finding identity; no implicit cross-session deduplication. Instances are separate occurrence counts.')
    return ({'alerts': alerts, 'summary': summary, 'grouping': grouping},
        {'alerts': scoped, 'summary': _summary(scoped, alerts),
         'grouping': grouping}, observations)


def sanitize(value, secrets=()):
    """Preserve semantic evidence pointers; strip credentials and raw traffic."""
    from .discovery_handoff import clean
    hidden = set()
    for secret in secrets:
        if isinstance(secret, str) and secret:
            hidden.update((secret, quote(secret, safe=''), quote_plus(secret), base64.b64encode(secret.encode()).decode()))
    hidden = sorted(hidden, key=len, reverse=True)
    def visit(item):
        if isinstance(item, dict):
            result = {}
            for key, val in item.items():
                if not isinstance(key, str):
                    raise ValueError('report keys must be strings')
                if key in ('raw', 'rawData', 'rawRequest', 'rawResponse', 'requestHeader', 'responseHeader', 'requestBody', 'responseBody', 'credentials'):
                    continue
                safe_key = visit(key)
                if safe_key in result:
                    raise ValueError('duplicate report key after redaction')
                secret_key = key.lower().replace('-', '').replace('_', '')
                result[safe_key] = '[private]' if secret_key in ('password', 'passwordvalue', 'token', 'accesstoken', 'refreshtoken', 'setuptoken', 'sessiontoken', 'authorization', 'cookie', 'setcookie', 'secret', 'clientsecret', 'apikey', 'privatekey') else visit(val)
            return result
        if isinstance(item, (list, tuple)):
            return [visit(v) for v in item]
        if isinstance(item, str):
            for secret in hidden:
                item = item.replace(secret, '[private]')
            item = clean(html.escape(item))
            for secret in hidden:
                item = item.replace(secret, '[private]')
        return item
    return visit(value)


def publish_reports(output, run, alerts, *, finalize=False, overwrite=False, secrets=()):
    """Publish a consistent coordinator snapshot through the canonical writer lock."""
    from .criteria_delegation import coordinator_lock
    with coordinator_lock(run):
        return _publish_reports_locked(output, run, alerts, finalize=finalize,
                                       overwrite=overwrite, secrets=secrets)


def _publish_reports_locked(output, run, alerts, *, finalize=False, overwrite=False, secrets=()):
    review = review_workflow(run)
    if finalize and not review['eligibleForCompletion']:
        raise CriteriaFinalizationError(review)
    alert_report, scoped_report, controls = alert_projection(run, alerts)
    result = copy.deepcopy(run)
    # Never let legacy closure metadata contradict the v2 assessment headline.
    legacy = {k: result.pop(k) for k in ('assessmentRound', 'taskCompletion', 'completionSummary', 'handoffClosesTask', 'roundClosed', 'roundOutcome', 'roundClosureReview') if k in result}
    if legacy:
        result['legacyCompletionContext'] = legacy
    result.update(workflowVersion=2, reportProjection=True,
        assessmentStatus='completed' if finalize else review['assessmentStatus'],
        criterionResults=copy.deepcopy(review['criterionResults']),
        criterionCounts=copy.deepcopy(review['criterionCounts']), criteriaReview=review,
        alertSummary=copy.deepcopy(alert_report['summary']))
    result.setdefault('controlObservations', []).extend(controls)
    cw = run['criteriaWorkflow']
    context = dict(cw['context'], assessmentId=run.get('assessmentId', cw.get('assessmentId', 'unknown')),
                   criteriaRevision=cw['criteriaRevision'], planRevision=cw['planRevision'])
    generation = dict(bundleId=str(uuid4()), kind='recomposition', performsRetest=False,
        writeGuarantee='staged new directory; overwrite is per-file atomic, not bundle crash-atomic')
    for report in (result, alert_report, scoped_report):
        report.update(workflowVersion=2, assessmentContext=copy.deepcopy(context),
            assessmentStatus=result['assessmentStatus'], reportGeneration=copy.deepcopy(generation))
    bundle = [sanitize(r, secrets) for r in (result, alert_report, scoped_report)]
    # Revalidate sanitized semantic pointers. If redaction removed needed data,
    # fail instead of publishing a conclusion without its declared evidence.
    # Digests bind private inputs; sanitizing requirements may change them, so
    # the report is explicitly non-executable and its review is a projection.
    validate_report_bundle(*bundle)
    write_bundle(output, bundle, overwrite=overwrite)
    return bundle[0]


def validate_report_bundle(run, alerts, scoped):
    ids = [r['findingId'] for r in alerts['alerts']]
    scoped_ids = [r['findingId'] for r in scoped['alerts']]
    if len(ids) != len(set(ids)) or len(scoped_ids) != len(set(scoped_ids)):
        raise ValueError('duplicate alert identity after redaction')
    indexed = dict(zip(ids, alerts['alerts']))
    expected_scoped = [r for r in alerts['alerts'] if r.get('criterionMappings')]
    if scoped['alerts'] != expected_scoped:
        raise ValueError('scoped alerts must contain exactly the mapped alert subset')
    workflow = validate_workflow(run['criteriaWorkflow'])
    criteria = {c['id']: c for c in workflow['criteria']}
    operations = operation_index(run.get('operations', []))
    # Resource/unknown-effect decisions also carry semantic evidence pointers.
    # They must survive redaction just like ordinary case observations, or a
    # completed projection could retain a disposition whose only proof vanished.
    from .question_evidence import read_pointer, validate_observation_links
    for row in workflow.get('caseResults', []):
        validate_observation_links(row, operations)
    validate_observation_links({'resolvedEffects': workflow.get('resolutions', [])}, operations)
    for row in (workflow.get('resourceReview', {}).get('resources', []) +
                workflow.get('containedEffects', [])):
        if row.get('operationId') not in operations:
            raise ValueError('unresolved report resource/effect operation reference')
        read_pointer(operations[row['operationId']], row.get('resultPath'))
    seen = set()
    for row in alerts['alerts']:
        kind = row.get('recordKind')
        if kind not in ('native-zap-alert', 'observed-security-alert'):
            raise ValueError('invalid report alert classification')
        transport = _zap_transport(row)
        if transport not in ('zap-proxy', 'zap-sendRequest', 'zap-native') or (kind == 'native-zap-alert' and transport != 'zap-native'):
            raise ValueError('report alert lost ZAP provenance')
        mappings = row.get('criterionMappings')
        if not isinstance(mappings, list):
            raise ValueError('alert criterionMappings list required')
        if row.get('scopeMapping') != ('mapped' if mappings else 'unmapped'):
            raise ValueError('alert mapping status inconsistent')
        if not mappings:
            _text(row.get('unmappedReason'), 'unmapped alert reason')
        for mapping in mappings:
            cid = mapping.get('criterionId')
            if cid not in criteria or (row['findingId'], cid) in seen:
                raise ValueError('duplicate or missing criterion mapping')
            seen.add((row['findingId'], cid))
            criterion = criteria[cid]
            if mapping.get('rawText') != criterion['rawText'] or mapping.get('source') != criterion['source']:
                raise ValueError('mapping must retain original criterion wording/source')
            _text(mapping.get('rationale'), 'alert mapping rationale')
        if kind == 'observed-security-alert':
            refs = row.get('operationIds', [])
            if not refs or any(r not in operations for r in refs):
                raise ValueError('unresolved report alert operation reference')
            if any(_zap_transport(operations[r]) not in ('zap-proxy', 'zap-sendRequest', 'zap-native') for r in refs):
                raise ValueError('report alert operation lost ZAP provenance')
    for row in scoped['alerts']:
        if indexed.get(row['findingId']) != row or not row.get('criterionMappings'):
            raise ValueError('scoped alert must be identical to mapped alert details')
    if any(any(r.get(k) != run.get(k) for k in ('workflowVersion', 'assessmentContext', 'assessmentStatus', 'reportGeneration')) for r in (alerts, scoped)):
        raise ValueError('report bundle context mismatch')
    if alerts['summary'] != _summary(alerts['alerts']) or scoped['summary'] != _summary(scoped['alerts'], alerts['alerts']):
        raise ValueError('alert counts inconsistent')
    if run.get('alertSummary') != alerts['summary']:
        raise ValueError('RUN alert summary inconsistent')


def write_bundle(output, reports, *, overwrite=False):
    """Same publication guarantees as legacy compact_results; preserve history."""
    names = ('RUN.json', 'ALERTS.json', 'SCOPE_ALERTS.json')
    requested = Path(output).absolute()
    out = requested.parent.resolve()/requested.name
    def check():
        if requested.is_symlink() or out.is_symlink():
            raise ValueError('report destination symlink')
        if out.exists():
            if not overwrite:
                raise FileExistsError(out)
            if not out.is_dir() or any(p.name not in names or p.is_symlink() or not p.is_file() for p in out.iterdir()):
                raise ValueError('overwrite only a regular three-report destination')
    check()
    data = [json.dumps(r, ensure_ascii=False, indent=2, allow_nan=False).encode() for r in reports]
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.criteria-', dir=out.parent) as temporary:
        staged = Path(temporary)/'reports'
        staged.mkdir(mode=0o700)
        for name, raw in zip(names, data):
            atomic_bytes(staged/name, raw)
        validate_report_bundle(*(json.loads((staged/n).read_bytes()) for n in names))
        check()
        if out.exists():
            for name in names:
                os.replace(staged/name, out/name)
        else:
            os.rename(staged, out)
        fd = os.open(out, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
