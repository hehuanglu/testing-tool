"""Native compatibility pin and bounded research preflight; no Java build for mapping changes."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from .discovery import ROOT
from .runtime import DockerRuntime
from .journal import Journal
from .anonymous import DEFAULT_LIMITS

def verify_jar(path,pin):
    path=Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=pin['jarSha256']:raise ValueError('native JAR pin mismatch')
    if pin.get('provider')!='JsonBearerAuthBootstrapProvider' or pin.get('defaultEnabled') is not False or not pin.get('compatibilityEvidenceRefs'):raise ValueError('native provider compatibility unproven')
    for row in pin.get('sourceFiles',[]):
        if hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()!=row['sha256']:raise ValueError('native source compatibility drift')
    if not pin.get('sourceFiles'):raise ValueError('native provider source pins required')
    return True

def preflight(out):
    # Reuse existing owned measurement path and anonymous bounded Docker HTTP profile.
    # This is a research candidate, not operational qualification/calibration of a new topology.
    out=Path(out);rt=DockerRuntime(out.name,out,Journal(out/'resource-journal.jsonl',out.name,'resource-measurement'))
    rt.plan=SimpleNamespace(data={'runtime':json.loads((ROOT/'profiles/runtime-baseline.json').read_bytes())})
    sample=rt.resource_sample();required=DEFAULT_LIMITS['reserveBytes']+2*DEFAULT_LIMITS['artifactBytes']
    if min(sample['hostFree'],sample['dockerFree'])<required or sample['ramAvailable']<3*1024**3:raise ValueError('native bounded research resource headroom unavailable')
    return {**sample,'diskRequiredBytes':required,'ramRequiredBytes':3*1024**3,'profile':'existing bounded Docker HTTP research candidate; new topology qualification pending'}
