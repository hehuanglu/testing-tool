"""Small stdlib-only durable primitives, also executable in isolated fault volumes."""
import hashlib
import json
import os
from pathlib import Path
import stat
import threading
import uuid


def _bytes(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def write_all(fd,data,offset=None):
    view=memoryview(data);position=0
    while position<len(view):
        n=os.write(fd,view[position:]) if offset is None else os.pwrite(fd,view[position:],offset+position)
        if n<=0:raise OSError('non-progressing write')
        position+=n


def atomic_bytes(path,data):
    """No-clobber publication only after full bytes, hash and file fsync readback."""
    path=Path(path)
    if path.is_symlink() or path.parent.is_symlink():raise OSError('symlink destination')
    temporary=path.parent/('.pending-'+uuid.uuid4().hex)
    fd=os.open(temporary,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        write_all(fd,data);os.fsync(fd);os.lseek(fd,0,os.SEEK_SET)
        observed=bytearray()
        while len(observed)<len(data):
            chunk=os.read(fd,min(65536,len(data)-len(observed)))
            if not chunk:break
            observed.extend(chunk)
        if bytes(observed)!=data or os.fstat(fd).st_size!=len(data):raise OSError('write readback mismatch')
        # link is atomic and fails if final name exists; rename could overwrite it.
        os.link(temporary,path,follow_symlinks=False)
        parent=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(parent)
        finally:os.close(parent)
    finally:
        os.close(fd)
        try:temporary.unlink()
        except OSError:pass


class ReservedStop:
    """Two preallocated, checksum-framed slots; no new inode needed at ENOSPC.

    Each slot is an independent record. A torn newest slot leaves the preceding
    valid frame. Neither frame is a complete bundle manifest or security verdict.
    """
    SLOT=32768
    def __init__(self,path,run_id,plan_hash):
        self.path=Path(path);self.run_id=run_id;self.plan_hash=plan_hash;self.seq=-1;self.slot_offset=0;self.lock=threading.Lock()
        self.fd=os.open(self.path,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            write_all(self.fd,b' '*self.SLOT*2);os.fsync(self.fd)
            self.record({'state':'reserved-before-runtime','cleanupStatus':'pending','stopUnconfirmed':True})
        except BaseException:self.close();raise
    def record(self,data):
        with self.lock:
            body={'runId':self.run_id,'planHash':self.plan_hash,'seq':self.seq+1,'data':data}
            payload=_bytes(body);frame=_bytes({'record':body,'sha256':hashlib.sha256(payload).hexdigest()})
            if len(frame)>self.SLOT:raise ValueError('reserved record too large')
            self.slot_offset=(body['seq']%2)*self.SLOT
            write_all(self.fd,frame.ljust(self.SLOT,b' '),self.slot_offset);os.fsync(self.fd);self.seq=body['seq']
    @classmethod
    def read(cls,path):
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode) or os.fstat(fd).st_size!=2*cls.SLOT:raise ValueError('invalid reserve file')
            frames=[]
            for offset in (0,cls.SLOT):
                try:
                    f=json.loads(os.pread(fd,cls.SLOT,offset));r=f['record']
                    if hashlib.sha256(_bytes(r)).hexdigest()==f['sha256'] and type(r['seq']) is int:frames.append(r)
                except (ValueError,KeyError,TypeError):pass
            if not frames:raise ValueError('no intact reserved frame')
            identities={(r['runId'],r['planHash']) for r in frames}
            if len(identities)!=1:raise ValueError('reserve identity mismatch')
            return max(frames,key=lambda r:r['seq'])
        finally:os.close(fd)
    def close(self):
        if getattr(self,'fd',None) is not None:os.close(self.fd);self.fd=None
