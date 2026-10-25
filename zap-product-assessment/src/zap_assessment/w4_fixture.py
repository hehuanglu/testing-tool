"""Explicit owned development workload; never registered as a product mode."""
from .pilot import fixture_inputs,LiveScanner
from .contracts import AuthorityRegistry,Blocked
class W4Scanner(LiveScanner):
    def start(self,kind,target):
        if kind!='active':return super().start(kind,target)
        from .transport import field
        policies=self.engine('ascan','view','scanPolicyNames',{}).get('scanPolicyNames')
        if not isinstance(policies,list) or 'w4-query-only' not in policies:raise Blocked('owned active policy ambiguous')
        result=self.mcp.call('zap_attack_start',{'targetUrl':target,'recurse':'false','policy':'w4-query-only'})
        if field(result,'Execution Mode').lower()!='direct':raise Blocked('queued fixture refused')
        return field(result,'Operation ID')
    def status(self,kind,op):
        done=super().status(kind,op)
        if kind=='active':
            # Exactly one owned active scan. MCP operation ID need not be ZAP ID.
            rows=self.engine('ascan','view','scans',{}).get('scans')
            if not isinstance(rows,list) or len(rows)!=1:raise Blocked('owned active scan identity ambiguous')
            scan=str(rows[0]['id']);progress=self.engine('ascan','view','scanProgress',{'scanId':scan})
            self.active_progress=getattr(self,'active_progress',[])+[{'scanId':scan,'terminal':done,'progress':progress}]
        return done

def inputs(active=False):
    p,w,r,raw=fixture_inputs()
    if active:
        p['crawlPath']='/api/echo?q=baseline';w['active']=True;w['workflowId']='w4-owned-active-conformance'
        w['operations'].append('active');w['destructiveLevel']='synthetic-mutations'
        a=r.get(p['authorizationRef']);a['operations']=list(w['operations']);a['destructiveLevel']=w['destructiveLevel'];r=AuthorityRegistry({a['recordId']:a})
    return p,w,r,raw
