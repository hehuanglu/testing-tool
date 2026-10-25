"""Owned paired actual-sink control; raw history/cells remain private.

stdin accepts only a locked owned plan plus creation metadata. It accepts no
product URL/credential. Success is native sink replay, not product admission.
"""
import hashlib
import http.client
from http.server import ThreadingHTTPServer
import json
import os
import resource
import secrets
import sys
import threading
import time

from .credential_broker import BrokerBinding
from .errors import Blocked
from .finalsource_delegated import TargetBinding
from .live_sink_probe import (api, Target, start_engine, wait_engine, stop_engine, read_session_database)
from .native_secret_gate import collect_history, NativePair, NativeG3Replay, REASON_CODES, HistoryShapeIssue
from .private_db import strict_json, control_forms

STAGE='input'
FAILURE_CODES=REASON_CODES|frozenset(('paired_private_probe_failed','paired_input_contract',
    'paired_input_binding','paired_session_not_fresh','paired_seed_response','paired_passive_timeout',
    'paired_incomplete_matrix_admitted','paired_input_budget','live_sink_startup_failed',
    'live_sink_api_failed','live_sink_api_contract','live_sink_decoder_compile_failed','live_sink_database_read_failed'))


def execute(value):
    global STAGE
    resource.setrlimit(resource.RLIMIT_CORE,(0,0));os.umask(0o077)
    if not isinstance(value,dict) or set(value)!={'plan','planHash','resource'}:
        raise Blocked('paired_input_contract')
    plan=value['plan'];meta=value['resource']
    encoded=json.dumps(plan,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    if (plan.get('contract')!='actual-zap-sink-control/1.1' or plan.get('pairedAudit') is not True
            or plan.get('target')!='owned-loopback:18080' or plan.get('productInputAccepted') is not False
            or plan.get('operationalAdmission') is not False
            or hashlib.sha256(encoded).hexdigest()!=value['planHash']
            or set(meta)!={'id','imageId','startedAt','networkId'} or meta['imageId']!=plan['imageId']):
        raise Blocked('paired_input_binding')
    target_binding=TargetBinding(meta['id'],meta['imageId'],meta['startedAt'],meta['networkId'],'127.0.0.1',18080)
    binding=BrokerBinding(plan['runId'],value['planHash'],'owned-control','owned-canary',None,
        'owned-native-sink/1.1','http://127.0.0.1:18080',plan['expiresAt'])
    secret=secrets.token_urlsafe(48);forms=control_forms(secret)
    server=ThreadingHTTPServer(('127.0.0.1',18080),Target)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    collected=[];version=None;proc=None;log=None
    try:
        for phase in ('zero','positive'):
            STAGE=phase+'-startup';log=open('/tmp/paired-'+phase+'.log','wb')
            proc=start_engine(log);version=wait_engine(proc)
            # The saved zero-case database is closed/read before a new session
            # reuses its owned tmpfs destination. No borrowed state is touched.
            api('core','action','newSession',name='',overwrite='true')
            if api('core','view','numberOfMessages')!={'numberOfMessages':'0'}:
                raise Blocked('paired_session_not_fresh')
            STAGE=phase+'-seed'
            for index,form in enumerate(forms.values()):
                conn=http.client.HTTPConnection('127.0.0.1',8090,timeout=5)
                try:
                    conn.request('GET','http://127.0.0.1:18080/control/'+str(index),
                        headers={'X-Zpa-Seed':form.decode('ascii') if phase=='positive' else 'owned-clean-'+str(index),
                                 'Connection':'close'})
                    response=conn.getresponse();response.read(4096)
                    if response.status!=200:raise Blocked('paired_seed_response')
                finally:conn.close()
            end=time.monotonic()+30;stable=0
            while stable<2:
                if time.monotonic()>=end:raise Blocked('paired_passive_timeout')
                stable=stable+1 if api('pscan','view','recordsToScan')=={'recordsToScan':'0'} else 0
                time.sleep(.25)
            STAGE=phase+'-history'
            history=collect_history(lambda c,k,n,args:api(c,k,n,**args),page_size=2)
            api('core','action','saveSession',name='/session/w5-saved-session',overwrite='true')
            STAGE=phase+'-stop';stop_engine(proc)
            STAGE=phase+'-database';database=read_session_database()
            collected.append((history,database));log.close();log=None;proc=None
        STAGE='private-replay'
        now=time.time()
        pair=NativePair('success',binding,target_binding,None,'owned-native-canary',
            collected[0][0],collected[0][1],collected[1][0],collected[1][1],now,min(now+60,binding.expires_at))
        replayer=NativeG3Replay(secret=secret,pairs=(pair,))
        receipt=replayer.inspect(binding=binding,target=target_binding,epoch=None,now=now)
        # Exercise the actual gate path as a negative control. Complete native
        # pairs do not supply the other141pairs or platform/product acceptance.
        try:
            replayer.verify('G3',(b'private-native-g3-replay/1.0',),binding=binding,
                            target=target_binding,epoch=None,now=now)
        except Blocked as exc:
            if str(exc)!='native_g3_actual_sink_matrix_incomplete':raise
        else:raise Blocked('paired_incomplete_matrix_admitted')
        return {'schemaVersion':'actual-zap-sink-control/1.1','status':'pass','zapVersion':version,
                'privateReplay':receipt,'incompleteMatrixRejected':True,'writerTerminals':2,
                'freshSessions':2,'controlRequests':10,'activeRequests':0,'productRequests':0,
                'sourceValuesIncluded':False,'rawCellsExportedToController':False,
                'platformAcceptance':False,'operationalAdmission':False}
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=10)
            except Exception:proc.kill();proc.wait(timeout=5)
        if log is not None:log.close()
        server.shutdown()


def main():
    try:
        raw=sys.stdin.buffer.read(65537)
        if len(raw)>65536:raise Blocked('paired_input_budget')
        result=execute(strict_json(raw))
    except BaseException as exc:
        reason=str(exc) if isinstance(exc,Blocked) and str(exc) in FAILURE_CODES else 'paired_private_probe_failed'
        result={'schemaVersion':'actual-zap-sink-control/1.1','status':'blocked','stage':STAGE,
                'reasonCode':reason,'productRequests':0,
                'sourceValuesIncluded':False,'rawCellsExportedToController':False,'operationalAdmission':False}
        if isinstance(exc,HistoryShapeIssue):result['historyShape']=exc.shape
    print(json.dumps(result,separators=(',',':')))
    return 0 if result['status']=='pass' else 2


if __name__=='__main__':raise SystemExit(main())
