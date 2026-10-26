"""Actual owned-scanner sink readers. Decoded values remain in the auditor pipe.

Readers do not grant G3. Unsupported file/database formats and inaccessible
containers return blocked rather than silently reducing the sink denominator.
"""
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import os
import select
import time
import stat
import tarfile
import zipfile

from .errors import Blocked,SecretLeak

MAX=8*1024*1024
ARCHIVE_MAX=512*1024*1024


class AuditStream:
    """Constant-memory archive input with a byte budget and a wall deadline."""
    def __init__(self,stream):
        self.stream=stream;self.count=0;self.hash=hashlib.sha256();self.deadline=time.monotonic()+60
    def read(self,size):
        size=min(size,65536)
        if hasattr(self.stream,'fileno'):
            try:fd=self.stream.fileno()
            except io.UnsupportedOperation:fd=None
        else:fd=None
        if fd is not None:
            left=self.deadline-time.monotonic()
            if left<=0 or not select.select([fd],[],[],left)[0]:raise Blocked('container archive read deadline')
            data=os.read(fd,size)
        else:data=self.stream.read(size)
        self.count+=len(data);self.hash.update(data)
        if self.count>ARCHIVE_MAX:raise Blocked('container archive byte budget')
        return data


def decoded_views(blob):
    """Declared pipeline transforms: raw, gzip, ZIP. No arbitrary decompression."""
    if len(blob)>MAX:raise Blocked('secret decoder byte budget')
    if blob.startswith(b'SQLite format 3\x00'):
        raise Blocked('SQLite checkpoint/WAL decoder unproven')
    yield blob
    if blob.startswith(b'\x1f\x8b'):
        with gzip.GzipFile(fileobj=io.BytesIO(blob)) as stream:
            data=stream.read(MAX+1)
            if len(data)>MAX:raise Blocked('gzip expansion budget')
            yield data
    elif blob.startswith(b'PK\x03\x04'):
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            if len(archive.infolist())>2000:raise Blocked('zip member budget')
            total=0
            for member in archive.infolist():
                if member.is_dir():continue
                if member.flag_bits&1:raise Blocked('encrypted archive unproven')
                total+=member.file_size
                if member.file_size>MAX or total>64*1024*1024:raise Blocked('zip expansion budget')
                yield archive.read(member)


def check_views(auditor,blob):
    count=0
    try:
        for view in decoded_views(blob):
            count+=1
            if auditor.matches(view):raise SecretLeak('canary detected in decoded sink')
    except (OSError,ValueError,zipfile.BadZipFile) as exc:
        if isinstance(exc,Blocked):raise
        raise Blocked('secret decoder failed') from None
    return count


def audit_tar(auditor,raw,*,precredential=False,prior_index=None):
    if isinstance(raw,bytes):
        if len(raw)>ARCHIVE_MAX:raise Blocked('container archive byte budget')
        raw=io.BytesIO(raw)
    stream_input=AuditStream(raw)
    files=views=0;total=0;paths=[];unchanged=0
    prior={r['path']:r for r in prior_index or []}
    try:
        with tarfile.open(fileobj=stream_input,mode='r|') as archive:
            for member in archive:
                check_views(auditor,json.dumps({'path':member.name,'link':member.linkname}).encode())
                if member.isdir():continue
                if not member.isfile():raise Blocked('container alias/special file decoder unproven')
                files+=1;total+=member.size
                if files>10000 or total>ARCHIVE_MAX:raise Blocked('container audit inventory budget')
                stream=archive.extractfile(member)
                if member.size>MAX:
                    # Libraries extracted from the pinned image before secret
                    # delivery cannot acquire a secret while byte-identical.
                    # This is an exact prior-byte proof, never an extension skip.
                    h=hashlib.sha256();read=0;tail=b''
                    while True:
                        chunk=stream.read(1024*1024)
                        if not chunk:break
                        read+=len(chunk);h.update(chunk)
                        if auditor.matches(tail+chunk):raise SecretLeak('canary detected in large sink')
                        tail=chunk[-4096:]
                    item={'path':member.name,'bytes':read,'sha256':h.hexdigest(),
                          'precredentialBaseline':True}
                    if read!=member.size:raise Blocked('large sink read incomplete')
                    if not precredential:
                        if prior.get(member.name)!=item:raise Blocked('changed large sink decoder unproven')
                        unchanged+=1
                    paths.append(item)
                else:
                    blob=stream.read(MAX+1)
                    if len(blob)!=member.size:raise Blocked('container audit file truncated')
                    item={'path':member.name,'bytes':member.size,'sha256':hashlib.sha256(blob).hexdigest(),
                          'precredentialBaseline':True}
                    if precredential:
                        if auditor.matches(blob):raise SecretLeak('canary detected before credential delivery')
                    elif prior.get(member.name)==item:
                        unchanged+=1
                    else:
                        views+=check_views(auditor,blob)
                        item.pop('precredentialBaseline')
                    paths.append(item)
    except (tarfile.TarError,OSError):raise Blocked('container archive inaccessible') from None
    while stream_input.read(65536):pass
    return {'files':files,'decodedViews':views,'bytes':total,'paths':paths,
            'precredentialSnapshot':precredential,'unchangedPrecredentialFiles':unchanged,
            'archiveSha256':stream_input.hash.hexdigest(),'archiveBytes':stream_input.count,'canaryMatches':0}


def audit_database(auditor,raw,*,expect_canary=False):
    tables=[];cells=bytes_seen=0;matched=0;complete=None;matched_families=set()
    text_types={1,12,-1,-9,-15,-16,2005,2011}
    binary_types={-2,-3,-4,2004}
    for line in raw.splitlines():
        try:value=json.loads(line)
        except ValueError:raise Blocked('database decoder output malformed') from None
        if not isinstance(value,dict) or complete is not None:
            raise Blocked('database record after terminal or invalid envelope')
        kind=value.get('kind')
        if kind=='table':
            name=value.get('name')
            if (not isinstance(name,str) or not name or len(name)>256
                    or name in tables):raise Blocked('database table inventory invalid')
            tables.append(name)
        elif kind=='cell':
            if (value.get('table') not in tables or not isinstance(value.get('column'),str)
                    or not value['column'] or type(value.get('sqlType')) is not int
                    or value['sqlType'] in (2000,2002,2003,2009,1111)):
                raise Blocked('database cell binding or SQL decoder invalid')
            try:data=base64.b64decode(value['base64'],validate=True)
            except (ValueError,TypeError,KeyError):raise Blocked('database cell encoding invalid') from None
            cells+=1;bytes_seen+=len(data)
            if bytes_seen>128*1024*1024:raise Blocked('decoded database budget')
            # A compressed value matching in several views is still one cell;
            # two TEXT matches cannot stand in for the BINARY reader control.
            cell_match=any(auditor.matches(view) for view in decoded_views(data))
            matched+=cell_match
            if cell_match:
                if value['sqlType'] in text_types:matched_families.add('text')
                if value['sqlType'] in binary_types:matched_families.add('binary')
        elif kind=='complete':
            if any(type(value.get(k)) is not int or value[k]<0 for k in ('tables','rows','cells','decodedBytes')):
                raise Blocked('database terminal counts invalid')
            complete=value
        else:raise Blocked('database decoder blocked or unsupported')
    if (complete is None or complete['cells']!=cells or complete['decodedBytes']!=bytes_seen
            or complete['tables']!=len(tables) or not tables):raise Blocked('database decoder incomplete')
    if expect_canary:
        if matched_families!={'text','binary'}:raise Blocked('JDBC text and binary positive control missed')
    elif matched:raise SecretLeak('canary detected in saved-session database')
    return {'tables':tables,'rows':complete['rows'],'decodedCells':cells,'decodedBytes':bytes_seen,
            'canaryMatches':matched,'seededControl':expect_canary,'decoder':'HSQL JDBC all PUBLIC table typed cells'}


def audit_tree(auditor,source,*,precredential=False,prior_index=None):
    """Read the exact host backing of an owned bind; no Docker archive lock.

    The container's verified Mounts mapping supplies source, never target input.
    Values are read without following aliases and only metadata is returned.
    """
    source=Path(source);prior={r['path']:r for r in prior_index or []};paths=[];views=unchanged=total=0
    if source.is_symlink():raise Blocked('bind source alias unproven')
    files=sorted(source.rglob('*')) if source.is_dir() else [source]
    for path in files:
        info=path.lstat()
        if stat.S_ISDIR(info.st_mode):continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise Blocked('bind alias/special file decoder unproven')
        if len(paths)>=10000 or total+info.st_size>ARCHIVE_MAX:raise Blocked('bind audit inventory budget')
        name=source.name+'/'+str(path.relative_to(source)) if path!=source else source.name
        data=[];h=hashlib.sha256();tail=b'';read=0
        possible_prior=prior.get(name,{}).get('precredentialBaseline') is True
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,'rb') as stream:
            while chunk:=stream.read(65536):
                h.update(chunk);read+=len(chunk)
                if not possible_prior and auditor.matches(tail+chunk):raise SecretLeak('canary detected in owned bind sink')
                tail=chunk[-4096:]
                if info.st_size<=MAX:data.append(chunk)
            after=os.fstat(stream.fileno())
        if (read!=info.st_size or (info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)!=
                (after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)):
            raise Blocked('bind changed during secret readback')
        item={'path':name,'bytes':read,'sha256':h.hexdigest(),'precredentialBaseline':True}
        if not precredential:
            if prior.get(name)==item:unchanged+=1
            elif read>MAX:
                if possible_prior:
                    with path.open('rb') as stream:
                        tail=b''
                        while chunk:=stream.read(65536):
                            if auditor.matches(tail+chunk):raise SecretLeak('canary detected in changed large bind sink')
                            tail=chunk[-4096:]
                raise Blocked('changed large bind decoder unproven')
            else:
                views+=check_views(auditor,b''.join(data));item.pop('precredentialBaseline')
        total+=read;paths.append(item)
    return {'files':len(paths),'decodedViews':views,'bytes':total,'paths':paths,
            'precredentialSnapshot':precredential,'unchangedPrecredentialFiles':unchanged,
            'archiveSha256':hashlib.sha256(json.dumps(paths,sort_keys=True).encode()).hexdigest(),
            'archiveBytes':total,'reader':'verified bind backing files, not Docker archive','canaryMatches':0}


def artifact_digest(root,relative):
    """Streaming integrity readback for large retained library/database artifacts."""
    parts=Path(relative).parts
    if not parts or Path(relative).is_absolute() or '..' in parts or str(Path(relative))!=relative:
        raise Blocked('unsafe scanner artifact path')
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=child
        child=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
        with os.fdopen(child,'rb') as stream:
            before=os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>ARCHIVE_MAX:
                raise Blocked('scanner artifact type/size unsupported')
            h=hashlib.sha256();read=0
            while chunk:=stream.read(65536):h.update(chunk);read+=len(chunk)
            after=os.fstat(stream.fileno())
            if (read!=before.st_size or (before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=
                    (after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)):
                raise Blocked('scanner artifact changed during readback')
            return h.hexdigest()
    finally:os.close(fd)


def container_sinks(runtime,name,*,precredential=False):
    info=runtime.check_owner(name)
    metadata={k:info.get(k) for k in ('Path','Args')}
    metadata.update(cmd=info['Config'].get('Cmd'),entrypoint=info['Config'].get('Entrypoint'),
                    environment=info['Config'].get('Env'),mounts=info.get('Mounts'),ulimits=info['HostConfig'].get('Ulimits'))
    receipt=runtime.audit_blob('process-argv-env-mounts',json.dumps(metadata).encode())
    # Only hashes/limits escape. Never serialize the inspected environment.
    limits=metadata['ulimits'] or []
    if not any(r['Name']=='core' and r['Hard']==0 and r['Soft']==0 for r in limits):
        raise Blocked('core dump bound unproven')
    proc=subprocess.run(['docker','logs',name],capture_output=True,timeout=10)
    if proc.returncode:raise Blocked('owned logs inaccessible')
    logs=runtime.audit_blob('owned-process-logs',proc.stdout+proc.stderr)
    result={'containerId':info['Id'],'imageId':info['Image'],'metadata':receipt,
            'logs':logs,'coreDumpLimit':0,'archives':[]}
    # Mutable files are read again after stop. No raw archive is written to disk.
    if name==runtime.names[2]:roots=['/home/zap/.ZAP','/home/zap/.cache','/tmp']
    elif name==runtime.names[3]:roots=['/tmp']
    else:roots=[]  # UID-private source tmpfs uses separate live metadata/access proof.
    # Docker creates ancestors of bind destinations even on a read-only root.
    # Audit the exact mounted roots, not their parent or unrelated host content.
    for mount in info.get('Mounts',[]):
        if mount.get('Type')=='bind':roots.append(mount['Destination'])
    if not hasattr(runtime,'precredential_files'):runtime.precredential_files={}
    proc=subprocess.run(['docker','diff',name],capture_output=True,timeout=10)
    if proc.returncode:raise Blocked('owned filesystem diff inaccessible')
    runtime.audit_blob('filesystem-diff-paths',proc.stdout)
    diff=proc.stdout.decode().splitlines()
    for row in diff:
        if len(row)<3 or row[0] not in 'ACD':raise Blocked('filesystem diff record unproven')
        path=row[2:]
        if row[0]=='D':continue
        if name==runtime.names[1] and path.startswith('/tmp/'):
            # Guard root is read-only; only its UID-private tmpfs socket is
            # excluded from tar (sockets have no stored credential bytes).
            if path=='/tmp/w5-control.sock':continue
            if (getattr(runtime,'private_source_mode',False) and getattr(runtime,'source_zone_verified',False)
                    and path in ('/tmp/w5-private-source','/tmp/w5-private-source/A.json','/tmp/w5-private-source/B.json')):
                # This is the locked allowed source zone, never a forbidden sink.
                # Read its actual tmpfs/UID/file identity through source-status;
                # do not export source bytes through Docker cp to the host.
                continue
        if any(path==root or path.startswith(root+'/') or root.startswith(path+'/') for root in roots):continue
        roots.append(path)
    roots=[r for r in roots if not any(r!=other and r.startswith(other+'/') for other in roots)]
    result['filesystemDiffSha256']=hashlib.sha256(proc.stdout).hexdigest()
    if name==runtime.names[1] and info['HostConfig'].get('ReadonlyRootfs') is not True:
        raise Blocked('guard writable root unproven')
    for root in roots:
        key=(name,root)
        if not hasattr(runtime,'sink_stages'):runtime.sink_stages=[]
        stage={'containerId':info['Id'],'root':root,'precredential':precredential,'complete':False}
        runtime.sink_stages.append(stage)
        mounts=[m for m in info.get('Mounts',[]) if m.get('Type')=='bind' and m['Destination']==root]
        if len(mounts)==1:
            peer=Path(mounts[0]['Source'])
            allowed=peer.resolve().is_relative_to(runtime.root) or peer.resolve()==Path(__file__).resolve().parents[1]
            if not allowed:raise Blocked('bind source outside owned runtime/source scope')
            audit=audit_tree(runtime.auditor,peer,precredential=precredential,prior_index=runtime.precredential_files.get(key))
        else:
            proc=subprocess.Popen(['docker','cp',name+':'+root,'-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                audit=audit_tar(runtime.auditor,proc.stdout,precredential=precredential,
                                prior_index=runtime.precredential_files.get(key))
                proc.wait(timeout=5)
                if proc.returncode:raise Blocked('container sink archive inaccessible')
            finally:
                if proc.poll() is None:proc.kill();proc.wait(timeout=5)
                proc.stdout.close();proc.stderr.close()
        stage.update(complete=True,archiveBytes=audit['archiveBytes'],files=audit['files'])
        if precredential:runtime.precredential_files[key]=audit['paths']
        if not hasattr(runtime,'host_audited'):runtime.host_audited={}
        for mount in info.get('Mounts',[]):
            if mount.get('Type')!='bind' or mount['Destination']!=root:continue
            prefix=Path(mount['Source']).name+'/'
            for item in audit['paths']:
                if item['path'].startswith(prefix):
                    peer=Path(mount['Source'])/item['path'][len(prefix):]
                    runtime.host_audited[str(peer)]=item
        result['archives'].append({'root':root,**audit})
    return result
