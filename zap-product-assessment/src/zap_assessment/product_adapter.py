"""Wire mappings for W6. Finalsource mapping is source-derived/runtime-unverified.

No URLs, credentials, target provisioning or admission live here. Both adapters
feed the same state replay; the alternate uses UUID-like strings and a different
HTTP method, route, request names and envelope.
"""
from .business import indexed, money, minor
from .evidence import EvidenceInvalid


class ProductAdapter:
    def __init__(self, manifest):
        self.m = manifest
        self.actors, self.resources = indexed(manifest)
        self.alternate = manifest['adapter'] == 'alternate-ledger'

    def request(self, c):
        r = self.resources[c['resourceRef']]; op = c['operation']; inp = c['input']
        rid = str(r['wireId'])
        if self.alternate:
            paths = {'account.read':('GET','/vault/wallets/'+rid),
                     'account.create':('POST','/vault/wallets'),
                     'account.update':('PATCH','/vault/wallets/'+rid),
                     'account.delete':('DELETE','/vault/wallets/'+rid),
                     'goal.update':('PATCH','/targets/'+rid),
                     'expense':('POST','/journal/debits'), 'revenue':('POST','/journal/credits'),
                     'account.list':('GET','/vault/wallets'), 'goal.list':('GET','/targets'),
                     'category.list':('GET','/labels'), 'transaction.list':('GET','/journal')}
            body = None
            if op == 'account.create': body = {'label':r['initial']['name'], 'openingUnits':r['initial']['balanceMinor']}
            elif op == 'account.update': body = {'label':inp['name'], 'units':minor(inp['balance'])}
            elif op == 'goal.update': body = {'ceilingUnits':minor(inp['target'])}
            elif op in ('expense','revenue'):
                body = {'walletKey':r['wireId'], 'labelKey':self.resources[inp['categoryRef']]['wireId'], 'units':minor(inp['amount'])}
        else:
            paths = {'account.read':('GET','/api/v1/accounts/'+rid),
                     'account.create':('POST','/api/v1/accounts'),
                     'account.update':('PUT','/api/v1/accounts/'+rid),
                     'account.delete':('DELETE','/api/v1/accounts/'+rid),
                     'goal.update':('PUT','/api/v1/goals/'+rid),
                     'expense':('POST','/api/v1/transactions'), 'revenue':('POST','/api/v1/transactions'),
                     'account.list':('GET','/api/v1/accounts'), 'goal.list':('GET','/api/v1/goals'),
                     'category.list':('GET','/api/v1/categories/options'),
                     'transaction.list':('GET','/api/v1/transactions?type=All&limit=100&offset=0')}
            body = None
            if op == 'account.create':
                body = {'bank_name':r['initial']['name'], 'account_type':'Synthetic', 'branch_name':'W6',
                        'account_number_full':str(r['wireId']).zfill(8), 'balance':money(r['initial']['balanceMinor'])}
            elif op == 'account.update':
                body = {'bank_name':inp['name'], 'account_type':'Synthetic', 'branch_name':'W6', 'balance':money(minor(inp['balance']))}
            elif op == 'goal.update': body = {'target_amount':money(minor(inp['target']))}
            elif op in ('expense','revenue'):
                body = {'accountId':r['wireId'], 'category_id':self.resources[inp['categoryRef']]['wireId'],
                        'type':'Expense' if op=='expense' else 'Revenue', 'amount':money(minor(inp['amount'])),
                        'transactionDate':'2026-10-19T00:00:00Z', 'itemDescription':c['caseId'],
                        'shopName':'W6', 'paymentMethod':'Synthetic', 'status':'Complete'}
        method, path = paths[op]
        return {'method':method,'path':path,'body':body}

    def owner_probe(self, c):
        r = self.resources[c['resourceRef']]
        op = 'account.read' if r['kind']=='account' else r['kind']+'.list'
        return {'caseId':c['caseId']+'-owner','actorRef':r['ownerActorRef'],
                'operation':op,'resourceRef':r['resourceRef'],'input':{}}

    def payload(self, body):
        return body['result']['value'] if self.alternate else body['data']

    def check_response(self, c, status, body, expected, state):
        """Check target disclosure, exact membership and response values, not status alone."""
        if status >= 400:
            # Strict bounded non-disclosing envelope; unknown fields count as disclosure.
            safe = ({'fault':{'code':status,'text':'request rejected'}} if self.alternate
                    else {'statusCode':status,'message':'request rejected'})
            return [] if body == safe else ['disclosure_confirmed']
        reasons = []
        try:
            value = self.payload(body); op = c['operation']; r = self.resources[c['resourceRef']]
            slot = state['resources'][c['resourceRef']]
            if op.endswith('.list'):
                kind = op.split('.')[0]; actor = c['actorRef']
                if kind == 'transaction':
                    txs = {k:v for k,v in state['transactions'].items() if v['ownerActorRef']==actor}
                    if self.alternate:
                        rows=value; actual={v['memo']: (v['walletKey'],v['units'],v['side']) for v in rows}
                        wanted={k:(self.resources[t['accountRef']]['wireId'],t['amountMinor'],t['type']) for k,t in txs.items()}
                    else:
                        rows=value['data']; actual={v['itemDescription']:(v['accountId'],minor(str(v['amount'])),v['type']) for v in rows}
                        wanted={k:(self.resources[t['accountRef']]['wireId'],t['amountMinor'],'Expense' if t['type']=='expense' else 'Revenue') for k,t in txs.items()}
                        if value['total'] != len(txs) or value['hasMore'] is not False: reasons.append('list_pagination_unproven')
                else:
                    refs = [ref for ref,x in self.resources.items() if x['kind']==kind and x['ownerActorRef']==actor and state['resources'][ref]['exists']]
                    if self.alternate:
                        rows=value; actual={v['key']:v for v in rows}
                        wanted={self.resources[ref]['wireId']:self._alternate_value(ref,state) for ref in refs}
                    elif kind == 'account':
                        rows=value['accounts'];actual={v['id']:(minor(str(v['balance'])),v['bank_name']) for v in rows}
                        wanted={self.resources[ref]['wireId']:(state['resources'][ref]['balanceMinor'],state['resources'][ref]['name']) for ref in refs}
                        if value['user_id'] != self.actors[actor]['subject']: reasons.append('list_actor_mismatch')
                    elif kind == 'goal':
                        rows=([value['savingGoal']] if value['savingGoal'] is not None else [])+value['expenseGoals']
                        actual={v['goal_id']:minor(str(v['target_amount'])) for v in rows}
                        wanted={self.resources[ref]['wireId']:state['resources'][ref]['targetMinor'] for ref in refs}
                    else:
                        rows=value;actual={v['category_id']:v['name'] for v in rows}
                        wanted={self.resources[ref]['wireId']:state['resources'][ref]['name'] for ref in refs}
                if len(actual) != len(rows) or actual != wanted: reasons.append('list_isolation_or_state_violated')
            elif self.alternate:
                if op == 'account.delete': correct = value == {'removed':r['wireId']}
                elif op in ('expense','revenue'):
                    correct = value['walletKey']==r['wireId'] and value['units']==minor(c['input']['amount']) and value['memo']==c['caseId']
                else: correct = value == self._alternate_value(c['resourceRef'],state)
                if not correct: reasons.append('response_value_or_binding_violated')
            elif op in ('account.read','account.create','account.update'):
                obj = value if op=='account.read' else value['account']
                ident = 'account_id' if op=='account.update' else 'id'
                if obj[ident]!=r['wireId'] or minor(str(obj['balance']))!=slot['balanceMinor'] or obj['bank_name']!=slot['name']:
                    reasons.append('response_value_or_binding_violated')
                if op != 'account.read' and obj['user_id'] != self.actors[r['ownerActorRef']]['subject']: reasons.append('response_owner_mismatch')
            elif op == 'goal.update':
                obj = value['updated_goal']
                if obj['goal_id']!=r['wireId'] or minor(str(obj['target_amount']))!=slot['targetMinor']: reasons.append('response_value_or_binding_violated')
            elif op == 'account.delete':
                if value != {'deleted_account_id':r['wireId']}: reasons.append('response_value_or_binding_violated')
            else:
                if value['accountId']!=r['wireId'] or value['category_id']!=self.resources[c['input']['categoryRef']]['wireId'] or minor(str(value['amount']))!=minor(c['input']['amount']):
                    reasons.append('response_value_or_binding_violated')
        except (KeyError, TypeError, ValueError, EvidenceInvalid):
            reasons.append('response_envelope_or_value_invalid')
        return reasons

    def _alternate_value(self, ref, state):
        r=self.resources[ref];s=state['resources'][ref]
        value={'key':r['wireId'],'principal':self.actors[r['ownerActorRef']]['subject']}
        if r['kind']=='account':value.update(label=s['name'],units=s['balanceMinor'])
        elif r['kind']=='goal':value['ceilingUnits']=s['targetMinor']
        else:value['label']=s['name']
        return value


def prepare_jobs(manifest):
    from .business import expected_states, digest
    adapter=ProductAdapter(manifest);actors,resources=indexed(manifest)
    result=[]
    def job(actor,request):return {'actorRef':actor,'subject':actors[actor]['subject'],'request':request}
    identity={'method':'GET','path':'/__w6/identity','body':None}
    for c,status,before,after in expected_states(manifest):
        owner=resources[c['resourceRef']]['ownerActorRef'];probe=adapter.owner_probe(c)
        if not before['resources'][c['resourceRef']]['exists']:probe['operation']=resources[c['resourceRef']]['kind']+'.list'
        result.append({'caseId':c['caseId'],'ownerIdentity':job(owner,identity),
                       'ownerPositive':job(owner,adapter.request(probe)),'identity':job(c['actorRef'],identity),
                       'exchange':job(c['actorRef'],adapter.request(c)),'expectedPostStateSha256':digest(after)})
    return result
