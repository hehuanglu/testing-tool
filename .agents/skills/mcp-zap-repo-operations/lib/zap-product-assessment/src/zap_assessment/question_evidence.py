"""Validate reviewed semantic readback links, never infer verdicts from HTTP/raw data.

Pointers are RFC 6901 paths relative to an operation. Explicit compatibility uses
{dimension: {from: observed, to: required}}; route/method/input/origin/objective
cannot be inherited. History and the execution journal remain authoritative.
"""
import copy
from .business_discovery import strings, validate_question_fields, CONTEXT_KEYS


def bound_context(row, *, question=False):
    """Use only this record's explicit context, never a neighboring operation.

    Operation/action state is an execution state, so only question state or an
    explicit coverageContext.state denotes product state.
    """
    context=copy.deepcopy(row.get('coverageContext',{}))
    for key in CONTEXT_KEYS-({'state'} if not question else set()):
        if key in row and row[key] is not None:
            if key in context and context[key]!=row[key]:
                raise ValueError('conflicting explicit coverage context')
            context[key]=row[key]
    validate_question_fields({'coverageContext':context})
    return context


def merge_context(left,right):
    if any(k in left and left[k]!=v for k,v in right.items()):
        raise ValueError('pending effect context conflict')
    return {**left,**right}


def operation_index(operations):
    rows = list(operations.values()) if isinstance(operations, dict) else list(operations)
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'] or row['id'] in result:
            raise ValueError('invalid/duplicate evidence operation ID')
        result[row['id']] = row
    return result


def read_pointer(operation, path):
    if not isinstance(path, str) or not path.startswith('/'):
        raise ValueError('operation-relative resultPath required')
    value = operation
    for raw in path[1:].split('/'):
        import re
        if re.search(r'~(?![01])', raw):
            raise ValueError('invalid resultPath escape')
        key = raw.replace('~1', '/').replace('~0', '~')
        try:
            if isinstance(value, list):
                if not key.isdigit() or (len(key) > 1 and key.startswith('0')):
                    raise ValueError('invalid resultPath index')
                value = value[int(key)]
            elif isinstance(value, dict):
                value = value[key]
            else:
                raise ValueError('resultPath traverses scalar')
        except (KeyError, IndexError):
            raise ValueError('unresolved resultPath') from None
    if value is None or value == '' or value == [] or value == {}:
        raise ValueError('empty resultPath readback')
    return value


def context_diagnostics(expected, actual, compatibility=None, operation_id=None):
    if not isinstance(actual, dict):
        raise ValueError('evidence context object required')
    validate_question_fields({'coverageContext': actual})
    compatibility = compatibility or {}
    if not isinstance(compatibility, dict):
        raise ValueError('invalid evidence compatibility')
    dimensions = compatibility.get('dimensions', {})
    if not isinstance(dimensions, dict):
        raise ValueError('compatibility dimensions mapping required')
    if compatibility:
        if not compatibility.get('basis') or not isinstance(compatibility['basis'], str):
            raise ValueError('compatibility basis required')
        strings(compatibility.get('operationIds'), 'compatibility operation IDs')
        if operation_id not in compatibility['operationIds']:
            raise ValueError('compatibility does not bind operation')
        if set(dimensions) - set(expected):
            raise ValueError('compatibility dimension outside question')
        for key, binding in dimensions.items():
            if key in ('origin', 'method', 'route', 'inputLocation', 'objective'):
                raise ValueError('request/objective cannot be inherited')
            if not isinstance(binding, dict) or set(binding) != {'from', 'to'}:
                raise ValueError('explicit compatibility from/to required')
            if binding['from'] != actual.get(key) or binding['to'] != expected[key]:
                raise ValueError('compatibility dimension mismatch')
    diagnostics = []
    for key, required in expected.items():
        observed = actual.get(key)
        if required in (None, 'unknown', 'unresolved', 'product-defined') or observed in (None, 'unknown', 'unresolved', 'product-defined'):
            diagnostics.append('context-unknown:' + key)
        elif observed != required and key not in dimensions:
            diagnostics.append('context-mismatch:' + key)
    return diagnostics


def validate_observation_links(observation, operations):
    """Validate references, including context and resolution links after redaction."""
    if not isinstance(observation,dict):raise ValueError('observation object required')
    ops = operation_index(operations)
    strings(observation.get('operationIds', []), 'observation operation IDs')
    if set(observation.get('operationIds', [])) - set(ops):
        raise ValueError('unresolved observation operation ID')
    links = observation.get('evidenceLinks', [])
    if not isinstance(links, list):
        raise ValueError('invalid evidenceLinks')
    for link in links:
        if not isinstance(link, dict) or link.get('operationId') not in ops:
            raise ValueError('unresolved evidence operation ID')
        if link.get('role') not in ('support', 'context'):
            raise ValueError('invalid evidence link role')
        strings(link.get('observationUnits', []), 'link observation units')
        if link['role'] == 'support' and (not link.get('observationUnits') or link.get('resultRead') is not True or not isinstance(link.get('basis'), str) or not link['basis'].strip()):
            raise ValueError('support requires read units and basis')
        read_pointer(ops[link['operationId']], link.get('resultPath'))
        if not isinstance(link.get('context'), dict):
            raise ValueError('evidence context required')
        validate_question_fields({'coverageContext': link['context']})
        compatibility = link.get('compatibility')
        if compatibility:
            if not isinstance(compatibility, dict):
                raise ValueError('invalid compatibility')
            strings(compatibility.get('operationIds'), 'compatibility operation IDs')
            if set(compatibility['operationIds']) - set(ops):
                raise ValueError('unresolved compatibility operation ID')
    resolutions = observation.get('resolvedEffects', [])
    if not isinstance(resolutions, list):
        raise ValueError('invalid resolvedEffects')
    for resolution in resolutions:
        if (not isinstance(resolution, dict) or not isinstance(resolution.get('actionId'), str) or
            resolution.get('resolutionOperationId') not in ops or not isinstance(resolution.get('basis'), str) or not resolution['basis']):
            raise ValueError('invalid effect resolution')
        read_pointer(ops[resolution['resolutionOperationId']], resolution.get('resultPath'))
    return ops


def merge_pending_binding(previous, supplied):
    """Merge observations without replacing identity retained by an earlier source."""
    binding = ('caseId', 'assessmentId', 'taskId', 'workerId', 'packetDigest', 'effect')
    if any(previous.get(key) is not None and supplied.get(key) is not None
           and previous[key] != supplied[key] for key in binding):
        raise ValueError('pending effect binding conflict')
    merged = {**previous, **copy.deepcopy(supplied)}
    for key in binding:
        if merged.get(key) is None and key in previous:
            merged[key] = previous[key]
    merged['coverageContext'] = merge_context(previous.get('coverageContext', {}), bound_context(supplied))
    return merged


def collect_pending_effects(operations=(), attempts=(), extra=()):
    """Union operation uncertainty and durable intents; never authorize redispatch."""
    ops = operation_index(operations)
    result = {}
    grouped = {}
    for attempt in attempts:
        if not isinstance(attempt, dict):
            continue
        row = attempt.get('data', attempt)
        if not isinstance(row, dict) or not row.get('actionId'):
            continue
        if row is not attempt:
            row = dict(row)
            if attempt.get('kind') in ('intent', 'unknown', 'acknowledged', 'accepted', 'reconciled'):
                row['state'] = attempt['kind']
        grouped.setdefault(row['actionId'], []).append(row)
    for aid, history in grouped.items():
        if any(row.get('effect') in ('mutation', 'start') for row in history) and any(
                row.get('state') in ('intent', 'unknown') for row in history):
            merged = {}
            for row in history:
                merged = merge_pending_binding(merged, row)
            result[aid] = dict(merged, actionId=aid, effectId=aid, state='unknown')
    for op in ops.values():
        if op.get('outcomeUnknown') or op.get('pendingStart'):
            aid = op.get('actionId', op['id'])
            supplied = {key: op[key] for key in ('caseId', 'questionIds', 'dependsOnCases') if key in op}
            supplied.update(actionId=aid, effectId=aid, operationId=op['id'], coverageContext=bound_context(op))
            result[aid] = merge_pending_binding(result.get(aid, {}), supplied)
    for effect in extra:
        if not isinstance(effect, dict) or not effect.get('actionId', effect.get('effectId')):
            raise ValueError('invalid pending effect')
        aid = effect.get('actionId', effect.get('effectId'))
        supplied = {key: value for key, value in effect.items() if key != 'resolved'}
        result[aid] = merge_pending_binding(result.get(aid, {}), dict(supplied, actionId=aid, effectId=aid))
    return list(result.values())


def collect_run_pending(run, coordinator_effects=()):
    """Return all retained uncertainty before validating semantic resolutions."""
    return collect_pending_effects(run.get('operations', []), run.get('actionHistory', []),
                                   [*pending_effects_from_run(run), *coordinator_effects])


def pending_effects_from_run(run):
    """Read uncertainty retained in RUN/continuation without modifying snapshots."""
    effects=copy.deepcopy(run.get('pendingEffects',[]))
    operations=operation_index(run.get('operations',[]))
    continuation=run.get('continuation') or {}
    if not isinstance(continuation,dict):return effects
    for i,row in enumerate(continuation.get('pendingOperations',[]) or []):
        if not isinstance(row,dict):
            effects.append(dict(actionId='unbound-continuation-'+str(i),effectId='unbound-continuation-'+str(i)))
            continue
        if not (row.get('outcomeUnknown') or row.get('pendingStart') or row.get('lastKnownState') in ('unknown','intent','pending-start','unknown-start')):continue
        reference=row.get('operationRef')
        op=operations.get(reference,{}) if isinstance(reference,str) else {}
        aid=row.get('actionId') or op.get('actionId') or reference
        if not isinstance(aid,str) or not aid:aid='unbound-continuation-'+str(i)
        effect={k:copy.deepcopy(op[k]) for k in ('caseId','questionIds') if k in op}
        effect['coverageContext']=bound_context(op)
        effect.update({k:copy.deepcopy(row[k]) for k in ('caseId','questionIds') if k in row})
        effect['coverageContext']=merge_context(effect['coverageContext'],bound_context(row))
        effect.update(actionId=aid,effectId=aid)
        if isinstance(reference,str):effect['operationId']=reference
        effects.append(effect)
    return effects


def resolved_effect_ids(observation, operations, pending_effects):
    resolved = set()
    effects = {e['actionId']: e for e in pending_effects}
    for resolution in observation.get('resolvedEffects', []):
        aid = resolution['actionId']
        if aid not in effects:
            raise ValueError('resolution references unknown action')
        effect = effects[aid]
        op = operations[resolution['resolutionOperationId']]
        fact = read_pointer(op, resolution['resultPath'])
        if not isinstance(fact, dict) or fact.get('actionId') != aid or fact.get('resolved') is not True:
            raise ValueError('resolution must read the exact action outcome')
        expected = effect.get('coverageContext', {})
        actual = merge_context(bound_context(op),fact.get('context', {}))
        if context_diagnostics(expected, actual):
            raise ValueError('effect resolution context mismatch')
        if effect.get('caseId') and fact.get('caseId') != effect['caseId']:
            raise ValueError('effect resolution case mismatch')
        # With no object context the exact action AND case are still required.
        if not expected.get('objectRef') and not effect.get('caseId'):
            raise ValueError('effect identity insufficient for resolution')
        resolved.add(aid)
    return resolved


def affected(question, effect, observation):
    cid = question.get('caseId')
    qid = question.get('id')
    dependencies = set(question.get('dependsOnCases', []) + question.get('responsibilityIds', []))
    if cid:
        dependencies.add(cid)
    if effect.get('caseId') in dependencies or qid and qid in effect.get('questionIds', []):
        return True
    if effect.get('actionId') in question.get('actionIds', []) or effect.get('actionId') in [a.get('id') for a in question.get('actions', [])]:
        return True
    linked = set(observation.get('operationIds', [])) | {l['operationId'] for l in observation.get('evidenceLinks', [])}
    if effect.get('operationId') in linked:
        return True
    expected, actual = bound_context(question,question=True), effect.get('coverageContext', {})
    # Only a known independent object proves non-dependence in the absence of IDs.
    if expected.get('objectRef') not in (None, 'unknown') and actual.get('objectRef') not in (None, 'unknown'):
        return expected['objectRef'] == actual['objectRef']
    if effect.get('caseId') and dependencies:
        return False
    return True  # insufficient binding: surface a diagnostic, never assume unrelated


def verified_zap_message(operation):
    """Bind a reviewed capture receipt to its operation and case context."""
    provenance = operation.get('provenance', {})
    if not isinstance(provenance, dict) or provenance.get('transport') not in ('zap-proxy', 'zap-sendRequest', 'zap-native'):
        return False
    receipt = operation.get('zapMessageReceipt')
    if not isinstance(receipt, dict):
        return False
    identity = ('scannerResourceId', 'sessionId', 'messageId')
    for key in identity:
        value = provenance.get(key)
        if not isinstance(value, str) or not value.strip() or receipt.get(key) != value:
            return False
    context = bound_context(operation)
    for key in ('actorRef', 'fixtureRef', 'requestRef'):
        value = context.get(key)
        if not isinstance(value, str) or not value.strip() or receipt.get(key) != value:
            return False
    if receipt.get('caseId') != operation.get('caseId') or not operation.get('caseId'):
        return False
    try:
        if receipt.get('resultPath') != '/zapCapture':
            return False
        capture = read_pointer(operation, receipt['resultPath'])
    except ValueError:
        return False
    if not isinstance(capture, dict) or any(capture.get(key) != receipt[key] for key in identity):
        return False
    for key in ('requestSha256', 'responseSha256'):
        value = receipt.get(key)
        if (not isinstance(value, str) or len(value) != 64 or capture.get(key) != value
                or any(char not in '0123456789abcdef' for char in value)):
            return False
    return True


def resolve_question_evidence(question, observation, operations, pending_effects=(), *,
                              allocation=None, workflow=None, assessment_id=None):
    validate_question_fields(question)
    ops = validate_observation_links(observation, operations)
    allocated = None
    if allocation is not None:
        from .evidence_allocation import validate_allocation
        allocated = validate_allocation(allocation, question, ops,
            workflow=workflow, assessment_id=assessment_id)
    required = set(question.get('requiredEvidence', question.get('requiredObservations', [])))
    require_zap = question.get('requireZapMessageEvidence') is True
    if 'evidenceLinks' not in observation:
        if require_zap:
            return dict(supportedUnits=[], missingUnits=sorted(required), contextDiagnostics=['verified-zap-message-required'],
                        unresolvedEffectIds=[], supportOperationIds=[], contextOperationIds=[])
        units = set(observation.get('evidenceUnits', observation.get('observationUnits', [])))
        return dict(supportedUnits=sorted(units), missingUnits=sorted(required - units), contextDiagnostics=['legacy-unit-labels'],
            unresolvedEffectIds=[], supportOperationIds=observation.get('operationIds', []), contextOperationIds=[])
    resolved = resolved_effect_ids(observation, ops, pending_effects)
    unresolved = [e['effectId'] for e in pending_effects if not e.get('resolved') and e['actionId'] not in resolved and affected(question, e, observation)]
    diagnostics = []
    units, support, context = set(), [], []
    support_contexts=[]
    for link in observation['evidenceLinks']:
        oid = link['operationId']
        if link['role'] == 'context':
            context.append(oid)
            continue
        if require_zap and (ops[oid].get('caseId') != question.get('id', question.get('caseId'))
                            or not verified_zap_message(ops[oid])):
            diagnostics.append(oid + ':verified-zap-message-required')
            continue
        if allocated is not None:
            mapping = allocated.get(oid)
            if (mapping is None or link.get('compatibility') or
                    any(link.get(k) != mapping.get(k) for k in
                        ('observationUnits', 'resultPath', 'context'))):
                diagnostics.append(oid + ':unlisted-allocation-evidence-link')
                continue
            mismatch = []
        else:
            mismatch = context_diagnostics(bound_context(question,question=True), link['context'], link.get('compatibility'), oid)
        op_context = bound_context(ops[oid])
        mismatch += context_diagnostics(op_context, link['context'])
        if mismatch:
            diagnostics.extend(oid + ':' + d for d in mismatch)
            continue
        effective=copy.deepcopy(link['context'])
        for key,binding in link.get('compatibility',{}).get('dimensions',{}).items():effective[key]=binding['to']
        support_contexts.append(effective)
        units.update(link['observationUnits'])
        support.append(oid)
    if allocated is None and support_contexts and any(c!=support_contexts[0] for c in support_contexts[1:]):
        diagnostics.append('support-contexts-conflict-review-required')
        units.clear()
    if allocated is not None:
        from .role_object_matrix import matrix_link_diagnostics
        matrix_diagnostics = matrix_link_diagnostics(allocation, observation)
        if matrix_diagnostics:
            diagnostics.extend(matrix_diagnostics)
            units.clear()
    for key in ('evidenceUnits', 'observationUnits'):
        if key in observation:
            declared = set(strings(observation[key], key))
            if declared - units:
                raise ValueError('declared units exceed supported evidence links')
    if unresolved:
        diagnostics.append('pending-effects-require-readback')
        units.clear()
    return dict(supportedUnits=sorted(units), missingUnits=sorted(required - units), contextDiagnostics=sorted(set(diagnostics)),
        unresolvedEffectIds=sorted(unresolved), supportOperationIds=list(dict.fromkeys(support)), contextOperationIds=list(dict.fromkeys(context)))
