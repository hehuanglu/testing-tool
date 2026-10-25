"""ByteMe mappings stay in the adapter; shared helpers contain no product fields."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from zap_assessment.product_scope import reconcile

PATH=Path(__file__).resolve().parents[2]/'adapters/byteme/ownership/operate.py'


class ByteMeAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        previous_umask=os.umask(0o077)
        cls.addClassCleanup(os.umask,previous_umask)
        spec=importlib.util.spec_from_file_location('byteme_ownership_adapter',PATH)
        cls.adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.adapter)
        base=PATH.parents[1]
        for attr,relative in [('anonymous','anonymous/run.py'),('authenticated','authenticated/operate.py')]:
            spec=importlib.util.spec_from_file_location('byteme_'+attr+'_adapter',base/relative)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);setattr(cls,attr,module)

    def test_shared_stock_is_separate_from_cart_owner_item_and_quantity(self):
        before=dict(id=10,userId=20,items=[dict(id=30,quantity=3,food=dict(id=40,name='shared',stockQuantity=100))])
        after=copy.deepcopy(before);after['items'][0]['food']['stockQuantity']-=2
        check=self.adapter.foreign_cart_checkout_checks
        self.assertTrue(all(check(before,after,40,2).values()))
        for dimension in ('owner','item','quantity','food','stock'):
            bad=copy.deepcopy(after)
            if dimension=='owner':bad['userId']=21
            elif dimension=='item':bad['items'][0]['id']=31
            elif dimension=='quantity':bad['items'][0]['quantity']=4
            elif dimension=='food':bad['items'][0]['food']['id']=41
            else:bad['items'][0]['food']['stockQuantity']-=1
            self.assertFalse(all(check(before,bad,40,2).values()),dimension)

    def test_pagination_group_resolves_to_real_child_request_ids_before_recording(self):
        a=self.adapter;original=a.ROOT
        with tempfile.TemporaryDirectory() as tmp:
            a.ROOT=Path(tmp)
            try:
                (a.ROOT/'http').mkdir();a.save('cases.json',[]);a.save('observations.json',{})
                for page in (0,1,2):a.save(f'http/query-page-{page}.json',dict(id=f'query-page-{page}',state='acknowledged'))
                a.mark('collection','CUSTOMER','pagination','query',{'pages-read':True})
                self.assertEqual(a.load('cases.json')[0]['operationIds'],['query-page-0','query-page-1','query-page-2'])
                with self.assertRaises(ValueError):a.mark('collection','CUSTOMER','pagination','missing',{'pages-read':True})
            finally:a.ROOT=original

    def test_anonymous_new_source_input_survives_an_old_workload(self):
        spec={'components':{'schemas':{'Request':{'properties':{'title':{'type':'string'},'newInput':{'type':'string'}}}}}}
        operations=[dict(id='public-create',method='POST',path='/things',protected=False,input=[],body={'content':{'application/json':{'schema':{'$ref':'#/components/schemas/Request'}}}})]
        inventory=self.anonymous.source_inventory(spec,operations);case=inventory['cases'][0]
        self.assertIn('source-input:JSON-body:newInput',case['requiredEvidence'])
        seen={'source:public-create':dict(role='anonymous',outcome='matched',resultRead=True,evidenceUnits=['source-active-result-read','source-input:JSON-body:title'])}
        result=reconcile(inventory,seen,{})
        self.assertEqual(result['taskCompletion'],'partial');self.assertTrue(result['nextActions'])

    def test_authenticated_inventory_comes_from_schema_before_campaigns(self):
        a=self.authenticated;original=a.ROOT
        spec={'components':{'schemas':{'Request':{'properties':{'description':{'type':'string'},'amount':{'type':'integer'},'newInput':{'type':'string'}}}}}}
        op=dict(id='edit',method='PUT',pathTemplate='/things/{id}',protected=True,roles=['ROLE_A','ROLE_B'],parameters=[],requestBody={'content':{'application/json':{'schema':{'$ref':'#/components/schemas/Request'}}}})
        with tempfile.TemporaryDirectory() as tmp:
            a.ROOT=Path(tmp)
            try:
                a.build_responsibilities(spec,[op]);needs=a.load('responsibilities.json')
                for role in op['roles']:
                    self.assertEqual({r['field'] for r in needs if r['role']==role},{'description','amount','newInput','selector'})
                    self.assertTrue(next(r for r in needs if r['role']==role and r['field']=='newInput')['requiresAcceptedMutation'])
            finally:a.ROOT=original

    def test_fixture_forecast_uses_prior_selected_creates_without_a_pass_threshold(self):
        a=self.anonymous;original=a.ROOT
        with tempfile.TemporaryDirectory() as tmp:
            a.ROOT=Path(tmp);(a.ROOT/'guard-private').mkdir()
            rows=[dict(status=201,path='/api/auth/register',campaign='register-fullName',technique='ZAP active',ruleId=r) for r in ('40018','40003')]+[dict(kind='fixture-register',status=201)]
            (a.ROOT/'guard-private/traffic.jsonl').write_text('\n'.join(json.dumps(r) for r in rows))
            try:
                forecast=a.fixture_forecast();self.assertEqual(forecast['estimatedAccountCreates'],2)
                self.assertNotIn('pass',forecast);self.assertNotIn('taskCompletion',forecast)
            finally:a.ROOT=original


if __name__=='__main__':unittest.main()
