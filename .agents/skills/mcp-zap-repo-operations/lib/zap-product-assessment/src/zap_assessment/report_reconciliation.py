"""Findings/report semantics above native executors; no scan or export engine."""
from collections import Counter
import hashlib
import re
from urllib.parse import urlsplit

RISKS={'0':'Informational','1':'Low','2':'Medium','3':'High'}
CONFIDENCES={'0':'False Positive','1':'Low','2':'Medium','3':'High','4':'Confirmed'}


def parse_findings_instances(text, session):
    """Honor returned/total counts; a bounded details response is not always full.

    The current guided interface has pluginId/alertName filters but no offset.
    A saturated filtered group stays partial until an actual paging/snapshot
    interface is supplied. No fabricated offset/limit fields are dispatched.
    """
    if not isinstance(session,str) or not session:raise ValueError('session namespace required')
    count=re.search(r'^Alert instances returned: (\d+) of (\d+)$',text,re.M)
    if count is None:
        if text.rstrip().endswith('No alert instances matched the current filter.'):
            return {'session':session,'status':'complete','returned':0,'total':0,'rows':[]}
        raise ValueError('findings instance count missing')
    returned,total=map(int,count.groups());rows=[]
    for block in re.split(r'\n- Alert ID: ',text)[1:]:
        head=re.fullmatch(r'(\d+) \| Plugin ID: (\d+) \| Name: (.*?) \| Risk: (.*?) \| Confidence: (.*)',block.splitlines()[0])
        if not head:raise ValueError('findings instance header invalid')
        row=dict(zip(('id','pluginId','name','risk','confidence'),head.groups()))
        row['session']=session
        for label,key in [('URL','url'),('Param','param'),('Attack','attack'),('Evidence','evidence'),('Message ID','messageId'),('Method','method')]:
            m=re.search(r'^  '+label+r': (.*)$',block,re.M)
            if m:row[key]=m[1]
        if not all(k in row for k in ('url','method','param')):raise ValueError('findings instance fields missing')
        rows.append(row)
    if len(rows)!=returned or returned>total:raise ValueError('findings count mismatch')
    return {'session':session,'status':'complete' if returned==total else 'partial','returned':returned,'total':total,'rows':rows,
            'continuation':None if returned==total else 'Use actual pluginId/alertName filters; if a filtered group still exceeds the interface limit, keep partial. Minimal missing primitive: offset or cursor with stable snapshot.'}


def group_key(row):return (str(row['pluginId']),row['name'],row['risk'])
def key(row):return (row['session'],str(row['id']))
def param(row):return '' if row.get('param') in (None,'','<none>') else row['param']
def evidence(row):return '' if row.get('evidence') in (None,'','<none>') else row['evidence']
def sha(text):return hashlib.sha256(text.encode()).hexdigest()
def semantics(row):
    return (*group_key(row),row.get('method'),row.get('url'),param(row),row.get('confidence'),evidence(row))


def safe_row(row):
    # No wire bodies/headers/attacks/evidence text in shareable comparisons.
    value={k:row.get(k) for k in ('session','id','pluginId','name','risk','confidence','method','url','param','messageId')}
    value['evidenceSha256']=sha(evidence(row))
    return value


def normalize_report(report, session):
    rows=[];groups=[]
    for site in report.get('site',[]):
        for alert in site.get('alerts',[]):
            risk=RISKS.get(str(alert.get('riskcode')),str(alert.get('riskcode')))
            confidence=CONFIDENCES.get(str(alert.get('confidence')),str(alert.get('confidence')))
            items=alert.get('instances',[])
            if not isinstance(items,list):raise ValueError('report instances invalid')
            groups.append({'pluginId':str(alert['pluginid']),'name':alert['name'],'risk':risk,
                           'confidence':confidence,'nativeCount':alert.get('count'),'sampleRows':len(items),
                           'nativeCountEqualsSamples':str(alert.get('count'))==str(len(items)),
                           'systemic':alert.get('systemic'),'site':site.get('@name')})
            for item in items:
                rows.append({'session':session,'id':str(item['id']),'pluginId':str(alert['pluginid']),
                             'name':alert['name'],'risk':risk,'confidence':confidence,
                             'method':item.get('method'),'url':item.get('uri'),'param':item.get('param'),
                             'evidence':item.get('evidence',''),'messageId':item.get('messageId')})
    return rows,groups


def unique_rows(rows):
    unique={}
    for row in rows:
        k=key(row)
        if k in unique and unique[k]!=row:raise ValueError('conflicting instance identity within session')
        unique[k]=row
    return unique


def reconcile_findings_report(snapshot, report):
    session=snapshot['session'];findings=snapshot['rows'];samples,native_groups=normalize_report(report,session)
    f=unique_rows(findings);r=unique_rows(samples)
    missing=f.keys()-r.keys();extra=r.keys()-f.keys();common=f.keys() & r.keys()
    field_differences=[]
    for k in sorted(common):
        fields={n:{'findings':f[k].get(n),'report':r[k].get(n)} for n in ('pluginId','name','risk','confidence','method','url') if f[k].get(n)!=r[k].get(n)}
        if param(f[k])!=param(r[k]):fields['param']={'findings':param(f[k]),'report':param(r[k])}
        if evidence(f[k])!=evidence(r[k]):fields['evidenceSha256']={'findings':sha(evidence(f[k])),'report':sha(evidence(r[k]))}
        if fields:field_differences.append({'session':k[0],'id':k[1],'fields':fields})
    groups=[]
    for k in sorted({group_key(row) for row in findings+samples}):
        fr=[x for x in f.values() if group_key(x)==k];rr=[x for x in r.values() if group_key(x)==k]
        groups.append({'pluginId':k[0],'name':k[1],'severity':k[2],
            'findingsRecordedInstances':len(fr),'reportSampleRows':len(rr),
            'confidenceValues':sorted({x['confidence'] for x in fr}),
            'findingsIds':sorted(x['id'] for x in fr),'reportIds':sorted(x['id'] for x in rr),
            'omittedIds':sorted(x['id'] for x in fr if key(x) in missing),
            'reportOnlyIds':sorted(x['id'] for x in rr if key(x) in extra)})
    equivalents=[]
    for k in sorted(extra):
        equivalents.append({'report':safe_row(r[k]),'sameObservedFieldsDifferentId':[safe_row(x) for x in f.values() if semantics(x)==semantics(r[k])],
                            'identityConclusion':'not-merged; same observed fields do not establish identical alert/message identity'})
    return {'status':'complete' if snapshot['status']=='complete' else 'partial',
        'totalsSource':'findings details; recorded instances, not unique vulnerabilities',
        'findingsDeclaredTotal':snapshot['total'],'findingsRowsRead':len(findings),'findingsDistinctSessionIds':len(f),
        'repeatedFindingRows':len(findings)-len(f),'reportSampleRows':len(samples),'reportDistinctSessionIds':len(r),
        'commonIds':len(common),'omittedCount':len(missing),'reportOnlyCount':len(extra),
        'omitted':[safe_row(f[k]) for k in sorted(missing)],'reportOnly':equivalents,
        'commonIdFieldDifferences':field_differences,'groups':groups,'nativeReportGroups':native_groups,
        'groupCountsBySeverity':dict(Counter(g['severity'] for g in groups if g['findingsRecordedInstances'])),
        'nativeReportExhaustive':False,'matchesFindingsSnapshot':snapshot['status']=='complete' and not missing and not extra and not field_differences,'reportInterpretation':'native samples/representatives; do not derive full totals from count fields',
        'messageIdComparison':'Native traditional-json-plus instances omit messageId. Findings message IDs retained; do not invent a join from URL alone.',
        'nextAction':snapshot.get('continuation')}
