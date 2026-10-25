"""Recipe integration with a state stub; this is NOT an example deployment/runtime proof."""
import copy
import unittest
from zap_assessment.recipes.spring_fixtures import exercise

class StateStub:
    def __init__(self):self.stock=20;self.items=[];self.orders={};self.calls=[];self.id=0
    def request(self,label,actor,req,permission):
        self.calls.append((label,actor,copy.deepcopy(req),permission));oid=req['operationRef'];b=req['body'];status=200
        if oid=='food.read':value={'id':3,'stockQuantity':self.stock,'name':'test meal','price':'2.50'}
        elif oid=='cart.read':value={'userId':7,'items':copy.deepcopy(self.items)}
        elif oid=='cart.add':
            self.id+=1;self.items=[{'id':self.id,'food':{'id':3},'quantity':b['quantity']}];value={'userId':7,'items':copy.deepcopy(self.items)}
        elif oid=='cart.update':self.items[0]['quantity']=b['quantity'];value={'userId':7,'items':copy.deepcopy(self.items)}
        elif oid=='cart.remove':self.items=[];value={'userId':7,'items':[]}
        elif oid=='order.create':
            self.id+=1;q=self.items[0]['quantity'];self.stock-=q;self.items=[]
            value={'id':self.id,'userId':7,'status':'PENDING','orderType':b['orderType'],'items':[{'foodId':3,'foodName':'test meal','unitPrice':'2.50','quantity':q,'lineTotal':str(2.5*q)}],'totalAmount':str(2.5*q)}
            self.orders[self.id]=copy.deepcopy(value);status=201
        elif oid=='order.read':value=copy.deepcopy(self.orders[int(req['path'].split('/')[-1])])
        elif oid=='order.cancel':
            v=self.orders[int(req['path'].split('/')[-1])]
            if v['status']=='CANCELLED':status=409;value={'status':409}
            else:v['status']='CANCELLED';self.stock+=v['items'][0]['quantity'];value=copy.deepcopy(v)
        else:raise AssertionError('undeclared operation')
        return status,value,'owned-stub/'+label+'.json'

class SpringRecipeTests(unittest.TestCase):
    def test_dag_two_checkout_types_and_retained_cancel_exact_ledger(self):
        client=StateStub();revisions=[]
        result=exercise(client,{'customer':{'subject':'7'}},{'runId':'run','dedicated':True,'creationEvidence':'fresh owned fixture','quantity':2,'foodId':3,'ownerRef':'customer'},'run',lambda rows:revisions.append(copy.deepcopy(rows)))
        self.assertEqual(client.stock,20);self.assertEqual(client.items,[]);self.assertEqual(len(client.orders),2)
        self.assertEqual({o['orderType'] for o in client.orders.values()},{'DINE_IN','DELIVERY'})
        self.assertTrue(all(c['checkoutMatched'] and c['cancelMatched'] for c in result['checks']))
        self.assertEqual([r['state'] for r in result['ledger'] if r['kind']=='order'],['CANCELLED','CANCELLED'])
        self.assertGreater(len(revisions),4);self.assertTrue(all(r['runId']=='run' for r in result['ledger']))
        self.assertIn('cart.remove',{c[2]['operationRef'] for c in client.calls})
    def test_catalog_foreign_ownership_no_traffic(self):
        c=StateStub()
        with self.assertRaises(ValueError):exercise(c,{}, {'runId':'foreign'},'run',lambda r:None)
        self.assertEqual(c.calls,[])
    def test_lost_ack_checkout_no_second_mutation(self):
        class Lost(StateStub):
            def request(self,*args):
                result=super().request(*args)
                if args[2]['operationRef']=='order.create':raise TimeoutError('unknown ACK')
                return result
        c=Lost();revisions=[]
        with self.assertRaises(TimeoutError):exercise(c,{'customer':{'subject':'7'}},{'runId':'run','dedicated':True,'creationEvidence':'created','quantity':2,'foodId':3,'ownerRef':'customer'},'run',lambda r:revisions.append(copy.deepcopy(r)))
        self.assertEqual(len([v for v in c.calls if v[2]['operationRef']=='order.create']),1)
        self.assertEqual(len(c.orders),1);self.assertTrue(revisions)

if __name__=='__main__':unittest.main()
