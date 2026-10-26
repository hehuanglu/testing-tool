"""Offline authenticated FE discovery; never infer deployment or perform login."""
from pathlib import Path
from .fe_authenticated_contract import load,validate_journeys
from .fe_authenticated_recipes import select

def discover(product,recipe,observations=None):
    root=Path(product).resolve();kind=select(recipe)
    if kind=='reviewed':
        if not observations:raise ValueError('reviewed finite observations required')
        j=validate_journeys(load(observations))
    else:
        from .fe_authenticated_recipe_finalsource import discover as source_discover
        j=source_discover(root)
    if j['recipe']!=recipe:raise ValueError('recipe mismatch')
    for s in j['sources']:
        if not Path(s['path']).resolve().is_relative_to(root):raise ValueError('source outside requested product')
    from .fe_authenticated_recipe_finalsource import responsibility_inventory
    inventory=responsibility_inventory(root,j['sources']) if kind=='finalsource' else None
    return {'responsibilityInventory':inventory,'schemaVersion':'fe-authenticated-discovery/1.0','stage':'source-only','runtimeObserved':False,'productLocation':str(root),'recipe':recipe,'sources':j['sources'],'journeys':j}
