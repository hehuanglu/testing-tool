import operate as o,json
from inspect_results import rows_all
from urllib.parse import urlsplit
from zap_assessment.result_readers import read_jsonl

def run():
 assert not (o.ROOT/'input-poststate.json').exists(),'readback already exists'
 q=o.load('execution.json');rows=rows_all();result={};reads={}
 for folder in ('guard-execution','guard-status-path'):
  path=o.ROOT/folder/'variant-readback.jsonl'
  if path.exists():
   for row in read_jsonl(path):reads[(folder,row['sequence'])]=row
 for c in q['cases']:
  if c['operationId'] not in ('createFood','updateFood','createOrder'):continue
  camp=next(x for x in q['campaigns'] if x['caseId']==c['id'] and x['vectors']==['JSON-body'])
  selected=[r for r in rows if r.get('campaignId')==camp['id'] and str(r.get('ruleId')) in set(map(str,camp['ruleIds'])) and r['status'] in (200,201)]
  fields=['name','description','imageUrl'] if c['operationId'] in ('createFood','updateFood') else [f for f in c['body'] if f in ('tableNumber','recipientName','shippingPhone','shippingAddress','note')]
  for field in fields:
   changed=[r for r in selected if json.loads(r['body'])[field]!=c['body'][field]];assert changed,'no accepted native mutation '+c['id']+' '+field
   matched=[]
   for r in changed:
    value=json.loads(r['body'])[field];ack=json.loads(r['responseBody']);expected=value
    if field=='name':
     expected=value.strip() if c['method']=='PUT' else (str(value)+'-'+str(r['_sequence'])).strip()
    if c['operationId']=='createOrder' and isinstance(value,str):expected=value.strip() or None
    if ack.get(field)==expected:matched.append((r,ack,expected))
   assert matched,'ACK field mismatch '+c['id']+' '+field
   independent=[]
   for row,ack,expected in matched:
    check=reads.get((row['_capture'],row['_sequence']),{})
    if check.get('matched') and check.get('apiReadStatus')==200 and check.get('objectId')==ack['id'] and check.get('ack')==ack and check.get('readback',{}).get(field)==expected:
     if c['operationId']=='createOrder' and str(check['readback']['userId'])!=o.load('actors.json')['CUSTOMER']['subject']:continue
     independent.append(row['_sequence'])
   state={'apiReadStatus':200 if independent else None,'immediateIndependentVariantReadback':bool(independent),'independentlyReadVariants':len(independent),'acceptedMutationValueMatchedInSynchronousResponse':bool(matched),'laterOverwriteCannotSupplyEarlierVariantReadback':True}
   result[c['id']+'::'+field]={'acceptedNativeFieldMutations':len(changed),'acknowledgedInputValuesMatched':len(matched),'independentlyReadVariants':len(independent),'independentSequences':independent,'postState':state}
 o.save('input-poststate.json',{'completed':True,'fields':result,'readRequests':len(reads)});print(json.dumps({'postState':'complete','processingFields':len(result),'apiReads':len(reads)}),flush=True)
if __name__=='__main__':run()
