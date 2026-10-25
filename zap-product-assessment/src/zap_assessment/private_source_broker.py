"""Isolated source-broker candidate for an existing combined actor reference.

No CLI accepts product secrets. Instantiate the server only inside a verified
secret zone with the original file mounted read-only. It projects one actor over
the existing private AF_UNIX framing, after independent prerequisites. Raw file,
other-actor fields and historical tokens never reach the holder/controller.
This transport does not prove host/VM persistence safety or grant admission.
"""
from dataclasses import asdict, dataclass
import os
from pathlib import Path
import re
import socket
import stat
import threading
import time

from .credential_broker import BrokerBinding, _PrivateAudit
from .errors import Blocked
from .private_db import peer_identity, receive, send, strict_json
from .secret_audit import CanaryAuditor


def source_socket(run_id):
    if not isinstance(run_id,str) or not re.fullmatch('[A-Za-z0-9-]{1,70}',run_id):
        raise Blocked('source_broker_run_invalid')
    return '\0zpa-source-broker-'+run_id


def metadata(value):
    return (value.st_dev,value.st_ino,value.st_uid,value.st_gid,value.st_nlink,
            stat.S_IMODE(value.st_mode),value.st_size,value.st_mtime_ns,value.st_ctime_ns)


@dataclass(frozen=True,repr=False)
class PrivateSourcePin:
    path: Path
    identity: tuple

    def __repr__(self):return '<PrivateSourcePin metadata-only>'

    @classmethod
    def capture(cls,path):
        """Metadata only; does not open/read source values or content hashes."""
        path=Path(path)
        if (not path.is_absolute() or '..' in path.parts or path!=Path(os.path.abspath(path))
                or path.resolve(strict=True)!=path):raise Blocked('source_broker_path_invalid')
        info=path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_nlink!=1
                or stat.S_IMODE(info.st_mode)!=0o600 or not 1<=info.st_size<=16384):
            raise Blocked('source_broker_private_file_invalid')
        return cls(path,metadata(info))

    def read(self,forbidden_roots):
        try:
            if any(self.path.is_relative_to(Path(root).resolve()) for root in forbidden_roots):
                raise ValueError()
            if PrivateSourcePin.capture(self.path)!=self:raise ValueError()
            # Reuse no-follow traversal of every component from filesystem root.
            raw=CanaryAuditor.read_file('/',str(self.path).lstrip('/'))
            if len(raw)>16384 or PrivateSourcePin.capture(self.path)!=self:raise ValueError()
            return strict_json(raw)
        except Exception:raise Blocked('source_broker_source_changed_or_unavailable') from None


@dataclass(frozen=True)
class SourceGrant:
    reference_id: str
    binding: BrokerBinding
    source_actor: str
    peer_uid: int
    peer_gid: int

    def __post_init__(self):
        if (not isinstance(self.reference_id,str) or not re.fullmatch('[0-9a-f]{32}',self.reference_id)
                or not isinstance(self.binding,BrokerBinding) or self.source_actor not in ('A','B')
                or self.binding.actor_ref!=self.source_actor
                or any(type(n) is not int or n<=0 or n==1000 for n in (self.peer_uid,self.peer_gid))):
            raise Blocked('source_broker_grant_invalid')


class PrivateSourceBroker:
    def __init__(self, *, run_id, grants, source_pin, source_run, source_origin,
                 expected_subjects, check_current, record, forbidden_roots, clock=time.time):
        if (not isinstance(source_pin,PrivateSourcePin) or not grants or not forbidden_roots
                or not callable(check_current) or not callable(record)
                or set(expected_subjects)!={'A','B'} or expected_subjects['A']==expected_subjects['B']):
            raise Blocked('source_broker_contract_invalid')
        self.address=source_socket(run_id);self.run_id=run_id;self.grants={};self.used=set()
        for grant in grants:
            if (not isinstance(grant,SourceGrant) or grant.binding.run_id!=run_id
                    or grant.binding.subject!=str(expected_subjects[grant.source_actor])
                    or grant.reference_id in self.grants):raise Blocked('source_broker_grant_binding')
            self.grants[grant.reference_id]=grant
        self.pin=source_pin;self.source_run=source_run;self.source_origin=source_origin
        self.expected_subjects=dict(expected_subjects);self.check_current=check_current;self.record=record
        self.forbidden_roots=tuple(forbidden_roots);self.clock=clock;self.lock=threading.RLock()
        self.audit=_PrivateAudit();self.source_reads=0;self.listener=None;self.closed=threading.Event()

    def __repr__(self):return '<PrivateSourceBroker private>'

    def _project(self,grant):
        self.source_reads+=1;value=self.pin.read(self.forbidden_roots)
        if (not isinstance(value,dict) or set(value)!={'runId','origin','actors'}
                or value['runId']!=self.source_run or value['origin']!=self.source_origin
                or not isinstance(value['actors'],dict) or set(value['actors'])!={'A','B'}):
            raise Blocked('source_broker_source_provenance_invalid')
        for actor,row in value['actors'].items():
            if (not isinstance(row,dict) or set(row)!={'email','password','fullName','userId','registrationToken'}
                    or type(row['userId']) is not int or str(row['userId'])!=str(self.expected_subjects[actor])
                    or any(not isinstance(row[k],str) or not 1<=len(row[k])<=8192
                           for k in ('email','password','fullName','registrationToken'))):
                raise Blocked('source_broker_actor_source_invalid')
            # Track every secret read, including unused historical tokens and
            # the nonselected actor. No hash/fingerprint is exported.
            for key in ('email','password','registrationToken'):self.audit.register(row[key])
        selected=value['actors'][grant.source_actor]
        return {'username':selected['email'],'password':selected['password']}

    def handle(self,client):
        peer=peer_identity(client);request=receive(client,8192)
        grant=self.grants.get(request.get('referenceId'))
        if (grant is None or set(request)!={'op','referenceId','binding'} or request['op']!='resolve'
                or request['binding']!=asdict(grant.binding)):
            send(client,{'status':'denied','reasonCode':'binding'});return
        if peer!={'uid':grant.peer_uid,'gid':grant.peer_gid}:
            send(client,{'status':'denied','reasonCode':'peer'});return
        with self.lock:
            if grant.reference_id in self.used:
                send(client,{'status':'denied','reasonCode':'no_replay'});return
            # Consume before prerequisites/I/O/send: uncertain ACK is never a
            # second source read or automatic login retry.
            self.used.add(grant.reference_id)
            try:
                self.record({'event':'source_grant_reserved','referenceId':grant.reference_id,
                    'runId':grant.binding.run_id,'planHash':grant.binding.plan_hash,'actorRef':grant.binding.actor_ref})
                if self.clock()>=grant.binding.expires_at or self.check_current(grant.binding) is not True:
                    raise Blocked('source_broker_prerequisite_lost')
                credential=self._project(grant)
                if self.clock()>=grant.binding.expires_at or self.check_current(grant.binding) is not True:
                    raise Blocked('source_broker_prerequisite_lost')
                self.record({'event':'source_grant_delivery_attempt','referenceId':grant.reference_id,
                             'actorRef':grant.binding.actor_ref,'sourceValuesIncluded':False})
                send(client,{'status':'resolved','referenceId':grant.reference_id,**credential})
                credential.clear()
            except Exception:
                # No source/frame/transport exception text can leave this zone.
                send(client,{'status':'denied','reasonCode':'prerequisite_or_source'})

    def start(self):
        self.listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.listener.bind(self.address);self.listener.listen(4)
        def serve():
            while not self.closed.is_set():
                try:client,_=self.listener.accept()
                except OSError:return
                with client:
                    client.settimeout(8)
                    try:self.handle(client)
                    except Exception:
                        try:send(client,{'status':'denied','reasonCode':'private_channel'})
                        except Exception:pass
        self.thread=threading.Thread(target=serve,daemon=True,name='private-source-broker');self.thread.start()

    def close(self):
        self.closed.set()
        if self.listener:
            try:self.listener.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            self.listener.close();self.thread.join(2)
            if self.thread.is_alive():raise Blocked('source_broker_stop_unconfirmed')
        self.audit.forget()  # Reference drop only, not swap/dump zeroization.


@dataclass(frozen=True,repr=False)
class BrokeredReference:
    reference_id: str
    actor_ref: str
    binding: BrokerBinding
    server_uid: int
    server_gid: int

    def __post_init__(self):
        if (not isinstance(self.reference_id,str) or not re.fullmatch('[0-9a-f]{32}',self.reference_id)
                or not isinstance(self.binding,BrokerBinding) or self.actor_ref!=self.binding.actor_ref
                or any(type(n) is not int or n<=0 or n==1000 for n in (self.server_uid,self.server_gid))):
            raise Blocked('brokered_reference_contract_invalid')

    def __repr__(self):return '<BrokeredReference redacted>'

    def resolve(self, *, actor_ref, forbidden_roots):
        try:
            if actor_ref!=self.actor_ref or actor_ref!=self.binding.actor_ref:raise ValueError()
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as channel:
                channel.settimeout(8);channel.connect(source_socket(self.binding.run_id))
                # Authenticate both ends before sending even the opaque grant.
                # An attacker can pre-bind an abstract socket name in this netns.
                if peer_identity(channel)!={'uid':self.server_uid,'gid':self.server_gid}:raise ValueError()
                send(channel,{'op':'resolve','referenceId':self.reference_id,'binding':asdict(self.binding)})
                result=receive(channel,32768)
            if (set(result)!={'status','referenceId','username','password'} or result['status']!='resolved'
                    or result['referenceId']!=self.reference_id
                    or any(not isinstance(result[k],str) or not 1<=len(result[k])<=8192 for k in ('username','password'))):
                raise ValueError()
            return {'username':result['username'],'password':result['password']}
        except Exception:raise Blocked('brokered_reference_unavailable_no_replay') from None
