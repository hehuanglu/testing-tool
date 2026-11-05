"""Offline user criteria and report projections, independent of runner admission.

The tester interprets documents, applicability, observations and associations.
These helpers check declared structure and joins; they are not a policy oracle.
No document content is imported, dispatched or executed.
"""
import copy
import hashlib
import json


def stable_id(namespace, value):
    payload = json.dumps([namespace, value], sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def index(rows, label):
    if not isinstance(rows, (list, tuple)) or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f'{label} records must be a list of objects')
    result = {}
    for row in rows:
        key = row.get('id')
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f'{label} ID required')
        if key in result:
            raise ValueError(f'duplicate {label} ID: {key}')
        result[key] = row
    return result


def refs(values, known, label):
    if not isinstance(values, list) or any(not isinstance(v, str) or v not in known for v in values):
        raise ValueError(f'unresolved {label} reference')
    if len(values) != len(set(values)):
        raise ValueError(f'duplicate {label} reference')


def normalize_scope(document, previous=None):
    """Normalize an agent-prepared representation of JSON/text, never parse policy.

    Missing IDs use source identity, source ID or original location/text, never
    array position. Persist these IDs when editing the source. Prior duties are
    retained; removal needs an explicit user-excluded row with scopeBasis.
    """
    if not isinstance(document, dict):
        raise ValueError('agent-prepared scope object required')
    scope = copy.deepcopy(document)
    from .business_discovery import validate_question_fields
    if 'workflowVersion' in scope and (type(scope['workflowVersion']) is not int or scope['workflowVersion'] != 1):
        raise ValueError('unsupported scope workflowVersion')
    sources = index(scope.get('sources', []), 'source')
    if previous:
        for source in previous.get('sources', []):
            if source['id'] not in sources:
                scope.setdefault('sources', []).append(copy.deepcopy(source))
        sources = index(scope.get('sources', []), 'source')
    for source in sources.values():
        if not source.get('location'):
            raise ValueError('source location required')
    for criterion in scope.get('criteria', []):
        source = criterion.get('source', {})
        if (source.get('id') not in sources or not isinstance(source.get('location'), str) or not source['location'] or
            not isinstance(criterion.get('originalText'), str) or not criterion['originalText']):
            raise ValueError('criterion original text and source location required')
        criterion.setdefault('id', 'criterion-' + stable_id(source['id'],
            {'sourceId': criterion['sourceId']} if criterion.get('sourceId') else
            {'location': source['location'], 'text': criterion['originalText']}))
    if previous:
        prior = normalize_scope(previous)
        if prior.get('workflowVersion')==1 and scope.get('workflowVersion')!=1:
            raise ValueError('workflowVersion cannot downgrade to legacy closure')
        for key in ('assessmentId', 'product', 'environment'):
            if prior.get(key) is not None and scope.get(key) != prior[key]:
                raise ValueError(f'prior scope {key} changed')
        if scope.get('boundaries') != prior.get('boundaries') and scope.get('revision') == prior.get('revision'):
            raise ValueError('scope boundaries changed without a new revision')
        for field in ('sources', 'criteria', 'questions'):
            current = index(scope.get(field, []), field)
            if set(current) - {r['id'] for r in prior.get(field, [])} and scope.get('revision') == prior.get('revision'):
                raise ValueError('scope additions require a new revision')
            for old in prior.get(field, []):
                if old['id'] not in current:
                    scope.setdefault(field, []).append(copy.deepcopy(old))
                elif current[old['id']] != old:
                    if scope.get('revision') == prior.get('revision'):
                        raise ValueError('scope content changed without a new revision')
                    if field == 'questions' and current[old['id']].get('disposition') != 'user-excluded':
                        if any(current[old['id']].get(k) != old.get(k) for k in ('question', 'closureCondition')):
                            raise ValueError('changed question semantics require a new ID; retain prior question')
                        # A revised question cannot silently discard prior observation duties.
                        for key in ('requiredObservations', 'criterionIds', 'responsibilityIds', 'prerequisites'):
                            current[old['id']][key] = list(dict.fromkeys(old.get(key, []) + current[old['id']].get(key, [])))
            if field == 'sources':
                sources = index(scope[field], 'source')
        history = copy.deepcopy(prior.get('history', []))
        if scope.get('revision') != prior.get('revision'):
            history.append({k: copy.deepcopy(prior.get(k)) for k in ('revision', 'sources', 'criteria', 'questions', 'boundaries')})
        scope['history'] = history
    criteria = index(scope.get('criteria', []), 'criterion')
    questions = index(scope.get('questions', []), 'question')
    native = set()
    for c in criteria.values():
        s = c['source']
        if s['id'] not in sources:
            raise ValueError('unresolved source reference')
        if c.get('sourceId'):
            if not isinstance(c['sourceId'], (str, int)):
                raise ValueError('source criterion ID must be text or integer')
            identity = (s['id'], c['sourceId'])
            if identity in native:
                raise ValueError('duplicate source criterion ID in namespace')
            native.add(identity)
        app = c.get('applicability', {'status': 'unknown'})
        if app.get('status') not in ('applicable', 'not-applicable', 'unknown'):
            raise ValueError('invalid applicability')
        if app['status'] == 'not-applicable':
            if not app.get('basis') or app.get('gapKind'):
                raise ValueError('inapplicability needs product basis; prerequisite is not N/A')
        if c.get('disposition') not in (None, 'assigned', 'user-excluded'):
            raise ValueError('invalid criterion disposition')
        if c.get('disposition') == 'user-excluded' and not c.get('scopeBasis'):
            raise ValueError('only user changes scope')
        if 'coverageHistory' in c:
            from .coverage_presentation import validate_coverage_history
            validate_coverage_history(c['coverageHistory'], sources, c['id'])
    for q in questions.values():
        validate_question_fields(q)
        if q.get('questionRole', 'executable') not in ('executable', 'retained-aggregate'):
            raise ValueError('invalid questionRole')
        refs(q.get('criterionIds'), criteria, 'criterion')
        if not q['criterionIds'] or not q.get('question'):
            raise ValueError('question and parent criteria required')
        if q.get('disposition') not in (None, 'assigned', 'user-excluded'):
            raise ValueError('invalid question disposition')
        if q.get('disposition') == 'user-excluded' and not q.get('scopeBasis'):
            raise ValueError('only user changes question scope')
        for key in ('requiredObservations', 'responsibilityIds', 'contextResponsibilityIds', 'prerequisites'):
            values = q.get(key, [])
            if not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values) or len(set(values)) != len(values):
                raise ValueError(f'invalid question {key}')
        if 'refinesQuestionId' in q:
            refs([q['refinesQuestionId']], questions, 'refined question')
            parent = questions[q['refinesQuestionId']]
            if parent.get('questionRole') != 'retained-aggregate' or not set(q['criterionIds']) <= set(parent['criterionIds']):
                raise ValueError('refinement must retain aggregate criterion boundary')
            for key, value in parent.get('coverageContext', {}).items():
                if q.get('coverageContext', {}).get(key) != value:
                    raise ValueError('refinement changes aggregate boundary')
    for qid in questions:
        visited = set(); current = qid
        while current is not None:
            if current in visited:
                raise ValueError('question refinement cycle')
            visited.add(current); current = questions[current].get('refinesQuestionId')
    return scope


def canonical_alerts(alerts):
    """Preserve all findings and native counts; never guess cross-session dedup.

    Existing findingId denotes a caller-established canonical identity. A native
    id remains native. Without a source/session namespace content-derived IDs
    preserve separate records and explicitly limit attribution.
    """
    result = copy.deepcopy(alerts if isinstance(alerts, dict) else {'alerts': alerts})
    if 'alerts' not in result:
        if 'findings' in result:
            result['alerts'] = result.pop('findings')
        elif not result or set(result) <= {'summary', 'limitations', 'taskCompletion', 'scope'}:
            result['alerts'] = []
        else:
            raise ValueError('alerts/findings list required; adapt native report explicitly')
    rows = result['alerts']
    if not isinstance(rows, list):
        raise ValueError('alerts must be a list')
    ids = set()
    for finding in rows:
        if not isinstance(finding, dict):
            raise ValueError('finding must be an object')
        if not finding.get('findingId'):
            identity = {k: v for k, v in finding.items() if k not in ('criterionIds', 'criterionMappings')}
            native_id = finding.get('nativeAlertId', finding.get('nativeId', finding.get('id')))
            namespace = {k: finding[k] for k in ('product', 'origin', 'session', 'sessionId', 'sourceScope') if finding.get(k) is not None}
            if native_id is not None and namespace and finding.get('source'):
                identity = dict(source=finding['source'], namespace=namespace, nativeId=native_id)
            finding['findingId'] = 'finding-' + stable_id('assessment-finding', identity)
        fid = finding['findingId']
        if not isinstance(fid, str) or fid in ids:
            raise ValueError('duplicate/invalid canonical finding ID; reconcile source identity explicitly')
        ids.add(fid)
        finding.setdefault('attribution', 'unknown unless source/session and before/after data establish otherwise')
    return result


def project_scope(document, assessment, run, alerts, reconciliation=None):
    """Join every assigned criterion, with coverage separate from security outcome."""
    scope = normalize_scope(document)
    assessment = copy.deepcopy(assessment or {})
    if assessment and scope.get('revision') != assessment.get('scopeRevision'):
        raise ValueError('scope assessment revision mismatch')
    criteria = index(scope.get('criteria', []), 'criterion')
    questions = index(scope.get('questions', []), 'question')
    operations = index(run.get('operations', []), 'operation')
    findings = {f['findingId']: f for f in alerts['alerts']}
    cases = {c['caseId']: c for c in (reconciliation or {}).get('cases', [])}
    observations = assessment.get('questionObservations', {})
    if set(observations) - set(questions):
        raise ValueError('unresolved question observation reference')
    for operation in operations.values():
        refs(operation.get('criterionIds', []), criteria, 'criterion')
        refs(operation.get('questionIds', []), questions, 'question')
    from .question_evidence import collect_pending_effects, resolve_question_evidence, validate_observation_links, resolved_effect_ids, pending_effects_from_run
    new_workflow=scope.get('workflowVersion')==1
    pending=collect_pending_effects(operations,run.get('actionHistory',[]),
        (reconciliation or {}).get('pendingEffects',[])+pending_effects_from_run(run))
    if new_workflow:
        resolved=set()
        for observation in list(observations.values())+list((reconciliation or {}).get('observations',{}).values()):
            validate_observation_links(observation,operations)
            resolved.update(resolved_effect_ids(observation,operations,pending))
        pending=[{**e,'resolved':e['actionId'] in resolved} for e in pending]
    qrows = {}
    for qid, question in questions.items():
        refs(question.get('responsibilityIds', []), cases, 'responsibility')
        refs(question.get('contextResponsibilityIds', []), cases, 'context responsibility')
        obs = observations.get(qid, {})
        refs(obs.get('operationIds', []), operations, 'operation')
        if obs.get('outcome') not in (None, 'matched', 'violated', 'unknown'):
            raise ValueError('invalid question outcome')
        required = set(question.get('requiredObservations', []))
        units = obs.get('observationUnits', [])
        if not isinstance(units, list) or any(not isinstance(u, str) for u in units):
            raise ValueError('invalid observation units')
        evidence=None
        if new_workflow:
            evidence=resolve_question_evidence(question,{**obs,'evidenceLinks':obs.get('evidenceLinks',[])},operations,pending)
            units=evidence['supportedUnits']
        missing = sorted(required - set(units))
        linked = [cases[cid] for cid in question.get('responsibilityIds', [])]
        linked_open = [c for c in linked if c['status'] not in ('observed', 'not-applicable', 'user-excluded')]
        op_rows = [operations[oid] for oid in obs.get('operationIds', [])]
        # ACK/planned/running never establish an observation-complete question.
        op_open = any(o.get('status', o.get('executionStatus')) != 'completed' for o in op_rows)
        unknown = obs.get('outcomeUnknown') or any(c.get('outcomeUnknown') for c in linked) or any(o.get('outcomeUnknown') for o in op_rows)
        supported = bool(op_rows) or any(c['status'] == 'observed' for c in linked) and not linked_open
        if new_workflow:
            op_open=False
            unknown=bool(evidence['unresolvedEffectIds']) or bool(obs.get('outcomeUnknown') and not obs.get('resolvedEffects')) or any(c.get('outcomeUnknown') for c in linked)
            supported=bool(evidence['supportOperationIds'])

        sufficient = bool(required and question.get('closureCondition') and supported and not missing and
            not linked_open and not op_open and not unknown and obs.get('resultRead') is True and
            obs.get('outcome') in ('matched', 'violated') and obs.get('basis') and
            not question.get('unresolved') and not obs.get('unresolved') and not obs.get('blockers') and
            (not question.get('expectationRequired') or bool(question.get('expectedBehavior') and question.get('expectationBasis'))))
        blockers = copy.deepcopy(obs.get('blockers', []))
        blockers += [c for c in linked_open if c['status'] == 'blocked']
        state = 'observed' if sufficient else 'blocked' if blockers or unknown else 'partial' if units or op_rows else 'not-performed'
        if question.get('disposition') == 'user-excluded':
            state = 'user-excluded'
        qrows[qid] = {**copy.deepcopy(question), 'coverage': state, 'observation': obs,
            'missingObservations': missing, 'blockers': blockers, 'outcomeUnknown': bool(unknown),
            'securityAssessment': 'violation-supported' if sufficient and obs['outcome'] == 'violated' else
                'no-violation-observed' if sufficient else 'inconclusive'}
        if evidence is not None:qrows[qid]['questionEvidence']=evidence
    from .round_closure import review_aggregate_obligations
    from .residual_review import project_residual_work
    preliminary_residual = project_residual_work(assessment.get('residualReview'), scope,
        {**(reconciliation or {}), 'scopeQuestions': list(qrows.values())}, list(operations.values()), alerts)
    aggregate_accounting = review_aggregate_obligations(scope, assessment, list(qrows.values()), preliminary_residual)
    for state in aggregate_accounting['states']:
        q = qrows[state['aggregateQuestionId']]
        q['aggregateAccounting'] = copy.deepcopy(state)
        if q.get('disposition') != 'user-excluded':
            q['coverage'] = state['coverage']
        if state['accountingStatus'] == 'accounted':
            q['missingObservations'] = list(state['unansweredObligationIds'])
            children = [c for c in qrows.values() if c.get('refinesQuestionId') == q['id']]
            q['securityAssessment'] = ('violation-supported' if any(c['securityAssessment'] == 'violation-supported' for c in children)
                else 'no-violation-observed' if q['coverage'] == 'observed' and children else 'inconclusive')
    mappings = assessment.get('mappings', [])
    seen = set()
    for mapping in mappings:
        refs([mapping.get('criterionId')], criteria, 'criterion')
        refs([mapping.get('findingId')], findings, 'finding')
        if not mapping.get('rationale') or mapping.get('certainty') not in ('supported', 'uncertain'):
            raise ValueError('mapping rationale and certainty required')
        if not isinstance(mapping.get('violation', False), bool):
            raise ValueError('invalid mapping violation')
        refs(mapping.get('questionIds', []), questions, 'question')
        refs(mapping.get('operationIds', []), operations, 'operation')
        if any(mapping['criterionId'] not in questions[q]['criterionIds'] for q in mapping.get('questionIds', [])):
            raise ValueError('mapping question belongs to a different criterion')
        if mapping['certainty'] == 'supported' and not (mapping.get('observationBasis') and findings[mapping['findingId']].get('source')):
            raise ValueError('supported mapping requires observation basis and finding provenance')
        pair = (mapping['criterionId'], mapping['findingId'])
        if pair in seen:
            raise ValueError('duplicate criterion/finding association')
        seen.add(pair)
    rows = []
    open_work = []
    for cid, criterion in criteria.items():
        qs = [q for q in qrows.values() if cid in q['criterionIds']]
        associations = [m for m in mappings if m['criterionId'] == cid]
        app = criterion.get('applicability', {'status': 'unknown'})
        gaps = list(criterion.get('unresolved', []))
        excluded = criterion.get('disposition') == 'user-excluded'
        if excluded or app['status'] == 'not-applicable':
            coverage = 'not-performed'
        else:
            if app['status'] == 'unknown':
                gaps.append('applicability unresolved')
            if not any(q.get('disposition') != 'user-excluded' for q in qs):
                gaps.append('test questions/closure conditions not prepared')
            gaps.extend({'questionId': q['id'], 'coverage': q['coverage'], 'blockers': q['blockers'],
                         'missingObservations': q['missingObservations'], 'outcomeUnknown': q['outcomeUnknown']}
                        for q in qs if q['coverage'] not in ('observed', 'user-excluded'))
            coverage = ('observed' if qs and not gaps else 'blocked' if any(q['coverage'] == 'blocked' for q in qs) else
                'partial' if any(q['coverage'] in ('observed', 'partial') for q in qs) else 'not-performed')
        # A finding can establish a violation even when other questions remain open.
        violated = any(m['certainty'] == 'supported' and m.get('violation') is True for m in associations)
        violated = violated or any(q['securityAssessment'] == 'violation-supported' for q in qs)
        verdict = 'violation-supported' if violated else 'no-violation-observed' if coverage == 'observed' and not excluded else 'inconclusive'
        if app['status'] == 'not-applicable' and (violated or any(q['coverage'] != 'user-excluded' and q['observation'] for q in qs)):
            gaps.append('inapplicability conflicts with observations; tester must resolve')
        if excluded:
            gaps = ['user exclusion conflicts with observations; tester must resolve'] if any(q['observation'] for q in qs) else []
        row = {**copy.deepcopy(criterion), 'applicability': app, 'questions': qs,
            'findingIds': [m['findingId'] for m in associations], 'mappings': associations,
            'coverage': coverage, 'securityAssessment': verdict, 'openWork': gaps,
            'completion': 'partial' if gaps else 'complete'}
        from .coverage_presentation import coverage_view
        row['coverageView'] = coverage_view(row)
        row['coverageMeaning'] = 'current-question-projection'
        rows.append(row)
        if gaps:
            aggregate_open = any(q.get('questionRole') == 'retained-aggregate' and q['coverage'] not in ('observed', 'user-excluded') for q in qs)
            open_work.append({'criterionId': cid, 'reasons': gaps,
                'nextStep': 'review-decomposition' if aggregate_open else criterion.get('nextStep', 'resolve applicability, prerequisites or missing observations')})
    inventory_gaps = [] if scope.get('complete') is True and criteria else ['assigned scope completeness unresolved']
    complete = not open_work and not inventory_gaps
    mapped = {m['findingId'] for m in mappings}
    for finding in alerts['alerts']:
        finding['criterionIds'] = [m['criterionId'] for m in mappings if m['findingId'] == finding['findingId']]
        finding['criterionMappings'] = [copy.deepcopy(m) for m in mappings if m['findingId'] == finding['findingId']]
        finding['scopeMapping'] = 'mapped' if finding['findingId'] in mapped else finding.get('scopeMapping', 'unmapped')
    from .coverage_presentation import presentation_summary
    from .residual_review import project_residual_work
    residual = project_residual_work(assessment.get('residualReview'), scope,
        {**(reconciliation or {}), 'scopeQuestions': list(qrows.values())}, list(operations.values()), alerts)
    return {'scopeStatus': 'provided', 'securityScope': scope, 'criteria': rows,
        'coveragePresentation': presentation_summary(rows), 'residualReview': copy.deepcopy(assessment.get('residualReview')),
        'residualWork': residual, 'aggregateAccounting': aggregate_accounting,
        'scopeCompletion': 'complete' if complete else 'partial',
        'completionMeaning': 'applicability-only' if rows and all(c['applicability']['status'] == 'not-applicable' or c.get('disposition') == 'user-excluded' for c in rows) else 'assigned questions',
        'openWork': open_work, 'inventoryGaps': inventory_gaps,
        'summary': {'criteria': len(rows), 'uniqueFindings': len(findings), 'criterionAssociations': len(mappings),
                    'mappedFindings': len(mapped), 'unmappedFindings': len(findings) - len(mapped)}}


def validate_bundle(run, alerts, projection):
    """Recheck joins and identity after sanitization, without changing conclusions."""
    operations = index(run.get('operations', []), 'operation')
    findings = index([dict(f, id=f['findingId']) for f in alerts['alerts']], 'finding')
    criteria = index(projection.get('criteria', []), 'criterion')
    questions = index(projection.get('securityScope', {}).get('questions', []), 'question')
    if projection.get('scopeStatus') == 'provided':
        normalized=normalize_scope(projection['securityScope'])
        if set(criteria) != {c['id'] for c in normalized.get('criteria', [])}:
            raise ValueError('criterion projection lost an assigned requirement')
        for operation in operations.values():
            refs(operation.get('criterionIds', []), criteria, 'criterion')
            refs(operation.get('questionIds', []), questions, 'question')
        observations=run.get('scopeAssessment', {}).get('questionObservations', {})
        if set(observations) - set(questions):
            raise ValueError('unresolved question observation after redaction')
        from .question_evidence import validate_observation_links, context_diagnostics
        for qid,observation in observations.items():
            refs(observation.get('operationIds', []), operations, 'operation')
            validate_observation_links(observation,operations)
            for link in observation.get('evidenceLinks',[]):
                if link['role']=='support':context_diagnostics(questions[qid].get('coverageContext',{}),link['context'],link.get('compatibility'),link['operationId'])
        associations=[]
        normalized_criteria=index(normalized.get('criteria', []), 'normalized criterion')
        for criterion in criteria.values():
            refs(criterion.get('findingIds', []), findings, 'finding')
            qs=index(criterion.get('questions', []), 'projected question')
            refs(list(qs), questions, 'question')
            expected={q['id'] for q in questions.values() if criterion['id'] in q['criterionIds']}
            if set(qs)!=expected:
                raise ValueError('criterion projection lost a question')
            if 'coverageView' in criterion:
                from .coverage_presentation import coverage_view
                if any(criterion.get(key)!=normalized_criteria[criterion['id']].get(key) for key in ('coverageHistory','priorAssessment')):
                    raise ValueError('inconsistent projected historical record')
                if criterion['coverageView'] != coverage_view(criterion) or criterion.get('coverageMeaning') != 'current-question-projection':
                    raise ValueError('inconsistent coverageView')
            for question in qs.values():
                refs(question.get('observation', {}).get('operationIds', []), operations, 'operation')
                validate_observation_links(question.get('observation',{}),operations)
                if normalized.get('workflowVersion')==1:
                    from .question_evidence import resolve_question_evidence, collect_pending_effects, pending_effects_from_run
                    pending=collect_pending_effects(operations,run.get('actionHistory',[]),run.get('responsibilityReconciliation',{}).get('pendingEffects',[])+pending_effects_from_run(run))
                    all_observations=list(observations.values())+list(run.get('responsibilityReconciliation',{}).get('observations',{}).values())
                    from .question_evidence import resolved_effect_ids
                    resolved=set()
                    for obs in all_observations:resolved.update(resolved_effect_ids(obs,operations,pending))
                    pending=[{**e,'resolved':e['actionId'] in resolved} for e in pending]
                    proof=resolve_question_evidence(question,{**question.get('observation',{}),'evidenceLinks':question.get('observation',{}).get('evidenceLinks',[])},operations,pending)
                    if question.get('questionRole') != 'retained-aggregate' and question['coverage']=='observed' and (proof['missingUnits'] or proof['unresolvedEffectIds'] or not proof['supportOperationIds']):
                        raise ValueError('sanitized evidence no longer supports question closure')
            mappings=criterion.get('mappings', [])
            if criterion.get('findingIds', []) != [m['findingId'] for m in mappings]:
                raise ValueError('inconsistent projected finding associations')
            for mapping in mappings:
                refs([mapping['findingId']], findings, 'finding')
                refs(mapping.get('questionIds', []), questions, 'question')
                refs(mapping.get('operationIds', []), operations, 'operation')
                if mapping['criterionId'] != criterion['id']:
                    raise ValueError('inconsistent criterion association')
                associations.append(mapping)
        for finding in findings.values():
            expected=[m for m in associations if m['findingId']==finding['findingId']]
            if (sorted(finding.get('criterionMappings', []),key=lambda m:m['criterionId']) != sorted(expected,key=lambda m:m['criterionId']) or
                sorted(finding.get('criterionIds', [])) != sorted(m['criterionId'] for m in expected)):
                raise ValueError('inconsistent canonical finding associations')
        from .coverage_presentation import presentation_summary
        if 'coveragePresentation' in projection and projection['coveragePresentation'] != presentation_summary(list(criteria.values())):
            raise ValueError('inconsistent coverage presentation counts')
        if 'coveragePresentation' in projection and run.get('coveragePresentation') != projection['coveragePresentation']:
            raise ValueError('inconsistent RUN coverage presentation counts')
        if 'aggregateAccounting' in projection:
            from .round_closure import review_aggregate_obligations
            qs = list({q['id']:q for c in criteria.values() for q in c.get('questions', [])}.values())
            derived_aggregates = review_aggregate_obligations(normalized, run.get('scopeAssessment', {}), qs, projection.get('residualWork'))
            if derived_aggregates != projection['aggregateAccounting']:
                raise ValueError('inconsistent aggregate accounting')
            by_id = {s['aggregateQuestionId']:s for s in derived_aggregates['states']}
            for q in qs:
                if q.get('questionRole') == 'retained-aggregate':
                    state = by_id[q['id']]
                    if q.get('aggregateAccounting') != state or state['accountingStatus'] == 'accounted' and q['coverage'] != state['coverage']:
                        raise ValueError('inconsistent aggregate coverage')
        if 'residualWork' in projection:
            from .residual_review import project_residual_work
            derived = project_residual_work(projection.get('residualReview'), normalized,
                {**run.get('responsibilityReconciliation', {}), 'scopeQuestions': list({q['id']: q for c in criteria.values() for q in c.get('questions', [])}.values())},
                list(operations.values()), alerts)
            if (run.get('scopeAssessment', {}).get('residualReview') != projection.get('residualReview') or
                derived != projection['residualWork'] or run.get('residualWork') != derived):
                raise ValueError('inconsistent residual work projection')
        if 'workUnits' in run.get('completionSummary', {}).get('dast', {}):
            from .product_scope import compose_completion_summary
            derived = compose_completion_summary(run.get('responsibilityReconciliation'), projection, alerts, task_completion=run['taskCompletion'], assessment_round=run.get('assessmentRound'))
            if run['completionSummary'] != derived:
                raise ValueError('inconsistent completion summary')
            if run.get('trackSummary') != derived['trackSummary']:
                raise ValueError('inconsistent track summary')
        # Original source metadata/history may contain identically named keys.
        # Only the internal fields above are reference contracts, never document data.
    contexts = [r['assessmentContext'] for r in (run, alerts, projection)]
    if contexts[1:] != contexts[:-1] or len({r['taskCompletion'] for r in (run, alerts, projection)}) != 1:
        raise ValueError('inconsistent report context/completion')
    generations=[r.get('reportGeneration', {}).get('bundleId') for r in (run, alerts, projection)]
    if any(g is not None for g in generations) and (
            not all(isinstance(g,str) and g.strip() for g in generations) or generations[1:] != generations[:-1]):
        raise ValueError('inconsistent report generation; reconcile interrupted publication')

    from .round_closure import CLOSED, review_current_round, validate_round_definition
    rounds = [r.get('assessmentRound') for r in (run, alerts, projection)]
    if rounds[1:] != rounds[:-1]:raise ValueError('inconsistent assessmentRound')
    if rounds[0] is not None:
        definition = validate_round_definition(rounds[0])
        for key in ('assessmentId', 'product', 'environment', 'scopeRevision'):
            if definition[key] != run['assessmentContext'][key]:raise ValueError('round report context mismatch')
        if any(r.get('completionSummary') != run.get('completionSummary') for r in (alerts, projection)):
            raise ValueError('inconsistent round completion summary')
        closed = definition['status'] in CLOSED
        for report in (run, alerts, projection):
            if report.get('roundClosed') is not closed or report.get('taskCompletionMeaning') != 'assigned-obligation-coverage':
                raise ValueError('inconsistent roundClosed/coverage meaning')
        review = review_current_round(run, projection, run.get('responsibilityReconciliation'))
        if run.get('roundClosureReview') != review or projection.get('roundClosureReview') != review:
            raise ValueError('inconsistent current round closure review')
        if closed:
            closure = definition.get('closure', {})
            if review['eligibleStatus'] != definition['status'] or closure.get('review') != review or closure.get('scopeRevision') != definition['scopeRevision'] or not closure.get('finalizedAt') or not closure.get('inputRefs'):
                raise ValueError('stale or unverified round closure')

    from .coverage_presentation import round_outcome
    for report in (run, alerts, projection):
        if 'roundOutcome' in report and report['roundOutcome'] != round_outcome(rounds[0],run['taskCompletion']):
            raise ValueError('inconsistent round outcome headline')
