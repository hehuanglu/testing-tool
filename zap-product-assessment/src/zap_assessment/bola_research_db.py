"""Narrow local-test prerequisite provisioning. Never receives DB credentials."""
import json, subprocess
from .research_product import docker,TARGET
from . import bola_research as br

DB='finalsource-zap-test-database-1'
SCRIPT=r'''
const mysql=require('/app/node_modules/mysql2/promise'),dns=require('dns').promises;
let input='';process.stdin.on('data',x=>input+=x);process.stdin.on('end',async()=>{let c;try{
const x=JSON.parse(input),host=process.env.DB_HOST;
const resolved=await dns.lookup(host,{all:true});
if(!resolved.some(r=>r.address===x.address)||Number(process.env.DB_PORT||3306)!==3306)throw Error('binding');
c=await mysql.createConnection({host,port:3306,user:process.env.DB_USERNAME,password:process.env.DB_PASSWORD,database:process.env.DB_DATABASE,connectTimeout:5000,dateStrings:true});
const [[identity]]=await c.query('SELECT @@server_uuid AS serverUuid,DATABASE() AS databaseName');
if(x.uuid&&identity.serverUuid!==x.uuid)throw Error('server uuid drift');
if(x.mode==='preflight'){
 const [columns]=await c.query("SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('users','accounts','transactions','categories','goals','bills') ORDER BY TABLE_NAME,ORDINAL_POSITION");
 const [relations]=await c.query("SELECT TABLE_NAME,COLUMN_NAME,REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL");
 console.log(JSON.stringify({identity,resolved,columns,relations}));return;
}
const ids=['A','B'].map(a=>x.actors[a].subject);
if(ids.length!==2||ids[0]===ids[1]||ids.some(i=>!Number.isSafeInteger(i)||i<1))throw Error('actors');
const [users]=await c.execute('SELECT id,email FROM users WHERE id IN (?,?)',ids);
for(const a of Object.values(x.actors))if(!users.some(u=>u.id===a.subject&&u.email===a.email))throw Error('actor provenance');
if(x.mode==='provision'){
 await c.beginTransaction();const made=[];
 for(const actor of ['A','B']){const uid=x.actors[actor].subject,name=x.prefix+'-'+actor;
 const [[n]]=await c.execute('SELECT COUNT(*) AS n FROM categories WHERE user_id=?',[uid]);if(n.n!==0)throw Error('fresh categories required');
 const [r]=await c.execute('INSERT INTO categories (user_id,name) VALUES (?,?)',[uid,name]);made.push({table:'categories',actor,id:r.insertId,user_id:uid,name});
 const [b]=await c.execute('INSERT INTO bills (user_id,item_description,logo_url,due_date,last_charge_date,amount) VALUES (?,?,?,?,?,?)',[uid,name+'-bill','https://example.test/logo',x.due,x.last,actor==='A'?'17.2500':'38.7500']);made.push({table:'bills',actor,id:b.insertId,user_id:uid,item_description:name+'-bill'});
 }await c.commit();console.log(JSON.stringify({created:made,identity}));return;
}
if(x.mode==='cleanup-bills'){
 const deleted=[];for(const r of x.rows){if(r.table!=='bills'||!ids.includes(r.user_id)||!Number.isSafeInteger(r.id))throw Error('cleanup allowlist');
 const [d]=await c.execute('DELETE FROM bills WHERE id=? AND user_id=? AND item_description=?',[r.id,r.user_id,r.item_description]);deleted.push({id:r.id,affected:d.affectedRows});}
 console.log(JSON.stringify({deleted}));return;
}
if(x.mode!=='observe')throw Error('mode');
const result={};
for(const [table,sql] of Object.entries({
 accounts:'SELECT id,user_id,bank_name,balance FROM accounts WHERE user_id IN (?,?) ORDER BY id',
 categories:'SELECT id,user_id,name FROM categories WHERE user_id IN (?,?) ORDER BY id',
 transactions:'SELECT t.id,t.account_id,t.category_id,t.type,t.amount,t.status,t.item_description,t.transaction_date FROM transactions t LEFT JOIN accounts a ON a.id=t.account_id LEFT JOIN categories c ON c.id=t.category_id WHERE a.user_id IN (?,?) OR c.user_id IN (?,?) ORDER BY t.id',
 goals:'SELECT id,user_id,goal_type,category_id,target_amount,start_date,end_date FROM goals WHERE user_id IN (?,?) ORDER BY id',
 bills:'SELECT id,user_id,item_description,amount,due_date FROM bills WHERE user_id IN (?,?) ORDER BY id'
})){
const [rows]=await c.execute(sql,table==='transactions'?[...ids,...ids]:ids);if(rows.length>80)throw Error('observation row budget');result[table]=rows;
}
const [[absent]]=await c.query('SELECT (SELECT COUNT(*) FROM accounts WHERE id=2147483647)+(SELECT COUNT(*) FROM categories WHERE id=2147483647) AS n');
if(absent.n!==0)throw Error('nonexistent control occupied');
console.log(JSON.stringify(result));
}catch(e){if(c)await c.rollback();console.log(JSON.stringify({error:'fixture DB operation failed; no retry',errorType:e.name}));process.exitCode=2;}finally{if(c)await c.end();}});
'''

def metadata(name):
    return json.loads(docker('inspect','--format','{"id":{{json .Id}},"image":{{json .Image}},"running":{{json .State.Running}},"networks":{{json .NetworkSettings.Networks}}}',name))

class FixtureDB:
    def __init__(self,out,backend):
        self.out=out;self.backend=backend;db=metadata(DB)
        n=[n for n in db['networks'].values() if n['NetworkID']==backend['networkId']]
        if not db['running'] or len(n)!=1:raise ValueError('DB network binding')
        self.address=n[0]['IPAddress'];self.uuid=None
        observed=self.call('preflight')
        # Independent query inside the selected DB container; secret stays in its environment.
        script='MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot -N -e "SELECT @@server_uuid"'
        expected=docker('exec',DB,'sh','-c',script)
        if observed['identity']['serverUuid']!=expected:raise ValueError('DB server identity mismatch')
        self.uuid=expected
        required={'categories':{'id','user_id','name'},'bills':{'id','user_id','item_description','logo_url','due_date','last_charge_date','amount'},'transactions':{'id','account_id','category_id','amount','status'},'goals':{'id','user_id','category_id'}}
        for t,cols in required.items():
            if not cols<={r['COLUMN_NAME'] for r in observed['columns'] if r['TABLE_NAME']==t}:raise ValueError('DB schema drift')
        rels={(r['TABLE_NAME'],r['COLUMN_NAME'],r['REFERENCED_TABLE_NAME']) for r in observed['relations']}
        if not {('categories','user_id','users'),('bills','user_id','users'),('transactions','account_id','accounts'),('transactions','category_id','categories'),('goals','category_id','categories')}<=rels:raise ValueError('DB relations drift')
        self.pin={'databaseContainer':db['id'],'image':db['image'],'networkId':backend['networkId'],'address':self.address,'proof':observed,'independentServerUuid':expected}
        br.save(out,'DB_BINDING.json',self.pin)
        br.save(out,'DB_ALLOWLIST.json',{'writes':{'categories':['user_id','name'],'bills':['user_id','item_description','logo_url','due_date','last_charge_date','amount']},'insertBudget':4,'updates':0,'cleanup':'bills only exact id+owner+marker from provisioning ledger; categories retained if goals reference them','reads':'selected fixture columns scoped to two fresh verified user IDs; max80 rows/table; users id/email identity check output omitted','binding':'backend configured DB_HOST resolves selected container network IP; configured DB connection @@server_uuid equals independent DB-container query; schema/FKs verified before writes'})
    def call(self,mode,**kw):
        payload={'mode':mode,'address':self.address,'uuid':self.uuid,**kw}
        r=subprocess.run(['docker','exec','-i',TARGET,'node','-e',SCRIPT],input=json.dumps(payload).encode(),capture_output=True,timeout=15)
        if r.returncode:raise ValueError('fixture DB operation failed; no replay; diagnostic withheld')
        value=json.loads(r.stdout)
        if 'error' in value:raise ValueError('fixture DB rejected')
        return value
