"""In-reader JDBC bridge. Private socket/child pipes never traverse Docker I/O.

Only validated metadata is printed. Fixed Java modes and paths; no target URL,
password, token, arbitrary JDBC URL or arbitrary process command is accepted.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import select
import socket
import stat
import subprocess
import time

from .errors import Blocked
from .private_source import mount_type
from .secret_audit import CanaryAuditor
from .private_db import (CONTROL_ZONE,MAX_DECODED,receive,send,socket_name,strict_json,
                         validate_control_files,validate_public_receipt)


def stat_metadata(info):
    return {'inode':info.st_ino,'device':info.st_dev,'bytes':info.st_size,'uid':info.st_uid,'gid':info.st_gid,
            'mode':stat.S_IMODE(info.st_mode),'links':info.st_nlink}


def control_inventory():
    zone=Path(CONTROL_ZONE)
    if zone.is_symlink() or zone.resolve(strict=True)!=zone or not zone.is_dir():
        raise Blocked('private_db_control_zone_invalid')
    rows=[]
    for path in sorted(zone.iterdir()):
        info=path.lstat()
        if not stat.S_ISREG(info.st_mode):raise Blocked('private_db_control_file_invalid')
        rows.append({'name':path.name,**stat_metadata(info)})
    return validate_control_files({'filesystem':mount_type(zone),'zonePath':CONTROL_ZONE,
        'zone':stat_metadata(zone.stat()),'files':rows,'contentHashesIncluded':False})


def remove_control(inventory):
    # Refuse replacement/unknown files; delete only intentional owned control DB.
    if control_inventory()!=inventory:raise Blocked('private_db_control_changed_before_cleanup')
    zone=Path(CONTROL_ZONE)
    for row in inventory['files']:(zone/row['name']).unlink()
    zone.rmdir()
    if zone.exists() or zone.is_symlink():raise Blocked('private_db_control_cleanup_unconfirmed')
    return len(inventory['files'])


def java_decode(mode,password=None):
    argv=['java','-cp','/tmp:/zap/lib/hsqldb-2.7.4.jar','SessionDbReadback',
          'private-control' if mode=='control' else 'session']
    proc=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    output=bytearray();deadline=time.monotonic()+8
    try:
        if password is not None:
            if not isinstance(password,str) or not 12<=len(password)<=8192:raise Blocked('private_db_source_invalid')
            proc.stdin.write(password.encode()+b'\n');proc.stdin.flush()
        proc.stdin.close()
        while True:
            left=deadline-time.monotonic()
            if left<=0 or not select.select([proc.stdout],[],[],left)[0]:raise Blocked('private_db_decoder_deadline')
            part=os.read(proc.stdout.fileno(),65536)
            if not part:break
            output.extend(part)
            if len(output)>MAX_DECODED:raise Blocked('private_db_decoder_budget')
        code=proc.wait(timeout=max(.01,deadline-time.monotonic()))
        return code,bytes(output)
    finally:
        if proc.poll() is None:proc.kill();proc.wait(timeout=2)
        if not proc.stdin.closed:proc.stdin.close()
        proc.stdout.close()


def execute(*,binding,actor,case_id,mode,probe='valid'):
    if (set(binding)!={'runId','planHash','sourceMode','actorRef','privateDbControls'}
            or binding['sourceMode']!='private-file' or binding['privateDbControls'] is not True
            or binding['actorRef'] not in ('A','B') or actor!=binding['actorRef']):
        raise Blocked('private_db_bridge_binding_invalid')
    request={'op':'private-db','runId':binding['runId'],'planHash':binding['planHash'],
             'actorRef':actor,'caseId':case_id,'mode':mode}
    if probe=='wrong-actor':request['actorRef']='B' if actor=='A' else 'A'
    if probe=='wrong-plan':request['planHash']='0'*64
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as channel:
        channel.settimeout(12);channel.connect(socket_name(binding['runId']));send(channel,request)
        ready=receive(channel,16384)
        if probe!='valid':
            reason='peer_uid' if probe=='wrong-uid' else 'no_replay' if probe=='replay' else 'binding'
            expected={'status':'denied','reasonCode':reason,'peer':{'uid':1000,'gid':1000} if probe=='wrong-uid' else {'uid':1003,'gid':1003},
                      'sourceRead':False,'privateValueDelivered':False,'sourceValuesIncluded':False,
                      'requestedActorMatches':probe!='wrong-actor','requestedPlanMatches':probe!='wrong-plan',
                      'requestedRunMatches':True,'requestedCaseMatches':True}
            if ready!=expected:raise Blocked('private_db_denial_control_failed')
            return {'probe':probe,**ready}
        if set(ready)!=({'status','nonce','password'} if mode=='control' else {'status','nonce'}) or ready['status']!='ready':
            raise Blocked('private_db_source_channel_not_ready')
        nonce=ready['nonce'];password=ready.get('password')
        if Path(CONTROL_ZONE).exists() or Path(CONTROL_ZONE).is_symlink():raise Blocked('private_db_control_zone_not_fresh')
        code,raw=java_decode(mode,password)
        files=control_inventory() if mode=='control' and code==0 else None
        send(channel,{'nonce':nonce,'decoderExit':code,'decodedBase64':base64.b64encode(raw).decode(),'controlFiles':files})
        raw=b'';audited=receive(channel,4096)
        if (set(audited)!={'status','leakDetected'} or audited['status']!='audited'
                or type(audited['leakDetected']) is not bool):raise Blocked('private_db_holder_audit_incomplete')
        count=remove_control(files) if files else 0
        send(channel,{'nonce':nonce,'controlZoneRemoved':True,'removedControlFiles':count})
        receipt=receive(channel,65536)
        validate_public_receipt(receipt,run_id=binding['runId'],plan_hash=binding['planHash'],
                                actor=actor,case_id=case_id,mode=mode)
        if password and CanaryAuditor([password]).matches(json.dumps(receipt).encode()):
            raise Blocked('private_db_public_receipt_contains_source')
        return receipt


def main():
    os.umask(0o077)
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--actor',choices=['A','B'],required=True)
    ap.add_argument('--case',required=True);ap.add_argument('--mode',choices=['control','session'],default='control')
    ap.add_argument('--probe',choices=['valid','wrong-uid','wrong-actor','wrong-plan','replay'],default='valid');a=ap.parse_args()
    try:
        binding=strict_json(Path('/binding/w5-binding.json').read_bytes())
        result=execute(binding=binding,actor=a.actor,case_id=a.case,mode=a.mode,probe=a.probe)
    except BaseException:
        result={'status':'blocked','reasonCode':'private_db_bridge_failed','sourceValuesIncluded':False,
                'rawCellsExportedToController':False}
    print(json.dumps(result,separators=(',',':')))
    return 0 if result['status'] in ('pass','denied','leak') else 2


if __name__=='__main__':raise SystemExit(main())
