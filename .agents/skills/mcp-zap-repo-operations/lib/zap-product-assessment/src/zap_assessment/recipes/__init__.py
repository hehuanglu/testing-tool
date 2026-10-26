"""Explicit, code-owned recipes. No module loading from product documents."""
from . import ledger, archive
REGISTRY={r.ID:r for r in (ledger,archive)}
def select(name):
    if name not in REGISTRY:raise ValueError('unknown recipe; no setup/login/provision performed')
    return REGISTRY[name]
