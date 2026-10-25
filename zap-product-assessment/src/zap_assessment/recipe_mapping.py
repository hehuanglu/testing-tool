"""Finite recipe wire mapping admission, before any setup side effect."""
def check_auth(doc,*,login,identity,register,username,password,token,subject,registered):
    a=doc.get('auth');ops={o['id']:o for o in doc['operations']}
    if not a:raise ValueError('recipe auth absent')
    try:
        for oid,expected in [(a['loginOperationId'],login),(a['identity']['operationId'],identity),(a['identity']['actorSource']['operationId'],register)]:
            if (ops[oid]['method'],ops[oid]['pathTemplate'])!=expected:raise ValueError('recipe auth route/method mismatch')
        if (a['kind'],a['usernameField'],a['passwordField'],a['tokenPointer'],a['identity']['subjectPointer'],a['identity']['actorSource']['subjectPointer'],a['headerName'],a['headerPrefix'])!=('json-bearer',username,password,token,subject,registered,'Authorization','Bearer '):raise ValueError('recipe auth field mapping mismatch')
    except KeyError:raise ValueError('recipe auth operation missing') from None
