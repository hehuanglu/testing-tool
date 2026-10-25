"""Bounded direct fixture lane. Never counted as browser/native anonymous assessment."""
import json,ssl,urllib.request,urllib.error
from pathlib import Path
from .fe_anonymous_contract import save
from .fe_anonymous_binding import inspect

class DirectFixtures:
    def __init__(self,selection,out):
        self.selection=selection;self.out=Path(out);self.count=0
        self.context=ssl.create_default_context(cafile=selection['certificate']['path'])
    def send(self,method,path,body,token):
        inspect(self.selection)
        if self.count>=12:raise ValueError('direct fixture request budget')
        if not path.startswith('/') or path.startswith('//') or '\\' in path:raise ValueError('fixture target outside binding')
        self.count+=1;name='direct-fixtures/'+str(self.count).zfill(3)
        payload=json.dumps(body).encode() if body is not None else None
        save(self.out,name+'-intent.json',{'lane':'direct-fixture-only','method':method,'path':path,'body':body,'retry':False})
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*a):return None
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=self.context),NoRedirect())
        req=urllib.request.Request(self.selection['origin']+path,method=method,data=payload,headers={'Authorization':'Bearer '+token,'Accept':'application/json',**({'Content-Type':'application/json'} if payload else {})})
        try:r=opener.open(req,timeout=12)
        except urllib.error.HTTPError as e:r=e
        raw=r.read(1024**2+1)
        if len(raw)>1024**2:raise ValueError('fixture response budget')
        data=json.loads(raw);save(self.out,name+'-response.json',{'status':r.code,'body':data})
        if not 200<=r.code<300:raise ValueError('fixture request rejected; no replay')
        return data
