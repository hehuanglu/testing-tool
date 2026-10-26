"""Strict MCP Streamable HTTP client over a docker-exec network probe.

No model evaluates target/tool text. Only registered tool names and typed arguments.
"""
import json
import re
from .contracts import Blocked
from .evidence import EvidenceInvalid

TOOLS={'zap_crawl_start','zap_crawl_status','zap_crawl_stop','zap_attack_start','zap_attack_status','zap_attack_stop','zap_target_import','zap_passive_scan_status','zap_report_generate','zap_report_read_chunk','zap_findings_summary'}
class LostAck(ConnectionError): pass

class MCP:
    def __init__(self,request): self.request=request; self.session=None; self.seq=0; self.contracts={}
    def rpc(self,method,params=None,notification=False):
        self.seq+=1
        body={'jsonrpc':'2.0','method':method}
        if not notification: body['id']=self.seq
        if params is not None: body['params']=params
        headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream','MCP-Protocol-Version':'2025-03-26'}
        if self.session: headers['Mcp-Session-Id']=self.session
        response=self.request('http://127.0.0.1:7456/mcp','POST',headers,json.dumps(body).encode(),30)
        self.session=response['headers'].get('mcp-session-id',self.session)
        if response['status']>=400: raise Blocked('MCP HTTP failure')
        if notification: return {}
        text=response['body']
        if response['headers'].get('content-type','').startswith('text/event-stream') or text.startswith(('event:','data:',':')):
            # SSE is framed by CR/LF, not Python's broader Unicode splitlines().
            # Report content can contain literal NEL/U+0085 (and U+2028/2029)
            # inside a valid JSON string. Treating those as framing truncated
            # the JSON-RPC result before full report readback.
            docs=[];data=[]
            for line in text.split('\n'):
                if line.endswith('\r'):line=line[:-1]
                if not line:
                    if data:docs.append(json.loads('\n'.join(data)));data=[]
                    continue
                if line.startswith(':'):continue
                key,sep,value=line.partition(':')
                if sep and key=='data':data.append(value[1:] if value.startswith(' ') else value)
            if data:docs.append(json.loads('\n'.join(data)))
            docs=[d for d in docs if d.get('id')==self.seq]
            if len(docs)!=1: raise Blocked('MCP SSE response mismatch')
            value=docs[0]
        else: value=json.loads(text)
        if value.get('id')!=self.seq or 'error' in value or 'result' not in value: raise Blocked('MCP RPC failure')
        return value['result']
    def initialize(self):
        result=self.rpc('initialize',{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'zap-product-assessment','version':'0.1.0'}})
        self.rpc('notifications/initialized',notification=True)
        listing=self.rpc('tools/list')
        if not isinstance(listing.get('tools'),list) or listing.get('nextCursor'): raise Blocked('unbounded tool listing')
        self.contracts={t['name']:t['inputSchema'] for t in listing['tools']}
        if not TOOLS<=self.contracts.keys(): raise Blocked('required MCP capability absent')
        return {'serverInfo':result['serverInfo'],'protocolVersion':result['protocolVersion'],'tools':self.contracts}
    def call(self,name,args):
        if name not in TOOLS or name not in self.contracts: raise Blocked('unregistered MCP tool')
        from jsonschema import Draft202012Validator
        Draft202012Validator(self.contracts[name]).validate(args)
        result=self.rpc('tools/call',{'name':name,'arguments':args})
        if result.get('isError') or not isinstance(result.get('content'),list):
            self.last_response={'tool':name,'error':result}
            raise Blocked('MCP tool error')
        parts=result['content']
        if any(x.get('type')!='text' or not isinstance(x.get('text'),str) for x in parts): raise Blocked('tool content contract')
        text='\n'.join(x['text'] for x in parts)
        if text.startswith('"'):
            decoded=json.loads(text)
            if not isinstance(decoded,str): raise Blocked('unexpected MCP string envelope')
            text=decoded
        if len(text.encode())>2000000: raise Blocked('tool output exceeds limit')
        self.last_response={'tool':name,'text':text}
        return text

def field(text,label):
    matches=re.findall('^'+re.escape(label)+r': (.+)$',text,re.M)
    if len(matches)!=1: raise Blocked('tool field contract: '+label)
    return matches[0]

class Scanner:
    def __init__(self,mcp,engine,request,*,chunk_size=100000):
        if type(chunk_size) is not int or not 1<=chunk_size<=200000:raise ValueError('report chunk size outside interface bounds')
        self.mcp=mcp; self.engine=engine; self.request=request
        schema=getattr(mcp,'contracts',{}).get('zap_report_read_chunk',{})
        maximum=schema.get('properties',{}).get('maxChars',{}).get('maximum',200000)
        self.chunk_size=min(chunk_size,maximum)
    def health(self): return self.engine('core','view','version',{})
    def start(self,kind,url):
        text=self.mcp.call('zap_crawl_start' if kind=='crawl' else 'zap_attack_start',{'targetUrl':url,**({'strategy':'http'} if kind=='crawl' else {})})
        if field(text,'Execution Mode').lower()!='direct': raise Blocked('queued execution refused')
        return field(text,'Operation ID')
    def status(self,kind,op):
        text=self.mcp.call('zap_crawl_status' if kind=='crawl' else 'zap_attack_status',{'operationId':op})
        if field(text,'Operation ID')!=op or field(text,'Execution Mode').lower()!='direct': raise Blocked('operation mismatch')
        v=field(text,'Completed')
        if v not in ('yes','no'): raise Blocked('unknown terminal state')
        return v=='yes'
    def stop(self,kind,op): return self.mcp.call('zap_crawl_stop' if kind=='crawl' else 'zap_attack_stop',{'operationId':op})
    def passive(self):
        text=self.mcp.call('zap_passive_scan_status',{})
        backlog=int(field(text,'Records remaining'))
        # Upstream completed also evaluates active passive tasks. Both must agree.
        return backlog==0 and field(text,'Completed')=='yes'
    def import_schema(self,url,origin):
        text=self.mcp.call('zap_target_import',{'definitionType':'openapi','sourceKind':'url','source':url,'hostOverride':origin})
        if 'fail' in text.lower() or 'error' in text.lower() or 'warn' in text.lower(): raise Blocked('schema import warning/failure')
        return {'imported':True}
    def import_content(self,content,origin):
        text=self.mcp.call('zap_target_import',{'definitionType':'openapi','sourceKind':'content','source':content,'hostOverride':origin})
        expected='Guided target import result.\nDefinition Type: openapi\nSource Kind: content\nSource: client-supplied definition (contents withheld)\n\nOpenAPI content import completed with no reported import warnings. Review imported endpoints before starting an active scan.'
        if text.strip()!=expected: raise Blocked('content import unconfirmed/warning contract')
        return {'imported':True}
    def report(self,origin):
        text=self.mcp.call('zap_report_generate',{'format':'json','baseUrl':origin})
        # Pinned upstream emits Path, never treat other output text as an instruction.
        return field(text,'Path')
    def chunk(self,path,offset,sha):
        args={'reportPath':path,'offset':offset,'maxChars':self.chunk_size}
        if sha: args['expectedSha256']=sha
        page=json.loads(self.mcp.call('zap_report_read_chunk',args))
        if not hasattr(self,'chunk_observations'): self.chunk_observations=[]
        self.chunk_observations.append({k:v for k,v in page.items() if k!='content'})
        return page
    def findings(self,origin):
        # Structured report is the findings source; this summary is supplemental data only.
        return {'summary':self.mcp.call('zap_findings_summary',{'baseUrl':origin})}
    def seed(self,url):
        # The core sendRequest API routes a registered public GET through this ZAP session.
        from urllib.parse import urlsplit
        host=urlsplit(url).netloc
        return self.engine('core','action','sendRequest',{'request':f'GET {url} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n','followRedirects':'false'})
