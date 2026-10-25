"""Offline source discovery and reviewed-observation provider. No inferred environment."""
from pathlib import Path
from .fe_anonymous_contract import digest,load,validate_journeys,save

def discover(product,recipe,observations=None):
    root=Path(product).resolve()
    if recipe=='reviewed-fe/1.0':
        if not observations:raise ValueError('reviewed observations required')
        journeys=validate_journeys(load(observations))
    else:
        from .fe_anonymous_recipes import select
        journeys=select(recipe).discover(root)
    for s in journeys['sources']:
        if not Path(s['path']).resolve().is_relative_to(root):raise ValueError('source outside requested product')
    return {'schemaVersion':'fe-anonymous-discovery/1.0','productLocation':str(root),'stage':'source-only','recipe':recipe,'sources':journeys['sources'],'journeys':journeys,'runtimeObserved':False}
