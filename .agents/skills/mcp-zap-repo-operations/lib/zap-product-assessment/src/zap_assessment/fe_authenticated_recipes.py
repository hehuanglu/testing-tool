"""Explicit executable recipe registry; reviewed documents use the same finite worker."""
REGISTRY={'finalsource-fe-auth/1.0':'finalsource','reviewed-fe-auth/1.0':'reviewed'}
def select(recipe):
    if recipe not in REGISTRY:raise ValueError('unsupported authenticated FE recipe')
    return REGISTRY[recipe]

def materialize(journeys,selection):
    import copy
    result=copy.deepcopy(journeys)
    if select(journeys['recipe'])=='finalsource':
        from .fe_authenticated_recipe_finalsource import materialize as product_materialize
        return product_materialize(result,selection)
    return result

def prepare(journey,plan,actor,output):
    if select(plan['journeys']['recipe'])!='finalsource':raise ValueError('no reviewed setup adapter for this recipe')
    from pathlib import Path
    from .fe_authenticated_fixture_finalsource import binding,prepare_data
    target=Path(output);target.mkdir(mode=0o700,parents=True,exist_ok=True)
    requested=set(journey.get('setupRefs',[]));bound=None
    if requested&{'category','bill','paged-transactions','expense-transaction'}:
        cfg=plan['selection'].get('fixtureBinding')
        if not cfg:raise ValueError('owned backend/database binding absent; dependent setup remains open')
        needs=({'category'} if requested&{'category','paged-transactions','expense-transaction'} else set())|({'bill'} if 'bill' in requested else set())
        bound=binding(plan['selection'],cfg['backendId'],cfg['databaseId'],target,needs)
    values=prepare_data(plan['selection'],actor,target,requested,bound)
    fulfilled=set()
    if 'ownedAccountId' in values:fulfilled.add('owned-account')
    if 'nativeAccountId' in values:fulfilled.add('native-account')
    if 'categoryId' in values:fulfilled.add('category')
    if 'billId' in values:fulfilled.add('bill')
    from .fe_authenticated_contract import load
    ledger=load(target/'FIXTURE_DAG.json')
    if any(t['request']['type']=='Expense' for t in ledger['transactions']):fulfilled.add('expense-transaction')
    if len(ledger['transactions'])>10 and ledger.get('transactionFirstPage',{}).get('hasMore'):fulfilled.add('paged-transactions')
    return {'fixtures':values,'fulfilledRefs':sorted(fulfilled)}
