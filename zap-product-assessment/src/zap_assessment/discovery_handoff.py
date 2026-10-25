"""Derived PM report; native artifacts remain unchanged and private."""
from collections import Counter
import html
import json
from pathlib import Path
import re
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
from .research import digest,write_json,verify_manifest


def clean(value):
    if value is None:return None
    v=html.unescape(re.sub('<[^>]+>',' ',str(value)))
    v=re.sub(r'(?i)(\bauthorization\s*[:=]\s*["\']?Bearer\s+)[^\s"\'<>]+',r'\1[private]',v)
    v=re.sub(r'eyJ[\w-]+\.eyJ[\w-]+\.[\w-]+','[private-token]',v)
    # Assignment syntax and word boundaries preserve case IDs such as
    # issueAccessToken:CUSTOMER and prose such as "password validation".
    names=r'(?:password|accessToken|refreshToken|token|cookie|authorization|secret|api[-_]?key)'
    v=re.sub(r'(?i)(["\']\b'+names+r'["\']\s*:\s*)(["\'])(.*?)\2',r'\1"[private]"',v)
    v=re.sub(r'(?i)(\b'+names+r'\s*=\s*)[^\s,}&<]+',r'\1[private]',v)
    v=re.sub(r'(?im)(^\s*(?:cookie|set-cookie|authorization)\s*:\s*)[^\r\n]+',r'\1[private]',v)
    v=re.sub(r'(?im)^(userValue|passwordValue)\s*=.*$',r'\1=[private]',v)
    return v.strip()


def safe_url(value):
    u=urlsplit(value)
    q=[(k,'[private]' if any(x in k.lower() for x in ('token','password','secret','key')) else v) for k,v in parse_qsl(u.query,keep_blank_values=True)]
    return urlunsplit((u.scheme,u.netloc,u.path,urlencode(q),''))


def normalize(alerts, *, raw_ref, raw_sha):
    groups={};excluded=[]
    for i,a in enumerate(alerts):
        if '/__research_scope_denied__' in urlsplit(a.get('url','')).path:
            excluded.append({'index':i,'ruleId':str(a.get('pluginId')),'reason':'scope guard destination, excluded from app findings'});continue
        key=(str(a.get('pluginId')),a.get('name'),a.get('risk'),a.get('confidence'))
        if key not in groups:
            groups[key]={'findingId':'ZAP-'+str(len(groups)+1).zfill(3),'source':'ZAP','nativeRuleId':key[0],
             'name':clean(a.get('name')),'description':clean(a.get('description')),
             'severity':a.get('risk'),'confidence':a.get('confidence'),
             'impact':{'status':'unverified','description':'Cần tester xác minh tác động; alert của ZAP chưa tự chứng minh khai thác thành công.'},
             'remediation':clean(a.get('solution')),'references':clean(a.get('reference')),
             'retest':'Tái hiện cùng operation/parameter với fixture test và actor thuộc scope, đối chiếu response sau sửa.',
             'expectedBehavior':'Response không chứa dấu hiệu mà rule phát hiện.',
             'observedBehavior':'Dấu hiệu theo bằng chứng native từng instance; cần đọc response để xác minh.',
             'reproduction':'Dùng native method/URL/parameter và payload trong raw report private; không phát lại mutation trên dữ liệu thật.',
             'instances':[],'evidenceRefs':[]}
        g=groups[key]
        g['instances'].append({'nativeAlertId':str(a.get('id')),'url':safe_url(a.get('url','')),
             'method':a.get('method'),'parameter':clean(a.get('param')),'attack':clean(a.get('attack')),
             'evidence':clean(a.get('evidence')),'otherInfo':clean(a.get('other')),'actor':'run actor; identity sampled separately',
             'evidenceRef':f'{raw_ref}#/alerts/{i}'})
        g['evidenceRefs'].append({'path':raw_ref,'jsonPointer':f'/alerts/{i}','sha256':raw_sha,'access':'private-local'})
    result=list(groups.values())
    for g in result:g['instanceCount']=len(g['instances'])
    return result,excluded


def build_handoff(run_root,output):
    root=Path(run_root).resolve();out=Path(output).resolve();out.mkdir(parents=True,exist_ok=True)
    readback=verify_manifest(root)
    def read(n):return json.loads((root/n).read_text())
    run=read('RUN.json');alerts=read('ALERTS.json')['alerts'] if (root/'ALERTS.json').exists() else []
    ref=str(root/'ALERTS.json');groups,excluded=normalize(alerts,raw_ref=ref,raw_sha=digest(ref) if alerts else None)
    result={'schemaVersion':'pm-alerts/1.0','product':read('PRODUCT_DISCOVERY.json')['product'] if (root/'PRODUCT_DISCOVERY.json').exists() else None,
     'run':root.name,'executionStatus':run['executionStatus'],'evidenceStatus':run['evidenceStatus'],
     'securityVerdict':run['securityVerdict'],'cleanupStatus':run['cleanupStatus'],'gateDecision':run['gateDecision'],
     'scope':{'track':'be-authenticated','rules':[40012,40018],'vectors':['query','JSON-body'],'otherTracksExecuted':False},
     'grouping':'native rule/name/risk/confidence; instances are occurrences, not distinct bugs',
     'summary':{'groupsBySeverity':dict(Counter(g['severity'] for g in groups)),'alertGroups':len(groups),'instances':sum(g['instanceCount'] for g in groups),'excludedGuardInstances':len(excluded)},
     'alerts':groups,'excludedGuardObservations':excluded,
     'limitations':['Chưa chứng minh mọi product/track; adapter execution chỉ finalsource test.',
      'Chưa kiểm JWT hết hạn, refresh/revoke, bản product đã sửa hoặc mọi vector.',
      'Impact và khả năng khai thác cần tester xác minh; native reports có thể chứa false positive.',
      'Raw report/history chứa secrets, private local; folder này dẫn tới raw gốc, không tự chứa bản chia sẻ toàn bộ.'],
     'evidenceReadback':readback,'rawReports':[{'path':str(root/('report.'+ext)),'sha256':digest(root/('report.'+ext)),'access':'private-local'} for ext in ['json','html'] if (root/('report.'+ext)).exists()]}
    write_json(out/'ALERTS.json',result)
    write_json(out/'EVIDENCE_INDEX.json',{'findings':[{k:g[k] for k in ['findingId','nativeRuleId','evidenceRefs']} for g in groups],
        'rawEvidenceIndex':{'path':str(root/'EVIDENCE_INDEX.json'),'sha256':digest(root/'EVIDENCE_INDEX.json'),'access':'private-local'},'readback':readback})
    return result
