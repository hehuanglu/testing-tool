"""Read only, narrow Docker/TLS deployment inspector for FE research."""
import json
from pathlib import Path
import ssl
from urllib.parse import urlsplit
from .runtime import docker
from .fe_anonymous_contract import digest,canonical

def inspect(selection):
    sel=selection;b=sel['binding']
    fmt='{"id":{{json .Id}},"image":{{json .Image}},"started":{{json .State.StartedAt}},"running":{{json .State.Running}},"labels":{{json .Config.Labels}},"networks":{{json .NetworkSettings.Networks}},"ports":{{json .NetworkSettings.Ports}},"mounts":{{json .Mounts}}}'
    v=json.loads(docker(['inspect','--format',fmt,b['containerId']]))
    if v['running'] is not True or v['id']!=b['containerId'] or v['image']!=b['imageId'] or v['started']!=b['startedAt']:raise ValueError('FE deployment drift')
    if not any(n['NetworkID']==b['networkId'] and n['IPAddress']==b['address'] for n in v['networks'].values()):raise ValueError('FE network drift')
    labels=v['labels'];project=sel['environment']
    if labels.get('com.docker.compose.project')!=project and labels.get('zpa.controlOwner')!=project:raise ValueError('FE ownership/deployment mismatch')
    files=labels.get('com.docker.compose.project.config_files','').split(',')
    if sel.get('composeFiles')!=[{'path':f,'sha256':digest(f)} for f in files if f]:raise ValueError('compose order/source drift')
    for row in sel.get('configPins',[]):
        if digest(row['path'])!=row['sha256']:raise ValueError('config/certificate drift')
    cert=sel['certificate']
    if digest(cert['path'])!=cert['sha256']:raise ValueError('certificate file drift')
    import hashlib
    der=ssl.PEM_cert_to_DER_cert(Path(cert['path']).read_text())
    if hashlib.sha256(der).hexdigest()!=cert['derSha256']:raise ValueError('certificate DER mismatch')
    if labels.get('com.docker.compose.project'):
        u=urlsplit(sel['origin']);ports=v['ports'].get(str(sel['targetPort'])+'/tcp',[])
        if not any(x['HostIp']=='127.0.0.1' and int(x['HostPort'])==(u.port or 443) for x in ports):raise ValueError('canonical published port mismatch')
        if str(Path(sel['productLocation']).resolve())!=labels.get('com.docker.compose.project.working_dir'):raise ValueError('product deployment path mismatch')
        if not any(m['Source']==cert['path'] and not m['RW'] for m in v['mounts']):raise ValueError('public cert mount provenance')
    return {'binding':b,'origin':sel['origin'],'composeFiles':sel['composeFiles'],'certificateSha256':cert['sha256'],'configPins':sel.get('configPins',[])}
