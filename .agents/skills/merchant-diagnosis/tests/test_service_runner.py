"""Software integration doubles, never evidence of model or merchant success."""
import copy
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from test_runtime import S1, S2
import test_decisions
import service_store as store

S3 = '''# 数据接收与核对
门店：演示店
数据范围：合成周报
状态：待补数

## 数据覆盖
单店本周。

## 字段与口径
| 原字段 | 分析字段 | 单位 | 定义与来源 |
|---|---|---|---|
| 收入 | 实收 | 元 | raw.csv／row:2 |

## 核对结果
| 检查项 | 结果 | 证据或缺口 |
|---|---|---|
| 成本 | 待确认 | D1 |

## 待确认事项
| 缺口编号 | 待确认内容 | 影响的判断 | 补充方式 |
|---|---|---|---|
| D1 | 成本缺失 | 贡献测算 | 补成本台账 |
'''
S4 = '''# 经营诊断
门店：演示店
数据范围：合成周报
状态：待补数

## 事实与计算
| 指标 | 数值与单位 | 口径或算法 | 证据 |
|---|---|---|---|
| 贡献 | 待补充（D1） | 缺成本不能算贡献 | raw.csv／row:2 |

## 优先问题
| 编号 | 优先级 | 问题事实 | 证据 | 原因判断 | 判断状态 | 处理方向 |
|---|---|---|---|---|---|---|
| F1 | 高 | 成本未核 | raw.csv／row:2 | 缺口影响投入判断 | 待补数据 | 先补成本 |

## 初诊如何更新
| 原判断 | 处理 | 新依据 |
|---|---|---|
| F1 | 调整 | raw.csv／row:2 |

## 仍需确认
| 缺口编号 | 待验证问题 | 需要材料或试验 | 决策用途 |
|---|---|---|---|
| D1 | 成本 | 成本台账 | 决定是否有预算空间 |
'''
S5 = '''# 一页行动方案
门店：演示店
数据范围：合成周报
状态：待补数

## 一句话结论
先补成本，维持预算。

## 问题与证据
| 问题编号 | 问题 | 证据 |
|---|---|---|
| F1 | 成本不完整 | raw.csv／row:2 |

## 现在／建议
| 动作编号 | 关联问题 | 现在 | 建议 | 负责人 | 开始时间 | 投入 |
|---|---|---|---|---|---|---|
| A1 | F1 | 成本待核 | 核成本 | 店长 | 本周 | 现有人手 |

## 预期改善
| 动作编号 | 指标与单位 | 基线与来源 | 试行目标 | 测算与假设 |
|---|---|---|---|---|
| A1 | 成本完整性 | raw.csv／row:2 | 完成核对 | 不适用：未测算收益 |

## 下周跟进
| 动作编号 | 回传数据 | 复盘时间 | 继续条件 | 调整或停止条件 | 待补事项 |
|---|---|---|---|---|---|
| A1 | 成本与执行回执 | 下周 | 核实后判断 | 无法核实时调整采样 | D1 |

## 给老板的三句话
1. 当前先核成本。
2. 暂不追加广告。
3. 下周看回执再判断。
'''


class FakeClient:
    mode = 'test_double'

    def __init__(self, replies):
        self.replies = list(replies)
        self.messages = []

    def complete(self, messages):
        self.messages.append(copy.deepcopy(messages))
        value = self.replies.pop(0)
        if isinstance(value, Exception):
            raise value
        return {'data': value, 'metadata': {'mode': self.mode, 'inference_executed': False,
                'model': 'software-test-double', 'response_id': 'fixture', 'usage': {}, 'elapsed_seconds': 0}}


def final(report, decisions=None):
    return {'kind': 'final', 'report_markdown': report, 'decisions': decisions,
            'no_calculation_reason': '本例仅核缺成本，未做数量结论'}


def decisions():
    fixture = test_decisions.DecisionTests()
    fixture.setUp()
    return fixture.record


class ServiceRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.project = self.base / 'merchant'
        store.create_project(self.project, '演示店', '提高经营贡献', True)
        self.public = self.base / 'public.md'
        self.public.write_text('顾客提及变凉')
        store.add_material(self.project, self.public, 'public', 'public', '本次')

    def runner(self):
        self.assertIsNotNone(importlib.util.find_spec('service_runner'), 'service_runner is not implemented')
        return importlib.import_module('service_runner')

    def test_public_stages_require_review_and_export_contains_only_this_project(self):
        r = self.runner()
        client = FakeClient([final(S1), final(S2)])
        record = r.run_project(self.project, 'public', client)
        self.assertEqual('awaiting_review', record['status'])
        self.assertFalse(record['inference_executed'])
        with self.assertRaises(ValueError):
            r.export_project(self.project)
        store.record_review(self.project, record['id'], 'Tester', '软件测试，不是商家验收', True)
        path = r.export_project(self.project)
        self.assertTrue(path.is_file())
        payload = json.loads(path.with_suffix('.json').read_text())
        self.assertEqual(1, len(payload['cases']))
        self.assertEqual(2, len(payload['cases'][0]['versions'][0]['stages']))

    def test_one_structure_correction_preserves_both_drafts(self):
        r = self.runner()
        invalid = 'bad\n待补充（D1）\n待补充（D12）\n待补充'
        client = FakeClient([final(invalid), final(S1), final(S2)])
        record = r.run_project(self.project, 'public', client)
        stage = self.project / record['path'] / 'S1'
        self.assertEqual(invalid, (stage / 'draft-1.md').read_text())
        self.assertTrue((stage / 'draft-2.md').is_file())
        self.assertTrue(json.loads((stage / 'check-1.json').read_text())['errors'])
        feedback = json.loads(client.messages[1][-1]['content'])
        self.assertEqual(['一句话初诊', '发现与依据', '下一步补数'], feedback['expected_headings'])
        self.assertEqual([], feedback['actual_headings'])
        self.assertEqual([4], feedback['missing_id_lines'])

    def test_nontext_report_can_use_the_single_structure_correction(self):
        for report in ({'unexpected': 'object'}, ['unexpected'], 123):
            with self.subTest(report_type=type(report).__name__):
                client = FakeClient([final(report), final(S1), final(S2)])
                record = self.runner().run_project(self.project, 'public', client)
                self.assertEqual('awaiting_review', record['status'])
                feedback = json.loads(client.messages[1][-1]['content'])
                self.assertIn('report_markdown 必须为非空文字', feedback['correction_required'])
                self.assertEqual([], feedback['actual_headings'])
                self.assertEqual([], feedback['missing_id_lines'])
                stage = self.project / record['path'] / 'S1'
                self.assertEqual('', (stage / 'draft-1.md').read_text())
                self.assertEqual(S1, (stage / 'draft-2.md').read_text())

    def test_history_accepts_complete_manifest_and_rejects_unregistered_report(self):
        runner = self.runner()
        record = runner.run_project(self.project, 'public', FakeClient([final(S1), final(S2)]))
        store.record_review(self.project, record['id'], 'Tester', 'history fixture review', True)
        run_dir = (self.project / record['path']).resolve()
        self.assertEqual([run_dir / 'S1/report.md', run_dir / 'S2/report.md'],
                         runner._history(self.project, record))
        (run_dir / 'S3').mkdir()
        (run_dir / 'S3/report.md').write_text('未登记的新增诊断')
        with self.assertRaises(ValueError):
            runner._history(self.project, record)

    def test_history_rejects_modified_registered_report(self):
        runner = self.runner()
        record = runner.run_project(self.project, 'public', FakeClient([final(S1), final(S2)]))
        store.record_review(self.project, record['id'], 'Tester', 'history fixture review', True)
        report = self.project / record['path'] / 'S1/report.md'
        report.write_text('已登记报告被修改')
        with self.assertRaises(ValueError):
            runner._history(self.project, record)

    def test_rejected_review_guides_same_version_rerun_only(self):
        r = self.runner()
        first = r.run_project(self.project, 'public', FakeClient([final(S1), final(S2)]))
        store.record_review(self.project, first['id'], 'Tester', '评价串店，回查原材料', False)
        client = FakeClient([final(S1), final(S2)])
        r.run_project(self.project, 'public', client)
        context = json.loads(client.messages[0][1]['content'])['context']
        self.assertEqual('评价串店，回查原材料', context['review_feedback']['note'])
        self.public.write_text('新版本公开材料')
        store.add_material(self.project, self.public, 'public', 'public', '更正', replace=True)
        changed = FakeClient([final(S1), final(S2)])
        r.run_project(self.project, 'public', changed)
        self.assertIsNone(json.loads(changed.messages[0][1]['content'])['context']['review_feedback'])

    def test_failure_preserves_first_stage_and_does_not_create_fallback(self):
        r = self.runner()
        record = r.run_project(self.project, 'public', FakeClient([final(S1), ValueError('network failed')]))
        self.assertEqual('failed', record['status'])
        self.assertTrue((self.project / record['path'] / 'S1/report.md').exists())
        self.assertFalse((self.project / record['path'] / 'S2/report.md').exists())
        with self.assertRaises(ValueError):
            store.record_review(self.project, record['id'], 'Jim', 'fail', True)

    def test_api_failure_records_only_safe_error_category(self):
        from model_api import ModelAPIError
        record = self.runner().run_project(self.project, 'public', FakeClient([ModelAPIError('rate_limited')]))
        error = json.loads((self.project / record['path'] / 'S1/error-1.json').read_text())
        self.assertEqual('rate_limited', error['code'])
        execution = json.loads((self.project / record['path'] / 'execution.json').read_text())
        self.assertEqual('rate_limited', execution['calls'][0]['error_code'])
        self.assertEqual('failed', record['status'])

    def test_invalid_content_json_gets_one_shared_format_repair(self):
        from model_api import ModelAPIError
        malformed = ModelAPIError('invalid_response', {'phase':'content_json','finish_reason':'stop','json_error':'syntax'})
        client = FakeClient([malformed, final(S1), final(S2)])
        record = self.runner().run_project(self.project, 'public', client)
        self.assertEqual('awaiting_review', record['status'])
        self.assertTrue((self.project / record['path'] / 'S1/error-1.json').exists())
        self.assertIn('json_format_correction', client.messages[1][-1]['content'])
        self.assertTrue((self.project / record['path'] / 'S1/draft-2.md').exists())
        second = self.runner().run_project(self.project, 'public', FakeClient([malformed, final('bad'), final(S1)]))
        self.assertEqual('failed', second['status'])

    def test_native_parameter_repair_discards_invalid_turn_and_calculates_valid_request(self):
        from model_api import ModelClient
        from test_model_api import native_response, response
        request = {'requests': [{'id': 'fixed1', 'expression': 'a-b', 'unit': '条',
            'purpose': '参数修正测试', 'variables': {'a': {'value': 3, 'assumption': '合成输入'},
                                                 'b': {'value': 1, 'assumption': '合成输入'}}}]}
        invalid = copy.deepcopy(request)
        invalid['requests'][0]['variables'] = {'错误变量': {'value': 3, 'assumption': '合成输入'}}
        replies = [native_response(invalid, reasoning_content='PRIVATE_INVALID_RESPONSE'),
                   native_response(request), response(json.dumps(final(S1))), response(json.dumps(final(S2)))]
        captured = []
        def transport(url, payload, *args):
            captured.append(json.loads(payload)['messages'])
            return replies.pop(0)
        client = ModelClient('deepseek', 'offline-placeholder', 'offline-model', transport=transport)
        runner = self.runner()
        with patch('service_runner.calculate_requests', wraps=runner.calculate_requests) as calculate:
            record = runner.run_project(self.project, 'public', client)
        self.assertEqual('awaiting_review', record['status'])
        self.assertEqual(4, len(captured))
        calculate.assert_called_once()
        self.assertEqual(request['requests'], calculate.call_args.args[0])
        self.assertEqual(['system', 'system', 'user', 'user'], [m['role'] for m in captured[1]])
        feedback = json.loads(captured[1][-1]['content'])
        self.assertEqual('variable_fields', feedback['tool_format_correction']['tool_error'])
        for term in ('ASCII', 'value', 'null', 'evidence', 'assumption'):
            self.assertIn(term, feedback['instruction'])
        self.assertNotIn('PRIVATE_INVALID_RESPONSE', json.dumps(captured))
        self.assertNotIn('错误变量', json.dumps(captured, ensure_ascii=False))
        stage = self.project / record['path'] / 'S1'
        self.assertFalse((stage / 'response-1.json').exists())
        self.assertNotIn('PRIVATE_INVALID_RESPONSE', (stage / 'error-1.json').read_text())
        self.assertEqual(2, json.loads((stage / 'calculations.json').read_text())[0]['value'])

    def test_only_known_tool_parameter_errors_get_one_repair(self):
        from model_api import ModelAPIError
        for code in ('arguments_shape', 'request_fields', 'request_text', 'variables_shape',
                     'variable_fields', 'variable_value', 'variable_source', 'variable_citation'):
            with self.subTest(code=code):
                error = ModelAPIError('invalid_response', {'phase': 'tool_arguments',
                    'finish_reason': 'tool_calls', 'tool_error': code, 'json_error': 'other'})
                client = FakeClient([error, final(S1), final(S2)])
                record = self.runner().run_project(self.project, 'public', client)
                self.assertEqual('awaiting_review', record['status'])
                self.assertEqual(3, len(client.messages))

    def test_tool_parameter_json_and_report_repairs_share_one_budget(self):
        from model_api import ModelAPIError
        parameter = ModelAPIError('invalid_response', {'phase': 'tool_arguments',
            'finish_reason': 'tool_calls', 'tool_error': 'variable_fields', 'json_error': 'other'})
        malformed = ModelAPIError('invalid_response', {'phase': 'content_json',
            'finish_reason': 'stop', 'json_error': 'syntax'})
        for replies in ([parameter, parameter], [parameter, malformed], [malformed, parameter],
                        [parameter, final('bad')], [final('bad'), parameter]):
            with self.subTest(first=type(replies[0]).__name__, second=type(replies[1]).__name__):
                client = FakeClient([*replies, final(S1)])
                record = self.runner().run_project(self.project, 'public', client)
                self.assertEqual('failed', record['status'])
                self.assertEqual(2, len(client.messages))
                self.assertFalse((self.project / record['path'] / 'S1/report.md').exists())

    def test_tool_identity_json_and_unknown_errors_stop_without_repair(self):
        from model_api import ModelAPIError
        rejected = [(code, 'other') for code in ('call_identifier', 'function_definition', 'call_count',
            'message_role', 'message_content', 'tool_calls_shape', 'reasoning_field',
            'arguments_json', 'duplicate_key', 'non_finite', 'not_object', 'other')]
        rejected.extend(('variable_fields', code) for code in ('syntax', 'duplicate_key', 'non_finite'))
        for code, json_error in rejected:
            with self.subTest(code=code, json_error=json_error):
                error = ModelAPIError('invalid_response', {'phase': 'tool_arguments',
                    'finish_reason': 'tool_calls', 'tool_error': code, 'json_error': json_error})
                client = FakeClient([error, final(S1)])
                record = self.runner().run_project(self.project, 'public', client)
                self.assertEqual('failed', record['status'])
                self.assertEqual(1, len(client.messages))

    def test_network_failure_is_not_retried_as_format_repair(self):
        from model_api import ModelAPIError
        client = FakeClient([ModelAPIError('timeout'), final(S1)])
        record = self.runner().run_project(self.project, 'public', client)
        self.assertEqual('failed', record['status'])
        self.assertEqual(1, len(client.messages))

    def test_invalid_completed_responses_count_as_inference_without_success(self):
        from model_api import ModelAPIError
        malformed = ModelAPIError('invalid_response', {'phase': 'content_json',
            'finish_reason': 'stop', 'completion_tokens': 42})
        client = FakeClient([malformed, malformed])
        client.mode = 'api'
        record = self.runner().run_project(self.project, 'public', client)
        self.assertEqual('failed', record['status'])
        self.assertEqual([], record['completed_stages'])
        self.assertTrue(record['inference_executed'])
        execution = json.loads((self.project / record['path'] / 'execution.json').read_text())
        self.assertEqual(42, execution['calls'][0]['diagnostics']['completion_tokens'])

    def test_new_material_blocks_old_delivery_and_followup_needs_reviewed_history(self):
        r = self.runner()
        first = r.run_project(self.project, 'public', FakeClient([final(S1), final(S2)]))
        with self.assertRaises(ValueError):
            r.run_project(self.project, 'followup', FakeClient([]))
        store.record_review(self.project, first['id'], 'Tester', 'fixture review', True)
        with self.assertRaises(ValueError):
            r.run_project(self.project, 'followup', FakeClient([]))
        self.public.write_text('新评价信息')
        store.add_material(self.project, self.public, 'public', 'public', '本次', replace=True)
        with self.assertRaises(ValueError):
            r.export_project(self.project)

    def test_calculator_runs_before_final_and_results_are_in_next_request(self):
        r = self.runner()
        request = {'kind': 'calculate', 'requests': [{'id':'c1','expression':'a-b', 'unit':'条','purpose':'软件测试计数',
             'variables': {'a': {'value':3,'assumption':'测试输入'},'b':{'value':1,'assumption':'测试输入'}}}]}
        client = FakeClient([request, final(S1), final(S2)])
        record = r.run_project(self.project, 'public', client)
        self.assertEqual('awaiting_review', record['status'])
        values = json.loads((self.project / record['path'] / 'S1/calculations.json').read_text())
        self.assertEqual(2, values[0]['value'])
        self.assertIn('tool_results', client.messages[1][-1]['content'])

    def test_call_budget_prevents_unbounded_tool_loop(self):
        r = self.runner()
        reply = {'kind': 'calculate', 'requests': []}
        client = FakeClient([reply] * 3)
        record = r.run_project(self.project, 'public', client, max_calls=3)
        self.assertEqual('failed', record['status'])
        self.assertLessEqual(len(client.messages), 3)

    def test_native_calculator_preserves_assistant_and_returns_matching_tool_result(self):
        request = {'kind': 'calculate', 'requests': [{'id':'native1','expression':'a-b',
            'unit':'条','purpose':'工具往返测试','variables': {
                'a': {'value':3,'assumption':'测试输入'},
                'b': {'value':1,'assumption':'测试输入'}}}]}
        client = FakeClient([request, final('bad'), final(S1), final(S2)])
        original = client.complete
        assistant = {'role':'assistant','content':None,'reasoning_content':'合成测试上下文',
            'tool_calls':[{'id':'call_test','type':'function','function': {
                'name':'calculate','arguments':json.dumps({'requests':request['requests']})}}]}
        def native(messages):
            result = original(messages)
            if result['data']['kind'] == 'calculate':
                result.update(assistant_message=assistant, tool_call_id='call_test')
            else:
                result['assistant_message'] = {'role':'assistant',
                    'content':json.dumps(result['data']), 'reasoning_content':'合成格式修正上下文'}
            return result
        client.complete = native
        record = self.runner().run_project(self.project, 'public', client)
        self.assertEqual('awaiting_review', record['status'])
        self.assertEqual(assistant, client.messages[1][-2])
        reply = client.messages[1][-1]
        self.assertEqual('tool', reply['role'])
        self.assertEqual('call_test', reply['tool_call_id'])
        self.assertEqual(2, json.loads(reply['content'])['tool_results'][0]['value'])
        self.assertEqual('合成格式修正上下文', client.messages[2][-2]['reasoning_content'])

    def test_s5_cannot_reverse_s4_selected_strategy(self):
        r = self.runner()
        raw = self.base / 'raw.csv'
        raw.write_text('store,income\nS01,10\n')
        store.add_material(self.project, raw, 'weekly', 'business', 'W1')
        changed = decisions()
        options = changed['priorities'][0]['options']
        selected = next(o for o in options if o['status'] == 'selected')
        other = next(o for o in options if o['status'] != 'selected')
        selected['status'], other['status'] = 'deferred', 'selected'
        result = r.run_project(self.project, 'diagnosis', FakeClient([
            final(S3), final(S4, decisions()), final(S5, changed), final(S5, changed)]))
        self.assertEqual('failed', result['status'])
        self.assertEqual(['S3', 'S4'], result['completed_stages'])

    def test_material_tampering_between_stages_stops_run(self):
        r = self.runner()
        client = FakeClient([final(S1), final(S2)])
        original = client.complete
        def mutate(messages):
            result = original(messages)
            active = store.read_project(self.project)['materials']['public']['versions'][-1]
            (self.project / active['path']).write_text('未登记的新事实')
            return result
        client.complete = mutate
        result = r.run_project(self.project, 'public', client)
        self.assertEqual('failed', result['status'])
        self.assertEqual(1, len(client.messages))

    def test_export_holds_lock_against_material_update(self):
        r = self.runner()
        result = r.run_project(self.project, 'public', FakeClient([final(S1), final(S2)]))
        store.record_review(self.project, result['id'], 'Tester', 'fixture review', True)
        verify = r._verify_run
        def concurrent(root, record):
            self.public.write_text('新增内容')
            with self.assertRaises(ValueError):
                store.add_material(root, self.public, 'public', 'public', '本次', replace=True)
            return verify(root, record)
        with patch('service_runner._verify_run', side_effect=concurrent):
            self.assertTrue(r.export_project(self.project).is_file())

    def test_diagnosis_and_followup_freeze_replacements_and_previous_reports(self):
        r = self.runner()
        raw = self.base / 'raw.csv'
        raw.write_text('store,income\nS01,10\n')
        store.add_material(self.project, raw, 'weekly', 'business', 'W1')
        client = FakeClient([final(S3), final(S4, decisions()), final(S5, decisions())])
        first = r.run_project(self.project, 'diagnosis', client)
        self.assertEqual('awaiting_review', first['status'])
        store.record_review(self.project, first['id'], 'Tester', 'fixture review', True)
        raw.write_text('store,income\nS01,2\n')
        store.add_material(self.project, raw, 'weekly', 'business', 'W1', replace=True)
        second_client = FakeClient([final(S3), final(S4, decisions()), final(S5, decisions())])
        second = r.run_project(self.project, 'followup', second_client)
        self.assertEqual('awaiting_review', second['status'])
        bundle = json.loads((self.project / second['path'] / 'S3/materials.json').read_text())
        self.assertEqual(1, sum(m['name'] == 'raw.csv' for m in bundle['materials']))
        self.assertIn('2', next(m for m in bundle['materials'] if m['name'] == 'raw.csv')['fragments'][1]['text'])
        self.assertTrue(bundle['history'])
        self.assertIn('replaced_slots', second_client.messages[0][-1]['content'])
        context = json.loads(second_client.messages[0][1]['content'])['context']
        self.assertEqual('fixture review', context['previous_review']['note'])
        self.assertEqual(first['id'], context['previous_review']['run_id'])


if __name__ == '__main__':
    unittest.main()
