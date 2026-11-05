"""Declared feature/source reconciliation, not a crawler or completeness oracle."""
DEPTHS = {'boundary', 'processing', 'persistence', 'delivery', 'recovery'}
METHODS = {'zap-dast', 'zap-ui', 'zap-business-observation', 'outside-zap', 'unresolved'}
CONTEXT_KEYS = {'product', 'environment', 'origin', 'build', 'method', 'route', 'inputLocation',
                'actorRef', 'role', 'relation', 'objectRef', 'state', 'objective',
                'fixtureClass', 'fixtureRef', 'requestRef'}


def strings(value, label):
    if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value) or len(value) != len(set(value)):
        raise ValueError('invalid ' + label)
    return value


def records(value, label, key='id'):
    if not isinstance(value, list) or any(not isinstance(v, dict) for v in value):
        raise ValueError('invalid ' + label)
    ids = [v.get(key) for v in value]
    strings(ids, label + ' IDs')
    return {v[key]: v for v in value}


def references(value, known, label):
    if set(strings(value, label)) - set(known):
        raise ValueError('unresolved ' + label)


def validate_question_fields(question):
    if 'objectiveDepth' in question and question['objectiveDepth'] not in DEPTHS:
        raise ValueError('invalid objectiveDepth')
    if 'methodClass' in question and question['methodClass'] not in METHODS:
        raise ValueError('invalid methodClass')
    if 'expectationRequired' in question and type(question['expectationRequired']) is not bool:
        raise ValueError('invalid expectationRequired')
    if 'coverageContext' in question:
        context = question['coverageContext']
        if not isinstance(context, dict) or set(context) - CONTEXT_KEYS or any(not isinstance(v, str) or not v for v in context.values()):
            raise ValueError('invalid coverageContext')
    for key in ('expectedBehavior', 'expectationBasis', 'priorityBasis'):
        if key in question and (not isinstance(question[key], str) or not question[key].strip()):
            raise ValueError('invalid ' + key)
    if question.get('priority', 'normal') not in ('high', 'normal', 'low'):
        raise ValueError('invalid priority')
    if 'representation' in question:
        row = question['representation']
        if not isinstance(row, dict) or not row.get('basis'):
            raise ValueError('representation basis required')
        strings(row.get('representedVariants'), 'representedVariants')
        strings(row.get('excludedConclusions'), 'excludedConclusions')


def validate_discovery_review(inventory):
    if 'workflowVersion' in inventory and (type(inventory['workflowVersion']) is not int or inventory['workflowVersion'] != 1):
        raise ValueError('unsupported workflowVersion')
    cases = records(inventory.get('cases', []), 'cases', 'caseId')
    for case in cases.values():
        validate_question_fields(case)
        strings(case.get('requiredEvidence',[]),'requiredEvidence')
        strings(case.get('prerequisites',[]),'case prerequisites')
        references(case.get('dependsOnCases',[]),cases,'case dependencies')
        for action in case.get('actions', []):
            if 'usesExistingResult' in action and type(action['usesExistingResult']) is not bool:
                raise ValueError('invalid usesExistingResult')
            for key in ('unblocksCaseIds', 'dependsOnCases'):
                references(action.get(key, []), cases, key)
            strings(action.get('requires', []), 'action prerequisites')
            if 'selectionBasis' in action and not isinstance(action['selectionBasis'], str):
                raise ValueError('invalid selectionBasis')
    actions = [a.get('id') for c in cases.values() for a in c.get('actions', [])]
    strings(actions, 'action IDs')
    engagement = inventory.get('engagement')
    if engagement is not None:
        if not isinstance(engagement, dict):
            raise ValueError('invalid engagement')
        for key in ('objective', 'scopeBasis', 'methodBoundary'):
            if key in engagement and not isinstance(engagement[key], str):
                raise ValueError('invalid engagement ' + key)
        strings(engagement.get('limits', []), 'engagement limits')
        notes = engagement.get('authorityNotes', [])
        if not isinstance(notes, list) or any(not isinstance(n, dict) or any(not isinstance(n.get(k), str) or not n[k] for k in ('action', 'scope', 'basis')) for n in notes):
            raise ValueError('invalid authorityNotes')
    review = inventory.get('discoveryReview')
    if review is None:
        return
    if not isinstance(review, dict):
        raise ValueError('invalid discoveryReview')
    sources = records(review.get('sources', []), 'discovery sources')
    for source in sources.values():
        if source.get('kind') not in ('spec', 'ui-source', 'api-source', 'runtime', 'supplied-inventory'):
            raise ValueError('invalid source kind')
        for key in ('location', 'reviewedScope', 'remainingScope', 'limitationBasis'):
            if key in source and not isinstance(source[key], str):
                raise ValueError('invalid source ' + key)
        if 'affectsAssignment' in source and type(source['affectsAssignment']) is not bool:
            raise ValueError('invalid source assignment relevance')
    features = records(review.get('features', []), 'features')
    for feature in features.values():
        if not isinstance(feature.get('name'), str) or not feature['name']:
            raise ValueError('feature name required')
        references(feature.get('sourceIds', []), sources, 'feature sources')
        references(feature.get('caseIds', []), cases, 'feature cases')
        if feature.get('disposition') not in ('mapped', 'represented', 'no-additional-question', 'outside-assignment', 'unresolved'):
            raise ValueError('invalid feature disposition')
        for key in ('basis', 'scopeBasis'):
            if key in feature and not isinstance(feature[key], str):
                raise ValueError('invalid feature ' + key)
        if feature.get('disposition') == 'outside-assignment' and feature.get('gapKind') in ('capability', 'auth', 'fixture', 'configuration'):
            raise ValueError('capability/prerequisite is not outside assignment')
    references(review.get('reviewedCaseIds', []), cases, 'reviewed cases')
    if 'extent' in review:
        extent = review['extent']
        if not isinstance(extent, dict) or extent.get('kind') not in ('delta', 'assigned-scope') or not isinstance(extent.get('basis'), str) or not extent['basis']:
            raise ValueError('invalid discovery extent')
        references(extent.get('featureIds'), features, 'extent features')
        references(extent.get('caseIds'), cases, 'extent cases')
    for case in cases.values():
        references(case.get('featureIds', []), features, 'case features')
    gaps = review.get('unresolved', [])
    if not isinstance(gaps, list) or any(not isinstance(g, dict) or not isinstance(g.get('reason'), str) for g in gaps):
        raise ValueError('invalid discovery unresolved gaps')
    for gap in gaps:
        references(gap.get('affectedFeatureIds', []), features, 'affected features')
        references(gap.get('caseIds', []), cases, 'affected cases')
    if 'basis' in review and not isinstance(review['basis'], str):
        raise ValueError('invalid review basis')


def review_business_coverage(inventory):
    validate_discovery_review(inventory)
    review = inventory.get('discoveryReview')
    result = dict(unmappedFeatures=[], unreviewedCases=[], unresolvedSources=[], diagnostics=[], reviewStatus='legacy-unreviewed')
    if review is None:
        result['diagnostics'] = ['discovery-review-missing']
        if inventory.get('workflowVersion') == 1:
            result['reviewStatus'] = 'gaps'
        return result
    result['extent'] = review.get('extent', dict(kind='declared-inventory',
        featureIds=[f['id'] for f in review.get('features', [])], caseIds=review.get('reviewedCaseIds', []),
        basis='Legacy declared inventory; no whole-product discovery assertion'))
    for feature in review.get('features', []):
        disposition = feature['disposition']
        gap = (not feature.get('sourceIds') or disposition == 'unresolved' or
            disposition in ('mapped', 'represented') and not feature.get('caseIds') or
            disposition in ('represented', 'no-additional-question') and not feature.get('basis') or
            disposition == 'outside-assignment' and not feature.get('scopeBasis'))
        if gap:
            result['unmappedFeatures'].append(feature['id'])
        if disposition in ('mapped','represented'):
            for cid in feature.get('caseIds',[]):
                case=next(c for c in inventory['cases'] if c['caseId']==cid)
                if 'featureIds' in case and feature['id'] not in case['featureIds']:
                    result['diagnostics'].append('feature-case-delta:'+feature['id']+':'+cid)
        if disposition == 'represented':
            for cid in feature.get('caseIds', []):
                case = next(c for c in inventory['cases'] if c['caseId'] == cid)
                if not case.get('representation', {}).get('excludedConclusions'):
                    result['diagnostics'].append('representation-exclusions-missing:' + feature['id'])
    result['unreviewedCases'] = [c['caseId'] for c in inventory.get('cases', []) if c['caseId'] not in review.get('reviewedCaseIds', [])]
    for source in review.get('sources', []):
        if not source.get('location') or not source.get('reviewedScope'):
            result['unresolvedSources'].append(source['id'])
        elif source.get('remainingScope'):
            if source.get('affectsAssignment') is False and source.get('limitationBasis'):
                result.setdefault('limitations', []).append({'sourceId': source['id'], 'basis': source['limitationBasis']})
            else:
                result['unresolvedSources'].append(source['id'])
    if not review.get('sources'):
        result['diagnostics'].append('discovery-sources-missing')
    if not review.get('basis'):
        result['diagnostics'].append('discovery-basis-missing')
    if review.get('unresolved'):
        result['diagnostics'].extend('discovery-unresolved:' + str(i) for i, _ in enumerate(review['unresolved']))
    extent_features=set(result['extent']['featureIds'])
    reviewed_features=[f for f in review.get('features', []) if f['id'] in extent_features]
    result['featureGroupsReviewed'] = sum(f['id'] not in result['unmappedFeatures'] for f in reviewed_features)
    result['mappedFeatureGroups'] = sum(f['disposition'] in ('mapped', 'represented') for f in reviewed_features)
    result['noAdditionalQuestionGroups'] = sum(f['disposition'] == 'no-additional-question' for f in reviewed_features)
    result['reviewStatus'] = 'gaps' if any(result[k] for k in ('unmappedFeatures', 'unreviewedCases', 'unresolvedSources', 'diagnostics')) else 'reviewed'
    return result
