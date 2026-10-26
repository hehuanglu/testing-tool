"""Owned archive control API. Distinct nonfinancial transport/semantics proof only."""
ID='archive-control/1.0'
DAG=[{'id':'readers','requires':[],'operation':'join'}, {'id':'document','requires':['readers'],'operation':'create'}]
SURFACE={('POST','/echo'),('POST','/members'),('POST','/sessions'),('GET','/principal'),('GET','/documents'),('POST','/documents'),('GET','/documents/{key}'),('PATCH','/documents/{key}'),('DELETE','/documents/{key}'),('POST','/documents/{key}/seal'),('GET','/access')}
def admit(doc,track=None):
    auth=doc.get('auth')
    from ..recipe_mapping import check_auth
    if track!='be-anonymous':
        check_auth(doc,login=('POST','/sessions'),identity=('GET','/principal'),register=('POST','/members'),username='handle',password='passphrase',token='/session/bearer',subject='/principal/key',registered='/member/key')
    if track!='be-anonymous' and (not auth or auth['tokenPointer']!='/session/bearer' or auth['identity']['subjectPointer']!='/principal/key'):raise ValueError('archive auth mapping mismatch')
    for o in doc['operations']:
        if (o['method'],o['pathTemplate']) in SURFACE and o['protected']!=(o['pathTemplate'] not in ('/members','/sessions','/echo')):raise ValueError('archive protection drift')
    return [o['id'] for o in doc['operations'] if (o['method'],o['pathTemplate']) in SURFACE]
SUCCESS={'join':[201],'login':[200],'identity':[200],'list':[200],'create':[201],'read':[200],'rename':[200],'remove':[204]}
def policy(role,relation,action,state):
    if role=='LIBRARIAN' and action in ('read','list'):return 'allow'
    return 'allow' if role=='READER' and relation=='owner' else 'deny'
REGISTER_ROLE='READER'
def registration(marker,password,phone):
    return {'handle':marker,'passphrase':password}
CAPTURE_FIELDS=frozenset(('entry','key','owner','title','phase','fault','principal','entries','meta','index','limit','count','tier','problem','detail','member'))
ACTION_OPERATIONS={'read':('GET','/documents/{key}'),'list':('GET','/documents'),'create':('POST','/documents'),'rename':('PATCH','/documents/{key}'),'remove':('DELETE','/documents/{key}')}
MUTABLE_FIELDS={'create':['title'],'rename':['title']}

IDENTITY_STRATEGIES={role:{'version':'protected-json-subject-role/1.0','operationId':'identity','subjectPointer':'/principal/key','rolePointer':'/principal/tier'} for role in ('READER','LIBRARIAN')}
IDENTITY_STRATEGIES.update({role:{'version':'signed-jwt-protected-probe/1.0','operationId':'access','issuer':'archive-controlled','audience':'archive-native','roleClaim':'clearance',
    'expectedStatus':status,'responsePointer':pointer,'responseValue':value} for role,status,pointer,value in [('CURATOR',200,'/gate/state','present'),('AUDITOR',403,'/problem/key','role-denied')]})
