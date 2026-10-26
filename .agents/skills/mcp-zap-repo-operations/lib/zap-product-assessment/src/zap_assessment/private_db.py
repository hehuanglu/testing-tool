"""Owned W5 private JDBC channel. Raw values stay in holder/reader processes.

Linux abstract AF_UNIX is scoped to the run's existing network namespace. Peer
UID/GID1003 excludes the scanner UID; this is not host-admin/platform attestation.
The controller receives metadata, never the source or decoded cell stream.
"""
import base64
import json
import math
import secrets
import socket
import struct
import threading
import time

from .errors import Blocked,SecretLeak
from .scanner_secret_audit import audit_database
from .secret_audit import CanaryAuditor

CONTRACT='private-hsql-source/1.0'
CONTROL_ZONE='/tmp/w5-private-db-control'
ENCODINGS=('raw-utf8','base64-standard','base64-url','url-percent','json-escape')
MAX_FRAME=12*1024*1024
MAX_DECODED=8*1024*1024
TEXT_TYPES={1,12,-1,-9,-15,-16,2005,2011}
BINARY_TYPES={-2,-3,-4,2004}


def strict_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate private frame key')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,
                      parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite private frame')))


def socket_name(run_id):
    if not isinstance(run_id,str) or not run_id.replace('-','').isalnum() or len(run_id)>70:
        raise Blocked('private_db_run_binding_invalid')
    return '\0zpa-private-db-'+run_id


def _read(sock,size):
    value=bytearray()
    while len(value)<size:
        part=sock.recv(min(65536,size-len(value)))
        if not part:raise Blocked('private_db_frame_truncated')
        value.extend(part)
    return bytes(value)


def receive(sock,limit=MAX_FRAME):
    size=struct.unpack('!I',_read(sock,4))[0]
    if not 1<=size<=limit:raise Blocked('private_db_frame_budget')
    value=strict_json(_read(sock,size))
    if not isinstance(value,dict):raise Blocked('private_db_frame_invalid')
    return value


def send(sock,value):
    raw=json.dumps(value,separators=(',',':'),allow_nan=False).encode()
    if not 1<=len(raw)<=MAX_FRAME:raise Blocked('private_db_frame_budget')
    sock.sendall(struct.pack('!I',len(raw))+raw)


def peer_identity(sock):
    pid,uid,gid=struct.unpack('3i',sock.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
    return {'uid':uid,'gid':gid}  # peer PID may be unmapped across PID namespaces


def control_forms(password):
    if (not isinstance(password,str) or not 12<=len(password)<=8192
            or any(not 32<=ord(c)<=126 for c in password)):
        raise Blocked('private_db_source_family_unsupported')
    raw=password.encode()
    return dict(zip(ENCODINGS,(raw,base64.b64encode(raw),base64.urlsafe_b64encode(raw).rstrip(b'='),
        b''.join(('%%%02X'%b).encode() for b in raw),b''.join(('\\u%04x'%b).encode() for b in raw))))


def audit_private_control(raw,password):
    """Independent Python oracle checks tags, row/column/type and exact encoding.

    Java produces the encodings and reopens a persisted CACHED-table HSQL DB.
    Equality/comparison bytes never leave this holder-side function.
    """
    if not isinstance(raw,bytes) or len(raw)>MAX_DECODED:raise Blocked('private_db_decoder_budget')
    forms=control_forms(password);auditor=CanaryAuditor([password])
    result=audit_database(auditor,raw,expect_canary=True)
    if (result['tables']!=['PRIVATE_SOURCE_CONTROL'] or result['rows']!=5
            or result['decodedCells']!=15 or result['canaryMatches']!=10):
        raise Blocked('private_db_control_shape_invalid')
    rows={}
    try:
        for line in raw.splitlines():
            value=strict_json(line)
            if value['kind']!='cell':continue
            index=value.get('row');column=value.get('column');sql=value.get('sqlType')
            if (type(index) is not int or not 1<=index<=5
                    or value.get('table')!='PRIVATE_SOURCE_CONTROL'
                    or column not in ('ENCODING','TEXT_VALUE','BINARY_VALUE')):raise ValueError()
            row=rows.setdefault(index,{})
            if column in row:raise ValueError()
            if sql not in (BINARY_TYPES if column=='BINARY_VALUE' else TEXT_TYPES):raise ValueError()
            row[column]=base64.b64decode(value['base64'],validate=True)
        seen=set()
        for row in rows.values():
            if set(row)!={'ENCODING','TEXT_VALUE','BINARY_VALUE'}:raise ValueError()
            tag=row['ENCODING'].decode('ascii')
            if tag not in forms or tag in seen:raise ValueError()
            if row['TEXT_VALUE']!=forms[tag] or row['BINARY_VALUE']!=forms[tag]:raise ValueError()
            if not auditor.matches(row['TEXT_VALUE']) or not auditor.matches(row['BINARY_VALUE']):raise ValueError()
            seen.add(tag)
        if seen!=set(ENCODINGS):raise ValueError()
    except Exception:raise Blocked('private_db_encoding_row_binding_invalid') from None
    return {**result,'controlSource':'resolved-private-source','persistedFileDatabase':True,
        'encodingControls':[{'encoding':name,'textDetected':True,'binaryDetected':True,'exactBytes':True} for name in ENCODINGS],
        'sourceValuesIncluded':False,'contentHashesIncluded':False}


def validate_control_files(value):
    if (not isinstance(value,dict) or set(value)!={'filesystem','zonePath','zone','files','contentHashesIncluded'}
            or value['filesystem']!='tmpfs' or value['zonePath']!=CONTROL_ZONE
            or value['contentHashesIncluded'] is not False):raise Blocked('private_db_control_storage_unproven')
    fields={'inode','device','bytes','uid','gid','mode','links'}
    zone=value['zone'];files=value['files']
    if not isinstance(zone,dict) or set(zone)!=fields or not isinstance(files,list):raise Blocked('private_db_control_inventory_invalid')
    names=[]
    for row,is_file in [(zone,False),*[(r,True) for r in files]]:
        if (not isinstance(row,dict) or set(row)!=(fields|{'name'} if is_file else fields)
                or any(type(row.get(k)) is not int or row[k]<0 for k in fields)
                or row['inode']<=0 or row['uid']!=1003 or row['gid']!=1003
                or row['mode']!=(0o600 if is_file else 0o700)):
            raise Blocked('private_db_control_storage_identity_invalid')
        if is_file:
            if row['name'] not in ('session.data','session.properties','session.script','session.backup') or row['links']!=1:
                raise Blocked('private_db_control_file_unexpected')
            names.append(row['name'])
    if (len(names)!=len(set(names)) or not {'session.data','session.properties','session.script'}<=set(names)
            or any(r['bytes']<=0 for r in files)):
        raise Blocked('private_db_persisted_files_missing')
    return value


def validate_public_source(value,run_id,plan_hash):
    keys={'schemaVersion','runId','planHash','sourceKind','filesystem','zonePath','zone','files','sourceValuesIncluded','contentHashesIncluded'}
    if (not isinstance(value,dict) or set(value)!=keys or value['schemaVersion']!='owned-private-source/1.0'
            or value['runId']!=run_id or value['planHash']!=plan_hash
            or value['sourceKind']!='owned-guard-private-file-reference' or value['filesystem']!='tmpfs'
            or value['zonePath']!='/tmp/w5-private-source' or value['sourceValuesIncluded'] is not False
            or value['contentHashesIncluded'] is not False):raise Blocked('private_db_public_source_invalid')
    fields={'inode','device','bytes','uid','gid','links','mode','mtimeNs','ctimeNs'}
    if not isinstance(value['files'],list) or len(value['files'])!=2:raise Blocked('private_db_public_source_invalid')
    for row,actor in [(value['zone'],None),*zip(value['files'],('A','B'))]:
        if (not isinstance(row,dict) or set(row)!=(fields|{'actorRef','referenceId','relativePath'} if actor else fields)
                or any(type(row.get(k)) is not int or not 0<=row[k]<2**64 for k in fields)
                or row['uid']!=1003 or row['gid']!=1003 or row['mode']!=(0o600 if actor else 0o700)):
            raise Blocked('private_db_public_source_invalid')
        if actor and (row['actorRef']!=actor or row['referenceId']!='owned-private-file:'+actor
                or row['relativePath']!=actor+'.json' or row['links']!=1):raise Blocked('private_db_public_source_invalid')
    return value


def validate_public_receipt(value,*,run_id,plan_hash,actor,case_id,mode):
    """Bridge stdout allow-list. Unknown fields/strings never reach the host."""
    keys={'contract','status','mode','runId','planHash','actorRef','caseId','nonce','peer','sourceMetadata','audit',
          'controlFiles','cleanup','leakDetected','rawCellsExportedToController','sourceValuesIncluded',
          'contentHashesIncluded','startedAtMonotonic','completedAtMonotonic'}
    if (not isinstance(value,dict) or set(value)!=keys or value['contract']!=CONTRACT
            or value['status'] not in ('pass','leak') or value['mode']!=mode
            or value['runId']!=run_id or value['planHash']!=plan_hash or value['actorRef']!=actor
            or value['caseId']!=case_id or value['peer']!={'uid':1003,'gid':1003}
            or any(value[k] is not False for k in ('sourceValuesIncluded','contentHashesIncluded','rawCellsExportedToController'))
            or not isinstance(value['nonce'],str) or len(value['nonce'])!=32
            or any(c not in '0123456789abcdef' for c in value['nonce'])):
        raise Blocked('private_db_public_receipt_invalid')
    validate_public_source(value['sourceMetadata'],run_id,plan_hash)
    start=value['startedAtMonotonic'];end=value['completedAtMonotonic']
    if (any(type(t) not in (int,float) or not math.isfinite(t) for t in (start,end))
            or not 0<=end-start<=12 or type(value['leakDetected']) is not bool
            or value['leakDetected']!=(value['status']=='leak')):raise Blocked('private_db_public_timeline_invalid')
    audit=value['audit'];common={'tables','rows','decodedCells','decodedBytes','canaryMatches','seededControl','decoder'}
    if value['leakDetected']:
        if mode!='session' or audit!={'canaryLeakDetected':True,'sourceValuesIncluded':False}:
            raise Blocked('private_db_public_leak_receipt_invalid')
    else:
        extra={'controlSource','persistedFileDatabase','encodingControls','sourceValuesIncluded','contentHashesIncluded'} if mode=='control' else set()
        if (not isinstance(audit,dict) or set(audit)!=common|extra
                or audit['decoder']!='HSQL JDBC all PUBLIC table typed cells'
                or any(type(audit[k]) is not int or audit[k]<0 for k in ('rows','decodedCells','decodedBytes','canaryMatches'))
                or not isinstance(audit['tables'],list) or not audit['tables']):raise Blocked('private_db_public_audit_invalid')
        for table in audit['tables']:
            if (not isinstance(table,str) or not 1<=len(table)<=256
                    or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for c in table)):
                raise Blocked('private_db_public_table_invalid')
        if mode=='control':
            controls=[{'encoding':e,'textDetected':True,'binaryDetected':True,'exactBytes':True} for e in ENCODINGS]
            if (audit['tables']!=['PRIVATE_SOURCE_CONTROL'] or audit['rows']!=5 or audit['decodedCells']!=15
                    or audit['canaryMatches']!=10 or audit['seededControl'] is not True
                    or audit['controlSource']!='resolved-private-source' or audit['persistedFileDatabase'] is not True
                    or audit['encodingControls']!=controls or audit['sourceValuesIncluded'] is not False
                    or audit['contentHashesIncluded'] is not False):raise Blocked('private_db_public_controls_incomplete')
            if any(any(row[k] is not True for k in ('textDetected','binaryDetected','exactBytes')) for row in audit['encodingControls']):
                raise Blocked('private_db_public_controls_incomplete')
        elif audit['seededControl'] is not False or audit['canaryMatches']!=0 or 'HISTORY' not in audit['tables']:
            raise Blocked('private_db_public_session_invalid')
    if mode=='control':files=validate_control_files(value['controlFiles'])['files']
    else:
        if value['controlFiles'] is not None:raise Blocked('private_db_public_control_inventory_invalid')
        files=[]
    if (value['cleanup']!={'nonce':value['nonce'],'controlZoneRemoved':True,'removedControlFiles':len(files)}
            or value['cleanup']['controlZoneRemoved'] is not True or type(value['cleanup']['removedControlFiles']) is not int):
        raise Blocked('private_db_public_cleanup_invalid')
    return value


class PrivateDbServer:
    def __init__(self,*,run_id,plan_hash,actor,zone,current_case,canaries,record):
        self.run_id=run_id;self.plan_hash=plan_hash;self.actor=actor;self.zone=zone
        self.current_case=current_case;self.canaries=canaries;self.record=record;self.listener=None
        self.used=set();self.mutex=threading.Lock()

    def start(self):
        self.listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.listener.bind(socket_name(self.run_id));self.listener.listen(2)
        self.thread=threading.Thread(target=self.serve,name='private-jdbc-auditor',daemon=True);self.thread.start()

    def serve(self):
        while True:
            client,_=self.listener.accept()
            with client:
                client.settimeout(8)
                try:self.handle(client)
                except Exception:
                    # No raw JDBC/error/frame text is written to stderr/logs.
                    try:send(client,{'status':'blocked','reasonCode':'private_db_channel_failed','sourceValuesIncluded':False})
                    except Exception:pass

    def handle(self,client):
        identity=peer_identity(client);request=receive(client,4096)
        expected={'op','runId','planHash','actorRef','caseId','mode'}
        reason=('peer_uid' if identity!={'uid':1003,'gid':1003} else
                'binding' if (set(request)!=expected or request.get('op')!='private-db'
                  or request.get('runId')!=self.run_id or request.get('planHash')!=self.plan_hash
                  or request.get('actorRef')!=self.actor or request.get('caseId')!=self.current_case()
                  or request.get('mode') not in ('control','session')) else None)
        if reason:
            denied={'status':'denied','reasonCode':reason,'peer':identity,
                    'sourceRead':False,'privateValueDelivered':False,'sourceValuesIncluded':False,
                    'requestedActorMatches':request.get('actorRef')==self.actor,
                    'requestedPlanMatches':request.get('planHash')==self.plan_hash,
                    'requestedRunMatches':request.get('runId')==self.run_id,
                    'requestedCaseMatches':request.get('caseId')==self.current_case()}
            self.record({'event':'private_db_channel_denied',**denied,'atMonotonic':time.monotonic()})
            send(client,denied);return
        key=(request['mode'],request['caseId'])
        with self.mutex:
            if key in self.used:
                denied={'status':'denied','reasonCode':'no_replay','peer':identity,
                    'sourceRead':False,'privateValueDelivered':False,'sourceValuesIncluded':False,
                    'requestedActorMatches':True,'requestedPlanMatches':True,'requestedRunMatches':True,'requestedCaseMatches':True}
                self.record({'event':'private_db_channel_denied',**denied,'atMonotonic':time.monotonic()})
                send(client,denied);return
            self.used.add(key)
        # An audit read is separate from broker bootstrap/relogin.
        source=self.zone.reference(self.actor,lambda row:self.record({**row,'event':'private_db_source_resolved',
            'mode':request['mode'],'caseId':request['caseId']}))
        credential=source.resolve(actor_ref=self.actor,forbidden_roots=[])
        before=self.zone.metadata();nonce=secrets.token_hex(16);began=time.monotonic()
        ready={'status':'ready','nonce':nonce}
        if request['mode']=='control':ready['password']=credential['password']
        send(client,ready);ready.clear();decoded=receive(client)
        if (set(decoded)!={'nonce','decoderExit','decodedBase64','controlFiles'} or decoded['nonce']!=nonce
                or type(decoded['decoderExit']) is not int or decoded['decoderExit']!=0):
            raise Blocked('private_db_decoder_incomplete')
        try:raw=base64.b64decode(decoded['decodedBase64'],validate=True)
        except Exception:raise Blocked('private_db_decoder_encoding_invalid') from None
        if len(raw)>MAX_DECODED:raise Blocked('private_db_decoder_budget')
        leak=False
        try:
            if request['mode']=='control':
                files=validate_control_files(decoded['controlFiles'])
                audit=audit_private_control(raw,credential['password'])
            else:
                if decoded['controlFiles'] is not None:raise Blocked('private_db_session_control_mismatch')
                files=None;audit=audit_database(CanaryAuditor([*self.canaries(),credential['password']]),raw)
        except SecretLeak:
            leak=True;audit={'canaryLeakDetected':True,'sourceValuesIncluded':False}
        credential.clear();raw=b''
        if self.zone.metadata()!=before or self.current_case()!=request['caseId']:
            raise Blocked('private_db_source_or_case_drift')
        send(client,{'status':'audited','leakDetected':leak})
        cleanup=receive(client,4096)
        if (set(cleanup)!={'nonce','controlZoneRemoved','removedControlFiles'} or cleanup['nonce']!=nonce
                or cleanup['controlZoneRemoved'] is not True or type(cleanup['removedControlFiles']) is not int
                or cleanup['removedControlFiles']!=(len(files['files']) if files else 0)):
            raise Blocked('private_db_control_cleanup_unconfirmed')
        receipt={'contract':CONTRACT,'status':'pass' if not leak else 'leak','mode':request['mode'],
            'runId':self.run_id,'planHash':self.plan_hash,'actorRef':self.actor,'caseId':request['caseId'],
            'nonce':nonce,'peer':identity,'sourceMetadata':before,'audit':audit,'controlFiles':files,
            'cleanup':cleanup,'leakDetected':leak,'rawCellsExportedToController':False,
            'sourceValuesIncluded':False,'contentHashesIncluded':False,'startedAtMonotonic':began,
            'completedAtMonotonic':time.monotonic()}
        self.record({'event':'private_db_audited',**receipt});send(client,receipt)
