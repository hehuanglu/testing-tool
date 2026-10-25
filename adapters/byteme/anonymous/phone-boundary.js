const ScanRuleMetadata=Java.type('org.zaproxy.addon.commonlib.scanrules.ScanRuleMetadata');
function getMetadata(){return ScanRuleMetadata.fromYaml(`
id: 909901
name: ByteMe registration phone validation and normalization
description: Tests valid local, trimmed and international numbers and rejects malformed values on the discovered registration API.
solution: Validate and normalize phone numbers before storing customer data.
category: INJECTION
risk: MEDIUM
confidence: HIGH
cweId: 20
wascId: 20
status: alpha
`);}
function scanNode(as,msg){
  const body=JSON.parse(msg.getRequestBody().toString());
  if(Object.keys(body).length!==1 || !Object.prototype.hasOwnProperty.call(body,'phone'))return;
  const n=String(body.phone).replace(/\D/g,'').slice(-7);
  const tests=[{value:' 097'+n+' ',valid:true},{value:'+8498'+n,valid:true},{value:'096'+n,valid:true},{value:'１２３４５６７８９０',valid:false},{value:'09abc12345',valid:false}];
  for(const test of tests){
    if(as.isStop())return;
    const probe=msg.cloneRequest();probe.setRequestBody(JSON.stringify({phone:test.value}));
    probe.getRequestHeader().setContentLength(probe.getRequestBody().length());as.sendAndReceive(probe,false,false);
    const status=probe.getResponseHeader().getStatusCode();
    let mismatch=false;
    if(status===201){
      const record=JSON.parse(probe.getResponseBody().toString());mismatch=!test.valid || record.phone!==test.value.trim();
    }
    if(mismatch)as.newAlert().setParam('phone').setAttack(test.value).setEvidence('Created customer phone differs from the validated normalized input contract').setMessage(probe).raise();
  }
}
function scanHost(as,msg){}
function scan(as,msg,param,value){}
