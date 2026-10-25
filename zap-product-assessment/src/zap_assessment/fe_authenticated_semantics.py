"""Readback-only semantic derivation. Never invokes worker assertions or producer evaluation."""
import hashlib,json
from pathlib import Path
from urllib.parse import urlsplit,parse_qsl
from .fe_authenticated_transport import valid_owned_id
from .fe_authenticated_auth import pointer
from .fe_authenticated_contract import digest

def sha(blob):return hashlib.sha256(blob).hexdigest()
def request(message,origin):
    header=message.get('requestHeader','');line=header.splitlines()[0].split() if header else []
    if len(line)!=3:return None
    method,url,_=line
    if url.startswith('/'):url=origin+url
    headers={k.strip().lower():v.strip() for line in header.splitlines()[1:] if ':' in line for k,v in [line.split(':',1)]}
    status=message.get('responseHeader','').splitlines()[0].split() if message.get('responseHeader') else []
    return {'method':method,'url':url,'headers':headers,'body':message.get('requestBody',''),'response':message.get('responseBody',''),'status':int(status[1]) if len(status)>1 else None,'id':str(message.get('id'))}

def ui_predicate(p,state):
    kind=p['kind'];elements={e['selector']:e for e in state.get('elements',[])};e=elements.get(p.get('selector'),{});value=p.get('value')
    if kind=='urlPath':return urlsplit(state.get('url','')).path==value
    if kind in ('storagePresent','storageAbsent'):
        exists=p['key'] in state.get('sessionKeys' if p.get('area')=='session' else 'storageKeys',[])
        return exists if kind=='storagePresent' else not exists
    if kind=='ready':return state.get('ready')=='complete'
    if kind=='exists':return e.get('exists') is True
    if kind=='absent':return e.get('exists') is False
    if kind=='text':return e.get('exists') and str(value) in e.get('text','')
    if kind=='textAbsent':return e.get('exists') and not e.get('textTruncated',False) and str(value) not in e.get('text','')
    if kind=='invalid':return e.get('valid') is False
    if kind=='disabled':return e.get('disabled') is True
    if kind=='attribute':return e.get('attributes',{}).get(p['attribute'])==value
    if kind=='valueLength':return e.get('valueLength')==value
    facts=next((x for x in state.get('selectorFacts',[]) if x['selector']==p.get('selector')),{})
    if kind=='imageLoaded':return facts.get('imageLoaded') is True
    if kind=='checked':return facts.get('checked')==value
    if kind=='count':return facts.get('count')==value
    return False

def derive(root,p,records,messages):
    root=Path(root);errors=[];missing=[];origin=p['selection']['origin'];auth=p['journeys']['auth'];actors=json.loads((root/'ACTOR_BINDINGS.json').read_bytes());bindings=json.loads((root/'config/actor-bindings.json').read_bytes())
    initial_path=root/'private/ACTORS_INITIAL.json'
    if not initial_path.exists():
        missing.append('initial independent actor receipt absent');initial={}
    else:initial=json.loads(initial_path.read_bytes())
    fixtures={}
    for ref,a in initial.items():
        if a['role']!=auth['identity'].get('roleByActor',{}).get(ref,auth['identity']['expectedRole']):errors.append('actor role outside reviewed responsibility '+ref)
        fixtures[ref]={k:v for k,v in a.get('fixtures',{}).items() if not k.endswith('Id')}
        if any(actors.get(ref,{}).get(k)!=a[k] or bindings.get(ref,{}).get(k)!=a[k] for k in ('subject','role','provenance')):errors.append('actor receipt/final binding drift '+ref)
        authoritative=[]
        for proof in a['provenance']:
            source=Path(proof['path'])
            if not source.is_file() or digest(source)!=proof['sha256']:errors.append('actor provenance drift '+ref);continue
            try:
                doc=json.loads(source.read_bytes())
                if doc.get('schemaVersion')=='owned-fe-actor/1.0':
                    if any(doc.get(k)!=a[k] for k in ('subject','role','username')) or doc['selectionSha256']!=__import__('zap_assessment.fe_authenticated_contract',fromlist=['canonical']).canonical(p['selection']):raise ValueError('actor receipt')
                    registered=json.loads((source.parent/doc['registration']).read_bytes())['body']['data']['user'];protected_doc=json.loads((source.parent/doc['protectedIdentity']).read_bytes())['body']
                    if registered['id']!=a['subject'] or registered['email']!=a['username'] or str(pointer(protected_doc,auth['identity']['subjectPointer']))!=str(a['subject']):raise ValueError('actor raw identity')
                    if a['fixtures'].get('marker')!=doc['marker']:raise ValueError('actor marker')
                    authoritative.append(proof)
                elif a['username'] in doc and doc[a['username']]['subject']==a['subject'] and doc[a['username']]['role']==a['role']:authoritative.append(proof)
            except (ValueError,KeyError,TypeError):errors.append('actor provenance content mismatch '+ref)
        if not authoritative:errors.append('independent actor authority absent '+ref)
    if p['journeys']['recipe']=='finalsource-fe-auth/1.0':
        from .fe_authenticated_evidence_finalsource import setup_bindings
        try:
            for ref,values in setup_bindings(root,initial,p).items():fixtures[ref].update(values)
        except (ValueError,KeyError,TypeError) as e:errors.append('setup ownership proof: '+str(e))
    parsed=[x for m in messages if (x:=request(m,origin))]
    pairs={};protected=[];identity=[];asset_dispositions=[]
    for r in records:
        if r.get('transportState') in ('intent','sent','response-headers','unknown') or r.get('forwarded') is None:
            missing.append('unknown transport requires reconciliation '+str(r.get('sequence')));continue
        if not r.get('forwarded'):continue
        u=urlsplit(r['url'])
        if (u.scheme,u.netloc)!=(urlsplit(origin).scheme,urlsplit(origin).netloc):errors.append('origin drift')
        if r.get('upstreamCertificateSha256')!=p['selection']['certificate']['derSha256'] or r.get('upstreamSNI')!=u.hostname or r.get('upstreamHost')!=u.netloc:errors.append('app TLS binding absent')
        matches=[m for m in parsed if m['method']==r['method'] and m['url']==r['url'] and sha(m['body'].encode())==r['requestBodySha256'] and m['status']==r['status'] and sha(m['response'].encode())==r['responseBodySha256']]
        if r.get('credentialFingerprint') and not (r['method']=='POST' and u.path==auth['loginPath']):
            matches=[m for m in matches if sha(m['headers'].get('authorization','').encode())==r['credentialFingerprint']]
        if not matches:
            asset=next((a for a in p['selection'].get('publicAssets',[]) if a['path']==u.path and a['sha256']==r.get('responseBodySha256')),None)
            if asset and r['method']=='GET' and not u.query and not r.get('credentialFingerprint') and r.get('status')==200 and u.path.endswith(('.png','.svg','.jpg','.jpeg','.webp','.ico')):
                asset_dispositions.append({'sequence':r['sequence'],'path':u.path,'sha256':asset['sha256'],'nativeHistory':'omitted by native history','evidence':'exact deployed public asset hash + broker verified TLS','claim':'static asset arrival only; no native passive/active coverage claimed'});continue
            errors.append('native/broker request-response mismatch '+str(r['sequence']));continue
        m=matches[0];pairs[r['sequence']]=m
        if str(r.get('ruleId') or '')!=str(m['headers'].get('x-zap-scan-id') or ''):errors.append('native/broker rule attribution mismatch')
        if m['headers'].get('authorization'):
            fp=sha(m['headers']['authorization'].encode())
            if fp!=r.get('credentialFingerprint'):errors.append('credential fingerprint mismatch')
            actor=actors.get(r.get('actorRef'))
            if not actor:errors.append('actor binding absent');continue
            if m['method']=='GET' and u.path==auth['identity']['path']:
                try:
                    observed=str(pointer(json.loads(m['response']),auth['identity']['subjectPointer']))
                    role=str(pointer(json.loads(m['response']),auth['identity']['rolePointer'])) if auth['identity'].get('rolePointer') else actor['role']
                except (ValueError,TypeError,KeyError,IndexError):observed=None;role=None
                if observed!=str(actor['subject']) or role!=actor['role']:errors.append('protected principal/role mismatch')
                else:identity.append({'sequence':r['sequence'],'actorRef':r['actorRef'],'slot':r['authSlot'],'group':r['sessionGroup'],'epoch':r['authEpoch'],'at':r['at'],'fingerprint':fp,'messageId':m['id']})
            protected.append((r,m))
    for r,m in protected:
        if urlsplit(r['url']).path==auth['identity']['path']:continue
        probes=[i for i in identity if (i['actorRef'],i['slot'],i['group'],i['epoch'],i['fingerprint'])==(r.get('actorRef'),r.get('authSlot'),r.get('sessionGroup'),r.get('authEpoch'),r.get('credentialFingerprint')) and 0<=r['at']-i['at']<=p['limits']['identityMaxGapSeconds']]
        if not probes:errors.append('protected traffic without independently verified current identity '+str(r['sequence']))
    # Bootstrap fingerprints must originate in the same actor's wire response, not arbitrary supplied bearer.
    for i in identity:
        boot=[]
        for r in records:
            m=pairs.get(r.get('sequence'))
            if not m or r.get('actorRef')!=i['actorRef'] or r.get('authSlot')!=i['slot'] or r.get('sessionGroup')!=i['group'] or r.get('authEpoch')!=i['epoch'] or r.get('at',0)>i['at'] or m['method']!='POST' or urlsplit(m['url']).path!=auth['loginPath']:continue
            try:
                credential=pointer(json.loads(m['response']),auth['tokenPointer']);username=json.loads(m['body'])[auth['usernameField']]
                if username==bindings[i['actorRef']]['username'] and sha(('Bearer '+credential).encode())==i['fingerprint']:boot.append(m['id'])
            except (ValueError,TypeError,KeyError,IndexError):pass
        if not boot:errors.append('identity without admitted actor bootstrap')
    def wire_response(j,step,response,capture):
        if response.get('status')!=200:return False
        try:expected_url=origin+step['path'].format_map(fixtures[j['actorRef']])
        except KeyError:return False
        if response.get('url')!=expected_url:return False
        return any(r.get('caseId')==j['id'] and r.get('actorRef')==j['actorRef'] and r.get('sessionGroup')==j['sessionGroup'] and r.get('authSlot')=='browser' and r.get('identityPhase')=='authenticated' and capture['startedAt']<=r.get('at',0)<=capture['endedAt'] and r.get('method')=='GET' and r.get('url')==expected_url and r.get('status')==200 and r.get('sequence') in pairs and json.loads(pairs[r['sequence']]['response'])==response['body'] for r in records)
    # Derive campaign result bindings from the last successful wire response, never final fixtures.
    for campaign in p['campaigns']:
        candidates=[r for r in records if r.get('sequence') in pairs and r.get('forwarded') and r.get('campaignId')==campaign['id'] and r.get('actorRef')==campaign['actorRef'] and r['method']==campaign['method'] and r.get('status') in (200,201)]
        if campaign.get('resultBindings') and candidates:
            last=max(candidates,key=lambda r:r['sequence'])
            for key,path in campaign['resultBindings'].items():fixtures[campaign['actorRef']][key]=pointer(json.loads(pairs[last['sequence']]['response']),path)
    journey_rows=[];post_states=[];owned_ids=[];findings=[]
    for j in p['journeys']['journeys']:
        path=root/'browser'/j['sessionGroup']/(j['id']+'.json')
        if not path.exists():missing.append('journey '+j['id']);continue
        value=json.loads(path.read_bytes());steps=value['steps'];incomplete=value.get('outcome')=='failed'
        state=value.get('failureState',{}) if incomplete else value.get('finalState',{})
        if value.get('outcome')=='not-run':missing.append('journey dependency '+j['id']);continue
        reasons=[]
        expected_actions=[x['action'] for x in j['steps']]
        if [x['action'] for x in steps]!=(expected_actions[:len(steps)] if incomplete else expected_actions):reasons.append('missing UI action')
        if incomplete:
            if not value.get('errorType') or not value.get('endedAt') or value['endedAt']<value.get('startedAt',0):reasons.append('failed journey receipt absent')
            missing.append('failed journey '+j['id']+' after '+str(len(steps))+' captured actions; inspect failure evidence and transport reconciliation')
        if state.get('secure') is False or not incomplete and not state.get('secure'):reasons.append('secure UI absent')
        elif incomplete and state.get('secure') is not True:missing.append('failed journey UI snapshot '+j['id'])
        for index,step in enumerate(steps):
            spec=j['steps'][index] if index<len(j['steps']) else {}
            expected_spec=__import__('copy').deepcopy(spec)
            if expected_spec.get('predicate',{}).get('fixtureField'):
                expected_spec['predicate']['value']=fixtures.get(j['actorRef'],{}).get(expected_spec['predicate']['fixtureField'])
            if step.get('actionSpec')!=expected_spec:reasons.append('reviewed UI action specification mismatch')
            if expected_spec.get('predicate') and not ui_predicate(expected_spec['predicate'],step.get('state',{})):reasons.append('step predicate unsupported by captured DOM')
            if spec.get('action') in ('readback','post-state'):
                response=step.get('readback') if spec['action']=='readback' else step.get('postState',{}).get('response')
                if not response or not wire_response(j,spec,response,step):reasons.append('readback lacks protected native/broker response')
                else:
                    try:
                        if spec['action']=='readback':
                            values=pointer(response['body'],spec['pointer']);values=values if isinstance(values,list) else [values]
                            if spec.get('matchPointer'):values=[v for v in values if pointer(v,spec['matchPointer'])==fixtures[j['actorRef']][spec['matchFixture']]]
                            if len(values)!=1:raise ValueError('ambiguous owned readback')
                            extracted=pointer(values[0],spec['valuePointer'])
                            if not valid_owned_id(extracted,spec.get('idFormat','integer')):raise ValueError('invalid owned ID')
                            old=fixtures[j['actorRef']].get(spec['fixtureField'])
                            if old is not None and old!=extracted:raise ValueError('owned ID drift')
                            fixtures[j['actorRef']][spec['fixtureField']]=extracted;owned_ids.append({'journeyId':j['id'],'actorRef':j['actorRef'],'field':spec['fixtureField'],'id':extracted})
                        else:
                            expected=fixtures[j['actorRef']][spec['expectedFixture']] if spec.get('expectedFixture') else spec['expectedValue']
                            if step.get('postState',{}).get('expected')!=expected or step.get('postState',{}).get('pointer')!=spec['pointer']:reasons.append('captured post-state oracle differs from reviewed contract')
                            if pointer(response['body'],spec['pointer'])!=expected:findings.append({'journeyId':j['id'],'source':'browser-and-protected-readback','kind':'persistence-mismatch','pointer':spec['pointer'],'expected':expected,'actual':pointer(response['body'],spec['pointer']),'evidence':str(path)})
                            post_states.append({'journeyId':j['id'],'stepIndex':index,'pointer':spec['pointer'],'derived':expected})
                    except (ValueError,KeyError,IndexError,TypeError) as e:reasons.append('independent owned oracle '+str(e))
            image=Path(step['screenshot']['path'])
            if image.is_relative_to('/browser'):image=root/'browser'/image.relative_to('/browser')
            if not image.is_relative_to(root) or not image.exists() or sha(image.read_bytes())!=step['screenshot']['sha256']:reasons.append('DOM/screenshot evidence absent')
        predicates=[x['predicate'] for x in value.get('assertions',[])]
        if len(predicates)>len(j['expectedUi']) or not incomplete and len(predicates)!=len(j['expectedUi']):reasons.append('UI oracle absent')
        for expected,actual in zip(j['expectedUi'],predicates):
            compare=dict(actual);compare.pop('value',None);expected_compare=dict(expected);expected_compare.pop('value',None)
            if compare!=expected_compare or not expected.get('fixtureField') and actual.get('value')!=expected.get('value'):reasons.append('UI predicate changed')
            if expected.get('fixtureField') and actual.get('value')!=fixtures.get(j['actorRef'],{}).get(expected['fixtureField']):reasons.append('UI fixture predicate differs from owned actor binding')
            if not ui_predicate(actual,state):
                if any(a.get('predicate')==actual and a.get('passed') is False for a in value.get('assertions',[])):findings.append({'journeyId':j['id'],'source':'browser-DOM','kind':'UI-assertion-mismatch','predicate':actual,'evidence':str(path)})
                else:reasons.append('UI predicate unsupported by captured DOM')
        rows=[r for r in records if r.get('caseId')==j['id']]
        for n in j['expectedNetwork']:
            try:expected_path=n['path'].format_map(fixtures.get(j['actorRef'],{}))
            except KeyError:reasons.append('network ownership fixture absent');continue
            found=[r for r in rows if r.get('method')==n['method'] and urlsplit(r.get('url','')).path==expected_path]
            if n.get('absent') and found:reasons.append('unexpected UI request')
            if not n.get('absent') and not any(r.get('forwarded') and r.get('status') in n['statuses'] and r.get('sequence') in pairs for r in found):
                if incomplete:missing.append('failed journey network evidence '+j['id']+' '+n['method']+' '+expected_path)
                else:reasons.append('UI network evidence absent')
        if reasons:errors.extend(j['id']+': '+x for x in reasons)
        journey_rows.append({'id':j['id'],'reasons':reasons,'evidence':str(path),'completed':not reasons and not incomplete})
    delivery=[]
    from .fe_authenticated_campaigns import materialize
    materialized=[]
    for template in p['campaigns']:
        try:c=materialize(template,fixtures.get(template['actorRef'],{}))
        except (KeyError,ValueError):missing.append('campaign owned fixture '+template['id']);continue
        materialized.append(c);delivered=[]
        for r in records:
            m=pairs.get(r.get('sequence'))
            if not m or r.get('authSlot')!='native' or r.get('identityPhase')!='authenticated' or r.get('actorRef')!=c['actorRef'] or m['method']!=c['method'] or urlsplit(m['url']).path!=c['path'] or r.get('campaignId')!=c['id'] or m['status'] in (401,403) or not m['headers'].get('authorization'):continue
            rule=m['headers'].get('x-zap-scan-id')
            if rule not in [str(x) for x in c['ruleIds']]:continue
            if c['vector']=='query':
                entries=parse_qsl(urlsplit(m['url']).query,keep_blank_values=True)
                if len(entries)!=len({k for k,v in entries}):errors.append('duplicate query key delivered');continue
                baseline=c.get('query',{});candidate=dict(entries)
            else:
                baseline=c.get('body',{})
                try:candidate=json.loads(m['body'])
                except ValueError:continue
            if set(candidate)!=set(baseline):continue
            changed={k for k in candidate if str(candidate[k])!=str(baseline[k])}
            if changed and changed<=set(c['vectorFields']):delivered.append({'sequence':r['sequence'],'nativeMessageId':m['id'],'ruleId':rule,'changedFields':sorted(changed),'actorRef':r['actorRef']})
        if len(delivered)>c['maxDelivered']:errors.append('campaign changed-payload budget exceeded '+c['id'])
        arrivals=[r for r in records if r.get('campaignId')==c['id'] and r.get('forwarded') and r.get('method')==c['method'] and urlsplit(r['url']).path==c['path']]
        if len(arrivals)>c['maxAppRequests']:errors.append('campaign app budget exceeded '+c['id'])
        if not delivered:missing.append('changed protected native payload '+c['id'])
        baselines=[m for r,m in protected if r.get('actorRef')==c['actorRef'] and r.get('authSlot')=='browser' and r.get('caseId') in c['journeyIds'] and m['method']==c['method'] and urlsplit(m['url']).path==c['path'] and not m['headers'].get('x-zap-scan-id') and m['status'] in (200,201) and m['headers'].get('authorization') and (dict(parse_qsl(urlsplit(m['url']).query))=={k:str(v) for k,v in c.get('query',{}).items()} if c['vector']=='query' else m['body']==json.dumps(c.get('body',{}),separators=(',',':')))]
        if not baselines:missing.append('valid protected UI/native baseline '+c['id'])
        ops=json.loads((root/'OPERATIONS.json').read_bytes())
        op=next((o for o in ops if o.get('campaignId')==c['id']),None)
        if not op:missing.append('native operation attribution '+c['id'])
        if op:
            browser_probes=[i for i in identity if i['actorRef']==c['actorRef'] and i['slot']=='browser' and 0<=op['startedAt']-i['at']<=p['limits']['identityMaxGapSeconds']]
            native_probes=[i for i in identity if i['actorRef']==c['actorRef'] and i['slot']=='native' and 0<=op['startedAt']-i['at']<=p['limits']['identityMaxGapSeconds']]
            if not browser_probes or not native_probes:errors.append('browser/native continuity before active '+c['id'])
        for oracle in c['postState']:
            if oracle['kind']=='ui-reload':
                path=root/'browser'/next(j['sessionGroup'] for j in p['journeys']['journeys'] if j['id']==oracle['ref'])/(oracle['ref']+'.json')
                if not path.exists() or not any(s['action']=='reload' and (not op or s['startedAt']>=op['endedAt']) for s in json.loads(path.read_bytes())['steps']):missing.append('campaign UI reload after terminal '+c['id'])
            elif oracle['kind']=='owned-readback' and not any(s['journeyId']==oracle['ref'] for s in post_states):missing.append('campaign persistence readback '+c['id'])
        delivery.append({'campaignId':c['id'],'delivered':delivered})
    recorded=root/'MATERIALIZED_CAMPAIGNS.json'
    if recorded.exists():
        actual=json.loads(recorded.read_bytes());ids=[c['id'] for c in actual]
        if len(ids)!=len(set(ids)) or not set(ids)<={c['id'] for c in materialized} or actual!=[c for c in materialized if c['id'] in ids]:errors.append('materialized campaign drift')
    # Mutation post-state must be supported by a subsequent real reload, not an API-only success flag.
    for j in p['journeys']['journeys']:
        if j['effect']!='mutation':continue
        path=root/'browser'/j['sessionGroup']/(j['id']+'.json')
        if not path.exists():continue
        value=json.loads(path.read_bytes())
        if not j['postState'] or not any(x['action']=='reload' for x in value['steps']):missing.append('mutation persistence/reload '+j['id'])
        for oracle in j['postState']:
            if oracle['kind']=='owned-readback' and not any(o['journeyId']==j['id'] for o in post_states):missing.append('independent owned post-state oracle '+j['id'])
            elif oracle['kind'] not in ('ui-reload','owned-readback'):missing.append('unsupported mutation post-state oracle '+j['id'])
    for ref,a in actors.items():
        for key,value in a.get('fixtures',{}).items():
            if key not in fixtures.get(ref,{}) or fixtures[ref][key]!=value:errors.append('producer fixture lacks independently derived binding '+ref+':'+key)
    for r in p['journeys']['responsibilities']:
        if r['disposition']=='gap':missing.append('responsibility gap '+r['id'])
        elif r['disposition']=='planned' and not r['journeyIds']:missing.append('unassigned responsibility '+r['id'])
    return {'semanticsVersion':'fe-auth-independent/1.0','errors':errors,'missing':missing,'identity':identity,'journeys':journey_rows,'delivery':delivery,'ownedIds':owned_ids,'postStates':post_states,'browserObservations':findings,'assetDispositions':asset_dispositions,'workloadCompletion':'complete' if not errors and not missing else 'partial'}
