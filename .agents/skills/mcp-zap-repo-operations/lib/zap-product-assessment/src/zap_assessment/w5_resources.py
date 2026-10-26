"""Bounded W5 canary calibration profile; never changes operational admission.

The historical receipt sizes justify a candidate artifact cap, not a measured
peak claim. A fresh run must stay below that cap and publish its measurements.
"""
import hashlib
import json
import math
from pathlib import Path

from .errors import Blocked
from .runtime_safety import GIB,ResourceGate

MIB=1024**2
BASELINE='test-artifacts/mcp-zap-remediation/w5-scanner-20261019T064617Z/scanner-A-attempt14/gate-results.json'
BASELINE_SHA='6269883503830472165988432e5225bcf5f3a83c6f09b89ee642a3731bf7eb9f'
MEASUREMENTS=(
 ('test-artifacts/mcp-zap-remediation/w5-resource-20261019T084619Z/scanner-A/gate-results.json',
  '07fb08132e5218b9efbb95336f9fc9c752f9fd955d99e68ceed0fc52d4ef0c61',190052439),
 ('test-artifacts/mcp-zap-remediation/w5-resource-20261019T084619Z/scanner-B/gate-results.json',
  'ac4677ce23c4d2a407c62564ef59ccc77ea1fb99f8556dcc46f2628d20e36fae',190008091))


def bounded_profile(workspace):
    raw=(Path(workspace)/BASELINE).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=BASELINE_SHA:raise Blocked('W5 resource baseline drift')
    evidence=json.loads(raw)
    if evidence['status']!='development_pass_operational_blocked' or not evidence['cleanupConfirmed']:
        raise Blocked('W5 resource baseline not complete development evidence')
    observed=sum(item['bytes'] for item in evidence['artifactAudit'])
    measurements=[]
    for path,checksum,peak in MEASUREMENTS:
        raw=(Path(workspace)/path).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=checksum:raise Blocked('measured W5 calibration drift')
        record=json.loads(raw)
        if (record['status']!='development_pass_operational_blocked' or not record['cleanupConfirmed']
                or max(m['hostGrowth'] for m in record['resourceMetrics'])!=peak):raise Blocked('measured W5 calibration incomplete')
        measurements.append({'path':path,'sha256':checksum,'observedHostGrowthBytes':peak})
    # Two completed startup-through-cleanup measurements. Round 125% of their
    # maximum to 64 MiB, then retain the separate 2*growth+2GiB admission rule.
    peak=max(m['observedHostGrowthBytes'] for m in measurements)
    cap=(((peak*5+3)//4+64*MIB-1)//(64*MIB))*(64*MIB)
    profile={'schemaVersion':'w5-resource-profile/2.0','profileId':'bounded-fixture-v2',
        'scope':'owned-synthetic-delegated-canary','operationalAdmission':False,
        'growth':{'host':cap,'docker':GIB},'artifactCapBytes':cap,
        'ramPreflightBytes':3*GIB,'ramDuringBytes':3*GIB//2,
        'maxConfiguredWorkloadBytes':2016*MIB,'ramReserveBytes':GIB,
        'baseline':{'path':BASELINE,'sha256':BASELINE_SHA,'retainedAuditedBytes':observed,
                    'limitation':'image cache baseline; measured growth is pinned separately'},
        'measurements':measurements,'seedPinnedImageCache':True,
        'sampleSeconds':5,'reserveBytes':2*GIB}
    validate_profile(profile)
    return profile


def validate_profile(profile):
    if not isinstance(profile,dict):raise Blocked('W5 candidate resource profile invalid')
    version=profile.get('schemaVersion')
    if (version not in ('w5-resource-profile/1.0','w5-resource-profile/2.0')
            or profile.get('profileId')!=('bounded-fixture-v1' if version.endswith('1.0') else 'bounded-fixture-v2')
            or profile.get('scope')!='owned-synthetic-delegated-canary'
            or profile.get('operationalAdmission') is not False
            or profile.get('sampleSeconds')!=5 or profile.get('reserveBytes')!=2*GIB
            or profile.get('ramPreflightBytes')!=3*GIB or profile.get('ramDuringBytes')!=3*GIB//2
            or profile.get('maxConfiguredWorkloadBytes')!=2016*MIB or profile.get('ramReserveBytes')!=GIB):
        raise Blocked('W5 candidate resource profile invalid')
    baseline=profile.get('baseline',{})
    observed=baseline.get('retainedAuditedBytes')
    if (baseline.get('path')!=BASELINE or baseline.get('sha256')!=BASELINE_SHA
            or type(observed) is not int or observed<=0):raise Blocked('W5 resource baseline missing')
    cap=((2*observed+16*MIB-1)//(16*MIB))*(16*MIB)
    if version=='w5-resource-profile/2.0':
        expected=[{'path':path,'sha256':checksum,'observedHostGrowthBytes':peak} for path,checksum,peak in MEASUREMENTS]
        if profile.get('measurements')!=expected or profile.get('seedPinnedImageCache') is not True:
            raise Blocked('W5 measured resource references invalid')
        peak=max(row['observedHostGrowthBytes'] for row in expected)
        cap=(((peak*5+3)//4+64*MIB-1)//(64*MIB))*(64*MIB)
    if (profile.get('artifactCapBytes')!=cap or cap>512*MIB
            or profile.get('growth')!={'host':cap,'docker':GIB}
            or profile['ramPreflightBytes']<profile['maxConfiguredWorkloadBytes']+profile['ramReserveBytes']):
        raise Blocked('W5 candidate resource budget invalid')


def seed_image_cache(workspace,home):
    """Clone only pinned, precredential image libraries into a fresh owned home.

    This never copies a prior session, preferences, key, log or credential. APFS
    clones are distinct regular files with CoW semantics, not hardlinks.
    """
    import ctypes
    import os
    import stat
    from .scanner_secret_audit import artifact_digest
    workspace=Path(workspace);home=Path(home)
    raw=(workspace/BASELINE).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=BASELINE_SHA:raise Blocked('image cache source receipt drift')
    gate=json.loads(raw);run_root=(workspace/BASELINE).parent
    libc=ctypes.CDLL('/usr/lib/libSystem.B.dylib',use_errno=True)
    clone=libc.clonefile;clone.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int];clone.restype=ctypes.c_int
    rows=[]
    for sink in gate['containerSinkAudits']:
        if sink['stage']!='before-credential-delivery':continue
        for archive in sink['archives']:
            for entry in archive['paths']:
                name=entry['path']
                if (not name.startswith('zap-home/.ZAP/') or not entry.get('precredentialBaseline')
                        or not (('/addOnData/' in name and '/libs/' in name and name.endswith('.jar'))
                                or name.endswith(('/webdriver/linux/64/chromedriver','/webdriver/linux/64/geckodriver')))):
                    continue
                if artifact_digest(run_root,'runtime/'+name)!=entry['sha256']:raise Blocked('image cache bytes changed')
                source=run_root/'runtime'/name;target=home/Path(name).relative_to('zap-home')
                if target.exists() or target.is_symlink():raise Blocked('image cache target is not fresh')
                target.parent.mkdir(parents=True,exist_ok=True)
                for parent in (target.parent,*[q for q in target.parent.parents if q.is_relative_to(home)]):parent.chmod(0o777)
                if clone(os.fsencode(source),os.fsencode(target),0)!=0:raise Blocked('APFS image cache clone unavailable')
                target.chmod(0o777 if source.stat().st_mode&stat.S_IXUSR else 0o666)
                if (target.stat().st_nlink!=1 or target.stat().st_ino==source.stat().st_ino
                        or artifact_digest(home,str(target.relative_to(home)))!=entry['sha256']):
                    raise Blocked('image cache clone integrity failed')
                rows.append({'path':str(target.relative_to(home)),'bytes':entry['bytes'],'sha256':entry['sha256'],'nlink':1})
    if not rows:raise Blocked('image cache empty')
    return {'method':'APFS copy-on-write clones of pinned precredential image libraries only',
            'baselineSha256':BASELINE_SHA,'files':rows,'logicalBytes':sum(row['bytes'] for row in rows)}


class W5ResourceGate(ResourceGate):
    def __init__(self,contract,sampler,profile,**kwargs):
        validate_profile(profile)
        self.profile=profile
        super().__init__({**contract,'growth':profile['growth']},sampler,**kwargs)

    def required_ram(self,preflight):
        return self.profile['ramPreflightBytes' if preflight else 'ramDuringBytes']

    def _sample(self,preflight=False):
        result=super()._sample(preflight)
        self.samples[-1]['ramRequiredBytes']=self.required_ram(preflight)
        return result


def verify_measurements(profile,metrics,samples):
    """Check persisted cgroup/ownership readings against resource gate samples."""
    validate_profile(profile)
    if not isinstance(metrics,list) or len(metrics)!=len(samples) or len(metrics)<2:
        raise Blocked('W5 persisted resource measurements incomplete')
    previous={};observed=False
    for index,(metric,sample) in enumerate(zip(metrics,samples)):
        required=profile['ramPreflightBytes' if index==0 else 'ramDuringBytes']
        if sample.get('ramRequiredBytes')!=required:raise Blocked('W5 recorded RAM threshold contradicted')
        at=metric.get('at')
        if (type(at) not in (int,float) or not math.isfinite(at) or not 0<=sample['at']-at<=1
                or any(metric.get(k)!=sample[k] for k in ('hostFree','dockerFree','ramAvailable'))):
            raise Blocked('W5 cgroup and gate observations disagree')
        growth=metric.get('hostGrowth')
        if type(growth) is not int or not 0<=growth<=profile['artifactCapBytes']:
            raise Blocked('W5 artifact budget observation contradicted')
        peaks=metric.get('containerMemoryPeakBytes',{});memory=metric.get('containerMemory',{})
        if peaks and set(peaks)!=set(memory):raise Blocked('W5 cgroup memory inventory incomplete')
        limits=0
        for name,row in memory.items():
            observed=True
            if (any(type(row.get(k)) is not int or row[k]<0 for k in ('currentBytes','peakBytes','limitBytes'))
                    or row['limitBytes']==0 or row['currentBytes']>row['peakBytes']
                    or row['peakBytes']>row['limitBytes'] or peaks[name]!=row['peakBytes']
                    or row.get('oomKilled') is not False or type(row.get('running')) is not bool
                    or not isinstance(row.get('events'),dict)
                    or not {'oom','oom_kill'}<=set(row['events'])
                    or any(type(v) is not int or v<0 for v in row['events'].values())
                    or any(row['events'].get(k,0)>0 for k in ('oom','oom_kill','oom_group_kill'))
                    or not isinstance(row.get('containerId'),str) or len(row['containerId'])!=64):
                raise Blocked('W5 cgroup memory or OOM observation invalid')
            if name in previous:
                old=previous[name]
                if (row['containerId']!=old['containerId'] or row['limitBytes']!=old['limitBytes']
                        or row['peakBytes']<old['peakBytes']):raise Blocked('W5 memory ownership or peak drift')
            previous[name]=row;limits+=row['limitBytes']
        if limits>profile['maxConfiguredWorkloadBytes']:raise Blocked('W5 memory topology exceeded profile')
    if not observed:raise Blocked('W5 cgroup memory workload never observed')
