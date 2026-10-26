import json
import os
import stat
import threading
from pathlib import Path
from .contracts import Blocked,canonical,digest,utcnow

STATES=['REQUESTED','PROFILE_VALIDATED','PLAN_LOCKED','PREFLIGHT_PASSED','RESOURCES_READY','RUNNING','SETTLING','VERIFYING','EVIDENCE_READY','FINALIZED']
class Journal:
    def __init__(self,path,run_id,plan_hash,allow_partial_tail=False):
        self.path=Path(path); self.run_id=run_id; self.plan_hash=plan_hash
        self.allow_partial_tail=allow_partial_tail; self.partial_tail=False; self.mutex=threading.RLock()
        self.events=self.read(); self.state='REQUESTED'; self.emergency=False; self.io_failed=False
        for e in self.events:
            if e['kind']=='state': self.state=e['data']['state']
    def read(self):
        events=[]; prev='0'*64
        if self.path.exists():
            if self.path.is_symlink(): raise Blocked('journal symlink')
            try:
                fd=os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
                with os.fdopen(fd,'rb') as stream:
                    info=os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>64*1024*1024:raise Blocked('journal file type or budget invalid')
                    raw=stream.read(64*1024*1024+1)
                    if len(raw)!=info.st_size:raise Blocked('journal changed during read')
                lines=raw.splitlines(keepends=True)
                if lines and not lines[-1].endswith(b'\n'):
                    if not self.allow_partial_tail:raise Blocked('journal incomplete trailing record')
                    self.partial_tail=True;lines=lines[:-1]
                for line in lines:
                    def unique(pairs):
                        result={}
                        for key,value in pairs:
                            if key in result:raise Blocked('duplicate journal JSON key')
                            result[key]=value
                        return result
                    e=json.loads(line,object_pairs_hook=unique)
                    if not isinstance(e,dict) or set(e)!={'seq','prev','runId','planHash','at','kind','data','hash'} or type(e['seq']) is not int:raise Blocked('journal envelope invalid')
                    h=e.pop('hash')
                    if e['prev']!=prev or digest(e)!=h or e['runId']!=self.run_id or e['planHash']!=self.plan_hash or e['seq']!=len(events): raise Blocked('journal integrity failure')
                    e['hash']=h; events.append(e); prev=h
            except (ValueError,KeyError) as e: raise Blocked('journal integrity failure') from e
        return events
    def append(self,kind,data):
        with self.mutex:
            return self._append(kind,data)
    def _append(self,kind,data):
        if self.io_failed:
            if self.emergency:return None
            raise OSError('journal write previously failed')
        event={'seq':len(self.events),'prev':self.events[-1]['hash'] if self.events else '0'*64,'runId':self.run_id,'planHash':self.plan_hash,'at':utcnow().isoformat(),'kind':kind,'data':data}
        event['hash']=digest(event)
        try:
            fd=os.open(self.path,os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW,0o600)
            from .safety_io import write_all
            try:write_all(fd,canonical(event)+b'\n');os.fsync(fd)
            finally:os.close(fd)
            parent=os.open(self.path.parent,os.O_RDONLY)
            try: os.fsync(parent)
            finally: os.close(parent)
        except OSError:
            self.io_failed=True
            if self.emergency: return None
            raise
        self.events.append(event); return event
    def transition(self,state,recovery=False):
        okay=(self.state in STATES and state in STATES and STATES.index(state)==STATES.index(self.state)+1) or (state=='STOPPING' and self.state not in ('FINALIZED','FINALIZED_WITH_ERROR')) or (self.state=='STOPPING' and state in ('RECOVERING','FINALIZED_WITH_ERROR')) or (self.state=='RECOVERING' and state=='FINALIZED_WITH_ERROR')
        if recovery and self.state=='FINALIZED_WITH_ERROR' and state=='STOPPING': okay=True
        if not okay: raise Blocked('invalid lifecycle transition')
        self.append('state',{'state':state}); self.state=state

class Ownership:
    def __init__(self,path,run_id): self.path=Path(path); self.run_id=run_id
    def acquire(self):
        fd=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as f: json.dump({'runId':self.run_id,'quarantined':False},f); f.flush(); os.fsync(f.fileno())
    def check(self):
        if self.path.is_symlink(): raise Blocked('ownership symlink')
        data=json.loads(self.path.read_text())
        if data['runId']!=self.run_id: raise Blocked('resource belongs to another run')
        return data
    def quarantine(self):
        self.check()
        # Lock persists; no reuse while cancellation is unconfirmed.
        # Keep the original lock on write failure rather than truncate it first.
        from .safety_io import atomic_bytes
        temporary=self.path.with_name(self.path.name+'.quarantine')
        atomic_bytes(temporary,canonical({'runId':self.run_id,'quarantined':True}))
        os.replace(temporary,self.path)
    def release(self,verified_cleanup=False):
        if self.check()['quarantined'] and not verified_cleanup: raise Blocked('quarantined ownership retained')
        self.path.unlink()
