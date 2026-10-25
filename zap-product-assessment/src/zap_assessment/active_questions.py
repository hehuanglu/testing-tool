"""Question-level readback, separate from caller-supplied generic mutation labels.

Adapters normalize real requests and interpret application stages. This helper
does not infer business semantics, identity or sinks from an HTTP status alone.
"""


def assess_question(question, probes):
    unit = 'question:' + question['id']
    if question.get('disposition') == 'not-applicable':
        if not question.get('basis') or question.get('gapKind') in (
                'auth', 'role', 'fixture', 'capability', 'configuration'):
            raise ValueError('inapplicability needs a sink/context basis, not a missing prerequisite')
        return {'id': question['id'], 'status': 'not-applicable', 'unit': unit,
                'basis': question['basis'], 'requests': 0, 'evidenceUnits': [unit]}
    rules = {str(r) for r in question['ruleIds']}
    if not rules or question.get('minimumStage', 'boundary') not in ('boundary', 'processing', 'persistence'):
        raise ValueError('question technique/stage required')
    delivered = [p for p in probes if str(p.get('ruleId')) in rules
                 and p.get('changed') is True and p.get('application') is True
                 and p.get('identityValid') is True]
    accepted = {'boundary': {'boundary', 'processing', 'persistence'},
                'processing': {'processing', 'persistence'},
                'persistence': {'persistence'}}[question.get('minimumStage', 'boundary')]
    answers = [p for p in delivered if p.get('stage') in accepted and p.get('resultRead') is True]
    missing_fields=sorted(set(question.get('fields',[]))-{p.get('field') for p in answers})
    complete=bool(answers) and not missing_fields
    missing = None if complete else ('zero-probes' if not delivered else 'required-input-processing-or-readback-missing')
    return {'id': question['id'], 'status': 'observed' if complete else 'open', 'unit': unit,
            'requests': len(delivered), 'qualifyingRequests': len(answers),
            'stages': sorted({p.get('stage', 'unknown') for p in delivered}),
            'missing': missing, 'missingFields':missing_fields, 'evidenceUnits': [unit] if complete else []}
