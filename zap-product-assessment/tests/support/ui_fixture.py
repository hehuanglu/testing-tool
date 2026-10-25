"""W7 unit-contract corpus, NOT browser runtime evidence.

Real fixture HTTP is exercised, while DOM/command observations are generated.
The independent target is reused; no saved corpus is called actual UI execution.
"""
import copy
import json
from pathlib import Path
import tempfile
import threading
from http.server import HTTPServer
from zap_assessment.business_fixture import generate_manifest
from zap_assessment.business import digest,minor,money
from zap_assessment.product_adapter import ProductAdapter
from zap_assessment.ui_contract import VERSION,ui_steps,public_config,command_kinds
from zap_assessment.ui_fixture import UIProduct,UIHandler
from zap_assessment.bola_http import exchange
from zap_assessment.opaque_canary import source_controls


def sample(seed=711,alternate=False,reverse=False,fault='fixed',spike=False):
    fixture=generate_manifest('w6-w7-unit-'+str(seed),seed,'alternate-ledger' if alternate else 'finalsource-shaped',reverse)
    config=public_config(fixture);steps=ui_steps(fixture,spike)
    plan={'contractVersion':VERSION,'mode':'owned-synthetic-ui-diagnostic','scope':'session-spike' if spike else 'ui-business-flow',
      'runId':fixture['runId'],'fixtureHash':digest(fixture),'containerName':'w7-ui-unit','profileVolume':'w7-ui-unit-profile',
      'image':'sha256:'+'a'*64,'fidelity':'owned-synthetic-source-derived-ui','fault':fault,'steps':steps,
      'evidenceKind':'unit-contract-corpus','sourcePins':{'unit-contract-corpus':'b'*64},'securityApproval':False,'productRequestsPermitted':False,
      'spikePlanHash':None if spike else 'c'*64}
    with tempfile.TemporaryDirectory() as tmp:
        target=UIProduct(fixture,config,tmp,fault);server=HTTPServer(('127.0.0.1',18080),UIHandler);server.product=target
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();rows=[];seq=0;token=None;shown_id='';balance='';actor='anonymous';subject='';status=0;last_id=''
        def call(action,request):
            nonlocal seq,last_id,status
            seq+=1;last_id=fixture['runId']+'-contract-'+str(seq)
            headers={'Content-Type':'application/json','User-Agent':'Firefox/999.0 (unit-contract-corpus)',
                     'X-W7-Request':last_id,'X-W7-Action':action,'X-W6-Case':'ui-expense'}
            if token:headers['Authorization']='Bearer '+token
            payload=json.dumps(request['body']).encode() if request['body'] is not None else None
            status,body,_=exchange('http://127.0.0.1:18080',request['method'],request['path'],headers,payload,3)
            return body
        try:
            for s in steps:
                before=copy.deepcopy(target.product.state);start=len(target.arrivals);shown_id='';balance='';action=s['action']
                if action=='login':
                    a=s['actorRef'];body=call('login',{'method':'POST','path':'/api/auth/login','body':{'email':config['actors'][a]['email'],'password':target.passwords[a]}})
                    token=body['data']['accessToken'];proof=call('identity',{'method':'GET','path':'/__w7/identity','body':None});actor=proof['actorRef'];subject=str(proof['subject'])
                elif action=='logout':token=None;actor='anonymous';subject=''
                else:
                    if action=='reload':call('identity',{'method':'GET','path':'/__w7/identity','body':None})
                    body=call('read' if action=='reload' else action,ProductAdapter(fixture).request(s['case']))
                    if action in ('read','reload') and status==200:
                        obj=body['result']['value'] if alternate else body['data'];shown_id=str(obj['key'] if alternate else obj['id']);balance=money(obj['units']) if alternate else obj['balance']
                rows.append({'stepId':s['stepId'],'actorRef':s['actorRef'],'action':action,'commandKinds':command_kinds(action),
                    'navigation':'webdriver-refresh' if action=='reload' else 'none','requestIds':[r['requestId'] for r in target.arrivals[start:]],
                    'dom':{'actorRef':actor,'subject':subject,'requestId':last_id,'status':status,'loginVisible':actor=='anonymous',
                           'passwordCleared':True,'accountId':shown_id,'balance':balance,'alertPresent':False,'complete':len(rows)+1},
                    'preState':before,'postState':copy.deepcopy(target.product.state),'errorCode':None})
        finally:server.shutdown();server.server_close();thread.join()
        source=source_controls(target.canaries());audit={'scope':'browser-profile-diagnostic-only','profileMatches':1,'profileVerdict':'fail',
          'fingerprints':source['fingerprints'],'sourceValuesIncluded':False,'sourceControlTests':source['controls']['tested'],'sourceControlMisses':0,
          'requiredOperationalPairs':143,'operationalG3':'blocked','browserClosedBeforeAudit':True,'profileFiles':[],'unknownReaderCount':0,
          'testOnly':'Unit-generated profile/DOM receipts; not a real Firefox execution.'}
        runtime={'id':'unit-container','name':plan['containerName'],'image':plan['image'],'runId':plan['runId'],'networkMode':'none','readOnlyRoot':True,
          'profileVolume':plan['profileVolume'],'memoryBytes':768*1024**2,'memorySwapBytes':768*1024**2,'capDrop':['ALL'],'pidsLimit':256}
        obs={'steps':rows,'runtime':runtime,'screenshots':[],'browser':{'browserName':'firefox','browserVersion':'999.0'},
             'driverPin':{'driverSha256':'f'*64},'browserCleanupError':False,'evidenceKind':'unit-contract-corpus'}
        cleanup={'runtime':copy.deepcopy(runtime),'containerRemoved':True,'volumeRemoved':True,'rawProfileRetention':'private-outside-workspace','privateProfileIndexSha256':'e'*64}
        return [plan,fixture,obs,copy.deepcopy(target.arrivals),audit,cleanup]
