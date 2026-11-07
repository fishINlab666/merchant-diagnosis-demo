"""Structured report checks; fixtures are synthetic, not merchant evidence."""
import copy
import importlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


def materials():
    return {'materials': [{'name': 'weekly.csv', 'sha256': 'a' * 64,
                          'fragments': [{'locator': 'row:2', 'text': '实收100；老板说成本40'}]}]}


def citation():
    return [{'material': 'weekly.csv', 'locator': 'row:2'}]


def request(identifier='c1', unknown=False):
    return {'id': identifier, 'expression': 'income-cost', 'variables': {
        'income': {'value': 100, 'evidence': citation()},
        'cost': {'value': None if unknown else 40,
                 'assumption': '成本未提供'} if unknown else {'value': 40, 'evidence': citation()}},
        'unit': '元', 'purpose': '按老板已明确口径计算经营贡献'}


def report():
    return {'merchant': {'name': '测试店', 'scope': '单店', 'period': '本周', 'synthetic': True},
            'headline': '先检查高峰包装，已有数据支持小范围试行。',
            'money': {'label': '本周经营贡献', 'calc_id': 'c1', 'unit': '元', 'period': '本周',
                      'note': '采用老板已说明成本；不是净利润。', 'basis': '实收减已说明成本'},
            'findings': [{'title': '高峰包装值得先查', 'detail': '先按现有证据试行。',
                          'basis': '本次周报', 'evidence': citation()}],
            'actions': [{'title': '抽查高峰包装', 'owner': '店长', 'timing': '明天开始',
                         'budget': '现有人手', 'success': '记录问题次数', 'stop': '影响出餐就停止'}],
            'followup': {'when': '一周后', 'collect': '问题次数与执行回执', 'decision': '决定是否扩大'},
            'charts': [{'type': 'bar', 'title': '经营贡献', 'unit': '元', 'caption': '本周已说明口径',
                        'series': [{'label': '当前', 'calc_id': 'c1'}]}],
            'analysis': {'goal': '改善体验', 'chosen_strategy': '小范围包装试行',
                         'alternatives': ['暂无广告问题，不选择加投'],
                         'execution': '建议，尚未执行', 'assumptions': []}, 'gaps': []}


class QuickContractTests(unittest.TestCase):
    def contract(self):
        self.assertIsNotNone(importlib.util.find_spec('quick_contract'), 'quick contract missing')
        return importlib.import_module('quick_contract')

    def calculations(self, unknown=False):
        from service_calculator import calculate_requests
        return calculate_requests([request(unknown=unknown)], materials())

    def test_computed_values_bound_once_without_model_copy_or_ids(self):
        original = report()
        original['money']['value'] = 999
        result = self.contract().bind_report(original, materials(), self.calculations())
        self.assertEqual(60, result['money']['value'])
        self.assertEqual(60, result['charts'][0]['series'][0]['value'])
        self.assertEqual(999, original['money']['value'])
        self.assertNotIn('id', result['actions'][0])

    def test_unknown_cost_preserves_actions_and_null(self):
        result = self.contract().bind_report(report(), materials(), self.calculations(True))
        self.assertIsNone(result['money']['value'])
        self.assertIsNone(result['charts'][0]['series'][0]['value'])
        self.assertEqual('抽查高峰包装', result['actions'][0]['title'])

    def test_reject_forged_calculation_error_and_unit_mismatch(self):
        for mutation in ('missing', 'error', 'unit'):
            with self.subTest(mutation=mutation):
                values = self.calculations()
                if mutation == 'missing':
                    values = []
                elif mutation == 'error':
                    values[0]['status'] = 'error'
                else:
                    values[0]['unit'] = '万元'
                with self.assertRaises(ValueError):
                    self.contract().bind_report(report(), materials(), values)

    def test_main_money_cannot_bypass_calculator_with_value(self):
        value = report()
        value['money'].pop('calc_id')
        value['money'].update(value=60, evidence=citation())
        with self.assertRaises(ValueError):
            self.contract().bind_report(value, materials(), [])

    def test_main_money_rejects_constants_even_with_unused_sourced_variable(self):
        from service_calculator import calculate_requests
        for expression, variables in [('123', {}), ('sum(100,20)', {}),
                                      ('123', request()['variables'])]:
            item = request()
            item.update(expression=expression, variables=variables)
            values = calculate_requests([item], materials())
            with self.subTest(expression=expression, variables=bool(variables)), self.assertRaisesRegex(ValueError, '变量'):
                self.contract().bind_report(report(), materials(), values)

    def test_main_money_keeps_conversion_constants_and_explicit_assumptions(self):
        from service_calculator import calculate_requests
        for expression, variables, expected in [
            ('income*10000-cost', request()['variables'], 999960),
            ('estimate*10000', {'estimate': {'value': 2, 'assumption': '建议试行上限，待验证'}}, 20000)]:
            item = request()
            item.update(expression=expression, variables=variables)
            values = calculate_requests([item], materials())
            result = self.contract().bind_report(report(), materials(), values)
            self.assertEqual(expected, result['money']['value'])

    def test_public_only_report_can_finish_without_numeric_claim(self):
        value = report()
        value['money'].pop('calc_id')
        value['money']['value'] = None
        value['charts'] = []
        result = self.contract().bind_report(value, materials(), [])
        self.assertIsNone(result['money']['value'])

    def test_optional_copy_and_chart_alias_are_normalized_without_model_retry(self):
        value = report()
        value['money'].pop('note')
        value['charts'][0]['type'] = 'bars'
        value['charts'][0].pop('caption')
        value['findings'][0].pop('basis')
        value['followup']['collect'] = '一份执行回执'
        result = self.contract().bind_report(value, materials(), self.calculations())
        self.assertEqual('bar', result['charts'][0]['type'])
        self.assertEqual('', result['money']['note'])
        self.assertEqual(['一份执行回执'], result['followup']['collect'])

    def test_extreme_integer_fails_with_controlled_validation_error(self):
        value = report()
        value['charts'][0]['series'] = [{'label': '异常', 'value': 10 ** 400, 'evidence': citation()}]
        with self.assertRaises(ValueError):
            self.contract().bind_report(value, materials(), self.calculations())

    def test_only_existing_citations_and_unique_basename_are_accepted(self):
        value = report()
        value['findings'][0]['evidence'][0]['material'] = '/local/weekly.csv'
        result = self.contract().bind_report(value, materials(), self.calculations())
        self.assertEqual('weekly.csv', result['findings'][0]['evidence'][0]['material'])
        for source, locator in [('other.csv', 'row:2'), ('weekly.csv', 'row:900')]:
            value['findings'][0]['evidence'] = [{'material': source, 'locator': locator}]
            with self.assertRaises(ValueError):
                self.contract().bind_report(value, materials(), self.calculations())

    def test_chart_raw_number_requires_source_and_finite_number(self):
        for number in (True, float('nan'), float('inf'), 100):
            value = report()
            value['charts'][0]['series'] = [{'label': '实收', 'value': number}]
            with self.subTest(number=number), self.assertRaises(ValueError):
                self.contract().bind_report(value, materials(), self.calculations())
        value['charts'][0]['series'][0]['evidence'] = citation()
        result = self.contract().bind_report(value, materials(), self.calculations())
        self.assertEqual(100, result['charts'][0]['series'][0]['value'])

    def test_parse_direct_wrapper_and_fence_but_reject_duplicate_or_nonfinite(self):
        module = self.contract()
        for value in (report(), {'kind': 'final', 'report': report()},
                      '```json\n' + json.dumps({'kind': 'final', 'report': report()}) + '\n```'):
            self.assertEqual(report(), module.parse_report(value))
        for value in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}', 'prefix {} suffix'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.parse_report(value)

    def test_required_business_actions_and_merchant_identity_are_not_repaired(self):
        for mutate in ('action', 'followup', 'merchant', 'strategy'):
            value = report()
            if mutate == 'action':
                value['actions'][0]['stop'] = ''
            elif mutate == 'followup':
                value['followup']['decision'] = ''
            elif mutate == 'strategy':
                value['analysis']['chosen_strategy'] = ''
            else:
                value['merchant']['name'] = '另一个商家'
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                self.contract().bind_report(value, materials(), self.calculations(),
                                            expected_merchant=report()['merchant'])


if __name__ == '__main__':
    unittest.main()
