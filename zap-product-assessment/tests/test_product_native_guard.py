"""Execute the generated native guard JS in an isolated VM; no ZAP or product traffic."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_multi_product import workflow
from zap_assessment.product_native import guard

@unittest.skipUnless(shutil.which('node'),'Node runtime required for generated JS behavior')
class NativeGuardTests(unittest.TestCase):
    def test_generated_guard_origin_method_query_fixed_reference_and_budget(self):
        p,_=workflow();p['limits']['maxRequests']=12;p['workload']['mutableBodyFields']={'create':['title']}
        q={'origin':'http://owned-alias:18080','identityPath':'/principal','execution':{'seeds':[{'method':'POST','path':'/documents','body':{'title':'owned','reference':'fixed-run-id'}}],'attacks':[]}}
        class Zap:
            def call(self,*args,**kwargs):return {}
        with tempfile.TemporaryDirectory() as tmp,patch('zap_assessment.product_native.docker'):
            guard(Zap(),'owned-zap',q,tmp,'/sessions',p)
            script=(Path(tmp)/'product-scope.js').read_text()
            harness=r'''
const vm=require('node:vm');const vars={};
class URI{constructor(url){this.value=new URL(url);}getPath(){return this.value.pathname;}getQuery(){return this.value.search.substring(1);}getAuthority(){return this.value.host;}toString(){return this.value.toString();}}
const context={Java:{type:(name)=>{if(name.endsWith('ScriptVars'))return {getGlobalVar:k=>vars[k],setGlobalVar:(k,v)=>vars[k]=v};if(name.endsWith('.URI'))return URI;throw Error('unknown Java class '+name);}}};
vm.createContext(context);vm.runInContext(SOURCE,context);
function attempt(method,url,body){
 let uri=new URI(url);let wire=body===null?'':typeof body==='string'?body:JSON.stringify(body);
 const headers={Authorization:'Bearer controlled',Cookie:'session=controlled','Proxy-Authorization':'controlled','Content-Type':'application/json','Transfer-Encoding':'chunked'};
 const header={getURI:()=>uri,getMethod:()=>method,setURI:v=>uri=v,setMethod:v=>method=v,setContentLength:v=>headers['Content-Length']=v,setHeader:(k,v)=>{if(v===null)delete headers[k];else headers[k]=v;}};
 const msg={getRequestHeader:()=>header,getRequestBody:()=>wire,setRequestBody:v=>wire=v};
 context.sendingRequest(msg,0,null); // Any exception fails the test; it is not containment.
 return {url:String(uri),method,body:wire,headers};
}
const results=[
 attempt('POST','http://owned-alias:18080/documents',{title:'attack string',reference:'fixed-run-id'}),
 attempt('POST','http://owned-alias:18080/documents',{title:'x',reference:'foreign-id'}),
 attempt('POST','http://owned-alias:18080/documents',{title:'x',reference:'fixed-run-id',actorId:'foreign'}),
 attempt('POST','http://outside/documents',{title:'x',reference:'fixed-run-id'}),
 attempt('DELETE','http://owned-alias:18080/documents',{title:'x',reference:'fixed-run-id'}),
 attempt('POST','http://owned-alias:18080/documents?actorId=foreign',{title:'x',reference:'fixed-run-id'}),
 attempt('POST','http://owned-alias:18080/documents','{broken'),
 attempt('POST','http://owned-alias:18080/documents',{title:{nested:'x'},reference:'fixed-run-id'}),
 attempt('POST','http://owned-alias:18080/documents',{title:['x'],reference:'fixed-run-id'}),
 attempt('POST','http://owned-alias:18080/documents','null'),
 attempt('POST','http://owned-alias:18080/documents','{"title":1e999,"reference":"fixed-run-id"}'),
 attempt('GET','http://owned-alias:18080/principal',null),
 attempt('GET','http://owned-alias:18080/principal',null)];
process.stdout.write(JSON.stringify({results,vars}));
'''.replace('SOURCE',json.dumps(script))
            result=subprocess.run(['node','-e',harness],capture_output=True,text=True,check=True)
            value=json.loads(result.stdout)
            self.assertEqual(value['results'][0]['body'],json.dumps({'title':'attack string','reference':'fixed-run-id'},separators=(',',':')))
            self.assertEqual(value['results'][11]['url'],'http://owned-alias:18080/principal')
            for index in (1,2,3,4,5,6,7,8,9,10,12):
                row=value['results'][index]
                self.assertEqual((row['url'],row['method'],row['body']),('http://owned-alias:18080/__research_scope_denied__','GET',''))
                self.assertEqual(row['headers'],{'Content-Length':0,'Host':'owned-alias:18080'})
            self.assertEqual(value['vars']['product.guard.requests'],'13');self.assertEqual(value['vars']['product.guard.blocks'],'11')

if __name__=='__main__':unittest.main()
