import copy
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.check = importlib.import_module('validate_decisions').validate_decisions
        self.materials = {'materials': [{'name': 'raw.csv', 'fragments': [{'locator': 'row:2', 'text': 'S01,10'}]}]}
        self.diagnosis = '## 优先问题\n| 编号 | 问题 |\n|---|---|\n| F1 | 缺货 |\n'
        self.plan = '## 现在／建议\n| 动作编号 | 关联问题 |\n|---|---|\n| A1 | F1 |\n'
        self.record = {'version': '1.0', 'goal': '改善经营贡献', 'scope': ['S01'],
            'baseline': [{'metric': '贡献', 'status': 'unknown', 'value': None, 'unit': '元', 'period': '本周', 'reason': '缺成本', 'evidence': [{'material': 'raw.csv', 'locator': 'row:2'}]}],
            'segments': [{'id': 'G1', 'members': ['S01'], 'basis': '本次仅一家门店，不作分层'}],
            'priorities': [{'finding_id': 'F1', 'segment_ids': ['G1'], 'why_now': '缺货影响接单',
                'evidence': [{'material': 'raw.csv', 'locator': 'row:2'}],
                'options': [{'strategy': '补货记录', 'status': 'selected', 'reason': '先识别时点'},
                            {'strategy': '增加广告', 'status': 'deferred', 'reason': '先确认承接'}],
                'action_ids': ['A1']}],
            'execution': {'status': 'unknown', 'evidence': [], 'review': '7天收执行人、范围、实际投入与同口径周表'}}

    def validate(self, record=None, plan=True):
        return self.check(self.record if record is None else record, self.materials, self.diagnosis, self.plan if plan else None)

    def test_valid_and_s4_without_action_plan(self):
        self.assertEqual([], self.validate())
        self.record['priorities'][0]['action_ids'] = []
        self.assertEqual([], self.validate(plan=False))

    def test_options_and_unknown_links_rejected(self):
        for field, value in [('options', [self.record['priorities'][0]['options'][0]]), ('finding_id', 'F99'), ('action_ids', ['A99']), ('segment_ids', ['G99'])]:
            record = copy.deepcopy(self.record)
            record['priorities'][0][field] = value
            with self.subTest(field=field): self.assertTrue(self.validate(record))

    def test_unknown_material_or_locator_rejected(self):
        for field, value in [('material', 'other.csv'), ('locator', 'row:99')]:
            record = copy.deepcopy(self.record)
            record['priorities'][0]['evidence'][0][field] = value
            self.assertTrue(self.validate(record))

    def test_partition_duplicate_or_missing_members(self):
        for members in [['S01', 'S01'], ['S99'], []]:
            record = copy.deepcopy(self.record)
            record['segments'][0]['members'] = members
            self.assertTrue(self.validate(record))

    def test_missing_values_and_execution_evidence(self):
        self.record['baseline'][0]['value'] = 0
        self.assertTrue(self.validate())
        self.record['baseline'][0]['status'] = 'known'
        self.assertEqual([], self.validate())
        self.record['execution']['status'] = 'executed'
        self.assertTrue(self.validate())

    def test_unmapped_actions_or_findings_rejected(self):
        self.diagnosis += '| F2 | 另一问题 |\n'
        self.assertTrue(self.validate())
        self.diagnosis = self.diagnosis.replace('| F2 | 另一问题 |\n', '')
        self.plan += '| A2 | F1 |\n'
        self.assertTrue(self.validate())

    def test_malformed_records_return_errors(self):
        for value in [None, [], {}, {'version': '1.0', 'priorities': [None]}, {**self.record, 'segments': 'bad'}, {**self.record, 'baseline': [None]}]:
            with self.subTest(value=value): self.assertTrue(self.validate(value if value is not None else []))

    def test_action_link_must_match_its_report_finding(self):
        self.plan = self.plan.replace('| A1 | F1 |', '| A1 | F9 |')
        self.assertTrue(self.validate())


if __name__ == '__main__':
    unittest.main()
