"""W6 owned-synthetic write contract and independent state replay.

This is separate from borrowed BOLA v1.4. No product execution authority is
provided here. Money is scaled integer (four decimal places), never float math.
The HTTP fixture does not import this replay implementation.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
import re
from jsonschema import Draft202012Validator
from .contracts import ROOT, canonical
from .evidence import EvidenceInvalid
from .verification import strict_json

VERSION = 'w6-owned-business-1'
OPERATIONS = {'account.read', 'account.create', 'account.update', 'account.delete',
              'goal.update', 'expense', 'revenue', 'account.list', 'goal.list',
              'category.list', 'transaction.list'}


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def minor(value, scale=4):
    if isinstance(value, (bool, float)):
        raise EvidenceInvalid('money_requires_exact_decimal')
    try:
        amount = Decimal(str(value))
        units = amount * 10 ** scale
        if not amount.is_finite() or units != units.to_integral_value() or abs(units) > 2**53-1:
            raise EvidenceInvalid('money_precision_or_range')
        return int(units)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise EvidenceInvalid('invalid_money') from exc


def money(units):
    if type(units) is not int:
        raise EvidenceInvalid('minor_units_must_be_integer')
    return format(Decimal(units) / 10000, '.4f')


def indexed(manifest):
    return ({a['actorRef']: a for a in manifest['actors']},
            {r['resourceRef']: r for r in manifest['resources']})


def validate_manifest(m):
    schema = strict_json((ROOT/'schemas/remediation/business-fixture.schema.json').read_bytes())
    if list(Draft202012Validator(schema).iter_errors(m)):
        raise EvidenceInvalid('invalid_business_fixture_schema')
    actors, resources = indexed(m)
    if len(actors) != len(m['actors']) or len(resources) != len(m['resources']):
        raise EvidenceInvalid('duplicate_fixture_reference')
    if set(actors) != {'A', 'B', 'anonymous'} or actors['anonymous']['subject'] is not None:
        raise EvidenceInvalid('actor_inventory')
    if actors['A']['subject'] == actors['B']['subject'] or any(actors[a]['subject'] is None for a in ('A','B')):
        raise EvidenceInvalid('actor_identity_alias')
    if len({str(a['subject']) for a in actors.values()}) != 3:
        raise EvidenceInvalid('ambiguous_actor_identity')
    wire = set()
    for r in resources.values():
        key = (r['kind'], str(r['wireId']))
        if key in wire or r['ownerActorRef'] not in ('A', 'B'):
            raise EvidenceInvalid('resource_identity_or_owner')
        wire.add(key)
        if r['provenance']['runId'] != m['runId'] or not r['provenance']['sourceRef']:
            raise EvidenceInvalid('fixture_provenance_binding')
        if r['kind'] in ('account','goal'):
            amount = r['initial']['balanceMinor' if r['kind']=='account' else 'targetMinor']
            if type(amount) is not int or amount < 0 or amount > 2**53-1:
                raise EvidenceInvalid('invalid_initial_money')
    ids = set()
    for c in m['transitions']:
        if c['caseId'] in ids or c['operation'] not in OPERATIONS or c['actorRef'] not in actors:
            raise EvidenceInvalid('duplicate_or_unknown_transition')
        ids.add(c['caseId'])
        r = resources.get(c['resourceRef'])
        if not r or c['operation'].split('.')[0] in ('account','goal','category') and c['operation'].split('.')[0] != r['kind']:
            raise EvidenceInvalid('transition_resource_kind')
        if c['operation'] in ('expense','revenue'):
            cat = resources.get(c['input'].get('categoryRef'))
            if r['kind'] != 'account' or not cat or cat['kind'] != 'category' or minor(c['input'].get('amount')) <= 0:
                raise EvidenceInvalid('transaction_resource_or_amount')
        if c['operation'] == 'account.update': minor(c['input']['balance'])
        if c['operation'] == 'goal.update': minor(c['input']['target'])
        # Expected behavior is derived, never supplied as pass/deny by fixture input.
        required_inputs = ({'name','balance'} if c['operation']=='account.update' else
                           {'target'} if c['operation']=='goal.update' else
                           {'categoryRef','amount'} if c['operation'] in ('expense','revenue') else set())
        if set(c['input']) != required_inputs:
            raise EvidenceInvalid('transition_input_contract')
        if c['operation']=='account.update' and (minor(c['input']['balance'])<0 or not isinstance(c['input']['name'],str) or not c['input']['name']):
            raise EvidenceInvalid('invalid_account_input')
        if c['operation']=='goal.update' and minor(c['input']['target'])<=0:
            raise EvidenceInvalid('invalid_goal_input')
    for operation in OPERATIONS:
        if {c['actorRef'] for c in m['transitions'] if c['operation']==operation} != {'A','B','anonymous'}:
            raise EvidenceInvalid('required_actor_operation_coverage_missing')
    if m['adapter']=='finalsource-shaped' and any(type(r['wireId']) is not int for r in resources.values()):
        raise EvidenceInvalid('finalsource_requires_numeric_ids')
    if not m['transitions'] or not m['coverageGaps']:
        raise EvidenceInvalid('missing_transition_or_explicit_gap_inventory')
    return m


def initial_state(m):
    _, resources = indexed(m)
    return {'resources': {ref: {'exists': r['initial']['exists'],
                               **{k:v for k,v in r['initial'].items() if k != 'exists'}}
                          for ref,r in resources.items()}, 'transactions': {}}


def transition(m, state, c):
    """Pure oracle: derive expected decision/state from initial state + inputs."""
    actors, resources = indexed(m)
    r = resources[c['resourceRef']]; op = c['operation']; actor = c['actorRef']
    result = deepcopy(state); slot = result['resources'][c['resourceRef']]
    if actor == 'anonymous': return 401, result
    if op.endswith('.list'): return 200, result
    if op == 'account.create':
        # Product create has implicit authenticated owner, no cross-owner parameter.
        if actor != r['ownerActorRef']: raise EvidenceInvalid('unsupported_cross_owner_create')
        if slot['exists']: return 409, result
        slot['exists'] = True
        return 201, result
    if op in ('expense','revenue'):
        cat = resources[c['input']['categoryRef']]
        if r['ownerActorRef'] != actor or cat['ownerActorRef'] != actor or not slot['exists']:
            return 400, result
        amount = minor(c['input']['amount'])
        if op == 'expense' and slot['balanceMinor'] < amount: return 400, result
        slot['balanceMinor'] += amount if op == 'revenue' else -amount
        result['transactions'][c['caseId']] = {'accountRef':c['resourceRef'],
            'categoryRef':c['input']['categoryRef'], 'ownerActorRef':actor,
            'amountMinor':amount, 'type':op}
        return 201, result
    if not slot['exists']: return 404, result
    if r['ownerActorRef'] != actor: return 403, result
    if op == 'account.update':
        slot['balanceMinor'] = minor(c['input']['balance']); slot['name'] = c['input']['name']
    elif op == 'goal.update': slot['targetMinor'] = minor(c['input']['target'])
    elif op == 'account.delete':
        slot['exists'] = False
        result['transactions'] = {k:v for k,v in result['transactions'].items() if v['accountRef'] != c['resourceRef']}
    elif op != 'account.read': raise EvidenceInvalid('unsupported_operation')
    if any(v.get('balanceMinor',v.get('targetMinor',0)) < 0 for v in result['resources'].values()):
        raise EvidenceInvalid('negative_expected_money')
    return 200, result


def expected_states(m):
    state = initial_state(m)
    for c in m['transitions']:
        status, after = transition(m, state, c)
        yield c, status, state, after
        state = after
