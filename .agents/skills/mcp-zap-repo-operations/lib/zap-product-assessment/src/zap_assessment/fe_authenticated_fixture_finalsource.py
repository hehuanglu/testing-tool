"""Owned finalsource setup/readback adapter. These calls never count as FE/native coverage."""
import datetime as dt,hashlib,http.client,json,os,secrets,ssl,subprocess,time
from pathlib import Path
from urllib.parse import urlsplit
from .fe_authenticated_binding import inspect
from .fe_authenticated_contract import canonical,digest,load,save

class FixtureClient:
    def __init__(self,selection,out,max_requests=36):
        self.selection=selection;self.out=Path(out);existing=sorted((self.out/'setup').glob('*-request.json'));self.count=len(existing);self.max_requests=max_requests;self.unknown=any(load(p).get('state') in ('sent','unknown') and load(p).get('method') not in ('GET','HEAD','OPTIONS') for p in existing)
    def send(self,method,path,body=None,token=None):
        if self.unknown and method not in ('GET','HEAD','OPTIONS'):raise ValueError('unknown setup mutation; read/reconcile only, never replay')
        inspect(self.selection)
        if self.count>=self.max_requests:raise ValueError('owned setup/readback budget')
        if not path.startswith('/') or path.startswith('//') or any(x in path for x in ('\\','\r','\n','#')):raise ValueError('fixture origin/path')
        u=urlsplit(self.selection['origin']);self.count+=1;name='setup/'+str(self.count).zfill(3)
        raw=json.dumps(body,separators=(',',':')).encode() if body is not None else None
        row={'lane':'owned-setup-readback','method':method,'path':path,'body':body,'state':'intent','replay':False};save(self.out,name+'-request.json',row)
        c=http.client.HTTPSConnection(u.hostname,u.port or 443,context=ssl.create_default_context(cafile=self.selection['certificate']['path']),timeout=12)
        try:
            c.connect()
            if hashlib.sha256(c.sock.getpeercert(binary_form=True)).hexdigest()!=self.selection['certificate']['derSha256']:raise ValueError('fixture TLS fingerprint drift')
            headers={'Host':u.netloc,'Content-Type':'application/json','Accept':'application/json'}
            if token:headers['Authorization']='Bearer '+token
            row['state']='sent';save(self.out,name+'-request.json',row);c.request(method,path,raw,headers);r=c.getresponse();blob=r.read(2*1024**2+1)
            if len(blob)>2*1024**2:raise ValueError('fixture response budget')
            result=json.loads(blob);row.update(state='response-observed',status=r.status);save(self.out,name+'-request.json',row);save(self.out,name+'-response.json',{'status':r.status,'body':result})
            if not 200<=r.status<300:raise ValueError('fixture request rejected; no replay')
            return result
        except Exception:
            if row['state']=='sent':self.unknown=True;row['state']='unknown';save(self.out,name+'-request.json',row)
            raise
        finally:c.close()

def create_actor(selection,out,actor_ref,run_id):
    """Fresh registration receipt plus independently protected collection identity; no hashes read."""
    out=Path(out);out.mkdir(parents=True,mode=0o700,exist_ok=False);client=FixtureClient(selection,out)
    marker=run_id+'-'+actor_ref+'-'+secrets.token_hex(4);username=marker+'@example.test';password='Owned!'+secrets.token_urlsafe(24)
    registered=client.send('POST','/api/auth/register',{'fullName':marker,'email':username,'password':password,'confirm Password':password});user=registered['data']['user'];token=registered['data']['token']
    observed=client.send('GET','/api/v1/accounts',token=token)
    if user['email']!=username or observed['data']['user_id']!=user['id'] or observed['data']['accounts']!=[]:raise ValueError('fresh actor independently protected identity/empty state mismatch')
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=7)));day=now.date();start=day.replace(day=1);next_month=(start.replace(day=28)+dt.timedelta(days=4)).replace(day=1);end=next_month-dt.timedelta(days=1)
    receipt={'schemaVersion':'owned-fe-actor/1.0','actorRef':actor_ref,'subject':user['id'],'role':'user','username':username,'marker':marker,'registration':'setup/001-response.json','protectedIdentity':'setup/002-response.json','source':'fresh-registration-and-protected-collection','productLocation':selection['productLocation'],'selectionSha256':canonical(selection),'setupOnly':True,'retention':'fresh user retained; no supported user DELETE API'};path=save(out,'ACTOR_RECEIPT.json',receipt)
    fixtures={'marker':marker,'accountMarker':marker+'-ui','editedAccountMarker':marker+'-edited','accountNumber':str(secrets.randbelow(10**14)+10**14),'transactionMarkerRevenue':marker+'-revenue','transactionMarkerExpense':marker+'-expense','today':str(day),'monthStart':str(start),'monthEnd':str(end),'currentMonth':day.strftime('%Y-%m'),'previousMonth':(start-dt.timedelta(days=1)).strftime('%Y-%m'),'year':str(day.year),'previousYear':str(day.year-1)}
    fixtures.update(nativeAccountMarker=marker+' <em data-fe-owned="marker">owned</em>',categoryMarker=marker+'-category',billMarker=marker+'-bill',billLogo=selection['origin']+next(a['path'] for a in selection['publicAssets'] if a['path'].endswith('.png')),firstPageMarker=marker+'-page-0',lastPageMarker=marker+'-page-10',billDueDate=str(day+dt.timedelta(days=3)))
    return {'username':username,'password':password,'subject':user['id'],'role':'user','source':'fresh-registration-and-protected-collection','setupToken':token,'provenance':[{'path':str(path),'sha256':digest(path)}],'fixtures':fixtures,'setupRoot':str(out)}

def binding(selection,backend_id,database_id,out,requested=('category','bill')):
    """Independent backend env/DNS -> exact DB container/schema/FK binding, no password output."""
    inspect(selection);fmt='{"id":{{json .Id}},"image":{{json .Image}},"started":{{json .State.StartedAt}},"running":{{json .State.Running}},"labels":{{json .Config.Labels}},"networks":{{json .NetworkSettings.Networks}}}'
    def meta(cid):return json.loads(subprocess.check_output(['docker','inspect','--format',fmt,cid],text=True))
    be=meta(backend_id);db=meta(database_id)
    for value in (be,db):
        if not value['running'] or value['labels'].get('com.docker.compose.project')!=selection['environment'] or value['labels'].get('com.docker.compose.project.working_dir')!=selection['productLocation']:raise ValueError('DB prerequisite deployment binding mismatch')
    if be['labels'].get('com.docker.compose.service')!='backend' or db['labels'].get('com.docker.compose.service')!='database':raise ValueError('backend/database service identity mismatch')
    program="""const mysql=require('mysql2/promise'),dns=require('node:dns').promises;(async()=>{const addresses=await dns.lookup(process.env.DB_HOST,{all:true});const c=await mysql.createConnection({host:process.env.DB_HOST,port:Number(process.env.DB_PORT),user:process.env.DB_USERNAME,password:process.env.DB_PASSWORD,database:process.env.DB_DATABASE});const [db]=await c.query('SELECT DATABASE() AS databaseName, @@hostname AS dbHostname');const [columns]=await c.execute('SELECT TABLE_NAME,COLUMN_NAME,DATA_TYPE,IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (?,?,?) ORDER BY TABLE_NAME,ORDINAL_POSITION',['users','categories','bills']);const [foreignKeys]=await c.execute('SELECT TABLE_NAME,COLUMN_NAME,REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (?,?) AND REFERENCED_TABLE_NAME IS NOT NULL',['categories','bills']);console.log(JSON.stringify({configuredHost:process.env.DB_HOST,configuredPort:process.env.DB_PORT,addresses,database:db[0],columns:columns.filter(x=>x.TABLE_NAME!=='users'||['id','email'].includes(x.COLUMN_NAME)),foreignKeys}));await c.end();})().catch(e=>{console.error(e.code||'binding-failed');process.exit(2)});"""
    p=subprocess.run(['docker','exec','-i',be['id'],'node','-'],input=program,text=True,capture_output=True,timeout=20)
    if p.returncode:raise ValueError('independent backend DB binding failed: '+p.stderr[:100])
    observed=json.loads(p.stdout);addresses={x['address'] for x in observed['addresses']};db_addresses={x['IPAddress'] for x in db['networks'].values()}
    if not addresses&db_addresses:raise ValueError('backend DB DNS does not resolve bound database container')
    fks={(x['TABLE_NAME'],x['COLUMN_NAME'],x['REFERENCED_TABLE_NAME'],x['REFERENCED_COLUMN_NAME']) for x in observed['foreignKeys']}
    needed={('categories' if k=='category' else 'bills','user_id','users','id') for k in requested}
    if not needed<=fks:raise ValueError('fixture ownership FK proof absent')
    result={'backend':be,'database':db,'observed':observed,'budget':{'newCategoriesPerActor':1,'newBillsPerActor':1},'columns':{'categories':['user_id','name'],'bills':['user_id','item_description','logo_url','due_date','last_charge_date','amount']},'prohibited':['existing row updates','user/role/token/auth config writes','password hash reads'],'setupOnly':True};save(out,'DB_BINDING.json',result);return result

def db_prerequisites(bound,actor,selection,out,requested=('category','bill')):
    """Insert at most one fresh category and one fresh bill for this actor, with intent/ID ledger."""
    out=Path(out);requested=set(requested)&{'category','bill'}
    if not requested:return {}
    ledger=out/('DB_PREREQUISITES-'+('-'.join(sorted(requested)))+'.json')
    if ledger.exists():raise ValueError('DB setup intent exists; reconcile exact IDs, never replay')
    day=dt.date.fromisoformat(actor['fixtures']['today']);marker=actor['fixtures']['marker'];assets=[a for a in selection.get('publicAssets',[]) if a['path'].endswith('.png')]
    if 'bill' in requested and not assets:raise ValueError('same-origin owned bill logo asset unavailable')
    intent={'actorSubject':actor['subject'],'username':actor['username'],'categoryName':marker+'-category','billDescription':marker+'-bill','logoUrl':selection['origin']+assets[0]['path'] if assets else None,'dueDate':str(day+dt.timedelta(days=3)),'lastChargeDate':str(day-dt.timedelta(days=4)),'amount':'12.50','requested':sorted(requested),'rowBudget':len(requested),'state':'intent','mutationReplay':False};save(out,ledger.name,intent)
    payload=json.dumps(intent)
    program="""const mysql=require('mysql2/promise');let raw='';process.stdin.on('data',x=>raw+=x);process.stdin.on('end',async()=>{let c;try{const x=JSON.parse(raw);c=await mysql.createConnection({host:process.env.DB_HOST,port:Number(process.env.DB_PORT),user:process.env.DB_USERNAME,password:process.env.DB_PASSWORD,database:process.env.DB_DATABASE});await c.beginTransaction();const [users]=await c.execute('SELECT id,email FROM users WHERE id=? AND email=?',[x.actorSubject,x.username]);if(users.length!==1)throw Error('owner-bind');const [oldCategory]=await c.execute('SELECT id FROM categories WHERE user_id=? AND name=?',[x.actorSubject,x.categoryName]);const [oldBill]=await c.execute('SELECT id FROM bills WHERE user_id=? AND item_description=?',[x.actorSubject,x.billDescription]);if((x.requested.includes('category')&&oldCategory.length)||(x.requested.includes('bill')&&oldBill.length))throw Error('prior-intent');let receipt={createdRows:0};if(x.requested.includes('category')){const [category]=await c.execute('INSERT INTO categories (user_id,name) VALUES (?,?)',[x.actorSubject,x.categoryName]);const [rows]=await c.execute('SELECT id,user_id,name FROM categories WHERE id=? AND user_id=?',[category.insertId,x.actorSubject]);receipt.category=rows[0];receipt.createdRows++;}if(x.requested.includes('bill')){const [bill]=await c.execute('INSERT INTO bills (user_id,item_description,logo_url,due_date,last_charge_date,amount) VALUES (?,?,?,?,?,?)',[x.actorSubject,x.billDescription,x.logoUrl,x.dueDate,x.lastChargeDate,x.amount]);const [rows]=await c.execute('SELECT id,user_id,item_description,amount FROM bills WHERE id=? AND user_id=?',[bill.insertId,x.actorSubject]);receipt.bill=rows[0];receipt.createdRows++;}await c.commit();console.log(JSON.stringify(receipt));await c.end();}catch(e){if(c){try{await c.rollback();await c.end()}catch{}}console.error(e.code||e.message||'setup-failed');process.exit(2)}});"""
    # Program is code-owned; private intent goes via stdin, never argv/env/tool output.
    wrapper='const {spawn}=require("node:child_process");const p=spawn(process.execPath,["-e",'+json.dumps(program)+'],{stdio:["pipe","inherit","inherit"]});p.stdin.end('+json.dumps(payload)+');p.on("exit",c=>process.exit(c||0));'
    result=subprocess.run(['docker','exec','-i',bound['backend']['id'],'node','-'],input=wrapper,text=True,capture_output=True,timeout=20)
    if result.returncode:intent.update(state='unknown-or-rolled-back',errorCode=result.stderr[:120],retention='retain intent; query exact owned marker/IDs, never reinsert');save(out,ledger.name,intent);raise ValueError('DB prerequisite did not ACK; reconcile only')
    receipt=json.loads(result.stdout)
    if receipt['createdRows']!=len(requested) or any(receipt[k]['user_id']!=actor['subject'] for k in requested):raise ValueError('DB owned row readback mismatch')
    intent.update(state='acknowledged',receipt=receipt,retention='retain exact run-owned rows; no DML substitution for UI; no implicit cascade cleanup');save(out,ledger.name,intent)
    return {k+'Id':receipt[k]['id'] for k in requested}


def prepare_data(selection,actor,out,requested,db_binding=None):
    """Stage-specific finite DAG; lack of category/bill setup cannot block owned-account reads."""
    out=Path(out);out.mkdir(parents=True,mode=0o700,exist_ok=True);ledger_path=out/'FIXTURE_DAG.json';client=FixtureClient(selection,out)
    ledger=load(ledger_path) if ledger_path.exists() else {'schemaVersion':'owned-fe-fixtures/1.0','subject':actor['subject'],'marker':actor['fixtures']['marker'],'state':'intent','accounts':[],'transactions':[],'maxNewAccounts':2,'maxNewTransactions':11,'fixtures':{},'retention':'retain acknowledged exact IDs where API cleanup unavailable; no replay','setupOnly':True}
    if ledger['subject']!=actor['subject']:raise ValueError('fixture actor drift')
    token=actor['setupToken'];marker=actor['fixtures']['marker'];save(out,ledger_path.name,ledger)
    requested=set(requested)
    need_accounts=2 if 'native-account' in requested else 1 if requested&{'owned-account','paged-transactions','expense-transaction'} else 0
    # Existing acknowledged fixtures are retained when a later allocation needs less.
    for label in ('Owned prerequisite','Owned native disposable')[len(ledger['accounts']):need_accounts]:
        number=str(secrets.randbelow(10**14)+10**14);body={'bank_name':label+' '+marker,'account_type':'Checking','branch_name':'Owned setup','account_number_full':number,'balance':1000}
        a=client.send('POST','/api/v1/accounts',body,token)['data']['account']
        if a['user_id']!=actor['subject'] or a['bank_name']!=body['bank_name']:raise ValueError('fixture account ownership mismatch')
        ledger['accounts'].append({'id':a['id'],'number':number,'body':body,'ack':a});save(out,ledger_path.name,ledger)
    account_ids=[a['id'] for a in ledger['accounts']];owner=client.send('GET','/api/v1/accounts',token=token)
    if owner['data']['user_id']!=actor['subject'] or not set(account_ids)<={x['id'] for x in owner['data']['accounts']}:raise ValueError('protected fixture collection ownership mismatch')
    if account_ids:ledger['fixtures']['ownedAccountId']=account_ids[0]
    if len(account_ids)>1:ledger['fixtures']['nativeAccountId']=account_ids[1]
    ledger.update(state='accounts-acknowledged',accountIds=account_ids);save(out,ledger_path.name,ledger)
    database_needs=({'category'} if requested&{'category','paged-transactions','expense-transaction'} else set())|({'bill'} if 'bill' in requested else set())
    if database_needs:
        if db_binding is None:raise ValueError('required DB fixture binding absent; independent branches remain open')
        existing=ledger.setdefault('database',{})
        missing={k for k in database_needs if k+'Id' not in existing}
        if missing:
            existing.update(db_prerequisites(db_binding,actor,selection,out,missing));ledger['fixtures'].update(existing);save(out,ledger_path.name,ledger)
        if 'category' in database_needs:
            options=client.send('GET','/api/v1/categories/options',token=token)['data']
            if not any(x['category_id']==existing['categoryId'] and x['name']==marker+'-category' for x in options):raise ValueError('category API readback mismatch')
            ledger['categoryOptions']=options
        if 'bill' in database_needs:
            bills=client.send('GET','/api/v1/bills',token=token)['data']['data']
            if not any(x['billId']==existing['billId'] and x['userId']==actor['subject'] for x in bills):raise ValueError('bill API readback mismatch')
            ledger['bills']=bills
        save(out,ledger_path.name,ledger)
    if set(requested)&{'paged-transactions','expense-transaction'}:
        target_count=11 if 'paged-transactions' in requested else max(1,len(ledger['transactions']))
        ledger['transactionTargetCount']=target_count
        for index in range(len(ledger['transactions']),target_count):
            body={'accountId':account_ids[0],'transactionDate':actor['fixtures']['today'],'type':'Revenue' if 'paged-transactions' in requested and index%2==0 else 'Expense','itemDescription':marker+'-page-'+str(index),'category_id':ledger['fixtures']['categoryId'],'shopName':'Owned setup merchant','amount':'1.00','paymentMethod':'Cash','status':'Complete'}
            result=client.send('POST','/api/v1/transactions',body,token)['data'];ledger['transactions'].append({'request':body,'ack':result});save(out,ledger_path.name,ledger)
        collection=client.send('GET','/api/v1/transactions?type=All&limit=10&offset=0',token=token)['data']
        if collection['total']!=len(ledger['transactions']) or 'paged-transactions' in requested and (not collection['hasMore'] or len(collection['data'])!=10):raise ValueError('transaction fixture readback mismatch')
        net=sum(float(t['request']['amount'])*(1 if t['request']['type']=='Revenue' else -1) for t in ledger['transactions'])
        balance=float(ledger['accounts'][0]['ack']['balance'])+net
        ledger['fixtures'].update(expectedBalanceAfterRevenue=round(balance+7.25,2),expectedBalanceAfterExpense=round(balance,2));ledger['transactionFirstPage']=collection
    ledger.update(state='acknowledged',readback={'accountCollection':owner});save(out,ledger_path.name,ledger);return ledger['fixtures']
