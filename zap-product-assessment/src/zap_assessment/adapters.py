"""Two explicit runtime adapters; profiles cannot load code or shell commands."""
import os
from .contracts import Blocked,canonical

def prepare_synthetic(plan,folder):
    p=plan.data['product'];w=plan.data['workflow']
    fixture=folder/'fixture';fixture.mkdir(mode=0o777,exist_ok=True);os.chmod(fixture,0o777)
    (fixture/'openapi.json').write_bytes(canonical(plan.data['schema']))
    (fixture/'product.txt').write_text(p['productId']);(fixture/'rate.txt').write_text(str(w['maxRate']))

def registered_runtime(run_id,folder,journal,plan):
    if plan.data['workflow'].get('workflowId')=='w4-owned-active-conformance':raise Blocked('development active fixture requires explicit observed harness')
    from .runtime import DockerRuntime
    from .existing import ExistingDockerRuntime
    registry={'synthetic-http-v1':DockerRuntime,'docker-existing-http-v1':ExistingDockerRuntime}
    adapter=plan.data['product']['adapter']
    if adapter not in registry:raise Blocked('runtime adapter not registered')
    runtime=registry[adapter](run_id,folder,journal);runtime.plan=plan;return runtime
