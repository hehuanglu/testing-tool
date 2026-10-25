"""Read-only authenticated deployment/build adapter; no login or provisioning."""
from .fe_anonymous_binding import inspect as inspect_transport
from .fe_authenticated_contract import digest,load

def inspect(selection):
    result=inspect_transport(selection)
    for ref in selection.get('buildEvidence',[]):
        if digest(ref['path'])!=ref['sha256']:raise ValueError('source/build binding evidence drift')
    for row in selection.get('publicAssets',[]):
        if not row.get('sha256') or not row['path'].startswith('/'):raise ValueError('asset binding incomplete')
    return result
