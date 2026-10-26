#!/usr/bin/env python3
"""Create exactly two owned category fixtures when the app has no creation API.

The current user authorizes dedicated test data, not DB reset or existing-row
updates. DB credentials exist only in process memory/stdin. A network-restricted
one-shot client verifies actor identities and inserts two new rows in a transaction.
Never retries a write after an ambiguous ACK. No borrowed container exec/restart.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from zap_assessment.runtime import docker

SCRIPT=r"""
const mysql=require('/app/node_modules/mysql2/promise');let input='';
process.stdin.on('data',x=>input+=x);process.stdin.on('end',async()=>{
 let c;try{
 const x=JSON.parse(input);c=await mysql.createConnection({host:x.host,port:3306,user:x.username,password:x.password,database:x.database,connectTimeout:5000});
 await c.beginTransaction();
 const [users]=await c.execute('SELECT id,email FROM users WHERE id IN (?,?)',[x.actors.A.userId,x.actors.B.userId]);
 for(const a of Object.values(x.actors))if(!users.some(u=>u.id===a.userId&&u.email===a.email))throw Error('fixture actor identity mismatch');
 const [before]=await c.execute('SELECT id,user_id,name FROM categories WHERE user_id IN (?,?) ORDER BY id',[x.actors.A.userId,x.actors.B.userId]);
 if(before.some(r=>r.name.startsWith(x.prefix)))throw Error('prefix already exists; do not retry mutation');
 const made=[];
 for(const actor of ['A','B']){const a=x.actors[actor],name=x.prefix+'-'+actor;
 const [r]=await c.execute('INSERT INTO categories (user_id,name) VALUES (?,?)',[a.userId,name]);made.push({actor,id:r.insertId,user_id:a.userId,name});}
 const [after]=await c.execute('SELECT id,user_id,name FROM categories WHERE id IN (?,?) ORDER BY id',[made[0].id,made[1].id]);
 if(after.length!==2||!made.every(m=>after.some(r=>r.id===m.id&&r.user_id===m.user_id&&r.name===m.name)))throw Error('insert readback mismatch');
 await c.commit();console.log(JSON.stringify({executionStatus:'completed',created:made,readback:after,beforeIds:before.map(r=>r.id),existingRowsUpdated:0,existingRowsDeleted:0}));
 }catch(e){if(c)await c.rollback();console.log(JSON.stringify({executionStatus:'failed',errorType:e.name,message:'Category fixture transaction did not complete; inspect prefix before retry'}));process.exitCode=1;}
 finally{if(c)await c.end();}
});
"""

def meta(name):
    j=json.loads(docker(['inspect','--format','{"id":{{json .Id}},"image":{{json .Image}},"startedAt":{{json .State.StartedAt}},"running":{{json .State.Running}},"networks":{{json .NetworkSettings.Networks}},"project":{{json (index .Config.Labels "com.docker.compose.project")}}}',name]))
    if not j['running'] or j['project']!='finalsource-zap-test' or len(j['networks'])!=1:raise ValueError('test binding')
    n=next(iter(j.pop('networks').values()));return j|{'networkId':n['NetworkID'],'address':n['IPAddress']}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--receipt',type=Path,required=True);ap.add_argument('--credentials',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    receipt=json.loads(a.receipt.read_text())
    if receipt.get('environment')!='finalsource-zap-test' or not receipt.get('fixtureCreationAuthorized'):raise ValueError('dedicated fixture authority required')
    out=a.output.resolve();out.mkdir(mode=0o700);run='p0-category-'+uuid.uuid4().hex[:12];anchor=run+'-net';client=run+'-client'
    db=meta('finalsource-zap-test-database-1');back=meta('finalsource-zap-test-backend-1')
    if db['networkId']!=back['networkId']:raise ValueError('network mismatch')
    actors={k:{f:v for f,v in j.items() if f in ['userId','email']} for k,j in json.loads(a.credentials.read_text())['actors'].items() if k in ['A','B']}
    intent={'runId':run,'db':db,'backendImage':back['image'],'actors':{k:v['userId'] for k,v in actors.items()},'prefix':run,
            'mutation':'INSERT exactly two categories; transaction; no existing updates/deletes','sourceSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'at':time.time()}
    (out/'intent.json').write_text(json.dumps(intent,indent=2));(out/'source.py').write_bytes(Path(__file__).read_bytes())
    # Read only the exact DB fields in memory; never serialize/print the environment.
    env=json.loads(docker(['inspect','--format','{{json .Config.Env}}','finalsource-zap-test-backend-1']))
    env=dict(v.split('=',1) for v in env)
    payload={'host':db['address'],'username':env['DB_USERNAME'],'password':env['DB_PASSWORD'],'database':env['DB_DATABASE'],'actors':actors,'prefix':run};env.clear()
    baseline=json.loads((ROOT/'profiles/runtime-baseline.json').read_text());created={};result={}
    try:
        created[anchor]=docker(['run','-d','--name',anchor,'--label','zpa.run='+run,'--network',db['networkId'],'--cap-add','NET_ADMIN',baseline['boundary'],'sleep','180']).strip()
        for rule in ['iptables -P OUTPUT DROP','iptables -P INPUT DROP','ip6tables -P OUTPUT DROP','ip6tables -P INPUT DROP','iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT','iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT',f'iptables -A OUTPUT -p tcp -d {db["address"]} --dport 3306 -m owner --uid-owner 1004 -j ACCEPT']:
            docker(['exec',anchor,*rule.split()])
        (out/'firewall.txt').write_text(docker(['exec',anchor,'iptables-save']))
        created[client]=docker(['create','-i','--name',client,'--label','zpa.run='+run,'--network','container:'+anchor,'--cap-drop','ALL','--security-opt','no-new-privileges','--user','1004:1004','--entrypoint','node',back['image'],'-e',SCRIPT]).strip()
        (out/'resources.json').write_text(json.dumps(created,indent=2))
        r=subprocess.run(['docker','start','--attach','-i',client],input=json.dumps(payload).encode(),capture_output=True,timeout=20);payload.clear()
        (out/'client-output.txt').write_bytes(r.stdout);(out/'client-stderr.txt').write_bytes(r.stderr)
        if r.returncode:raise ValueError('fixture client failed; do not retry inserts')
        result=json.loads(r.stdout);(out/'result.json').write_text(json.dumps(result,indent=2))
        if result['executionStatus']!='completed':raise ValueError('fixture transaction failed')
    finally:
        removed=[]
        for name,cid in reversed(list(created.items())):
            j=json.loads(docker(['inspect',name]))[0]
            if j['Id']!=cid or j['Config']['Labels'].get('zpa.run')!=run:raise ValueError('cleanup ownership')
            if j['State']['Running']:docker(['stop','--timeout','2',name])
            docker(['rm',name]);removed.append(name)
        (out/'cleanup.json').write_text(json.dumps({'cleanupStatus':'clean','removed':removed,'retainedFixtureRows':result.get('created',[]),'targetContainerLifecycleUnmodified':True},indent=2))
        for f in out.iterdir():
            if f.is_file():f.chmod(0o600)
    print(json.dumps({'executionStatus':result.get('executionStatus'),'createdCategoryIds':{v['actor']:v['id'] for v in result.get('created',[])}}))

if __name__=='__main__':main()
