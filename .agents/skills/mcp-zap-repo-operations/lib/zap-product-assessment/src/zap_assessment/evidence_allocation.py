"""Finite coordinator bookkeeping for native evidence under an unchanged plan.

These mappings record an authority interpretation; they do not grant traffic,
change approvals, infer an oracle, or authenticate the referenced source prose.
"""
from urllib.parse import urlsplit

from .business_discovery import strings
from .contracts import digest
from .question_evidence import bound_context, read_pointer, verified_zap_message


REQUEST_VARIANTS = frozenset({'origin', 'route', 'requestRef'})
UNKNOWN = (None, 'unknown', 'unresolved', 'product-defined')


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('allocation ' + label + ' required')


def _origin(value):
    _text(value, 'origin')
    parsed = urlsplit(value)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.path or parsed.query or parsed.fragment
            or any(c.isspace() for c in value)):
        raise ValueError('allocation requires exact origin URLs')
    return parsed


def validate_allocation(allocation, question, operations, *, workflow, assessment_id):
    """Validate exact bindings and return operation mappings, without changing data."""
    from .criteria_workflow import approval_digest, _approval_status
    if not isinstance(allocation, dict) or type(allocation.get('version')) is not int or allocation['version'] != 1:
        raise ValueError('native evidence allocation version 1 required')
    if not isinstance(workflow, dict) or workflow.get('version') not in (2, 3) or not assessment_id:
        raise ValueError('allocation requires current criteria workflow and assessment identity')
    if not all(_approval_status(workflow).values()):
        raise ValueError('allocation requires current workflow approval')
    expected = dict(assessmentId=assessment_id, caseId=question.get('id', question.get('caseId')),
        criteriaDigest=approval_digest(workflow, 'criteria'), planDigest=approval_digest(workflow, 'plan'),
        workflowContext=workflow['context'], baseContext=bound_context(question, question=True),
        requiredEvidence=question['requiredEvidence'])
    if any(allocation.get(k) != v for k, v in expected.items()):
        raise ValueError('stale or foreign allocation binding')
    cases = [c for c in workflow['plan']['cases'] if c['id'] == expected['caseId']]
    if len(cases) != 1 or dict(cases[0], caseId=expected['caseId']) != question:
        raise ValueError('allocation question must be the exact approved case')
    _text(allocation.get('basis'), 'basis')
    for key in ('authorityRefs', 'deploymentRefs'):
        if not strings(allocation.get(key), 'allocation ' + key):
            raise ValueError('allocation ' + key + ' required')
    bindings = allocation.get('originBindings', [])
    if not isinstance(bindings, list):
        raise ValueError('allocation originBindings list required')
    aliases = set()
    for binding in bindings:
        if not isinstance(binding, dict) or set(binding) != {'from', 'to'}:
            raise ValueError('allocation exact origin from/to required')
        before, after = _origin(binding['from']), _origin(binding['to'])
        pair = (binding['from'], binding['to'])
        if (pair in aliases or pair[0] == pair[1] or before.scheme != after.scheme
                or before.port != after.port or pair[0] != expected['baseContext'].get('origin')):
            raise ValueError('allocation origin binding must preserve scheme/port and bind base origin')
        aliases.add(pair)
    rows = allocation.get('operations')
    if not isinstance(rows, list) or not rows:
        raise ValueError('allocation finite operations required')
    matrix = allocation.get('comparisonMatrix')
    matrix_variants = set()
    if 'comparisonMatrix' in allocation:
        from .role_object_matrix import MATRIX_VARIANTS
        matrix_variants = MATRIX_VARIANTS
    result, invariant, scanner = {}, None, None
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('allocation operation object required')
        oid = row.get('operationId')
        if not isinstance(oid, str) or oid not in operations or oid in result:
            raise ValueError('allocation duplicate or missing operation')
        op = operations[oid]
        units = strings(row.get('observationUnits'), 'allocation observation units')
        if (not units and not matrix_variants) or set(units) - set(question['requiredEvidence']):
            raise ValueError('allocation unit outside required evidence')
        actual = bound_context(op)
        if (row.get('context') != actual or any(v in UNKNOWN for v in actual.values())
                or any(actual.get(k) in UNKNOWN for k in
                       ('origin', 'build', 'method', 'route', 'actorRef', 'fixtureRef', 'requestRef', 'objective'))
                or any(actual.get(k) != v for k, v in workflow['context'].items())):
            raise ValueError('allocation operation context or workflow mismatch')
        base = expected['baseContext']
        if any(actual.get(k) != v for k, v in base.items() if k not in REQUEST_VARIANTS):
            raise ValueError('allocation changes a fixed case dimension')
        if actual.get('origin') != base.get('origin') and (base.get('origin'), actual.get('origin')) not in aliases:
            raise ValueError('allocation origin is not listed')
        if (op.get('caseId') != expected['caseId'] or op.get('effect') != 'read'
                or op.get('status', op.get('executionStatus')) == 'planned'
                or 'read' not in question['effects'] or not verified_zap_message(op)):
            raise ValueError('allocation requires exact case native read receipt')
        if (row.get('provenance') != op.get('provenance')
                or row.get('receiptDigest') != digest(op['zapMessageReceipt'])
                or row.get('captureDigest') != digest(op['zapCapture'])):
            raise ValueError('allocation native provenance or receipt hash mismatch')
        _text(op['provenance'].get('rawRef'), 'private raw receipt reference')
        read_pointer(op, row.get('resultPath'))
        current = {k: v for k, v in actual.items() if k not in {'route', 'requestRef'} | matrix_variants}
        identity = tuple(op['provenance'][k] for k in ('scannerResourceId', 'sessionId', 'transport'))
        if invariant is not None and (invariant != current or scanner != identity):
            raise ValueError('allocation pair context or scanner session conflict')
        invariant, scanner = current, identity
        result[oid] = row
    if matrix_variants:
        from .role_object_matrix import validate_matrix
        validate_matrix(matrix, result, operations)
    return result


def allocation_index(run, workflow, operations):
    """Reject stale/unused allocations too; absence preserves existing callers."""
    rows = run.get('evidenceAllocations', [])
    if not isinstance(rows, list):
        raise ValueError('evidenceAllocations list required')
    cases = {c['id']: c for c in workflow['plan']['cases']}
    result = {}
    for row in rows:
        if not isinstance(row, dict) or row.get('caseId') not in cases or row['caseId'] in result:
            raise ValueError('duplicate or unknown evidence allocation case')
        cid = row['caseId']
        validate_allocation(row, dict(cases[cid], caseId=cid), operations,
                            workflow=workflow, assessment_id=run.get('assessmentId'))
        result[cid] = row
    return result
