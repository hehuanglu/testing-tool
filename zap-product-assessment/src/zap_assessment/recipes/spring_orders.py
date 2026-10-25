"""Reviewed Spring source semantics; policy is a source-derived hypothesis, not certification."""
import hashlib
import json
from pathlib import Path
import re
from ..product_source import source_inventory
ID='spring-orders/1.0'
# Explicit finite semantics paired with independently extracted controller mappings.
ROWS=[('register','POST','/api/auth/register',False,201,[]),('login','POST','/api/auth/token',False,200,[]),
 ('cart.read','GET','/api/cart',True,200,[]),('cart.add','POST','/api/cart/items',True,200,[]),
 ('cart.update','PUT','/api/cart/items/{cartItemId}',True,200,[]),('cart.remove','DELETE','/api/cart/items/{cartItemId}',True,200,[]),
 ('order.create','POST','/api/orders',True,201,[]),('order.list','GET','/api/orders',True,200,['status','orderType','page','size']),
 ('order.read','GET','/api/orders/{orderId}',True,200,[]),('order.cancel','DELETE','/api/orders/{orderId}',True,200,[]),
 ('order.confirm','POST','/api/orders/{orderId}/confirm',True,200,[]),('order.status','PUT','/api/orders/{orderId}/status',True,200,[]),
 ('food.list','GET','/api/foods',False,200,['categoryId']),('food.read','GET','/api/foods/{id}',False,200,[]),
 ('food.search','GET','/api/foods/search',False,200,['q','categoryId']),('food.create','POST','/api/foods',True,201,[]),
 ('food.update','PUT','/api/foods/{id}',True,200,[]),('food.delete','DELETE','/api/foods/{id}',True,204,[])]
AUTH={'kind':'json-bearer','loginOperationId':'login','usernameField':'email','passwordField':'password','tokenPointer':'/accessToken',
 'headerName':'Authorization','headerPrefix':'Bearer ','identity':{'operationId':'cart.read','subjectPointer':'/userId',
 'actorSource':{'operationId':'register','subjectPointer':'/id'},'expectedStatus':200,'contentType':'application/json'},
 'credentialRef':'private:run/actors','evidenceRefs':['config/SecurityConfiguration.java','cart/service/CartService.java','auth/controller/AuthController.java'], 'confidence':'medium'}
DAG=[{'id':'customers','requires':[],'permission':'setup','operation':'register','roles':['CUSTOMER']},
 {'id':'catalog','requires':[],'permission':'dedicated-catalog','reason':'dedicated food/stock/category; ADMIN credential needs separate authority'},
 {'id':'cart','requires':['customers','catalog'],'operation':'cart.add'},
 {'id':'order','requires':['cart'],'operation':'order.create'},
 {'id':'cancel','requires':['order'],'operation':'order.cancel','cleanup':'CANCELLED retained; stock restored once; no account/order delete API'}]

def discover(product):
    root=Path(product).resolve(strict=True);sources=[]
    source_root=root/'src/main/java/org/example' if (root/'src/main/java/org/example').is_dir() else root
    def source_ref(relative):
        return str((source_root/relative).relative_to(root))
    reviewed=json.loads(Path(__file__).with_name('spring-orders-source-pins.json').read_text())['files']
    for relative,expected in reviewed.items():
        path=source_root/relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('reviewed Spring recipe source drift/conflict; read semantics and update recipe with provenance')
    for path in sorted(source_root.rglob('*.java')):
        sources.append({'id':str(path.relative_to(root)),'path':str(path.relative_to(root)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    # Small Spring mapping reader, deliberately limited to these direct controller annotations.
    found={}
    for path in source_root.rglob('*Controller.java'):
        text=path.read_text();head=text.split('public class',1)[0]
        base=re.search(r'@RequestMapping\((?:path\s*=\s*)?"([^"]+)"',head);base=base[1] if base else ''
        for m in re.finditer(r'@(Get|Post|Put|Delete|Patch)Mapping\b(?:\(([^\n]*)\))?',text):
            arg=m[2] or '';p=re.search(r'"([^"]*)"',arg);route=base+(p[1] if p else '')
            found[(m[1].upper(),route)]=str(path.relative_to(root))
    wanted={(r[1],r[2]) for r in ROWS}
    if found.keys()!=wanted:raise ValueError('Spring recipe/controller inventory conflict; review new mappings')
    operations=[]
    for oid,method,path,protected,status,query in ROWS:
        operations.append({'id':oid,'method':method,'pathTemplate':path,'protected':protected,
            'semantics':oid+'; source hypothesis; success '+str(status),'input':{'query':query},
            'evidenceRefs':[found[(method,path)],source_ref('config/SecurityConfiguration.java')],'confidence':'medium'})
    mutations=[r[0] for r in ROWS if r[3] and r[1] not in ('GET','HEAD','OPTIONS')]
    auth=json.loads(json.dumps(AUTH))
    auth['evidenceRefs']=[source_ref(ref) for ref in auth['evidenceRefs']]
    obs={'sources':sources,'operations':operations,'auth':auth,'backendOnly':True,
        'fixtures':[{'id':'cart-order-stock','operationIds':mutations,'preparation':'CUSTOMER A/B; dedicated ADMIN catalog/stock -> cart -> order; no role minting',
        'ownership':'fresh actor register /id and exact ledger IDs','postconditions':['stock delta, order snapshot, cart clear','cancel retains CANCELLED and restores stock once','denial checks all affected state'],
        'evidenceRefs':[source_ref(ref) for ref in ('order/service/OrderService.java','cart/service/CartService.java','food/service/FoodService.java')],'confidence':'medium'}],
        'policies':[{'id':'source-policy','status':'hypothesis','evidenceRefs':[source_ref(ref) for ref in ('config/SecurityConfiguration.java','order/service/OrderService.java','cart/service/CartService.java')]}],
        'gaps':['Controller source inventory only; deployed/framework inventory unresolved','EMPLOYEE/ADMIN identity needs authorized credentials and role-specific protected strategy','No deployment/build/schema/config provided; no runtime qualification']}
    obs['gaps']=[{'status':'not-observed','description':g,'evidenceRefs':[source_ref('config/SecurityConfiguration.java')]} for g in obs['gaps']]
    return source_inventory(root,obs)

PUBLIC_FRAMEWORK_PATHS=frozenset(('/openapi.yaml','/swagger-ui.html','/swagger-ui/index.html','/v3/api-docs/swagger-config','/actuator/health','/error'))

def admit(doc,track=None):
    expected={(m,p):protected for _,m,p,protected,_,_ in ROWS}
    supported=[o['id'] for o in doc['operations'] if (o['method'],o['pathTemplate']) in expected and o['protected']==expected[(o['method'],o['pathTemplate'])]]
    for o in doc['operations']:
        if (o['method'],o['pathTemplate']) in expected and o['protected']!=expected[(o['method'],o['pathTemplate'])]:raise ValueError('recipe protection drift')
        if o['pathTemplate'] in PUBLIC_FRAMEWORK_PATHS and track=='be-anonymous':
            if o['method']!='GET' or o['protected']:raise ValueError('framework read/protection drift')
            supported.append(o['id'])
    expected_auth=[]
    for prefix in ('','src/main/java/org/example/'):
        candidate=json.loads(json.dumps(AUTH))
        candidate['evidenceRefs']=[prefix+ref for ref in AUTH['evidenceRefs']]
        expected_auth.append(candidate)
    if track!='be-anonymous' and doc.get('auth') not in expected_auth:raise ValueError('recipe auth/provenance drift; review mapping')
    return supported

def registration(marker, password, phone):
    return {'fullName':marker,'email':marker+'@example.test','phone':phone,'password':password,'confirmPassword':password}

def checkout(kind):
    if kind=='DINE_IN':return {'orderType':kind,'tableNumber':'T-owned','paymentMethod':'CASH'}
    if kind=='DELIVERY':return {'orderType':kind,'recipientName':'Owned fixture','shippingPhone':'0901234567','shippingAddress':'Owned test address','paymentMethod':'COD'}
    raise ValueError('unknown order type')

def policy(role, relation, action, state):
    if action.startswith('food.'):
        return 'allow' if action in ('food.read','food.list','food.search') or role=='ADMIN' else 'deny'
    if action.startswith('cart.'):
        return 'allow' if role=='CUSTOMER' and (relation in ('owner','shared-catalog') or action in ('cart.read','cart.add')) else 'deny'
    if action in ('order.read','order.list'):return 'allow' if role=='EMPLOYEE' or role=='CUSTOMER' and relation=='owner' else 'deny'
    if action=='order.create':return 'allow' if role=='CUSTOMER' else 'deny'
    if action=='order.cancel':return 'allow' if role=='CUSTOMER' and relation=='owner' and state=='PENDING' else 'deny'
    if action in ('order.confirm','order.status'):return 'allow' if role=='EMPLOYEE' and state not in ('COMPLETED','CANCELLED') else 'deny'
    return 'unknown'

SUCCESS={r[0]:[r[4]] for r in ROWS}

def expected_case(role, relation, action, state, request, resource):
    """Reviewed source policy, including the requested transition, before dispatch.

    These statuses are derived from SecurityConfiguration and OrderService, never
    from observed responses. The legacy role-only policy API remains unchanged.
    """
    if action in ('food.read','food.list','food.search'):return {'access':'allow','denialStatuses':[]}
    if role=='ANONYMOUS':return {'access':'deny','denialStatuses':[401]}
    allowed_roles=(['ADMIN'] if action.startswith('food.') and action not in ('food.read','food.list','food.search') else
        ['CUSTOMER','EMPLOYEE'] if action in ('order.read','order.list') else
        ['EMPLOYEE'] if action in ('order.confirm','order.status') else ['CUSTOMER'])
    if role not in allowed_roles:return {'access':'deny','denialStatuses':[403]}
    if action in ('cart.update','cart.remove') and relation!='owner':return {'access':'deny','denialStatuses':[404]}
    if action in ('order.read','order.list','order.cancel') and role=='CUSTOMER' and relation!='owner':return {'access':'deny','denialStatuses':[403]}
    if action=='order.cancel' and state!='PENDING':return {'access':'deny','denialStatuses':[409]}
    if action in ('order.confirm','order.status'):
        next_state='CONFIRMED' if action=='order.confirm' else (request.get('body') or {}).get('status')
        states={'PENDING','CONFIRMED','PROCESSING','SHIPPING','COMPLETED','CANCELLED'}
        if next_state not in states or next_state=='PENDING':return {'access':'deny','denialStatuses':[400]}
        kind=resource.get('typeValue')
        if action=='order.status' and (kind not in ('DINE_IN','DELIVERY') or resource.get('typePointer')!='/orderType'):raise ValueError('order transition type provenance missing')
        allowed={'PENDING':{'CONFIRMED','CANCELLED'},'CONFIRMED':{'PROCESSING','CANCELLED'},
            'PROCESSING':{'CANCELLED','COMPLETED' if kind=='DINE_IN' else 'SHIPPING'},'SHIPPING':{'COMPLETED'},'COMPLETED':set(),'CANCELLED':set()}
        if next_state not in allowed.get(state,set()):return {'access':'deny','denialStatuses':[409]}
    return {'access':'allow','denialStatuses':[]}
REGISTER_ROLE='CUSTOMER'
CHECKOUT_ACTIONS=frozenset(('order.create',))

def workload_templates(doc):
    """No guessed IDs. Read/denial subset is executable after real binding and authority."""
    cases=[]
    for oid,path in [('food.list','/api/foods'),('food.search','/api/foods/search?q=owned'),('cart.read','/api/cart')]:
        denied=oid=='cart.read'
        cases.append({'id':oid,'operationId':oid,'method':'GET','path':path,'body':None,'headers':{},'fixtureRefs':[],
            'category':'protected-denial' if denied else 'public-success',
            'expected':{'statuses':[401,403] if denied else [200],'contentType':'application/json','equals':{},'present':[]}})
    selected={c['operationId'] for c in cases}
    dispositions=[{'operationId':o['id'],'disposition':('protected-denial' if o['protected'] else 'public-exercise') if o['id'] in selected else 'conditional',
                   'reason':'read subset' if o['id'] in selected else 'Requires owned fixture, role, mutation budget or dedicated catalog'} for o in doc['operations']]
    return {'be-anonymous':{'operationIds':sorted(selected),'permissions':['read'],'cases':cases,'dispositions':dispositions},
        'be-authenticated':{'operationIds':['cart.read','order.list'],'permissions':['read','active'],
            'requests':[{'method':'GET','path':'/api/cart'},{'method':'GET','path':'/api/orders'}],
            'execution':{'crawl':'/api/cart','seeds':[{'method':'GET','path':'/api/cart','expected':[200]},
                {'method':'GET','path':'/api/orders?page=0&size=20','expected':[200]}],
                'attacks':[{'method':'GET','path':'/api/orders?page=0&size=20'}]}},
        'setup':{'operationIds':['register','login','cart.read'],'permissions':['setup','login','read'],'actorRefs':{'customer-one':'CUSTOMER','customer-two':'CUSTOMER'}},
        'fixtureDAG':DAG,'dependencies':{'catalog':'dedicated category/food/stock and authority; no shared data writes','roles':'EMPLOYEE/ADMIN credential refs and role-specific identity, register only CUSTOMER'}}
CAPTURE_FIELDS=frozenset(('id','userId','items','food','foodId','foodName','unitPrice','quantity','lineTotal','totalAmount','name','price','stockQuantity','categoryId','description','imageUrl',
 'status','orderType','tableNumber','recipientName','shippingPhone','shippingAddress','paymentMethod','note','confirmedBy','confirmedAt','cancelledAt','completedAt','createdAt','updatedAt',
 'content','page','size','totalElements','code','message','path','timestamp','errors','field','fieldErrors'))
ACTION_OPERATIONS={oid:(m,p) for oid,m,p,*_ in ROWS}
BUSINESS_OPERATION_IDS=('cart.read','cart.add','cart.update','cart.remove','order.create','order.read','order.cancel','food.read')
def prepare_business(client,actors,catalog,run_id,record):
    from .spring_fixtures import exercise
    return exercise(client,actors,catalog,run_id,record)

def validate_actor(actor):
    if actor['role']!='CUSTOMER' and actor['identityRequest']['operationRef']=='cart.read':raise ValueError('cart identity is CUSTOMER-only; role-specific protected identity required')
MUTABLE_FIELDS={'cart.add':['quantity'],'cart.update':['quantity'],'order.create':['note','tableNumber','recipientName','shippingPhone','shippingAddress'],
 'order.status':['status'],'food.create':['name','description','price'],'food.update':['name','description','price']}
REQUIRED_READS={'order.create':['cart.read','food.read','order.read'],'order.cancel':['order.read','food.read','cart.read'],
 'cart.add':['cart.read'],'cart.update':['cart.read'],'cart.remove':['cart.read']}

# The order owner field is never a caller identity. Privileged caller identity is
# the independently sourced principal in a signature-verified JWT on a protected probe.
IDENTITY_STRATEGIES={
 'EMPLOYEE':{'version':'signed-jwt-protected-probe/1.0','operationId':'order.list','issuer':'sa-local-dev','audience':'sa-mock-api','roleClaim':'role','expectedStatus':200,'responsePointer':'/page','responseValue':'0'},
 'ADMIN':{'version':'signed-jwt-protected-probe/1.0','operationId':'order.list','issuer':'sa-local-dev','audience':'sa-mock-api','roleClaim':'role','expectedStatus':403,'responsePointer':'/code','responseValue':'FORBIDDEN'}}
