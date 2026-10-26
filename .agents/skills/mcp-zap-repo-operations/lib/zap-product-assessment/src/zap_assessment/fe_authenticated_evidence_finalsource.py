"""Independent finalsource setup evidence reader. Never calls the setup producer."""
import json
from pathlib import Path

def load(path):return json.loads(Path(path).read_bytes())
def setup_bindings(root,actors,plan):
    result={}
    for ref,actor in actors.items():
        folder=Path(root)/'private/fixtures'/ref
        ledger_path=folder/'FIXTURE_DAG.json'
        if not ledger_path.exists():continue
        ledger=load(ledger_path)
        if ledger['subject']!=actor['subject'] or ledger['marker']!=actor['fixtures']['marker']:raise ValueError('setup actor/marker drift')
        requests=[]
        for path in sorted((folder/'setup').glob('*-request.json')):
            req=load(path)
            if req['state']!='response-observed':raise ValueError('unreconciled setup intent '+path.name)
            response=load(path.with_name(path.name.replace('-request','-response')))
            if response['status']!=req['status']:raise ValueError('setup response status drift')
            requests.append((req,response))
        values={}
        if len(ledger['accounts'])>ledger.get('maxNewAccounts',len(ledger['accounts'])) or len({a['id'] for a in ledger['accounts']})!=len(ledger['accounts']):raise ValueError('setup account ledger invalid')
        for index,row in enumerate(ledger['accounts']):
            proofs=[response['body']['data']['account'] for req,response in requests if req['method']=='POST' and req['path']=='/api/v1/accounts' and req['body']==row['body'] and response['status']==201]
            if len(proofs)!=1 or proofs[0]!=row['ack'] or proofs[0]['id']!=row['id'] or proofs[0]['user_id']!=actor['subject']:raise ValueError('account setup ownership/raw response')
            collections=[response['body']['data'] for req,response in requests if req['method']=='GET' and req['path']=='/api/v1/accounts' and response['status']==200]
            if not any(doc['user_id']==actor['subject'] and any(a['id']==row['id'] and a['bank_name']==row['body']['bank_name'] for a in doc['accounts']) for doc in collections):raise ValueError('setup collection ownership absent')
            values['ownedAccountId' if index==0 else 'nativeAccountId']=row['id']
        if ledger.get('database'):
            db_files=sorted(folder.glob('DB_PREREQUISITES-*.json'))
            if (folder/'DB_PREREQUISITES.json').exists():db_files.append(folder/'DB_PREREQUISITES.json')
            if not db_files:raise ValueError('DB prerequisite receipt missing')
            bound=load(folder/'DB_BINDING.json');derived={}
            if bound['backend']['id']!=plan['selection']['fixtureBinding']['backendId'] or bound['database']['id']!=plan['selection']['fixtureBinding']['databaseId']:raise ValueError('DB runtime binding drift')
            fks={(x['TABLE_NAME'],x['COLUMN_NAME'],x['REFERENCED_TABLE_NAME'],x['REFERENCED_COLUMN_NAME']) for x in bound['observed']['foreignKeys']}
            for db_file in db_files:
                db=load(db_file);needs=db.get('requested',['category','bill'])
                if db['state']!='acknowledged' or db['actorSubject']!=actor['subject'] or db['username']!=actor['username'] or db['receipt']['createdRows']!=len(needs) or db['rowBudget']!=len(needs):raise ValueError('DB finite intent/owner proof')
                for name in needs:
                    table='categories' if name=='category' else 'bills';field=name+'Id';row=db['receipt'][name]
                    if (table,'user_id','users','id') not in fks or field in derived:raise ValueError('DB duplicate/ownership binding')
                    if row['user_id']!=actor['subject'] or type(row['id']) is not int or row['id']<=0 or ledger['database'].get(field)!=row['id']:raise ValueError('DB row ownership/ID')
                    derived[field]=row['id']
                    if name=='category':
                        options=[response['body']['data'] for req,response in requests if req['path']=='/api/v1/categories/options' and req['method']=='GET']
                        if not any(any(x['category_id']==row['id'] and x['name']==db['categoryName'] for x in xs) for xs in options):raise ValueError('DB category independent API binding')
                    else:
                        bills=[response['body']['data']['data'] for req,response in requests if req['path']=='/api/v1/bills' and req['method']=='GET']
                        if not any(any(x['billId']==row['id'] and x['userId']==actor['subject'] for x in xs) for xs in bills):raise ValueError('DB bill independent API binding')
            if derived!=ledger['database']:raise ValueError('DB omitted fixture')
            values.update(derived)
        if ledger['transactions']:
            balance=float(ledger['accounts'][0]['ack']['balance'])
            expected_count=ledger.get('transactionTargetCount',11)
            if len(ledger['transactions'])!=expected_count:raise ValueError('transaction fixture count')
            for row in ledger['transactions']:
                req=row['request'];proofs=[response['body']['data'] for request,response in requests if request['method']=='POST' and request['path']=='/api/v1/transactions' and request['body']==req and response['status']==201]
                if len(proofs)!=1 or proofs[0]!=row['ack'] or req['accountId']!=values['ownedAccountId'] or req['category_id']!=values['categoryId']:raise ValueError('transaction setup response/reference')
                balance+=float(req['amount'])*(1 if req['type']=='Revenue' else -1)
            pages=[response['body']['data'] for req,response in requests if req['path']=='/api/v1/transactions?type=All&limit=10&offset=0' and req['method']=='GET']
            if not any(x['total']==expected_count and (expected_count<=10 or x['hasMore'] and len(x['data'])==10) for x in pages):raise ValueError('transaction setup collection proof')
            values.update(expectedBalanceAfterRevenue=balance+7.25,expectedBalanceAfterExpense=balance)
        if values!=ledger['fixtures']:raise ValueError('setup fixture values differ from independently derived IDs/math')
        result[ref]=values
    return result


def cleanup_readback(root,owned_ids=()):
    root=Path(root);result=load(root/'FIXTURE_CLEANUP.json')
    if result['replay']:raise ValueError('cleanup replay')
    actors=load(root/'private/ACTORS_INITIAL.json');expected={};retained=set()
    for ref,actor in actors.items():
        retained.add((ref,'principal',str(actor['subject'])))
        ledger_path=root/'private/fixtures'/ref/'FIXTURE_DAG.json'
        if not ledger_path.exists():continue
        ledger=load(ledger_path)
        if ledger['subject']!=actor['subject']:raise ValueError('cleanup setup actor mismatch')
        ids=[a['id'] for a in ledger['accounts']]
        if len(set(ids))!=len(ids) or len(ids)>ledger.get('maxNewAccounts',len(ids)) or any(type(i) is not int or i<=0 for i in ids):raise ValueError('cleanup setup exact account obligation')
        if ids:expected[ref]=ids
        for kind,field in (('category','categoryId'),('bill','billId')):
            if ledger.get('database',{}).get(field) is not None:retained.add((ref,kind,str(ledger['database'][field])))
    if set(result['accounts'])!=set(expected):raise ValueError('cleanup actor obligations omitted or unexpected')
    for row in owned_ids:
        if row['actorRef'] not in actors:raise ValueError('cleanup unexpected owned actor')
        if row['field'] in ('ownedGoalId','expenseGoalId'):retained.add((row['actorRef'],'goal',str(row['id'])))
    observed=[]
    for row in result['retained']:
        if not row.get('reason') or not row.get('ids'):raise ValueError('retention exact IDs/reason absent')
        observed.extend((row['actorRef'],row['kind'],str(i)) for i in row['ids'])
    if len(observed)!=len(set(observed)) or set(observed)!=retained:raise ValueError('retention obligations omitted or unexpected')
    for ref,ids in result['accounts'].items():
        folder=root/'private/cleanup'/ref;intent=load(folder/'CLEANUP_INTENT.json');ledger=load(root/'private/fixtures'/ref/'FIXTURE_DAG.json')
        if ids!=expected[ref] or ids!=intent['exactAccountIds'] or intent['state']!='acknowledged' or intent['subject']!=actors[ref]['subject']:raise ValueError('cleanup exact owned intent')
        before=load(folder/'setup/001-response.json')['body']['data']
        present=set(ids)&{a['id'] for a in before['accounts']}
        after=load(folder/('setup/'+str(len(present)+2).zfill(3)+'-response.json'))['body']['data']
        if before['user_id']!=ledger['subject'] or after['user_id']!=ledger['subject'] or set(ids)&{a['id'] for a in after['accounts']}:raise ValueError('cleanup protected ownership/absence')
        ui_ids={row['id'] for row in owned_ids if row['actorRef']==ref and row['field']=='uiAccountId'}
        if ui_ids&{a['id'] for a in after['accounts']}:raise ValueError('UI-created account deletion absence missing')
        for n,identifier in enumerate([i for i in ids if i in present],2):
            request=load(folder/('setup/'+str(n).zfill(3)+'-request.json'));response=load(folder/('setup/'+str(n).zfill(3)+'-response.json'))
            if request['method']!='DELETE' or request['path']!='/api/v1/accounts/'+str(identifier) or request['state']!='response-observed' or response['body']['data']['deleted_account_id']!=identifier:raise ValueError('cleanup DELETE raw readback')
    return result
