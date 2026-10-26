"""Run-owned tmpfs source references for W5 synthetic diagnostics only.

Source bytes are created/read in the holder. Only immutable file metadata leaves
the holder; no password/content hash is exported. This proves a source path, not
platform zeroization or general product credential admission.
"""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import stat
import time

from .credential_broker import SourceReference
from .errors import Blocked
from .safety_io import write_all


def mount_type(path):
    """Read the actual deepest Linux mount covering a controlled source path."""
    try:
        data=Path('/proc/self/mountinfo').read_bytes()
        if len(data)>1024*1024:raise ValueError()
        matches=[]
        for line in data.decode().splitlines():
            left,right=line.split(' - ',1);parts=left.split();where=Path(parts[4])
            if '\\' in str(where):continue  # controlled /tmp path needs no mount escapes
            if path==where or path.is_relative_to(where):matches.append((len(where.parts),right.split()[0]))
        if not matches:raise ValueError()
        return max(matches)[1]
    except Exception:raise Blocked('private_source_mount_unproven') from None


def _stat_record(value):
    return {'inode':value.st_ino,'device':value.st_dev,'bytes':value.st_size,
            'uid':value.st_uid,'gid':value.st_gid,'links':value.st_nlink,
            'mode':stat.S_IMODE(value.st_mode),'mtimeNs':value.st_mtime_ns,'ctimeNs':value.st_ctime_ns}


class TmpfsSourceZone:
    def __init__(self,path, *, run_id,plan_hash):
        self.path=Path(path);self.run_id=run_id;self.plan_hash=plan_hash;self._expected=None
        if (not self.path.is_absolute() or '..' in self.path.parts or not run_id
                or not isinstance(plan_hash,str) or len(plan_hash)!=64
                or any(c not in '0123456789abcdef' for c in plan_hash)):
            raise Blocked('private_source_binding_invalid')

    def __repr__(self):return '<TmpfsSourceZone redacted>'

    def create(self,credentials):
        """Only the holder-owned generator calls this; not a host seed API."""
        try:
            if self._expected is not None or set(credentials)!={'A','B'}:raise ValueError()
            if mount_type(self.path.parent)!='tmpfs':raise ValueError()
            parent=self.path.parent
            if parent.resolve(strict=True)!=parent or parent.is_symlink():raise ValueError()
            parent_info=parent.stat()
            if parent_info.st_uid!=os.geteuid() or stat.S_IMODE(parent_info.st_mode)!=0o700:raise ValueError()
            # Validate both source slots before the first write.
            blobs={}
            for actor,row in credentials.items():
                if (not isinstance(row,dict) or set(row)!={'username','password'}
                        or row['username']!=actor or not isinstance(row['password'],str)
                        or not 12<=len(row['password'])<=8192):raise ValueError()
                raw=json.dumps({'actorRef':actor,**row},separators=(',',':')).encode()
                if len(raw)>16384:raise ValueError()
                blobs[actor]=raw
            self.path.mkdir(mode=0o700)
            for actor in ('A','B'):
                fd=os.open(self.path/(actor+'.json'),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                try:write_all(fd,blobs[actor]);os.fsync(fd)
                finally:os.close(fd)
            fd=os.open(self.path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            try:os.fsync(fd)
            finally:os.close(fd)
            self._expected=self._observe()
            return self.metadata()
        except Exception:raise Blocked('private_source_creation_failed') from None

    def _observe(self):
        try:
            if mount_type(self.path)!='tmpfs' or self.path.resolve(strict=True)!=self.path:
                raise ValueError()
            fd=os.open(self.path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            try:
                zone=os.fstat(fd)
                if zone.st_uid!=os.geteuid() or stat.S_IMODE(zone.st_mode)!=0o700:raise ValueError()
                if set(os.listdir(fd))!={'A.json','B.json'}:raise ValueError()
                rows=[]
                for actor in ('A','B'):
                    value=os.stat(actor+'.json',dir_fd=fd,follow_symlinks=False)
                    if (not stat.S_ISREG(value.st_mode) or value.st_uid!=os.geteuid()
                            or stat.S_IMODE(value.st_mode)!=0o600 or value.st_nlink!=1
                            or not 1<=value.st_size<=16384):raise ValueError()
                    rows.append({'actorRef':actor,'referenceId':'owned-private-file:'+actor,
                                 'relativePath':actor+'.json',**_stat_record(value)})
            finally:os.close(fd)
            return {'schemaVersion':'owned-private-source/1.0','runId':self.run_id,'planHash':self.plan_hash,
                    'sourceKind':'owned-guard-private-file-reference','filesystem':'tmpfs',
                    'zonePath':str(self.path),'zone':_stat_record(zone),'files':rows,
                    'sourceValuesIncluded':False,'contentHashesIncluded':False}
        except Exception:raise Blocked('private_source_metadata_unproven') from None

    def metadata(self):
        if self._expected is None:raise Blocked('private_source_not_created')
        value=self._observe()
        if value!=self._expected:raise Blocked('private_source_identity_changed')
        return value

    def reference(self,actor,record):
        self.metadata()
        if actor not in ('A','B') or not callable(record):raise Blocked('private_source_actor_invalid')
        return TrackedSourceReference('owned-private-file:'+actor,self.path/(actor+'.json'),actor,self,record)


@dataclass(frozen=True,repr=False)
class TrackedSourceReference(SourceReference):
    zone: object
    record: object

    def __repr__(self):return '<TrackedSourceReference redacted>'

    def resolve(self, *, actor_ref,forbidden_roots):
        before=self.zone.metadata()
        value=super().resolve(actor_ref=actor_ref,forbidden_roots=forbidden_roots)
        after=self.zone.metadata()
        if before!=after:raise Blocked('private_source_changed_during_resolve')
        metadata=next(row for row in after['files'] if row['actorRef']==actor_ref)
        self.record({'event':'private_source_resolved','runId':self.zone.run_id,
                     'planHash':self.zone.plan_hash,'sourceKind':after['sourceKind'],
                     'sourceValuesIncluded':False,'contentHashesIncluded':False,'source':metadata,
                     'atMonotonic':time.monotonic()})
        return value
