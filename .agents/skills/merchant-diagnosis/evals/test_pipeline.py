import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from file_readers import read_table_file
from pipeline import InputError, apply_mappings, calculate_scenario, map_tables, public_diagnosis, run_pipeline
from llm_client import LlmError, LlmResult


def mapping_for(path, grain, fields):
    return {'file_name': Path(path).name, 'sheet_name': 'Sheet1', 'grain': grain, 'fields': fields}


class PipelineTest(unittest.TestCase):
    def test_reads_csv_and_applies_ai_header_mapping_to_real_cells(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'weekly.csv'
            path.write_text('门店编号,周期,成交单量,GMV（元）,商家让利,推广产品,消耗金额,归因成交\nS1,2026-10-12,1200,"60,000",4000,搜索推广,800,14400\n', encoding='utf-8-sig')
            previews = read_table_file(path)
            ai_result = {
                'mappings': [mapping_for(path, 'store_week_tools', {
                    'store_id': '门店编号', 'week_start': '周期', 'orders': '成交单量', 'net_gmv': 'GMV（元）',
                    'merchant_subsidy': '商家让利', 'tool_name': '推广产品', 'spend': '消耗金额', 'attributed_gmv': '归因成交',
                })],
                'missing_fields': [],
                'notes': '工具粒度',
            }
            report = apply_mappings(previews, ai_result)
            self.assertEqual(report['store_id'], 'S1')
            self.assertEqual(report['orders'], 1200)
            self.assertEqual(report['net_gmv'], 60000)
            self.assertEqual(report['tools'][0]['tool_name'], '搜索推广')
            self.assertEqual(report['tools'][0]['roi'], 18)

    def test_reads_xlsx_multiple_sheets_and_merges_summary_with_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.xlsx'
            workbook = Workbook()
            summary = workbook.active
            summary.title = '门店周报'
            summary.append(['store', 'week', 'orders', 'gmv', 'subsidy'])
            summary.append(['S1', '2026-10-12', 1200, 60000, 4000])
            tools = workbook.create_sheet('推广明细')
            tools.append(['tool', 'cost', 'attributed'])
            tools.append(['搜索推广', 800, 14400])
            workbook.save(path)
            previews = read_table_file(path)
            ai_result = {
                'mappings': [
                    {'file_name': path.name, 'sheet_name': '门店周报', 'grain': 'store_week', 'fields': {'store_id': 'store', 'week_start': 'week', 'orders': 'orders', 'net_gmv': 'gmv', 'merchant_subsidy': 'subsidy'}},
                    {'file_name': path.name, 'sheet_name': '推广明细', 'grain': 'store_week_tools', 'fields': {'tool_name': 'tool', 'spend': 'cost', 'attributed_gmv': 'attributed'}},
                ],
                'missing_fields': [],
            }
            report = apply_mappings(previews, ai_result)
            self.assertEqual(report['net_gmv'], 60000)
            self.assertEqual(report['tools'][0]['spend'], 800)
            self.assertEqual(report['tools'][0]['attributed_gmv'], 14400)

    def test_unknown_tool_sheet_can_only_inherit_a_unique_store_and_week_with_warning(self):
        previews = [
            {'file_name': 'summary.csv', 'sheet_name': 'Sheet1', 'headers': ['store', 'period', 'orders'], 'rows': [['S1', '2026-10-12', 1200]]},
            {'file_name': 'tools.csv', 'sheet_name': 'Sheet1', 'headers': ['campaign', 'cost', 'attributed'], 'rows': [['搜索推广', 800, 14400]]},
        ]
        report = apply_mappings(previews, {
            'mappings': [
                {'file_name': 'summary.csv', 'sheet_name': 'Sheet1', 'grain': 'store_week', 'fields': {'store_id': 'store', 'week_start': 'period', 'orders': 'orders'}},
                {'file_name': 'tools.csv', 'sheet_name': 'Sheet1', 'grain': 'unknown', 'fields': {'tool_name': 'campaign', 'spend': 'cost', 'attributed_gmv': 'attributed'}},
            ],
            'missing_fields': [],
        })
        self.assertEqual(report['tools'][0]['tool_name'], '搜索推广')
        self.assertIn('唯一门店', ' '.join(report['warnings']))

    def test_missing_fields_are_exposed_without_inventing_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'partial.csv'
            path.write_text('门店,订单\nS1,100\n', encoding='utf-8')
            previews = read_table_file(path)
            report = apply_mappings(previews, {
                'mappings': [mapping_for(path, 'store_week', {'store_id': '门店', 'orders': '订单'})],
                'missing_fields': ['net_gmv', 'tools'],
            })
            self.assertIsNone(report['net_gmv'])
            self.assertEqual(report['tools'], [])
            self.assertIn('net_gmv', report['missing_fields'])

    def test_multiple_store_ids_are_rejected_instead_of_mixed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'multi.csv'
            path.write_text('门店,订单\nS1,100\nS2,200\n', encoding='utf-8')
            previews = read_table_file(path)
            with self.assertRaisesRegex(InputError, '多个门店'):
                apply_mappings(previews, {
                    'mappings': [mapping_for(path, 'store_week', {'store_id': '门店', 'orders': '订单'})],
                    'missing_fields': [],
                })

    def test_scenario_uses_program_calculation_not_model_arithmetic(self):
        report = {
            'net_gmv': 60000,
            'merchant_subsidy': 4000,
            'tools': [
                {'tool_name': '点金推广', 'spend': 1000, 'attributed_gmv': 10000, 'roi': 10, 'attribution_window_days': 7, 'attribution_definition': '点击归因'},
                {'tool_name': '搜索推广', 'spend': 800, 'attributed_gmv': 14400, 'roi': 18, 'attribution_window_days': 7, 'attribution_definition': '点击归因'},
            ],
        }
        result = calculate_scenario(report, {
            'mode': 'reallocate', 'source_tool': '点金推广', 'target_tool': '搜索推广', 'amount': 400,
            'gross_margin': 0.45, 'marginal_factor': 0.8, 'merchant_subsidy_delta': 0, 'period': 'week',
        })
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['delta_gmv'], 2560)
        self.assertEqual(result['delta_gross_profit'], 1152)

    def test_map_tables_calls_real_client_with_headers(self):
        class FakeClient:
            def complete_json(self, stage, payload):
                self.stage = stage
                self.payload = payload
                return type('Result', (), {'data': {'mappings': [], 'missing_fields': ['orders'], 'notes': '无法识别'}})()

        client = FakeClient()
        result = map_tables([{'file_name': 'x.csv', 'sheet_name': 'Sheet1', 'headers': ['订单'], 'rows': [[100]]}], client)
        self.assertEqual(result['missing_fields'], ['orders'])
        self.assertEqual(client.stage, 'table_mapping')
        self.assertEqual(client.payload['tables'][0]['headers'], ['订单'])

    def test_public_diagnosis_uses_model_observations_not_a_preset_template(self):
        class FakeClient:
            def complete_json(self, stage, payload):
                self.stage = stage
                self.payload = payload
                return LlmResult(data={
                    'headline': '配送体验可能是这家店的第一道转化门槛',
                    'observations': [{'title': '配送反馈集中', 'evidence': '两条评价提到变凉', 'why_it_matters': '可能影响到手品质', 'next_check': '复核出餐与配送'}],
                    'data_request': {'summary': '需要周报验证', 'items': ['订单与净 GMV'], 'boundary_note': '公开信息先用于确定核查方向。'},
                }, model='fake-kimi', usage={'total_tokens': 10})

        client = FakeClient()
        result = public_diagnosis('店铺评价：送到饭凉了', client)
        self.assertIn('配送体验', result['headline'])
        self.assertEqual(client.stage, 'public_diagnosis')
        self.assertIn('送到饭凉了', client.payload['public_text'])

    def test_public_absolute_claims_are_repaired_before_delivery(self):
        class FakeClient:
            def __init__(self):
                self.stages = []

            def complete_json(self, stage, payload):
                self.stages.append(stage)
                if stage == 'public_diagnosis':
                    data = {'headline': '配送正在系统性摧毁门店', 'observations': [], 'data_request': {'summary': '', 'items': [], 'boundary_note': ''}}
                else:
                    data = {'headline': '配送体验需要优先核查', 'observations': [], 'data_request': {'summary': '', 'items': [], 'boundary_note': ''}}
                return LlmResult(data=data, model='fake-kimi', usage={'total_tokens': 10})

        client = FakeClient()
        result = public_diagnosis('配送 42 分钟', client)
        self.assertEqual(client.stages, ['public_diagnosis', 'public_diagnosis_repair'])
        self.assertEqual(result['headline'], '配送体验需要优先核查')

    def test_full_pipeline_runs_three_ai_stages_and_writes_real_metadata(self):
        class FakeClient:
            def complete_json(self, stage, payload):
                if stage == 'public_diagnosis':
                    data = {'headline': '先核查配送与投放效率', 'observations': [], 'data_request': {'summary': '需要周报', 'items': [], 'boundary_note': '公开信息先用于确定核查方向。'}}
                elif stage == 'table_mapping':
                    data = {
                        'mappings': [{'file_name': 'demo-weekly.csv', 'sheet_name': 'Sheet1', 'grain': 'store_week_tools', 'fields': {
                            'store_id': '门店ID', 'week_start': '周开始', 'orders': '订单', 'net_gmv': '净GMV', 'merchant_subsidy': '商家补贴',
                            'platform_subsidy': '平台补贴', 'tool_name': '投放工具', 'spend': '消耗', 'attributed_gmv': '归因净GMV',
                            'attribution_window_days': '归因窗口', 'attribution_definition': '归因定义', 'exported_at': '导出时间',
                        }}],
                        'missing_fields': [], 'notes': '工具粒度',
                    }
                elif stage == 'full_diagnosis':
                    data = {
                        'headline': '先把低效预算移到同口径高 ROI 工具',
                        'issues': [{'title': '点金推广 ROI 偏低', 'evidence': 'ROI 10 对比搜索推广 18', 'why_it_matters': '连续下滑'}],
                        'recommendation': {'mode': 'reallocate', 'source_tool': '点金推广', 'target_tool': '搜索推广', 'amount': 400, 'gross_margin': 0.45, 'marginal_factor': 0.8, 'merchant_subsidy_delta': 0, 'period': 'week'},
                        'client_talk_tracks': ['先调整 400 元。', '保留基本盘。', '下周复核实际 ROI。'],
                        'follow_ups': [{'action': '挪移 400 元', 'owner': '门店运营', 'metric': '实际 ROI 与毛利', 'review_date': '2026-10-19', 'stop_condition': '低于基线就回退'}],
                        'boundary_note': '测算用于比较方案，不是收益承诺。',
                    }
                else:
                    data = {
                        'headline': '先把低效预算移到同口径高 ROI 工具',
                        'issues': [{'title': '点金推广 ROI 偏低', 'evidence': 'ROI 10 对比搜索推广 18', 'why_it_matters': '预算结构有优化空间'}],
                        'recommendation': {'mode': 'reallocate', 'source_tool': '点金推广', 'target_tool': '搜索推广', 'amount': 400, 'gross_margin': 0.45, 'marginal_factor': 0.8, 'merchant_subsidy_delta': 0, 'period': 'week'},
                        'client_talk_tracks': ['先调整 400 元。', '保留基本盘。', '下周复核实际 ROI。'],
                        'follow_ups': [{'action': '挪移 400 元', 'owner': '门店运营', 'metric': '实际 ROI 与毛利', 'review_date': '2026-10-19', 'stop_condition': '低于基线就回退'}],
                        'boundary_note': '测算用于比较方案，不是收益承诺。',
                    }
                tokens = {'public_diagnosis': 10, 'table_mapping': 20, 'full_diagnosis': 30, 'full_diagnosis_repair': 30}[stage]
                return LlmResult(data=data, model='fake-kimi', usage={'total_tokens': tokens})

        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'run'
            result = run_pipeline('公开店铺文本', [Path(__file__).parents[1] / 'assets/demo-weekly.csv'], FakeClient(), out)
            metadata = json.loads((out / 'run-metadata.json').read_text())
            full_text = (out / 'full-diagnosis.md').read_text()
            self.assertEqual(metadata['actual_ai_calls'], 4)
            self.assertEqual(metadata['token_usage']['total_tokens'], 90)
            self.assertEqual(metadata['calls'][-1]['stage'], 'full_diagnosis_repair')
            self.assertEqual(result['full']['calculation']['delta_gmv'], 2560)
            self.assertLessEqual(full_text.count('不是收益承诺'), 1)
            self.assertNotIn('不是已经证实的结论', full_text)

    def test_model_failure_does_not_write_a_fake_success_report(self):
        class FailingClient:
            def complete_json(self, stage, payload):
                raise LlmError('API unavailable')

        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'run'
            with self.assertRaisesRegex(LlmError, 'API unavailable'):
                run_pipeline('公开文本', [], FailingClient(), out)
            self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
