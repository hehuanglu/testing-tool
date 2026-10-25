import unittest
from zap_assessment.bola_research import project_response
from zap_assessment.product_checks import check_case
from zap_assessment.recipes.spring_orders import CAPTURE_FIELDS


class SpringErrorProjectionTests(unittest.TestCase):
    def test_full_error_envelope_and_denial_oracle(self):
        error = {'status': 404, 'code': 'CART_ITEM_NOT_FOUND', 'message': 'missing',
                 'path': '/api/cart/items/2', 'fieldErrors': [{'field': 'quantity', 'message': 'invalid'}]}
        body, complete = project_response(error, CAPTURE_FIELDS, [])
        self.assertTrue(complete)
        self.assertEqual(body, error)
        observed = {'response': {'status': 404, 'body': body}, 'before': {'quantity': 1},
                    'after': {'quantity': 1}, 'disclosed': False, 'captureComplete': complete}
        expected = {'access': 'deny', 'denialStatuses': [404]}
        self.assertEqual(check_case(expected, observed)['outcome'], 'matched')
        observed['after'] = {'quantity': 2}
        self.assertIn('side-effect-after-denial', check_case(expected, observed)['reasons'])
        observed['after'] = observed['before']
        observed['disclosed'] = True
        self.assertEqual(check_case(expected, observed)['outcome'], 'violated')

    def test_empty_field_errors_are_complete(self):
        self.assertTrue(project_response({'fieldErrors':[]},CAPTURE_FIELDS,[])[1])

    def test_unknown_outer_and_nested_fields_still_inconclusive(self):
        for body in ({'fieldErrors': [], 'unreviewed': 'value'},
                     {'fieldErrors': [{'field': 'quantity', 'unreviewed': 'value'}]}):
            projected, complete = project_response(body, CAPTURE_FIELDS, [])
            self.assertFalse(complete)
            observed = {'response': {'status': 404, 'body': projected}, 'before': {}, 'after': {},
                        'disclosed': False, 'captureComplete': complete}
            self.assertEqual(check_case({'access': 'deny', 'denialStatuses': [404]}, observed)['outcome'], 'inconclusive')

if __name__ == '__main__':
    unittest.main()
