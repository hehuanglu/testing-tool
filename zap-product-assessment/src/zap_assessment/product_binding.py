"""Independent local Docker backend inspector, no FE/proxy dependency or environment reads."""
import datetime as dt
import ipaddress
import json
import re
from .runtime import docker
from .discovery import validate_transport, execution_origin

FORMAT='{"id":{{json .Id}},"image":{{json .Image}},"started":{{json .State.StartedAt}},"running":{{json .State.Running}},"project":{{json (index .Config.Labels "com.docker.compose.project")}},"controlOwner":{{json (index .Config.Labels "zpa.control.owner")}},"networks":{{json .NetworkSettings.Networks}},"ports":{{json .NetworkSettings.Ports}},"exposed":{{json .Config.ExposedPorts}}}'

def inspect_backend(selection, read=None):
    if selection.get('transport')!='docker-http/1.0':raise ValueError('unsupported transport; explicit Docker HTTP backend required; TLS adapter pending')
    read=read or (lambda name:json.loads(docker(['inspect','--format',FORMAT,name])))
    v=read(selection['container']);networks=v['networks'];network=selection['network']
    if not v['running'] or v['project']!=selection['environment'] or network not in networks:raise ValueError('backend ownership/network unavailable')
    n=networks[network];port=int(selection['port'])
    if not 1<=port<=65535 or str(port)+'/tcp' not in (v['exposed'] or {}):raise ValueError('backend port unverified')
    ipaddress.IPv4Address(n['IPAddress'])
    binding={'containerId':v['id'],'imageId':v['image'],'startedAt':v['started'],'networkId':n['NetworkID'],'address':n['IPAddress']}
    if binding!=selection['expectedBinding']:raise ValueError('backend binding drift')
    aliases=[a for a in (n.get('Aliases') or []) if a and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]*',a)]
    scanner=['http://'+host+':'+str(port) for host in dict.fromkeys([n['IPAddress'],*aliases])]
    direct=[]
    for p in (v['ports'] or {}).get(str(port)+'/tcp',[]) or []:
        if p['HostIp']=='127.0.0.1':direct.append('http://127.0.0.1:'+str(int(p['HostPort'])))
    return binding,{'environment':selection['environment'],'targetBinding':binding,'scannerOrigins':scanner,'directOrigins':direct,
                    'observedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'evidence':{'inspector':'docker-backend/1.0','aliases':aliases,'containerId':v['id'],'controlOwner':v.get('controlOwner')}}

def verify_binding(doc, selection, *, require_direct, read=None):
    b,proof=inspect_backend(selection,read)
    # Existing auth/direct reader requires a direct lane. Anonymous reader already permits its absence.
    if require_direct:
        validate_transport(doc,b,proof);execution_origin(doc,'direct')
    else:
        from .anonymous import transport
        transport(doc,b,proof)
    return b,proof
