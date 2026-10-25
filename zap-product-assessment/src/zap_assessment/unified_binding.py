"""Optional W9 parent linkage. Legacy child contracts retain their entry scope."""
import re

FIELDS = {'assessmentId', 'planHash', 'phase', 'childRunId', 'fixtureHash', 'scopeHash', 'epochPolicy'}


def validate_context(value, phases):
    if value is None: return None
    if (not isinstance(value, dict) or set(value) != FIELDS
            or any(not isinstance(v, str) for v in value.values())
            or not re.fullmatch('w9-[0-9a-f]{32}', value['assessmentId'])
            or value['phase'] not in phases
            or not re.fullmatch(r'(?:w6-w7-|w8-)[a-zA-Z0-9-]+', value['childRunId'])
            or value['epochPolicy'] != 'fresh-memory-only-stop-on-restart'
            or any(not re.fullmatch('[0-9a-f]{64}', value[k]) for k in ('planHash', 'fixtureHash', 'scopeHash'))):
        raise ValueError('invalid_unified_binding')
    return value


def bind_fixture(context, fixture_hash):
    if context is not None and context['fixtureHash'] != fixture_hash:
        raise ValueError('unified_fixture_binding_mismatch')


def docker_labels(context):
    if context is None: return []
    return ['--label', 'zpa.assessment=' + context['assessmentId'], '--label', 'zpa.phase=' + context['phase'],
            '--label', 'zpa.plan=' + context['planHash']]
