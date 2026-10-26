"""Finalsource compatibility recipe. Legacy extended business/continuation remain separate."""
ID='finalsource-ledger/1.0'
DAG=[{'id':'actors','requires':[],'operation':'register'}, {'id':'account','requires':['actors'],'operation':'account.create'}]
def admit(doc,track=None):
    from ..research_product import SURFACE
    from ..recipe_mapping import check_auth
    if track!='be-anonymous':
        check_auth(doc,login=('POST','/api/auth/login'),identity=('GET','/api/v1/accounts'),register=('POST','/api/auth/register'),username='email',password='password',token='/data/accessToken',subject='/data/user_id',registered='/data/user/id')
    expected={v for v in SURFACE}
    for o in doc['operations']:
        if (o['method'],o['pathTemplate']) in expected and o['protected']!=o['pathTemplate'].startswith('/api/v1/'):
            raise ValueError('ledger protection drift')
    auth=doc.get('auth')
    if track!='be-anonymous' and (not auth or auth['tokenPointer']!='/data/accessToken' or auth['identity']['subjectPointer']!='/data/user_id'):raise ValueError('ledger auth mismatch')
    return [o['id'] for o in doc['operations'] if (o['method'],o['pathTemplate']) in expected]
def success(doc,oid):
    op=next(o for o in doc['operations'] if o['id']==oid)
    return [201] if op['method']=='POST' and op['protected'] else [200]
def policy(role,relation,action,state):
    return 'allow' if relation in ('owner','shared-read') and (relation=='owner' or action.endswith('.read') or action.endswith('.list')) else 'deny'
REGISTER_ROLE='user'
def registration(marker,password,phone):
    return {'email':marker+'@example.test','password':password,'confirm Password':password,'fullName':marker}
CAPTURE_FIELDS=frozenset(('data','id','user_id','bank_name','account_type','branch_name','balance','account_id','accounts','deleted_account_id','statusCode','message','success','path'))
def mutable_fields(operation):
    p=operation['pathTemplate']
    if '/accounts' in p:return ['bank_name','balance','account_type','branch_name']
    if '/transactions' in p:return ['amount','itemDescription','shopName','paymentMethod']
    if '/goals' in p:return ['target_amount','start_date','end_date']
    return []
