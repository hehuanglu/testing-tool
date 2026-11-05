"""Reviewed residual planning, separate from completion, authority and dispatch.

This module checks declared structure and links. It never classifies prose or
accepts a caller's 'answered' label as evidence. Source documents, when supplied,
are data already read by the caller; the core never opens files.
"""
import copy

from .business_discovery import records, references, strings, validate_question_fields
from .question_evidence import operation_index, read_pointer

KINDS = {'test-gap', 'readback-gap', 'dependency', 'method-limit', 'generalization-limit',
    'answered', 'remediation', 'unclassified'}
ACTIONS = {'readback', 'execute', 'prepare', 'investigate', 'external-dependency', 'none'}
CATEGORIES = ('actionableReadback', 'actionableExecution', 'preparationNeeded', 'investigationNeeded',
    'externalDependencies', 'methodLimits', 'conclusionLimits', 'answered', 'remediation', 'unclassified')
ACTION_BUCKET = dict(readback='actionableReadback', execute='actionableExecution', prepare='preparationNeeded',
    investigate='investigationNeeded', **{'external-dependency': 'externalDependencies'})


def validate_source_texts(review, source_documents):
    """Preparation/import check against explicitly supplied JSON documents."""
    for item in review.get('items', []):
        if item['sourceRef'] not in source_documents:
            raise ValueError('residual source document not supplied: ' + item['sourceRef'])
        actual = read_pointer(source_documents[item['sourceRef']], item['sourcePointer'])
        if not isinstance(actual, str) or actual != item['originalText']:
            raise ValueError('residual originalText does not match source: ' + item['id'])
        if item.get('selectedText') and item['selectedText'] not in actual:
            raise ValueError('residual selectedText is not in originalText: ' + item['id'])
    for ref in review.get('unreviewedRefs', []):
        if ref.get('sourceRef'):
            if ref['sourceRef'] not in source_documents:
                raise ValueError('unreviewed source document not supplied')
            read_pointer(source_documents[ref['sourceRef']], ref.get('sourcePointer'))


def _projected_questions(reconciliation):
    return records(reconciliation.get('scopeQuestions', []), 'projected residual questions')


def validate_residual_review(review, scope, reconciliation, operations, findings, *, source_documents=None):
    """Invalid identity/shape is an input error; unfinished review is diagnostic."""
    if not isinstance(review, dict) or type(review.get('version')) is not int or review['version'] != 1:
        raise ValueError('unsupported residualReview version')
    if review.get('scopeRevision') != scope.get('revision'):
        raise ValueError('residual review scope revision mismatch')
    sources = records(review.get('sources'), 'residual sources')
    for source in sources.values():
        if source.get('kind') not in ('retained-report', 'current-scope', 'current-run', 'user-scope') or not isinstance(source.get('location'), str) or not source['location']:
            raise ValueError('invalid residual source')
    criteria = records(scope.get('criteria', []), 'residual criteria')
    questions = records(scope.get('questions', []), 'residual questions')
    cases = {c['caseId']: c for c in reconciliation.get('cases', [])}
    ops = operation_index(operations)
    finding_rows = findings.get('alerts', []) if isinstance(findings, dict) else findings
    fids = records([dict(f, id=f['findingId']) for f in finding_rows], 'residual findings')
    extent = review.get('reviewExtent')
    if not isinstance(extent, dict) or extent.get('kind') not in ('selected-groups', 'all-declared-residuals'):
        raise ValueError('invalid residual reviewExtent')
    if 'basis' in extent and not isinstance(extent['basis'], str):
        raise ValueError('invalid residual review extent basis')
    references(extent.get('sourceIds'), sources, 'review extent sources')
    references(extent.get('criterionIds'), criteria, 'review extent criteria')
    if not isinstance(review.get('unreviewedRefs'), list):
        raise ValueError('explicit residual unreviewedRefs required')
    for ref in review['unreviewedRefs']:
        if not isinstance(ref, dict) or not (ref.get('criterionId') or ref.get('sourceRef')):
            raise ValueError('invalid residual unreviewed reference')
        if 'criterionId' in ref:
            references([ref['criterionId']], criteria, 'unreviewed criterion')
        if 'sourceRef' in ref:
            references([ref['sourceRef']], sources, 'unreviewed source')
            if not isinstance(ref.get('sourcePointer'), str) or not ref['sourcePointer'].startswith('/'):
                raise ValueError('unreviewed source pointer required')
    diagnostics = []
    def diagnostic(code, item=None):
        diagnostics.append(dict(code=code, **({'itemId': item['id']} if item else {})))
    if not extent.get('basis') or not extent['sourceIds'] or not extent['criterionIds']:
        diagnostic('review-extent-basis-or-universe-missing')
    items = records(review.get('items'), 'residual items')
    proposed_ids = set()
    for item in items.values():
        references([item.get('sourceRef')], sources, 'residual source')
        if item.get('kind') not in KINDS or item.get('actionClass') not in ACTIONS:
            raise ValueError('invalid residual classification')
        for key in ('basis', 'nextStep', 'scopeBasis', 'methodBoundary', 'assignmentBasis'):
            if key in item and not isinstance(item[key], str):
                raise ValueError('invalid residual ' + key)
        if not all(isinstance(item.get(k), str) and item[k].strip() for k in ('sourcePointer', 'originalText', 'selectedText')) or not item['sourcePointer'].startswith('/'):
            raise ValueError('residual source pointer and original/selected text required')
        if item['selectedText'] not in item['originalText']:
            raise ValueError('residual selectedText is not in originalText')
        for key, known in (('criterionIds', criteria), ('questionIds', questions), ('caseIds', cases), ('findingIds', fids), ('operationIds', ops)):
            references(item.get(key, []), known, 'residual ' + key)
        if set(item.get('criterionIds', [])) - set(extent['criterionIds']) or item['sourceRef'] not in extent['sourceIds']:
            raise ValueError('residual item outside declared review extent')
        if any(not set(questions[q]['criterionIds']) & set(item.get('criterionIds', [])) for q in item.get('questionIds', [])):
            raise ValueError('residual question belongs to a different criterion')
        if not item.get('criterionIds') or not item.get('basis'):
            diagnostic('residual-rationale-missing', item)
        if not item.get('nextStep'):
            diagnostic('residual-next-step-missing', item)
        kind = item['kind']; action = item['actionClass']
        if kind == 'test-gap':
            if not (item.get('questionIds') or item.get('caseIds') or item.get('proposedQuestion')):
                diagnostic('test-gap-finite-question-missing', item)
            if 'proposedQuestion' in item:
                proposal = item['proposedQuestion']
                if not isinstance(proposal, dict):
                    raise ValueError('invalid proposed residual question')
                validate_question_fields(proposal)
                if not isinstance(proposal.get('id'), str) or not proposal['id'].strip():
                    raise ValueError('proposed question ID required')
                if proposal['id'] in proposed_ids:
                    raise ValueError('duplicate proposed question ID')
                proposed_ids.add(proposal['id'])
                if proposal.get('id') in questions:
                    raise ValueError('proposed question requires a new ID')
                strings(proposal.get('requiredObservations', []), 'proposed observations')
                if not all(proposal.get(k) for k in ('id', 'question', 'closureCondition', 'requiredObservations')):
                    diagnostic('proposed-question-not-finite', item)
            if action not in ('execute', 'prepare', 'readback', 'investigate'):
                diagnostic('test-gap-action-missing', item)
        links = item.get('resultRefs', [])
        if not isinstance(links, list) or any(not isinstance(r, dict) for r in links):
            raise ValueError('invalid residual resultRefs')
        for link in links:
            references([link.get('operationId')], ops, 'residual result operation')
            read_pointer(ops[link['operationId']], link.get('resultPath'))
        if kind == 'readback-gap':
            if not links:
                diagnostic('readback-result-reference-missing', item)
            if action not in ('readback', 'prepare', 'investigate'):
                diagnostic('readback-action-missing', item)
        if kind == 'dependency':
            dependency = item.get('dependency')
            if not isinstance(dependency, dict):
                diagnostic('dependency-details-missing', item)
            else:
                strings(dependency.get('optionsEvaluated', []), 'dependency options')
                for key in ('blockedBy', 'resumptionCondition', 'preparationNextStep'):
                    if key in dependency and not isinstance(dependency[key], str):
                        raise ValueError('invalid dependency ' + key)
                if not (dependency.get('blockedBy') and dependency.get('resumptionCondition') and dependency.get('optionsEvaluated') and
                        (item.get('criterionIds') or item.get('questionIds') or item.get('caseIds'))):
                    diagnostic('dependency-details-missing', item)
                if dependency.get('preparationNextStep'):
                    diagnostic('dependency-preparation-available', item)
            if action not in ('external-dependency', 'prepare', 'investigate', 'readback'):
                diagnostic('dependency-action-missing', item)
        if kind == 'generalization-limit':
            if not item.get('scopeBasis') or not item.get('excludedConclusions'):
                diagnostic('conclusion-limit-scope-basis-missing', item)
            strings(item.get('excludedConclusions', []), 'excluded conclusions')
        if kind == 'method-limit' and not item.get('methodBoundary'):
            diagnostic('method-boundary-missing', item)
        if kind in ('method-limit', 'generalization-limit') and action == 'execute':
            diagnostic('limit-cannot-authorize-execution', item)
        if kind == 'answered' and not item.get('questionIds'):
            diagnostic('answered-question-reference-missing', item)
        if kind == 'remediation':
            if not item.get('findingIds') or not item.get('assignmentBasis'):
                diagnostic('remediation-assignment-missing', item)
        if kind == 'unclassified':
            diagnostic('residual-unclassified', item)
    for cid in extent['criterionIds']:
        if not any(cid in item.get('criterionIds', []) for item in items.values()) and not any(ref.get('criterionId') == cid for ref in review['unreviewedRefs']):
            diagnostic('declared-group-without-reviewed-items:' + cid)
    if source_documents is not None:
        validate_source_texts(review, source_documents)
    return diagnostics


def project_residual_work(review, scope, reconciliation, operations, findings, *, source_documents=None):
    if review is None:
        return dict(version=1, residualReviewStatus='not-supplied', **{k: [] for k in CATEGORIES},
            reviewDiagnostics=[dict(code='residual-review-not-supplied')], unreviewedRefs=[], reviewExtent=None,
            decision='review-needed', decisionScope='unreviewed', reasons=['Residual backlog has not been reviewed'])
    diagnostics = validate_residual_review(review, scope, reconciliation, operations, findings, source_documents=source_documents)
    projected = _projected_questions(reconciliation)
    states = {c['caseId']: c for c in reconciliation.get('cases', [])}
    result = dict(version=1, residualReviewStatus='supplied', **{k: [] for k in CATEGORIES})
    for original in review['items']:
        item = copy.deepcopy(original); kind = item['kind']; action = item['actionClass']
        qs = [projected.get(q, {}) for q in item.get('questionIds', [])]
        cs = [states[c] for c in item.get('caseIds', [])]
        unknown = any(q.get('outcomeUnknown') or q.get('questionEvidence', {}).get('unresolvedEffectIds') for q in qs) or any(c.get('outcomeUnknown') for c in cs)
        if kind == 'answered' and (not qs or any(q.get('coverage') != 'observed' for q in qs) or unknown):
            diagnostics.append(dict(code='answered-not-supported-by-current-resolver', itemId=item['id']))
            item['effectiveKind'] = 'unclassified'; result['unclassified'].append(item)
            if unknown:
                item['effectiveActionClass'] = 'readback' if item.get('resultRefs') else 'investigate'
                result[ACTION_BUCKET[item['effectiveActionClass']]].append(copy.deepcopy(item))
            continue
        if kind == 'generalization-limit' and (any(q.get('coverage') not in ('observed', 'user-excluded') for q in qs) or any(c.get('status') not in ('observed', 'not-applicable', 'user-excluded') for c in cs)):
            diagnostics.append(dict(code='conclusion-limit-conflicts-with-assigned-open-question', itemId=item['id']))
            item['effectiveKind'] = 'unclassified'; result['unclassified'].append(item); continue
        if unknown and kind != 'unclassified':
            diagnostics.append(dict(code='related-unknown-effect-needs-readback', itemId=item['id']))
            action = 'readback' if item.get('resultRefs') else 'investigate'
            item['effectiveActionClass'] = action
            result[ACTION_BUCKET[action]].append(item); continue
        if kind == 'dependency' and (item.get('dependency') or {}).get('preparationNextStep'):
            item['effectiveActionClass'] = 'prepare'; result['preparationNeeded'].append(item); continue
        if kind in ('method-limit', 'generalization-limit'):
            result['methodLimits' if kind == 'method-limit' else 'conclusionLimits'].append(item)
            if action == 'execute':
                item['effectiveKind'] = 'unclassified'; result['unclassified'].append(copy.deepcopy(item))
            elif action != 'none':result[ACTION_BUCKET[action]].append(copy.deepcopy(item))
            continue
        if kind in ('answered', 'remediation', 'unclassified'):
            bucket = kind
        elif action != 'none':
            bucket = ACTION_BUCKET[action]
        else:
            bucket = {'method-limit': 'methodLimits', 'generalization-limit': 'conclusionLimits'}.get(kind, 'unclassified')
        result[bucket].append(item)
    unreviewed = copy.deepcopy(review['unreviewedRefs'])
    extent = copy.deepcopy(review['reviewExtent'])
    if extent['kind'] == 'selected-groups':
        for criterion in scope.get('criteria', []):
            if criterion['id'] not in extent['criterionIds'] and not any(r.get('criterionId') == criterion['id'] for r in unreviewed):
                unreviewed.append(dict(criterionId=criterion['id'], reason='outside-selected-review-groups'))
    actionable = any(result[k] for k in CATEGORIES[:4])
    # Unreviewed refs outside selected groups limit the claim, but do not prevent
    # a finite reviewed-scope decision. Unreviewed selected groups do prevent it.
    pending_review = bool(diagnostics or result['unclassified'] or extent['kind'] == 'all-declared-residuals' and unreviewed or any(
        r.get('criterionId') in extent['criterionIds'] or not r.get('criterionId') for r in unreviewed))
    decision = 'continue' if actionable else 'review-needed' if pending_review else 'handoff-with-dependencies' if result['externalDependencies'] else 'no-further-dynamic-action-in-reviewed-scope'
    reasons = ['Decision covers only the declared review universe; it does not establish assignment completion']
    if reconciliation.get('continuationStoppedByUser') is True:
        decision = 'review-needed'; reasons.append('User stop honored; proposed next work retained without dispatch')
    aggregate_states = [q['aggregateAccounting'] for q in projected.values() if q.get('aggregateAccounting')]
    if aggregate_states:
        result['accountedAggregateIds'] = sorted(s['aggregateQuestionId'] for s in aggregate_states if s['accountingStatus']=='accounted')
        result['pendingAggregateIds'] = sorted(s['aggregateQuestionId'] for s in aggregate_states if s['accountingStatus']=='pending')
    result.update(reviewDiagnostics=diagnostics, unreviewedRefs=unreviewed, reviewExtent=extent,
        decision=decision, decisionScope='reviewed-scope-only', reasons=reasons)
    return result
