"""Explicit, finite FE recipe registry. Names select adapters, never product detection."""
from . import fe_anonymous_recipe_finalsource
REGISTRY={'finalsource-fe/1.0':fe_anonymous_recipe_finalsource}

def select(recipe_id):
    if recipe_id not in REGISTRY:raise ValueError('unsupported FE recipe; reviewed observations provider remains separate')
    return REGISTRY[recipe_id]
