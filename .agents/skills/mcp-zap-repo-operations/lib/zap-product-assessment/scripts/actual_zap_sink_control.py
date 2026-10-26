#!/usr/bin/env python3
"""Owned, no-network live ZAP history/session positive control. No product input."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from zap_assessment.errors import Blocked
from zap_assessment.runtime import ZAP
from zap_assessment.contracts import canonical, digest
from zap_assessment.safety_io import atomic_bytes
from zap_assessment.private_db import strict_json
from zap_assessment.secret_inventory import SINKS,LIFECYCLE


def call(args, timeout=15):
    result = subprocess.run(['docker', *args], capture_output=True, timeout=timeout)
    if result.returncode:
        raise Blocked('owned_control_docker_failed')
    return result.stdout


def source_pin():
    paths = [*sorted((ROOT / 'src').rglob('*.py')),
             ROOT / 'src/zap_assessment/probes/SessionDbReadback.java', Path(__file__).resolve()]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def prepare(work,paired_audit=False):
    if not work.is_absolute() or work.exists() or work.is_symlink():
        raise Blocked('owned_control_work_not_fresh')
    if type(paired_audit) is not bool:raise Blocked('owned_control_plan_contract')
    plan = {'contract': 'actual-zap-sink-control/1.1' if paired_audit else 'actual-zap-sink-control/1.0', 'runId': 'live-sink-' + uuid.uuid4().hex,
            'sourcePins': source_pin(), 'image': ZAP,
            'imageId': call(['image', 'inspect', '--format', '{{.Id}}', ZAP]).decode().strip(),
            'createdAt': time.time(), 'expiresAt': time.time() + 900,
            'lifecycle': 'success', 'encodings': ['raw-utf8', 'base64-standard', 'base64-url',
                                               'url-percent', 'json-escape'],
            'resource': {'hostReserve': 2 * 1024**3, 'hostGrowth': 256 * 1024**2,
                         'dockerReserve': 2 * 1024**3, 'dockerGrowth': 1024**3,
                         'ramPreflight': 3 * 1024**3, 'ramDuring': 1536 * 1024**2,
                         'sampleSeconds': 5, 'memoryLimit': 1024**3},
            'target': 'owned-loopback:18080', 'productInputAccepted': False,
            'deadlineSeconds': 240, 'operationalAdmission': False}
    if paired_audit:plan['pairedAudit']=True
    work.mkdir(mode=0o700)
    # Frozen executable source, independently rehashed at entry. A live bind of
    # the editing checkout would make a long-running probe's source ambiguous.
    for relative, checksum in plan['sourcePins'].items():
        raw = (ROOT / relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != checksum:
            raise Blocked('owned_control_source_changed_during_prepare')
        target = work / 'source' / relative; target.parent.mkdir(parents=True, exist_ok=True)
        atomic_bytes(target, raw); target.chmod(0o444)
    atomic_bytes(work / 'plan.json', canonical(plan))
    return {'planHash': digest(plan), 'workDir': str(work), 'productRequests': 0}


def owner(name, plan, cid):
    fmt='{"Id":{{json .Id}},"Image":{{json .Image}},"State":{"Running":{{json .State.Running}},"OOMKilled":{{json .State.OOMKilled}},"StartedAt":{{json .State.StartedAt}}},"Config":{"Labels":{{json .Config.Labels}}},"NetworkSettings":{"Networks":{{json .NetworkSettings.Networks}}}}'
    info = strict_json(call(['inspect','--format',fmt,name]))
    if not isinstance(info,dict):raise Blocked('owned_control_metadata_contract')
    if ((cid is not None and info['Id'] != cid) or info['Image'] != plan['imageId']
            or info['Config']['Labels'].get('zpa.run') != plan['runId']):
        raise Blocked('owned_control_ownership_mismatch')
    return info


def validate_result(value):
    if isinstance(value,dict) and value.get('schemaVersion')=='actual-zap-sink-control/1.1':
        return validate_paired_result(value)
    common = {'schemaVersion', 'status', 'productRequests', 'operationalAdmission',
              'sourceValuesIncluded', 'rawCellsExportedToController'}
    if (not isinstance(value, dict) or value.get('schemaVersion') != 'actual-zap-sink-control/1.0'
            or value.get('productRequests') != 0 or value.get('operationalAdmission') is not False
            or value.get('sourceValuesIncluded') is not False or value.get('rawCellsExportedToController') is not False):
        raise Blocked('owned_control_result_contract')
    if value.get('status') == 'blocked':
        if not common <= value.keys() or set(value) - common - {'reasonCode', 'diagnostic'}:
            raise Blocked('owned_control_result_contract')
        reason = value.get('reasonCode')
        allowed_reasons = {'live_sink_' + s for s in ('row_invalid','duplicate_cell','seed_binding_invalid',
            'seed_type_changed','positive_control_missed','api_failed','api_contract','startup_failed',
            'seed_response_failed','history_control_missed','passive_timeout','decoder_compile_failed',
            'database_read_failed','probe_failed','duplicate_seed_header')}
        if reason not in allowed_reasons:
            raise Blocked('owned_control_result_contract')
        # No free-form strings/errors from the private child are published.
        diagnostic = value.get('diagnostic', {})
        if (not isinstance(diagnostic, dict) or set(diagnostic) - {'stage', 'encoding', 'historyMessages', 'matchedMessages'}
                or diagnostic.get('stage', 'initial') not in ('initial','history','save-session','shutdown','database')
                or diagnostic.get('encoding', 'raw-utf8') not in ('raw-utf8','base64-standard','base64-url','url-percent','json-escape')
                or any(type(diagnostic[k]) is not int or not 0 <= diagnostic[k] <= 100000
                       for k in ('historyMessages','matchedMessages') if k in diagnostic)):
            raise Blocked('owned_control_result_contract')
        return value
    if (set(value) != common | {'zapVersion','history','database','writerTerminal','passiveSettled',
                               'lifecycle','activeRequests','platformAcceptance'}
            or value['status'] != 'pass' or value['zapVersion'] != '2.17.0'
            or value['writerTerminal'] is not True or value['passiveSettled'] is not True
            or value['platformAcceptance'] is not False or value['lifecycle'] != 'success'
            or type(value['activeRequests']) is not int or value['activeRequests'] != 0):
        raise Blocked('owned_control_result_contract')
    encodings = ['raw-utf8','base64-standard','base64-url','url-percent','json-escape']
    for section in ('history', 'database'):
        part = value[section]
        expected = {'controls','messages'} if section == 'history' else {
            'controls','decoder','tables','decodedCells','decodedBytes','seededRequests',
            'sourceValuesIncluded','rawCellsExportedToController'}
        if not isinstance(part, dict) or set(part) != expected or not isinstance(part['controls'], list):
            raise Blocked('owned_control_result_contract')
        if len(part['controls']) != 5:
            raise Blocked('owned_control_result_contract')
        for row, encoding in zip(part['controls'], encodings):
            if (not isinstance(row, dict) or set(row) != {'encoding','detected','occurrences'} | ({'sqlType'} if section == 'database' else set())
                    or row['encoding'] != encoding or row['detected'] is not True
                    or type(row['occurrences']) is not int or not 1 <= row['occurrences'] <= 100000
                    or (section == 'database' and row['sqlType'] not in (12,-4,-3,-2,1,2004,2005))):
                raise Blocked('owned_control_result_contract')
        if section == 'history':
            if type(part['messages']) is not int or not 5 <= part['messages'] <= 100000:
                raise Blocked('owned_control_result_contract')
        elif (part['decoder'] != 'HSQL JDBC all PUBLIC table typed cells'
                or not isinstance(part['tables'], list) or 'HISTORY' not in part['tables']
                or len(part['tables']) != len(set(part['tables']))
                or any(not isinstance(t, str) or not re.fullmatch('[A-Z0-9_]{1,256}', t) for t in part['tables'])
                or any(type(part[k]) is not int or not 0 < part[k] <= 128 * 1024 * 1024 for k in ('decodedCells','decodedBytes'))
                or part['seededRequests'] != 5 or part['sourceValuesIncluded'] is not False
                or part['rawCellsExportedToController'] is not False):
            raise Blocked('owned_control_result_contract')
    return value


def validate_paired_result(value):
    common={'schemaVersion','status','productRequests','sourceValuesIncluded',
            'rawCellsExportedToController','operationalAdmission'}
    if (value.get('productRequests')!=0 or value.get('sourceValuesIncluded') is not False
            or value.get('rawCellsExportedToController') is not False or value.get('operationalAdmission') is not False):
        raise Blocked('owned_control_result_contract')
    if value.get('status')=='blocked':
        from zap_assessment.live_sink_pair import FAILURE_CODES
        stages={'input','private-replay'}|{p+'-'+s for p in ('zero','positive') for s in ('startup','seed','history','stop','database')}
        extra={'historyShape'} if 'historyShape' in value else set()
        if (set(value)!=common|{'reasonCode','stage'}|extra or value['reasonCode'] not in FAILURE_CODES
                or value['stage'] not in stages):raise Blocked('owned_control_result_contract')
        if extra:
            shape=value['historyShape'];fields={'id','requestHeader','requestBody','responseHeader','responseBody'}
            if (not isinstance(shape,dict) or set(shape)!=fields|{'idRepeated','idPositiveDecimal'}
                    or any(shape[k] not in ('str','int','float','bool','NoneType','list','dict','missing') for k in fields)
                    or type(shape['idRepeated']) is not bool or type(shape['idPositiveDecimal']) is not bool):
                raise Blocked('owned_control_result_contract')
        return value
    if (set(value)!=common|{'zapVersion','privateReplay','incompleteMatrixRejected','writerTerminals',
                           'freshSessions','controlRequests','activeRequests','platformAcceptance'}
            or value.get('status')!='pass' or value['zapVersion']!='2.17.0'
            or value['incompleteMatrixRejected'] is not True or value['platformAcceptance'] is not False
            or any(type(value[k]) is not int or value[k]!=v for k,v in
                   [('writerTerminals',2),('freshSessions',2),('controlRequests',10),('activeRequests',0)])):
        raise Blocked('owned_control_result_contract')
    replay=value['privateReplay'];required={(s,l) for s in SINKS for l in LIFECYCLE}
    expected_missing=required-{('zap-history','success'),('zap-session-db','success')}
    if (not isinstance(replay,dict) or set(replay)!={'contract','requiredPairs','nativePairsReplayed',
                    'missingPairs','samples','sourceValuesIncluded','platformAcceptance'}
            or replay['contract']!='private-native-g3-replay/1.0' or replay['requiredPairs']!=143
            or replay['nativePairsReplayed']!=2 or replay['sourceValuesIncluded'] is not False
            or replay['platformAcceptance'] is not False or not isinstance(replay['missingPairs'],list)
            or len(replay['missingPairs'])!=141 or len(replay['samples'])!=1):
        raise Blocked('owned_control_result_contract')
    if (any(not isinstance(r,dict) or set(r)!={'sinkId','lifecycle'} for r in replay['missingPairs'])
            or {(r['sinkId'],r['lifecycle']) for r in replay['missingPairs']}!=expected_missing):
        raise Blocked('owned_control_result_contract')
    sample=replay['samples'][0]
    if not isinstance(sample,dict) or set(sample)!={'lifecycle','zero','positive'} or sample['lifecycle']!='success':
        raise Blocked('owned_control_result_contract')
    zero=sample['zero'];positive=sample['positive']
    if (not isinstance(zero,dict) or set(zero)!={'historyMessages','historyForbiddenMatches','database','rawValuesIncluded'}
            or type(zero['historyMessages']) is not int or not 5<=zero['historyMessages']<=100000
            or type(zero['historyForbiddenMatches']) is not int or zero['historyForbiddenMatches']!=0
            or zero['rawValuesIncluded'] is not False or not isinstance(positive,dict)
            or set(positive)!={'historyMessages','historyControls','database','rawValuesIncluded'}
            or positive['rawValuesIncluded'] is not False):
        raise Blocked('owned_control_result_contract')
    # Reuse the existing positive-control output allow-list; this is publication
    # schema validation, not a replacement for the private byte replay.
    shaped={'schemaVersion':'actual-zap-sink-control/1.0','status':'pass','zapVersion':value['zapVersion'],
            'history':{'messages':positive['historyMessages'],'controls':positive['historyControls']},
            'database':positive['database'],'writerTerminal':True,'passiveSettled':True,'lifecycle':'success',
            'activeRequests':0,'productRequests':0,'sourceValuesIncluded':False,'rawCellsExportedToController':False,
            'platformAcceptance':False,'operationalAdmission':False}
    validate_result(shaped)
    db=zero['database']
    if (not isinstance(db,dict) or set(db)!={'tables','rows','decodedCells','decodedBytes','canaryMatches','seededControl','decoder'}
            or db['decoder']!='HSQL JDBC all PUBLIC table typed cells' or db['seededControl'] is not False
            or type(db['canaryMatches']) is not int or db['canaryMatches']!=0
            or not isinstance(db['tables'],list) or 'HISTORY' not in db['tables']
            or len(db['tables'])!=len(set(db['tables']))
            or any(not isinstance(t,str) or not re.fullmatch('[A-Z0-9_]{1,256}',t) for t in db['tables'])
            or any(type(db[k]) is not int or not 0<db[k]<=128*1024*1024 for k in ('rows','decodedCells','decodedBytes'))):
        raise Blocked('owned_control_result_contract')
    return value


def run(work, expected):
    plan = json.loads((work / 'plan.json').read_bytes())
    if digest(plan) != expected or plan['sourcePins'] != source_pin() or time.time() >= plan['expiresAt']:
        raise Blocked('owned_control_plan_source_or_deadline_drift')
    for relative, checksum in plan['sourcePins'].items():
        if hashlib.sha256((work / 'source' / relative).read_bytes()).hexdigest() != checksum:
            raise Blocked('owned_control_frozen_source_drift')
    fd = os.open(work / 'attempt.lock', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600); os.close(fd)
    fs = os.statvfs(work); budget = plan['resource']
    if fs.f_bavail * fs.f_frsize < 2 * budget['hostGrowth'] + budget['hostReserve']:
        raise Blocked('owned_control_host_headroom')
    name = 'zpa-' + plan['runId']; cid = None; result = None; samples = []; proc = None
    status = {'executionStatus': 'partial', 'evidenceStatus': 'incomplete',
              'securityVerdict': 'inconclusive', 'cleanupStatus': 'pending', 'gateDecision': 'block'}
    atomic_bytes(work / 'create-intent.json', canonical({'name': name, 'planHash': expected, 'imageId': plan['imageId']}))
    try:
        cid = call(['create', '--name', name, '--label', 'zpa.run=' + plan['runId'],
            '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--user', '1000:1000', '--memory', '1g', '--memory-swap', '1g', '--cpus', '2',
            '--pids-limit', '128', '--ulimit', 'core=0:0', '--log-driver', 'none',
            '--tmpfs', '/tmp:rw,size=128m,uid=1000,gid=1000,mode=0700',
            '--tmpfs', '/session:rw,size=128m,uid=1000,gid=1000,mode=0700',
            '--tmpfs', '/home/zap/.ZAP:rw,size=384m,uid=1000,gid=1000,mode=0700',
            '-v', str(work / 'source/src') + ':/package/src:ro', '-e', 'PYTHONPATH=/package/src',
            '-e', 'ZAP_MEMORY=512m', '--entrypoint', 'sleep', plan['imageId'], '300']).decode().strip()
        atomic_bytes(work / 'create-ack.json', canonical({'id': cid, 'name': name, 'planHash': expected}))
        owner(name, plan, cid); call(['start', cid])
        def sample(preflight=False):
            began = time.monotonic(); info = owner(name, plan, cid)
            raw = call(['exec', cid, 'python3', '-c',
                "import os,json,pathlib; f=os.statvfs('/'); m=dict(x.split(':',1) for x in open('/proc/meminfo')); c=pathlib.Path('/sys/fs/cgroup'); print(json.dumps({'dockerFree':f.f_bavail*f.f_frsize,'ramAvailable':int(m['MemAvailable'].split()[0])*1024,'memoryCurrent':int((c/'memory.current').read_text()),'memoryPeak':int((c/'memory.peak').read_text()),'memoryEvents':(c/'memory.events').read_text(),'vmSwapConfigured':len(open('/proc/swaps').readlines())>1}))"], timeout=3)
            row = json.loads(raw); row.update(startedAt=began, completedAt=time.monotonic(), containerId=info['Id'])
            row['hostFree'] = os.statvfs(work).f_bavail * os.statvfs(work).f_frsize
            samples.append(row)
            if (row['completedAt'] - began > budget['sampleSeconds']
                    or (len(samples) > 1 and row['completedAt'] - samples[-2]['completedAt'] > budget['sampleSeconds'])
                    or row['hostFree'] < budget['hostReserve']
                    or row['dockerFree'] < budget['dockerReserve'] + (2 * budget['dockerGrowth'] if preflight else 0)
                    or row['ramAvailable'] < budget['ramPreflight' if preflight else 'ramDuring']
                    or info['State']['OOMKilled']):
                raise Blocked('owned_control_resource_bound')
        sample(True)
        paired=plan.get('contract')=='actual-zap-sink-control/1.1'
        if paired:
            info=owner(name,plan,cid);networks=info['NetworkSettings']['Networks']
            if plan.get('pairedAudit') is not True or set(networks)!={'none'}:
                raise Blocked('owned_control_paired_binding')
            payload=canonical({'plan':plan,'planHash':expected,'resource':{'id':cid,'imageId':info['Image'],
                'startedAt':info['State']['StartedAt'],'networkId':networks['none']['NetworkID']}})
            proc=subprocess.Popen(['docker','exec','-i',cid,'python3','-m','zap_assessment.live_sink_pair'],
                                  stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            proc.stdin.write(payload);proc.stdin.close();proc.stdin=None
        else:
            proc = subprocess.Popen(['docker', 'exec', cid, 'python3', '-m', 'zap_assessment.live_sink_probe'],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deadline = time.monotonic() + plan['deadlineSeconds']
        while proc.poll() is None:
            if time.monotonic() >= deadline:
                raise Blocked('owned_control_deadline')
            sample(); time.sleep(.5)
        raw, stderr = proc.communicate(timeout=5)
        if len(raw) > 65536 or stderr:
            raise Blocked('owned_control_output_contract')
        result = validate_result(strict_json(raw))
        atomic_bytes(work / 'probe-result.json', canonical(result))
        if proc.returncode or result.get('status') != 'pass':
            raise Blocked('owned_control_probe_blocked')
        sample(); status.update(executionStatus='completed', evidenceStatus='complete')
    except Exception as exc:
        status['reasonCode'] = str(exc) if isinstance(exc, Blocked) else 'owned_control_failed'
    finally:
        # A missing create ACK is reconciled by exact intent name/image/label.
        # Never issue a second create/start or accept a similarly named resource.
        if cid is None:
            try:
                found = call(['ps', '-aq', '--filter', 'name=^/' + name + '$']).decode().strip()
                if found: cid = owner(name, plan, None)['Id']
                else: status['cleanupStatus'] = 'clean'
            except Exception:
                status['cleanupStatus'] = 'quarantine'
        if cid:
            try:
                owner(name, plan, cid); call(['stop', '--time', '5', cid]); info = owner(name, plan, cid)
                if info['State']['Running']: raise Blocked('owned_control_stop_unconfirmed')
                atomic_bytes(work / 'stop.json', canonical({'containerId': cid, 'terminal': True,
                    'oomKilled': info['State']['OOMKilled'], 'noReplay': True}))
                call(['rm', cid]); status['cleanupStatus'] = 'clean'
            except Exception:
                status['cleanupStatus'] = 'quarantine'
        if proc is not None:
            try: proc.communicate(timeout=5)
            except subprocess.TimeoutExpired: proc.kill(); proc.communicate(timeout=5)
        atomic_bytes(work / 'resource-samples.json', canonical(samples))
        atomic_bytes(work / 'status.json', canonical({**status, 'planHash': expected, 'productRequests': 0,
            'operationalAdmission': False, 'limitation': 'actual success-lifecycle controls only; platform/full G3 not accepted'}))
    return status


def recover(work, expected):
    plan = strict_json((work / 'plan.json').read_bytes())
    if digest(plan) != expected:
        raise Blocked('owned_control_recovery_pin_mismatch')
    intent = strict_json((work / 'create-intent.json').read_bytes())
    name = 'zpa-' + plan['runId']
    if intent != {'name': name, 'planHash': expected, 'imageId': plan['imageId']}:
        raise Blocked('owned_control_recovery_intent_mismatch')
    found = call(['ps', '-aq', '--filter', 'name=^/' + name + '$']).decode().strip()
    if found:
        info = owner(name, plan, None); cid = info['Id']
        ack = work / 'create-ack.json'
        if ack.exists() and strict_json(ack.read_bytes()) != {'id': cid, 'name': name, 'planHash': expected}:
            raise Blocked('owned_control_recovery_ack_mismatch')
        call(['stop', '--time', '5', cid])
        if owner(name, plan, cid)['State']['Running']:
            raise Blocked('owned_control_recovery_stop_unconfirmed')
        call(['rm', cid])
    value = {'cleanupStatus': 'clean', 'planHash': expected, 'noReplay': True,
             'removedOwnedResource': bool(found), 'productRequests': 0}
    atomic_bytes(work.parent / (work.name + '-recovery-' + uuid.uuid4().hex + '.json'), canonical(value))
    return value


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command', choices=['prepare', 'run', 'recover']); ap.add_argument('--work-dir', type=Path, required=True)
    ap.add_argument('--expect-plan-hash');ap.add_argument('--paired-audit',action='store_true')
    args = ap.parse_args()
    try:
        if args.command == 'prepare': result = prepare(args.work_dir,args.paired_audit)
        elif args.paired_audit:raise Blocked('paired_option_belongs_to_prepare')
        elif not args.expect_plan_hash: raise Blocked('external_plan_pin_required')
        elif args.command == 'recover': result = recover(args.work_dir, args.expect_plan_hash)
        else: result = run(args.work_dir, args.expect_plan_hash)
        print(json.dumps(result)); return 0 if result.get('executionStatus', 'completed') == 'completed' else 2
    except Exception:
        print(json.dumps({'gateDecision': 'block', 'reasonCode': 'owned_control_entry_refused', 'productRequests': 0})); return 2


if __name__ == '__main__': raise SystemExit(main())
