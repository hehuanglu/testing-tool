"""Registered Docker HTTP binding contracts. No target provisioning or authority minting."""
import ipaddress
import json
from urllib.parse import urlsplit
from .contracts import Blocked,digest,origin

def guard_values(p,w,a):
    u=urlsplit(p['attackOrigins'][0])
    return {'origin':p['attackOrigins'][0],'address':p['binding']['address'],'port':u.port or 80,'allowedPaths':p['allowedPaths'],'maxRate':w['maxRate'],'validUntil':a['validUntil'],'protocol':'http-only','credentials':'reject','redirects':'revalidate'}

def validate_binding(p,w,a):
    if p['adapter']!='docker-existing-http-v1' or a['schemaVersion']!='1.1':raise Blocked('unregistered binding/authority version')
    u=urlsplit(p['attackOrigins'][0]);origin(p['attackOrigins'][0],True)
    if u.scheme!='http':raise Blocked('HTTPS existing-target binding unsupported; TLS checks cannot be bypassed')
    try:ip=ipaddress.ip_address(u.hostname)
    except ValueError as e:raise Blocked('DNS binding unsupported; pinned literal IPv4 required') from e
    if ip.version!=4 or ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast:raise Blocked('existing binding requires exact Docker IPv4')
    if str(ip)!=p['binding']['address'] or a['resolvedAddresses']!=[str(ip)]:raise Blocked('binding address mismatch')
    if p['targetBuildRef']!=p['binding']['imageId'] or digest(p['binding'])!=a['bindingHash']:raise Blocked('unapproved build/binding')
    if a['owner']!=p['owner']:raise Blocked('authority owner mismatch')
    if a['retentionDays']!=p['retentionDays'] or not set(p['allowedPaths'])<=set(a['allowedPaths']):raise Blocked('authority coverage/retention mismatch')
    required={x['path'] for x in p['expectedOperations']}|set(p['publicSeeds'])|{p['healthPath'],p['crawlPath']}
    if not required<=set(p['allowedPaths']) or any('//' in x for x in p['allowedPaths']):raise Blocked('path not authorized by binding')
    if p['dependencyOrigins'] or w['active'] or w['authMode']!='none' or a['destructiveLevel']!='read-only':raise Blocked('unsupported existing target capability')
    for value in [p['owner'],p['environment']['identity'],a['owner'],a['issuer'],a['approvalRef'],a['environmentEvidenceRef']]:
        if value.upper().startswith(('UNRESOLVED','UNVERIFIED','PENDING')):raise Blocked('owner/environment authority unresolved')
    if p['environment']['kind']=='synthetic':
        if a['issuer']!='independent-target-harness' or not a['approvalRef'].startswith('user-authorized-binding-synthetic:'):raise Blocked('independent synthetic authority required')

def assertions_match(body,assertions):
    try:data=json.loads(body) if isinstance(body,(str,bytes)) else body
    except (ValueError,UnicodeError) as e:raise Blocked('health is not JSON') from e
    observed=[]
    for assertion in assertions:
        value=data
        try:
            for segment in assertion['pointer'].split('/')[1:]:value=value[segment]
        except (KeyError,TypeError,IndexError) as e:raise Blocked('health assertion missing') from e
        expected=assertion['equals']
        if type(value) is not type(expected) or value!=expected:raise Blocked('health identity assertion mismatch')
        observed.append({'pointer':assertion['pointer'],'equals':expected,'matched':True})
    return observed
