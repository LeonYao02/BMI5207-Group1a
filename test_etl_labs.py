import unittest
from etl_labs import parse_result
class TestResultParser(unittest.TestCase):
    def test_inequality(self):
        self.assertEqual(parse_result('<2.0'),(2.0,'<','INEQUALITY'))
    def test_numeric(self):
        self.assertEqual(parse_result('5.8'),(5.8,'','NUMERIC'))
    def test_text(self):
        self.assertEqual(parse_result('Non-Reactive'),('','','TEXT'))
if __name__=='__main__': unittest.main()
