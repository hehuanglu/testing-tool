"""Offline, product-independent joins and response policy observations from raw exchanges."""
import hashlib,re
from urllib.parse import urlsplit

def wire_key(message,origin):
    line=message.get('requestHeader','').splitlines()[0].split(' ',2)
    if len(line)!=3:raise ValueError('malformed native request')
    method,url=line[:2]
    if url.startswith('/'):url=origin+url
    status=re.match(r'HTTP/\S+ (\d{3})(?: |\r|\n|$)',message.get('responseHeader',''))
    return (method,url,hashlib.sha256(message.get('requestBody','').encode()).hexdigest(),int(status[1]) if status else None)

def correlate(plan,records,messages):
    origin=plan['selection']['origin'];lookup={}
    for message in messages:lookup.setdefault(wire_key(message,origin),[]).append(message)
    rows=[]
    for row in records:
        if not row.get('forwarded'):continue
        candidates=lookup.get((row['method'],row['url'],row['requestBodySha256'],row['status']),[])
        ids=[str(m['id']) for m in candidates if hashlib.sha256(m.get('responseBody','').encode()).hexdigest()==row['responseBodySha256']]
        exact_body=bool(ids)
        if not ids:
            ids=[str(m['id']) for m in candidates if re.search(r'(?im)^content-type: (?:image/|font/|application/(?:octet-stream|font|vnd\.ms-fontobject))',m.get('responseHeader',''))]
        if not ids:raise ValueError('app exchange missing from native history: sequence '+str(row['sequence']))
        if row['reason']!='app' or row['upstreamCertificateSha256']!=plan['selection']['certificate']['derSha256'] or row['upstreamSNI']!=urlsplit(origin).hostname:raise ValueError('unverified app exchange')
        rows.append({'sequence':row['sequence'],'caseId':row.get('caseId'),'campaignId':row.get('campaignId'),'nativeMessageIds':ids,'method':row['method'],'url':row['url'],'requestBodySha256':row['requestBodySha256'],'responseBodySha256':row['responseBodySha256'],'nativeResponseBodyHashVerified':exact_body,'status':row['status'],'equivalentNativeCopies':len(ids)})
    return {'matchPolicy':'exact method + canonical URL + request-body SHA256 + status + text response SHA256; binary assets may use metadata because native API decodes bytes; equal copies retained','forwarded':len(rows),'exchanges':rows}

def response_policies(messages):
    names=('content-security-policy','cache-control','strict-transport-security','x-content-type-options','x-frame-options','referrer-policy','permissions-policy','access-control-allow-origin','access-control-allow-credentials')
    groups={}
    for message in messages:
        header=message.get('responseHeader','');headers={}
        for line in header.splitlines()[1:]:
            k,sep,v=line.partition(':')
            if sep:headers.setdefault(k.lower(),[]).append(v.strip())
        if 'x-zpa-guard' in headers or header.startswith('HTTP/1.0 0'):continue
        content=','.join(headers.get('content-type',[])).split(';')[0];status=re.match(r'HTTP/\S+ (\d{3})',header)
        if not status:continue
        category=('error-response' if int(status[1])>=400 else 'document' if content=='text/html' else 'api-json' if content=='application/json' else 'asset')
        values={k:headers.get(k,[]) for k in names};cookies=[v.split('=',1)[0] for v in headers.get('set-cookie',[])]
        import json
        key=(category,content,int(status[1]),json.dumps(values,sort_keys=True),tuple(cookies))
        g=groups.setdefault(key,{'category':category,'contentType':content,'status':int(status[1]),'headers':values,'setCookieNames':cookies,'nativeMessageIds':[]})
        g['nativeMessageIds'].append(str(message['id']))
    return {'source':'native-zap-response-headers','interpretation':'observed policies grouped by document/assets/API/error; CORS/CSRF exploitability and DOM execution are separate claims','groups':list(groups.values())}

def evaluate_predicate(state,predicate):
    """Re-evaluate expected UI from captured facts, without trusting worker pass booleans."""
    kind=predicate['kind'];element=next((e for e in state.get('elements',[]) if e['selector']==predicate.get('selector')),None)
    if kind=='urlPath':return urlsplit(state['url']).path==predicate['value']
    if kind=='storagePresent':return predicate['key'] in state['sessionKeys' if predicate.get('area')=='session' else 'storageKeys']
    if kind=='ready':return state.get('ready')=='complete'
    if kind=='valueLength':return bool(element and element.get('valueLength')==predicate['value'])
    if kind=='absent':return bool(element and not element['exists'])
    if kind=='exists':return bool(element and element['exists'])
    if kind=='text':return bool(element and element['exists'] and predicate['value'] in element['text'])
    if kind=='invalid':return bool(element and element.get('valid') is False)
    if kind=='disabled':return bool(element and element.get('disabled'))
    if kind=='attribute':return bool(element and element.get('attributes',{}).get(predicate['attribute'])==predicate['value'])
    raise ValueError('unsupported captured predicate')


def mutation_obligations(records):
    """A sent intent without complete response remains unknown after hard loss."""
    return [{'sequence':r['sequence'],'caseId':r.get('caseId'),'campaignId':r.get('campaignId'),
             'requestBodySha256':r.get('requestBodySha256'),'method':r['method'],'url':r['url'],
             'reconciliationRequired':True,'retentionRequired':True,'mutationReplay':False}
            for r in records if r.get('transportState') in ('sent','response-headers','unknown') and r['method'] not in ('GET','HEAD','OPTIONS')]


def active_delivery(plan,records,messages,baselines):
    """Derive actual rule/vector delivery from app exchanges and native wire bytes."""
    import json
    joined=correlate(plan,records,messages);byseq={r['sequence']:r for r in joined['exchanges']};native={str(m['id']):m for m in messages};result={}
    for camp in plan['campaigns']:
        baseline=baselines[camp['id']];method,url,bodyhash,status=wire_key(baseline,plan['selection']['origin'])
        if method!=camp['method'] or urlsplit(url).path!=camp['path']:raise ValueError('baseline target mismatch')
        base=json.loads(baseline['requestBody'])
        if set(base)!=set(camp['fixtureBody']):raise ValueError('baseline fields mismatch')
        counts={str(r):0 for r in camp['ruleIds']};vectors={v:0 for v in camp['vectorFields']};sequences=[]
        for row in records:
            if row.get('campaignId')!=camp['id'] or not row.get('forwarded') or not row.get('ruleId'):continue
            rule=str(row['ruleId'])
            if row['method']!=camp['method'] or urlsplit(row['url']).path!=camp['path'] or rule not in counts:raise ValueError('unplanned native delivery')
            candidates=[native[i] for i in byseq[row['sequence']]['nativeMessageIds']]
            candidates=[m for m in candidates if re.search(r'(?im)^X-ZAP-Scan-ID:\s*'+re.escape(rule)+r'\s*$',m['requestHeader'])]
            if not candidates:raise ValueError('native rule header mismatch')
            payload=json.loads(candidates[0]['requestBody']);changed={k for k in set(base)|set(payload) if base.get(k)!=payload.get(k)}
            if not changed:continue  # Native rules also send unchanged control requests.
            if not changed<=set(camp['vectorFields']):raise ValueError('payload changed sibling field')
            counts[rule]+=1;sequences.append(row['sequence'])
            for v in changed:vectors[v]+=1
        app_attempts=sum(r.get('campaignId')==camp['id'] and (r.get('forwarded') is True or r.get('transportState') in ('sent','response-headers','unknown')) for r in records)
        if camp.get('maxAppRequests') is not None and app_attempts>camp['maxAppRequests']:raise ValueError('campaign app request cap exceeded')
        if len(sequences)>camp['maxDelivered']:raise ValueError('delivery cap exceeded')
        result[camp['id']]={'deliveredByRule':counts,'deliveredByVector':vectors,'sequences':sequences,'deliveryProven':all(counts.values()) and all(vectors.values())}
    return result


def transport_accounting(records):
    unknown={'sent','response-headers','unknown'}
    return {'attempted':len(records),'forwarded':sum(r.get('forwarded') is True for r in records),
            'blocked':sum(r.get('forwarded') is False and r.get('reason')!='transport-error' for r in records),
            'notSent':sum(r.get('forwarded') is False for r in records),
            'sent':sum(r.get('forwarded') is True or r.get('transportState') in unknown for r in records),
            'unknown':sum(r.get('transportState') in unknown for r in records)}
