"""Public unit fixtures, never runtime source/evidence or credential inputs."""
import base64
import copy
import json
import time

from zap_assessment.private_db import CONTRACT,CONTROL_ZONE,ENCODINGS,audit_private_control

PASSWORD='unit-private-source-1234567890'
FORMS={
    'raw-utf8':PASSWORD.encode(),
    'base64-standard':b'dW5pdC1wcml2YXRlLXNvdXJjZS0xMjM0NTY3ODkw',
    'base64-url':b'dW5pdC1wcml2YXRlLXNvdXJjZS0xMjM0NTY3ODkw',
    'url-percent':b''.join(('%%%02X'%b).encode() for b in PASSWORD.encode()),
    'json-escape':b''.join(('\\u%04x'%b).encode() for b in PASSWORD.encode())}


def decoded_control():
    rows=[{'kind':'table','name':'PRIVATE_SOURCE_CONTROL'}];total=0
    for index,tag in enumerate(ENCODINGS,1):
        for column,sql,data in [('ENCODING',12,tag.encode()),('TEXT_VALUE',12,FORMS[tag]),('BINARY_VALUE',-3,FORMS[tag])]:
            total+=len(data)
            rows.append({'kind':'cell','table':'PRIVATE_SOURCE_CONTROL','row':index,'column':column,'sqlType':sql,
                         'base64':base64.b64encode(data).decode()})
    rows.append({'kind':'complete','tables':1,'rows':5,'cells':15,'decodedBytes':total})
    return rows


def encode(rows):return b'\n'.join(json.dumps(r).encode() for r in rows)+b'\n'


def source_metadata(run='owned-db',plan='a'*64):
    info={'inode':100,'device':3,'bytes':256,'uid':1003,'gid':1003,'mode':0o600,'links':1,'mtimeNs':10,'ctimeNs':11}
    return {'schemaVersion':'owned-private-source/1.0','runId':run,'planHash':plan,
        'sourceKind':'owned-guard-private-file-reference','filesystem':'tmpfs','zonePath':'/tmp/w5-private-source',
        'zone':{**info,'mode':0o700,'links':2},
        'files':[{'actorRef':a,'referenceId':'owned-private-file:'+a,'relativePath':a+'.json',**info,'inode':i}
                 for i,a in enumerate(('A','B'),101)],'sourceValuesIncluded':False,'contentHashesIncluded':False}


def control_files():
    info={'inode':1000,'device':3,'bytes':256,'uid':1003,'gid':1003,'mode':0o600,'links':1}
    return {'filesystem':'tmpfs','zonePath':CONTROL_ZONE,'zone':{**info,'mode':0o700,'links':2},
        'files':[{'name':n,**info,'inode':i} for i,n in enumerate(('session.data','session.properties','session.script'),1001)],
        'contentHashesIncluded':False}


def receipt(case='success',mode='control',run='owned-db',plan='a'*64,nonce='b'*32):
    audit=audit_private_control(encode(decoded_control()),PASSWORD) if mode=='control' else {
        'decoder':'HSQL JDBC all PUBLIC table typed cells','tables':['HISTORY'],'rows':2,'decodedCells':2,
        'decodedBytes':32,'canaryMatches':0,'seededControl':False}
    return {'contract':CONTRACT,'status':'pass','mode':mode,'runId':run,'planHash':plan,'actorRef':'A','caseId':case,
        'nonce':nonce,'peer':{'uid':1003,'gid':1003},'sourceMetadata':source_metadata(run,plan),'audit':audit,
        'controlFiles':control_files() if mode=='control' else None,
        'cleanup':{'nonce':nonce,'controlZoneRemoved':True,'removedControlFiles':3 if mode=='control' else 0},
        'leakDetected':False,'rawCellsExportedToController':False,'sourceValuesIncluded':False,'contentHashesIncluded':False,
        'startedAtMonotonic':2,'completedAtMonotonic':3}


class UnitZone:
    def __init__(self):self.meta=source_metadata();self.resolves=0
    def metadata(self):return copy.deepcopy(self.meta)
    def reference(self,actor,record):
        zone=self
        class Ref:
            def resolve(self,**_):zone.resolves+=1;return {'username':'A','password':PASSWORD}
        return Ref()
