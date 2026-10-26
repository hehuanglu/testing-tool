"""Credential-reference candidate for an isolated holder, not runtime admission.

Only instantiate in the allowed secret zone. Python object privacy is not process
isolation: the controller must not host this object for product credentials. The
public methods return no credential/token/hash. Existing ActorSession owns epochs,
identity checks, auth-loss latch and producer stop. Platform/sink proof is separate.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import threading
import time
from urllib.parse import urlsplit

from .auth_lifecycle import ActorSession, AuthLost
from .errors import Blocked
from .secret_audit import CanaryAuditor


@dataclass(frozen=True)
class BrokerBinding:
    run_id: str
    plan_hash: str
    actor_ref: str
    subject: str
    role: str | None
    build_ref: str
    origin: str
    expires_at: float

    def __post_init__(self):
        values=(self.run_id,self.actor_ref,self.subject,self.build_ref)
        if (any(not isinstance(v,str) or not v or len(v)>256 or any(ord(c)<32 for c in v) for v in values)
                or (self.role is not None and (not isinstance(self.role,str) or not self.role
                    or len(self.role)>256 or any(ord(c)<32 for c in self.role)))):
            raise Blocked('broker_binding_invalid')
        if not isinstance(self.plan_hash,str) or not re.fullmatch('[0-9a-f]{64}',self.plan_hash):
            raise Blocked('broker_plan_hash_invalid')
        # The holder image is stdlib-only. Match the canonical origin contract
        # without importing the host JSON-schema dependency into the holder.
        try:
            u=urlsplit(self.origin);host=u.hostname
            if (u.scheme not in ('http','https') or not host or u.username or u.password
                    or u.path or u.query or u.fragment or host!=host.lower() or '%' in host
                    or host.endswith('.') or host.encode('idna').decode()!=host
                    or any(c.isspace() or ord(c)<32 for c in self.origin) or '\\' in self.origin):raise ValueError()
            try:
                ip=ipaddress.ip_address(host);host=f'[{ip.compressed}]' if ip.version==6 else str(ip)
            except ValueError:
                if all(c.isdigit() or c=='.' for c in host) or host.startswith('0x'):raise ValueError()
            port=u.port or (443 if u.scheme=='https' else 80)
            expected=u.scheme+'://'+host+(f':{port}' if port!=(443 if u.scheme=='https' else 80) else '')
            if self.origin!=expected:raise ValueError()
        except (ValueError,TypeError,UnicodeError):raise Blocked('broker_origin_invalid') from None
        if type(self.expires_at) not in (int,float) or not 0<self.expires_at<float('inf'):
            raise Blocked('broker_deadline_invalid')


@dataclass(frozen=True,repr=False)
class SourceReference:
    reference_id: str
    path: Path
    actor_ref: str

    def __repr__(self):return '<SourceReference redacted>'

    def resolve(self, *, actor_ref, forbidden_roots):
        """Read one private external source without following any path alias."""
        try:
            path=Path(self.path)
            if (not self.reference_id or not isinstance(self.reference_id,str)
                    or self.actor_ref!=actor_ref or not path.is_absolute()
                    or '..' in path.parts or path!=Path(os.path.abspath(path))):
                raise ValueError()
            for root in forbidden_roots:
                if path.is_relative_to(Path(root).resolve()):raise ValueError()
            fd=os.open(path.anchor,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            try:
                for part in path.parts[1:-1]:
                    child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
                    os.close(fd);fd=child
                child=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
                with os.fdopen(child,'rb') as stream:
                    before=os.fstat(stream.fileno())
                    if (not stat.S_ISREG(before.st_mode) or before.st_nlink!=1
                            or before.st_uid!=os.geteuid() or stat.S_IMODE(before.st_mode)!=0o600
                            or not 1<=before.st_size<=16384):raise ValueError()
                    blob=stream.read(16385);after=os.fstat(stream.fileno())
                    if (len(blob)!=before.st_size or
                            (before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=
                            (after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)):raise ValueError()
            finally:os.close(fd)
            def pairs(items):
                result={}
                for k,v in items:
                    if k in result:raise ValueError()
                    result[k]=v
                return result
            value=json.loads(blob,object_pairs_hook=pairs)
            if (not isinstance(value,dict) or set(value)!={'actorRef','username','password'}
                    or value['actorRef']!=actor_ref
                    or any(not isinstance(value[k],str) or not value[k] or len(value[k])>8192
                           for k in ('username','password'))):raise ValueError()
            return {'username':value['username'],'password':value['password']}
        except Exception:
            raise Blocked('credential_source_unavailable') from None


class _PrivateAudit(CanaryAuditor):
    """Generic comparisons stay inside holder; no public password fingerprints."""
    def __init__(self):
        self.values=[]
        self._pattern=re.compile(rb'(?!)')

    def register(self,value):
        if not isinstance(value,str) or not value or len(value)>8192:
            raise Blocked('credential_value_invalid')
        if value not in self.values:
            if len(self.values)>=256:raise Blocked('credential_inventory_exhausted')
            self.values.append(value)
        forms=set()
        for secret in self.values:
            raw=secret.encode();forms.add(raw)
            forms.update((base64.b64encode(raw),base64.b64encode(raw).rstrip(b'='),
                          base64.urlsafe_b64encode(raw),base64.urlsafe_b64encode(raw).rstrip(b'=')))
        self._pattern=re.compile(b'|'.join(re.escape(s) for s in sorted(forms,key=len,reverse=True)))

    def forget(self):
        self.values.clear();self._pattern=re.compile(rb'(?!)')


@dataclass(frozen=True,repr=False)
class GeneratedReference:
    """Trusted holder-local synthetic source, distinct from a private file ref.

    Not constructible by plan deserialization. The owned fixture installs the
    resolver in code; no secret value crosses the controller boundary.
    """
    reference_id: str
    actor_ref: str
    resolver: object

    def __repr__(self):return '<GeneratedReference redacted>'

    def resolve(self, *, actor_ref, forbidden_roots):
        try:
            if actor_ref!=self.actor_ref or not callable(self.resolver):raise ValueError()
            value=self.resolver()
            if (not isinstance(value,dict) or set(value)!={'username','password'}
                    or any(not isinstance(v,str) or not v or len(v)>8192 for v in value.values())):
                raise ValueError()
            return dict(value)
        except Exception:raise Blocked('credential_source_unavailable') from None


class _PrivateTransport:
    def __init__(self,owner,adapter):self.owner=owner;self.adapter=adapter

    def login(self):
        credential=self.owner._reference.resolve(actor_ref=self.owner._binding.actor_ref,
                                                 forbidden_roots=self.owner._forbidden)
        self.owner._audit.register(credential['password'])
        try:token=self.adapter.login(credential)
        finally:credential.clear()
        self.owner._audit.register(token)
        return token

    def identity(self,token):return self.adapter.identity(token)

    def refresh(self,token):
        value=self.adapter.refresh(token);self.owner._audit.register(value);return value

    def protected(self,token,method,path,body):
        return self.adapter.protected(token,method,path,body)

    def logout(self,token):return self.adapter.logout(token)


class CredentialBroker:
    """One holder-local session per immutable run/actor/build and source slot.

    `check_current` is a trusted runtime prerequisite callback, not data read from
    a self-declared registry. No product entry point is enabled by this primitive.
    Adapter login/transport/identity and record callbacks must run in the same
    secret zone; exception strings and raw target auth responses never escape.
    """
    def __init__(self, *, binding, source, adapter, producer, record, check_current,
                 forbidden_roots, operations, clock=time.time, allow_refresh=False,
                 poll_seconds=5,response_content_type='application/json',response_oracle=None,
                 response_safe=None):
        from .private_source_broker import BrokeredReference
        if (not isinstance(binding,BrokerBinding) or not isinstance(source,(SourceReference,GeneratedReference,BrokeredReference))
                or source.actor_ref!=binding.actor_ref or not callable(check_current)
                or not forbidden_roots or not operations):raise Blocked('broker_contract_invalid')
        if isinstance(source,BrokeredReference) and source.binding!=binding:
            raise Blocked('broker_source_grant_binding_mismatch')
        self._binding=binding;self._reference=source;self._forbidden=tuple(forbidden_roots)
        self._check_current=check_current;self._clock=clock;self._audit=_PrivateAudit()
        self._lock=threading.RLock();self._used=False;self._closed=False;self._destroyed=False
        self._operations=frozenset(operations)
        for method,path in self._operations:
            if method not in ('GET','POST','PUT','PATCH','DELETE','HEAD') or not self._safe_path(path):
                raise Blocked('broker_operation_invalid')
        self._session=ActorSession(actor=binding.actor_ref,subject=binding.subject,role=binding.role,
            build_ref=binding.build_ref,run_id=binding.run_id,plan_hash=binding.plan_hash,
            transport=_PrivateTransport(self,adapter),record=record,producer=producer,
            allow_refresh=allow_refresh,poll_seconds=poll_seconds,
            response_content_type=response_content_type,response_oracle=response_oracle,
            response_safe=lambda response:self._audit.response_safe(response) and
                (response_safe is None or response_safe(response) is True))

    def __repr__(self):return '<CredentialBroker redacted>'
    def __reduce__(self):raise TypeError('credential_broker_not_serializable')

    @staticmethod
    def _safe_path(path):
        if (not isinstance(path,str) or not path.startswith('/') or path.startswith('//')
                or '\\' in path or any(ord(c)<33 for c in path)):return False
        u=urlsplit(path)
        return not(u.scheme or u.netloc or u.fragment or '%' in u.path
                   or '..' in u.path.split('/') or '.' in u.path.split('/'))

    def _require(self,binding):
        if self._closed or binding!=self._binding:raise Blocked('broker_binding_mismatch')
        try:
            if self._clock()>=self._binding.expires_at or self._check_current(self._binding) is not True:
                raise ValueError()
        except Exception:
            self._session.cancel('exception');self._closed=True
            raise Blocked('broker_admission_lost') from None

    def bootstrap(self,binding):
        with self._lock:
            self._require(binding)
            if self._used:raise Blocked('broker_source_already_used')
            self._used=True
            self._session.bootstrap()
            return self._session.snapshot()

    def protected(self,binding,method,path,body=None):
        with self._lock:
            self._require(binding)
            if not self._safe_path(path) or (method,urlsplit(path).path) not in self._operations:
                raise Blocked('broker_operation_outside_scope')
            # Secrets in request content are forbidden on this API. Only the
            # private adapter may inject auth at its pinned final-hop origin.
            try:blob=json.dumps({'path':path,'body':body},ensure_ascii=False).encode()
            except Exception:raise Blocked('broker_request_invalid') from None
            if self._audit.matches(blob):raise Blocked('broker_request_contains_secret')
            return self._session.protected(method,path,body)

    def refresh(self,binding):
        with self._lock:
            self._require(binding);self._session.refresh();return self._session.snapshot()

    def poll(self,binding):
        with self._lock:
            self._require(binding);self._session.poll();return self._session.snapshot()

    def start_monitor(self,binding):
        with self._lock:
            self._require(binding);self._session.start_monitor()

    def logout(self,binding):
        with self._lock:
            self._require(binding);self._session.logout();return self._session.snapshot()

    def cancel(self,reason='cancel'):
        with self._lock:self._session.cancel(reason)

    def snapshot(self):return self._session.snapshot()

    def audit_bytes(self,binding,blob):
        """In-holder bounded comparison. A result is no sink-completeness proof."""
        with self._lock:
            # Cleanup/expiry audits are required after forwarding is latched.
            # This read-only comparison cannot resolve or resume a credential.
            if binding!=self._binding or self._destroyed or not self._used or not self._audit.values:
                raise Blocked('broker_audit_unbound')
            try:return {'matched':bool(self._audit.matches(blob)),'secretValuesIncluded':False}
            except Exception:raise Blocked('broker_audit_unproven') from None

    def close(self):
        with self._lock:
            try:self._session.close()
            finally:self._closed=True
            # Keep private comparison inventory until lifecycle audits finish.
            return self._session.snapshot()

    def destroy(self):
        """Drop Python references only; never claim swap/core zeroization."""
        with self._lock:
            try:self.close()
            finally:self._audit.forget();self._destroyed=True
