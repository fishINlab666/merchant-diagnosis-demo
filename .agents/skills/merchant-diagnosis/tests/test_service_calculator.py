import copy
import importlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
MATERIALS = {'materials': [{'name': '周表.csv', 'fragments': [
    {'locator': 'row:2', 'text': '收入,100'}, {'locator': 'row:3', 'text': '费用,80'}]}]}


def request(expression='income-cost', income=100, cost=80):
    return {'id':'C1', 'expression':expression, 'variables': {
        'income': {'value': income, 'evidence': [{'material':'周表.csv', 'locator':'row:2'}]},
        'cost': {'value':cost, 'evidence':[{'material':'周表.csv', 'locator':'row:3'}]}},
        'unit':'元', 'purpose':'判断是否继续追加预算'}


class CalculatorTests(unittest.TestCase):
    def calculate(self, requests, materials=MATERIALS):
        self.assertTrue((Path(__file__).resolve().parents[1] / 'scripts/service_calculator.py').exists(), 'calculator missing')
        return importlib.import_module('service_calculator').calculate_requests(requests, materials)

    def test_sourced_positive_and_negative_result(self):
        for cost, expected in ((80, 20), (150, -50)):
            req = request(cost=cost)
            before = copy.deepcopy(req)
            result = self.calculate([req])[0]
            self.assertEqual(expected, result['value'])
            self.assertEqual('ok', result['status'])
            self.assertEqual([], result['missing_variables'])
            for field in ('id','expression','variables','unit','purpose'):
                self.assertEqual(req[field], result[field])
            self.assertEqual(before, req)

    def test_missing_value_propagates_unknown_not_zero(self):
        result = self.calculate([request(cost=None)])[0]
        self.assertIsNone(result['value'])
        self.assertEqual('unknown', result['status'])
        self.assertEqual(['cost'], result['missing_variables'])
        self.assertEqual(100, self.calculate([request('income', cost=None)])[0]['value'])

    def test_assumption_is_explicit_and_retained(self):
        req = request()
        req['variables']['cost'] = {'value':80, 'evidence':[], 'assumption':'暂按每周费用80元测算'}
        result = self.calculate([req])[0]
        self.assertEqual([{'variable':'cost','assumption':'暂按每周费用80元测算'}], result['assumptions'])
        req['variables']['cost'].pop('assumption')
        with self.assertRaises(ValueError):
            self.calculate([req])

    def test_citations_must_reference_existing_locations(self):
        for evidence in ([{'material':'missing.csv','locator':'row:2'}],
                         [{'material':'周表.csv','locator':'row:999'}],
                         [{'material':'周表.csv','locator':'row:2 trailing text'}],
                         [{'material':'周表.csv','locator':'row:2-999'}]):
            req = request()
            req['variables']['income']['evidence'] = evidence
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                self.calculate([req])
        req = request()
        req['variables']['income']['evidence'][0]['locator'] = 'row:2-3'
        self.assertEqual(20, self.calculate([req])[0]['value'])

    def test_decimal_arithmetic_and_allowed_functions(self):
        cases = {'income+cost':0.3, '-income + +cost':0.1, 'mean(income,cost)':0.15,
                 'sum(income,cost)':0.3, 'max(income,cost)-min(income,cost)':0.1,
                 'abs(income-cost)':0.1, 'round(income/cost,2)':0.5}
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertEqual(expected, self.calculate([request(expression, .1, .2)])[0]['value'])

    def test_decimal_literal_retains_its_written_precision(self):
        result = self.calculate([request('0.100000000000000005 - 0.1')])[0]
        self.assertEqual(5e-18, result['value'])

    def test_round_uses_financial_half_up(self):
        for value, expected in ((2.345, 2.35), (-2.345, -2.35)):
            self.assertEqual(expected, self.calculate([request('round(income,2)', value)])[0]['value'])

    def test_division_by_zero_is_unavailable(self):
        result = self.calculate([request('income/cost', cost=0)])[0]
        self.assertEqual('error', result['status'])
        self.assertIsNone(result['value'])

    def test_arbitrary_code_and_unsupported_syntax_rejected(self):
        for expression in ('__import__("os").system("echo bad")','income.real', 'income[0]', '2**100000',
                           '[income for x in cost]', 'sum([income,cost])', 'income < cost', 'True', 'missing+1',
                           'round(income, cost=2)', 'lambda:1'):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                self.calculate([request(expression)])

    def test_nonfinite_bool_and_large_numbers_rejected(self):
        for value in (True, '100', float('nan'), float('inf'), 10**101):
            with self.subTest(value=str(value)[:20]), self.assertRaises(ValueError):
                self.calculate([request(income=value)])
        for expression in ('1e999', '9'*200, '+'*50+'income'):
            with self.assertRaises(ValueError):
                self.calculate([request(expression)])

    def test_duplicate_ids_and_batch_size_rejected(self):
        with self.assertRaises(ValueError):
            self.calculate([request(),request()])
        batch = [dict(request(), id='C'+str(i)) for i in range(101)]
        with self.assertRaises(ValueError):
            self.calculate(batch)


if __name__ == '__main__':
    unittest.main()
