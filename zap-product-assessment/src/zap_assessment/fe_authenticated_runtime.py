"""Owned authenticated deployment configuration; shared anonymous defaults stay closed."""
import os,json
from pathlib import Path
from .fe_anonymous_runtime import FERuntime
from .fe_authenticated_contract import save
from .fe_authenticated_auth import native_profile

class AuthenticatedRuntime(FERuntime):
    broker_module='fe_authenticated_transport'
    def __init__(self,plan,out,journal,actors):
        super().__init__(plan,out,journal);self.actors=actors
        self.update_bindings()
        self.authdir=self.root/'native-private';self.authdir.mkdir(mode=0o755)
        profiles=[]
        for ref,actor in actors.items():
            save(self.authdir,ref+'.password',actor['password'].encode()).chmod(0o444)
            profiles.append(native_profile(plan['journeys']['auth'],plan['selection']['origin'],actor,ref,'/research/'+ref+'.password'))
        save(self.authdir,'auth.yml',{'zap':{'auth':{'experimental-json-bearer-enabled':True}},'mcp':{'server':{'auth':{'bootstrap':{'profiles':profiles}}}}}).chmod(0o444)
    def mcp_mounts(self):return ['-v',str(self.authdir)+':/research:ro']
    def update_bindings(self):
        bindings={k:{**{n:a[n] for n in ('username','subject','role','provenance')},'fixtures':a.get('fixtures',{}),'ownedIds':{n:v for n,v in a.get('fixtures',{}).items() if n.endswith('Id') and type(v) is int and v>0}} for k,a in self.actors.items()}
        path=save(self.config,'actor-bindings.pending',bindings);path.chmod(0o444);os.replace(path,self.config/'actor-bindings.json')
    def mcp_environment(self,env):return {**env,'MCP_CLIENT_ID':'fe-authenticated-research','SPRING_CONFIG_ADDITIONAL_LOCATION':'file:/research/auth.yml'}
    def mode(self,case,*,transition=False,campaign=None,fixed=None,baseline_hash=None,actor=None,group=None,slot='browser',phase='authenticated',fixed_query=None):
        value={'caseId':case,'campaignId':campaign,'fixedFields':fixed or {},'fixedQuery':fixed_query or {},'baselineHash':baseline_hash,'actorRef':actor,'sessionGroup':group,'slot':slot,'phase':phase}
        path=save(self.config,'mode.pending',value);path.chmod(0o444);os.replace(path,self.config/'mode.json')
