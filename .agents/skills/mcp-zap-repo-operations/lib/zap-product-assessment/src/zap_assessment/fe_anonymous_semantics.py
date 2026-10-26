"""Independent producer lifecycle checks for evidence v1/v2; no trust in pass flags."""
import json
from .fe_anonymous_contract import load
from .fe_anonymous_analysis import active_delivery,mutation_obligations
from .transport import field

def text_response(path):
    response=load(path)
    if response.get('isError'):raise ValueError('MCP evidence contains error')
    text='\n'.join(c['text'] for c in response['content'] if c.get('type')=='text')
    return json.loads(text) if text.startswith('"') else text

def check(root,plan,records,messages,ops,require_all=True):
    engine=[];tools=[]
    for f in sorted((root/'engine').glob('*-request.json')):engine.append((f.name,load(f),load(f.with_name(f.name.replace('-request.json','-response.json')))))
    for f in sorted((root/'tools').glob('*-request.json')):tools.append((f.name,load(f),text_response(f.with_name(f.name.replace('-request.json','-response.json')))))
    # Stable observations must precede first export; counters cannot be self-attested.
    passive=load(root/'PASSIVE.json');export=next((i for i,(_,q,_) in enumerate(tools) if q['tool']=='zap_report_generate'),None)
    if export is None:raise ValueError('report generation evidence absent')
    observations=[t for _,q,t in tools[:export] if q['tool']=='zap_passive_scan_status']
    if len(observations)<2 or any(field(t,'Completed')!='yes' or field(t,'Records remaining')!='0' for t in observations[-2:]):raise ValueError('passive stable observations absent before export')
    if passive.get('settled') is not True or passive.get('stableSamples',0)<2:raise ValueError('passive summary contradicts observations')
    selected={o.get('campaignId') for o in ops if o['kind']=='active'}
    active_plan=dict(plan,campaigns=[c for c in plan['campaigns'] if c['id'] in selected])
    baselines={c['id']:load(root/('baselines/'+c['id']+'.json')) for c in active_plan['campaigns']}
    for cid,baseline in baselines.items():
        captured=[item for _,q,r in engine if q['component']=='core' and q['name']=='sendRequest' for item in r.get('sendRequest',[])]
        if baseline not in captured:raise ValueError('baseline differs from native send response')
    derived=active_delivery(active_plan,records,messages,baselines)
    campaigns={c['id']:c for c in plan['campaigns']};seen=set()
    for op in ops:
        if op['kind']=='crawl':
            statuses=[t for _,q,t in tools if q['tool']=='zap_crawl_status' and q['arguments'].get('operationId')==op['operationId']]
            if not statuses or field(statuses[-1],'Operation ID')!=op['operationId'] or field(statuses[-1],'Progress')!='100%' or op.get('finalStatus')!=statuses[-1]:raise ValueError('crawl terminal evidence mismatch')
            if not any(r.get('caseId')=='client-discovery' and r.get('forwarded') for r in records):raise ValueError('crawl delivery absent')
            continue
        if op['kind']!='active':raise ValueError('unknown operation kind')
        cid=op['campaignId'];camp=campaigns.get(cid)
        if not camp or cid in seen:raise ValueError('duplicate/unplanned active operation')
        seen.add(cid)
        if any(op.get(k)!=camp[k] for k in ('ruleIds','vectorFields','branch')):raise ValueError('campaign metadata drift')
        native=str(op['nativeId'])
        starts=[r for _,q,r in engine if q['component']=='ascan' and q['name']=='scan' and str(r.get('scan'))==native and q['arguments'].get('method')==camp['method'] and q['arguments'].get('url')==plan['selection']['origin']+camp['path']]
        statuses=[int(r['status']) for _,q,r in engine if q['component']=='ascan' and q['name']=='status' and str(q['arguments'].get('scanId'))==native]
        stops=[r for _,q,r in engine if q['component']=='ascan' and q['name']=='stop' and str(q['arguments'].get('scanId'))==native]
        if len(starts)!=1 or not statuses or statuses[-1]!=100 or op.get('finalNativeStatus')!=statuses[-1] or op.get('terminal') is not True:raise ValueError('active start/terminal evidence mismatch')
        if (op.get('boundedStop') or op.get('deadlineStop')) and not stops:raise ValueError('active stop evidence absent')
        actual=derived[cid]
        if op.get('deliveredByRule')!=actual['deliveredByRule'] or op.get('deliveryProven')!=actual['deliveryProven']:raise ValueError('final active delivery metadata mismatch')
        if require_all and not actual['deliveryProven']:raise ValueError('active rule/vector delivery absent')
    if require_all and seen!=set(campaigns):raise ValueError('active campaigns incomplete')
    return {'delivery':derived,'unknownMutations':mutation_obligations(records),'semantics':'independent/2.0','stoppedMeaning':'terminal means no longer running; coverage limited to observed rule/vector payloads'}
