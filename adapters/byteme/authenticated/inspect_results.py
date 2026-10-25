import operate as o,json,collections
from urllib.parse import urlsplit,parse_qsl

def rows_all():
 result=[]
 for dr in ('guard','guard-execution','guard-status-path'):
  folder=o.ROOT/dr;times={}
  if (folder/'proxy.jsonl').exists():
   for line in (folder/'proxy.jsonl').read_text().split('\n'):
    if not line:continue
    row=json.loads(line)
    if row.get('sequence') is not None:times[row['sequence']]=row['at']
  for file in sorted(folder.glob('[0-9]*.json')):
   seq=int(file.stem);result.append({**json.loads(file.read_bytes()),'_capture':dr,'_sequence':seq,'_at':times.get(seq)})
 return result
def inspect():
 q=o.load('execution.json');out=[]
 for camp in q['campaigns']:
  c=next(c for c in q['cases'] if c['id']==camp['caseId']);f=o.ROOT/'campaigns'/(camp['id']+'.json')
  if not f.exists():out.append({'id':camp['id'],'state':'pending'});continue
  r=json.loads(f.read_text());native=[x for x in rows_all() if x.get('campaignId')==camp['id'] and str(x.get('ruleId')) in set(map(str,camp['ruleIds']))];fields={}
  vector=camp['vectors'][0]
  for key in (camp['mutableKeys'] if vector in ('JSON-body','query') else ['selector' if vector=='path' else 'header']):
   hits=[]
   for x in native:
    if vector=='JSON-body':changed=json.loads(x['body']).get(key)!=c['body'][key]
    elif vector=='query':changed=dict(parse_qsl(urlsplit(x['url']).query,keep_blank_values=True)).get(key)!=dict(parse_qsl(urlsplit(c['path']).query,keep_blank_values=True)).get(key)
    elif vector=='path':changed=urlsplit(x['url']).path!=urlsplit(c['path']).path
    else:changed=any(k.lower() in ('user-agent','referer') and val not in ('Mozilla/5.0','') for k,val in x['headers'].items())
    if changed:hits.append(x)
   success=[x for x in hits if x['status'] in (200,201,204)]
   fields[key]={'mutations':len(hits),'statuses':dict(collections.Counter(x['status'] for x in hits)),'accepted':len(success)}
  out.append({'id':camp['id'],'state':r['status']['status'],'sessionAfter':r['sessionValidAfter'],'ruleRequests':len(native),'fields':fields})
 return out
if __name__=='__main__':print(json.dumps(inspect(),indent=2))
