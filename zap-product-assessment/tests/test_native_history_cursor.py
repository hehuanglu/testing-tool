import unittest
from zap_assessment.product_native import read_history


class HistoryCursorTests(unittest.TestCase):
    class Zap:
        def __init__(self, drift=False, truncate=False):
            self.rows = [{'id': str(i)} for i in (1, 4, 7, 101, 114, 128)]
            self.starts, self.count_calls = [], 0
            self.drift, self.truncate = drift, truncate
        def call(self, component, kind, name, **args):
            if name == 'numberOfMessages':
                self.count_calls += 1
                return {name: str(len(self.rows) + int(self.drift and self.count_calls > 1))}
            self.starts.append(args['start'])
            offset = max(0, args['start'] - 1)
            rows = self.rows[offset:offset + args['count']]
            return {'messages': rows[:-1] if self.truncate else rows}

    def test_sparse_ids_use_one_based_record_position(self):
        zap = self.Zap()
        self.assertEqual(read_history(zap, 'http://owned', 2), zap.rows)
        self.assertEqual(zap.starts, [0, 3, 5])

    def test_boundaries_and_duplicate_pages(self):
        for count in (0,1,100,101,200,201):
            zap=self.Zap();zap.rows=[{'id':str(i*7+1)} for i in range(count)]
            self.assertEqual(read_history(zap,'http://owned'),zap.rows)
            self.assertEqual(zap.starts,[0]+list(range(101,count+1,100)) if count else [])
        zap=self.Zap();zap.rows[2]=zap.rows[1]
        with self.assertRaises(ValueError):read_history(zap,'http://owned',2)
        for size in (0,-1,True):
            with self.assertRaises(ValueError):read_history(self.Zap(),'http://owned',size)

    def test_drift_and_missing_page_fail_closed(self):
        for zap in (self.Zap(drift=True), self.Zap(truncate=True)):
            with self.assertRaises(ValueError):
                read_history(zap, 'http://owned', 2)

if __name__ == '__main__':
    unittest.main()
