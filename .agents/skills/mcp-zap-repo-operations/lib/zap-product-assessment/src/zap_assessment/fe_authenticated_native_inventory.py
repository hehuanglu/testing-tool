"""Read-only native scan target binding; ZAP scans view does not include target URLs."""
import hashlib,json,time
from .fe_authenticated_contract import save

def targets(run,ids,label):
    values=[str(int(i)) for i in ids]
    if len(values)>32:raise ValueError('native recovery inventory budget')
    key='fa-inv-'+hashlib.sha256((label+str(time.time_ns())).encode()).hexdigest()[:20]
    code='const IDS='+json.dumps(values)+';const KEY='+json.dumps(key)+''';
const V=Java.type('org.zaproxy.zap.extension.script.ScriptVars');
let phase='extension';try {const C=Java.type('org.parosproxy.paros.control.Control');const E=Java.type('org.zaproxy.zap.extension.ascan.ExtensionActiveScan');const e=C.getSingleton().getExtensionLoader().getExtension(E.class);const rows=[];
for(const id of IDS){phase='scan';const scan=e.getScan(Number(id));if(scan===null)throw Error('missing owned scan');phase='pinned-target-field';const S=Java.type('org.parosproxy.paros.core.scanner.Scanner');const field=S.class.getDeclaredField('target');field.setAccessible(true);const target=field.get(scan);const node=target.getStartNode();if(node===null)throw Error('native start node absent');phase='history';const h=node.getHistoryReference();const m=h.getHttpMessage();rows.push({id:String(id),url:String(m.getRequestHeader().getURI()),method:String(m.getRequestHeader().getMethod()),historyId:h.getHistoryId()});}
V.setGlobalVar(KEY,JSON.stringify({targets:rows}));}catch(e){V.setGlobalVar(KEY,JSON.stringify({error:'native-target-readback-failed',phase:phase,errorType:String(e.name||'Java-error')}));}
'''
    path=run.rt.work/(key+'.js');path.write_text(code);path.chmod(0o444)
    run.engine('script','action','load',{'scriptName':key,'scriptType':'standalone','scriptEngine':'Graal.js','fileName':'/zap/wrk/'+path.name})
    try:
        run.engine('script','action','runStandAloneScript',{'scriptName':key});deadline=time.monotonic()+5
        while True:
            try:value=json.loads(run.engine('script','view','globalVar',{'varKey':key})['globalVar']);break
            except (ValueError,KeyError):
                if time.monotonic()>deadline:raise
                time.sleep(.1)
        if value.get('error') or sorted(t['id'] for t in value['targets'])!=sorted(values):raise ValueError('native target binding absent; retain and stop owned runtime only')
        save(run.out,'native-inventory/'+label+'.json',value);return value['targets']
    finally:run.engine('script','action','remove',{'scriptName':key})
