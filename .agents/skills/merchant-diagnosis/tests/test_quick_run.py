"""Offline integration of the quick path, including actual native-tool parsing."""
import copy
import importlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from test_quick_contract import report, request
from model_api import ModelClient, ModelAPIError


def envelope(message, finish='stop'):
    return json.dumps({'id': 'response-1', 'model': 'test-model',
        'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'total_tokens': 20},
        'choices': [{'finish_reason': finish, 'message': message}]}).encode()


def review(approved=True, issues=None):
    return envelope({'role': 'assistant', 'content': json.dumps(
        {'kind': 'review', 'approved': approved, 'issues': issues or []})})


class QuickRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = self.base / 'weekly.csv'
        self.source.write_text('乱表头,业务备注\n实收100,老板明确成本40\n', encoding='utf-8')
        self.run = self.base / 'run'

    def runner(self):
        self.assertIsNotNone(importlib.util.find_spec('quick_run'), 'quick runner missing')
        return importlib.import_module('quick_run')

    def prepare(self):
        self.runner().prepare_run([self.source], self.run, merchant='测试店', goal='改善体验',
                                  scope='单店', period='本周', synthetic=True, runtime='Unit test')

    def renderer(self):
        def export(value, output, *, metadata=None):
            Path(output).write_text('<html>测试导出</html>', encoding='utf-8')
            return Path(output)
        return patch.dict(sys.modules, {'boss_report': types.SimpleNamespace(export_boss=export)})

    def test_prepare_freezes_actual_materials_without_old_stage_templates(self):
        self.prepare()
        bundle = json.loads((self.run / 'materials.json').read_text())
        self.assertIn('老板明确成本40', json.dumps(bundle, ensure_ascii=False))
        prompt = (self.run / 'prompt.md').read_text()
        self.assertNotIn('## 本阶段模板', prompt)
        manifest = json.loads((self.run / 'manifest.json').read_text())
        self.assertEqual('Unit test', manifest['runtime'])
        self.assertTrue(manifest['python_version'])
        self.assertFalse(manifest['inference_executed'])
        with self.assertRaises(ValueError):
            self.prepare()

    def test_unreadable_attachment_does_not_discard_readable_material(self):
        image = self.base / 'photo.png'
        image.write_bytes(b'not-an-image')
        self.runner().prepare_run([self.source, image], self.run, merchant='测试店')
        bundle = json.loads((self.run / 'materials.json').read_text())
        self.assertEqual(['weekly.csv'], [m['name'] for m in bundle['materials']])
        self.assertEqual('photo.png', bundle['unreadable_materials'][0]['name'])
        self.assertIn('OCR', bundle['unreadable_materials'][0]['reason'])

    def test_frozen_material_tampering_stops_calculation(self):
        self.prepare()
        (self.run / 'materials.json').write_text('{}')
        with self.assertRaises(ValueError):
            self.runner().calculate_run(self.run, [request()])

    def test_cli_three_steps_export_real_offline_html(self):
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts/quick_run.py')]
        self.assertIsNotNone(importlib.util.find_spec('boss_report'), 'boss renderer missing')
        requests = self.base / 'requests.json'
        requests.write_text(json.dumps({'requests': [request()]}))
        draft = self.base / 'draft.json'
        draft.write_text(json.dumps(report()))
        commands = [command + ['prepare', '--input', str(self.source), '--output', str(self.run),
                              '--merchant', '测试店', '--scope', '单店', '--period', '本周', '--synthetic'],
                    command + ['calculate', '--run', str(self.run), '--requests', str(requests)],
                    command + ['finish', '--run', str(self.run), '--report', str(draft)]]
        for item in commands:
            result = subprocess.run(item, capture_output=True, text=True, check=False)
            self.assertEqual(0, result.returncode, result.stderr)
        html = (self.run / 'report.html').read_text()
        self.assertIn('测试店', html)
        self.assertNotIn('weekly.csv', html)
        self.assertNotIn('chosen_strategy', html)
        self.assertEqual(60, json.loads((self.run / 'report.json').read_text())['money']['value'])

    def test_api_cli_timeout_default_and_explicit_reach_transport_and_execution(self):
        for index, (arguments, expected) in enumerate((([], 120), (['--timeout', '1'], 1),
                                                      (['--timeout', '120'], 120))):
            with self.subTest(arguments=arguments):
                values = [{'kind': 'calculate', 'requests': [request()]},
                          {'kind': 'final', 'report': report()},
                          {'kind': 'review', 'approved': True, 'issues': []}]
                timeouts = []
                def transport(url, payload, headers, timeout, limit):
                    timeouts.append(timeout)
                    return envelope({'role': 'assistant', 'content': json.dumps(values.pop(0))})
                output = self.base / ('timeout-' + str(index))
                with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test-secret',
                                               'DEEPSEEK_MODEL': 'test-model'}), \
                        patch('model_api._http_transport', side_effect=transport), \
                        patch('sys.stdout', io.StringIO()), self.renderer():
                    status = self.runner().main(['api', '--input', str(self.source), '--output',
                        str(output), '--merchant', '测试店', '--synthetic'] + arguments)
                self.assertEqual(0, status)
                self.assertEqual([expected] * 3, timeouts)
                execution = json.loads((output / 'execution.json').read_text())
                self.assertEqual(expected, execution['client_settings']['timeout'])

    def test_api_cli_invalid_timeout_fails_before_loading_credentials_or_creating_run(self):
        for value in ('0', '-1', '121'):
            with self.subTest(value=value), patch('service.load_client') as load_client, \
                    patch('sys.stderr', io.StringIO()) as stderr:
                status = self.runner().main(['api', '--input', str(self.source), '--output',
                    str(self.run), '--merchant', '测试店', '--timeout', value])
                self.assertEqual(2, status)
                self.assertIn('1', stderr.getvalue())
                self.assertIn('120', stderr.getvalue())
                load_client.assert_not_called()
                self.assertFalse(self.run.exists())

    def test_three_step_flow_binds_actual_calculation_and_exports(self):
        self.prepare()
        results = self.runner().calculate_run(self.run, [request()])
        self.assertEqual(60, results[0]['value'])
        with self.renderer():
            output = self.runner().finish_run(self.run, {'kind': 'final', 'report': report()})
        self.assertEqual(self.run / 'report.html', output)
        value = json.loads((self.run / 'report.json').read_text())
        self.assertEqual(60, value['money']['value'])
        execution = json.loads((self.run / 'execution.json').read_text())
        self.assertEqual('completed', execution['status'])
        self.assertFalse(execution['inference_executed'])
        self.assertEqual('not_independently_reviewed', execution['business_review']['status'])
        with self.assertRaises(ValueError), self.renderer():
            self.runner().finish_run(self.run, report())

    def completed_prior(self):
        self.prepare()
        self.runner().calculate_run(self.run, [request()])
        with self.renderer():
            self.runner().finish_run(self.run, report())
        return self.run / 'report.json'

    def test_previous_report_is_frozen_as_judgment_not_current_evidence(self):
        previous = self.completed_prior()
        original = previous.read_bytes()
        current = self.base / 'next-run'
        self.runner().prepare_run([self.source], current, merchant='测试店', synthetic=True,
                                  previous_report=previous)
        bundle = json.loads((current / 'materials.json').read_text())
        self.assertEqual(['weekly.csv'], [m['name'] for m in bundle['materials']])
        self.assertEqual(60, bundle['history']['report']['money']['value'])
        self.assertEqual('historical_judgment', bundle['history']['kind'])
        self.assertTrue(bundle['history']['report_sha256'])
        prompt = (current / 'prompt.md').read_text()
        self.assertIn('撤回', prompt)
        self.assertIn('不能填入本轮数字', prompt)
        historical = request()
        historical['variables']['income']['evidence'][0]['material'] = 'report.json'
        with self.assertRaises(ValueError):
            self.runner().calculate_run(current, [historical])
        self.assertEqual(original, previous.read_bytes())

    def test_previous_report_rejects_other_merchant_unfinished_or_tampered(self):
        previous = self.completed_prior()
        with self.assertRaises(ValueError):
            self.runner().prepare_run([self.source], self.base / 'other', merchant='另一家店',
                                      synthetic=True, previous_report=previous)
        self.assertFalse((self.base / 'other').exists())
        execution = self.run / 'execution.json'
        original = execution.read_text()
        changed = json.loads(original)
        changed['status'] = 'prepared'
        execution.write_text(json.dumps(changed))
        with self.assertRaises(ValueError):
            self.runner().prepare_run([self.source], self.base / 'unfinished', merchant='测试店',
                                      synthetic=True, previous_report=previous)
        execution.write_text(original)
        changed = json.loads(previous.read_text())
        changed['headline'] = '改写后的旧判断'
        previous.write_text(json.dumps(changed))
        with self.assertRaises(ValueError):
            self.runner().prepare_run([self.source], self.base / 'tampered', merchant='测试店',
                                      synthetic=True, previous_report=previous)

    def test_previous_completed_run_without_new_output_digest_still_checks_identity(self):
        previous = self.completed_prior()
        execution = self.run / 'execution.json'
        value = json.loads(execution.read_text())
        value.pop('report_sha256', None)
        execution.write_text(json.dumps(value))
        current = self.base / 'legacy-next'
        self.runner().prepare_run([self.source], current, merchant='测试店', synthetic=True,
                                  previous_report=previous)
        history = json.loads((current / 'materials.json').read_text())['history']
        self.assertEqual('snapshot_and_binding', history['verification'])

    def test_previous_argument_reaches_api_and_cli(self):
        previous = self.completed_prior()
        current = self.base / 'api-next'
        payloads = []
        final = report()
        final['money'].pop('calc_id')
        final['money']['value'] = None
        final['charts'] = []
        def transport(url, payload, *args):
            payloads.append(json.loads(payload))
            return (envelope({'role': 'assistant', 'content': json.dumps({'kind': 'final', 'report': final})})
                    if len(payloads) == 1 else review())
        client = ModelClient('deepseek', 'test-secret', 'test-model', transport=transport)
        with self.renderer():
            self.runner().run_api([self.source], current, client=client, merchant='测试店',
                                 synthetic=True, previous_report=previous)
        user = next(item for item in payloads[0]['messages'] if item['role'] == 'user')
        self.assertEqual('historical_judgment', json.loads(user['content'])['history']['kind'])
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts/quick_run.py'),
                   'prepare', '--input', str(self.source), '--output', str(self.base / 'cli-next'),
                   '--merchant', '测试店', '--synthetic', '--previous-report', str(previous)]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_modified_input_snapshot_or_calculation_is_rejected(self):
        self.prepare()
        self.runner().calculate_run(self.run, [request()])
        (self.run / 'calculations.json').write_text('[]')
        with self.assertRaises(ValueError), self.renderer():
            self.runner().finish_run(self.run, report())

    def test_duplicate_calculation_ids_do_not_replace_earlier_values(self):
        self.prepare()
        self.runner().calculate_run(self.run, [request()])
        original = (self.run / 'calculations.json').read_bytes()
        with self.assertRaises(ValueError):
            self.runner().calculate_run(self.run, [request()])
        self.assertEqual(original, (self.run / 'calculations.json').read_bytes())

    def test_calculator_normalizes_unique_basename_without_changing_values(self):
        self.prepare()
        item = request()
        item['variables']['income']['evidence'][0]['material'] = '/local/weekly.csv'
        result = self.runner().calculate_run(self.run, [item])
        self.assertEqual(60, result[0]['value'])
        self.assertEqual('weekly.csv', result[0]['variables']['income']['evidence'][0]['material'])

    def test_export_failure_does_not_lose_draft_counter_or_block_recovery(self):
        self.prepare()
        self.runner().calculate_run(self.run, [request()])
        def fail(*args, **kwargs):
            raise OSError('simulated unavailable asset')
        with patch.dict(sys.modules, {'boss_report': types.SimpleNamespace(export_boss=fail)}):
            with self.assertRaises(OSError):
                self.runner().finish_run(self.run, report())
        self.assertEqual(1, json.loads((self.run / 'execution.json').read_text())['draft_count'])
        with self.renderer():
            self.runner().finish_run(self.run, report())
        self.assertEqual(2, len(list(self.run.glob('draft-*.txt'))))

    def test_invalid_draft_is_preserved_and_one_correction_can_finish(self):
        self.prepare()
        self.runner().calculate_run(self.run, [request()])
        with self.assertRaises(ValueError):
            self.runner().finish_run(self.run, '{"incomplete":')
        with self.renderer():
            self.runner().finish_run(self.run, report())
        self.assertEqual(2, len(list(self.run.glob('draft-*.txt'))))

    def test_native_tool_roundtrip_keeps_reasoning_and_one_conversation(self):
        payloads = []
        tool_message = {'role': 'assistant', 'content': None, 'reasoning_content': 'test reasoning',
            'tool_calls': [{'id': 'call_1', 'type': 'function', 'function': {'name': 'calculate',
                'arguments': json.dumps({'requests': [request()]})}}]}
        replies = [envelope(tool_message, 'tool_calls'),
                   envelope({'role': 'assistant', 'content': json.dumps({'kind': 'final', 'report': report()})}),
                   review()]
        def transport(url, payload, headers, timeout, limit):
            payloads.append(json.loads(payload))
            return replies.pop(0)
        client = ModelClient('deepseek', 'test-secret', 'test-model', transport=transport, thinking='enabled')
        with self.renderer():
            output = self.runner().run_api([self.source], self.run, client=client, merchant='测试店',
                goal='改善体验', scope='单店', period='本周', synthetic=True)
        self.assertTrue(output.is_file())
        self.assertEqual(3, len(payloads))
        assistant = next(m for m in payloads[1]['messages'] if m.get('tool_calls'))
        self.assertEqual(tool_message, assistant)
        result = next(m for m in payloads[1]['messages'] if m['role'] == 'tool')
        self.assertEqual('call_1', result['tool_call_id'])
        self.assertEqual(60, json.loads(result['content'])['tool_results'][0]['value'])
        execution = json.loads((self.run / 'execution.json').read_text())
        self.assertEqual(3, execution['model_calls'])
        self.assertEqual(2, execution['analysis_calls'])
        self.assertEqual(1, execution['review_calls'])
        self.assertEqual(8, execution['max_calls'])
        self.assertEqual('test-model', execution['client_settings']['model'])
        self.assertEqual('test_double', execution['mode'])
        self.assertFalse(execution['inference_executed'])
        self.assertEqual('approved', execution['business_review']['status'])
        reviewer = payloads[2]['messages']
        self.assertEqual(['system', 'system', 'user'], [item['role'] for item in reviewer])
        review_input = json.loads(reviewer[-1]['content'])
        self.assertEqual(60, review_input['report']['money']['value'])
        self.assertEqual(100, review_input['calculations'][0]['variables']['income']['value'])
        self.assertIn('原始数值', reviewer[1]['content'])
        self.assertIn('差额', reviewer[1]['content'])
        self.assertNotIn('test reasoning', json.dumps(reviewer))
        self.assertEqual(1, len(list(self.run.glob('review-response-*.json'))))
        self.assertNotIn('test-secret', ''.join(p.read_text() for p in self.run.glob('*.json')))

    def test_api_call_limit_leaves_failed_record_without_fallback(self):
        client = ModelClient('deepseek', 'test-secret', 'test-model', transport=lambda *args:
            envelope({'role': 'assistant', 'content': json.dumps({'kind': 'calculate', 'requests': [request()]})}))
        with self.assertRaises(ValueError):
            self.runner().run_api([self.source], self.run, client=client, merchant='测试店', max_calls=1)
        self.assertFalse((self.run / 'report.html').exists())
        execution = json.loads((self.run / 'execution.json').read_text())
        self.assertEqual('failed', execution['status'])
        self.assertEqual(0, execution['model_calls'])

    def test_api_correction_does_not_restart_material_or_stage_processing(self):
        bad = report()
        bad['money'].pop('calc_id')
        bad['money']['value'] = None
        bad['charts'] = []
        good = copy.deepcopy(bad)
        bad['actions'][0]['stop'] = ''
        replies = [envelope({'role': 'assistant', 'content': json.dumps({'kind': 'final', 'report': value})})
                   for value in (bad, good)] + [review()]
        client = ModelClient('deepseek', 'test-secret', 'test-model', transport=lambda *args: replies.pop(0))
        with self.renderer():
            self.runner().run_api([self.source], self.run, client=client, merchant='测试店',
                                 scope='单店', period='本周', synthetic=True)
        self.assertEqual(2, len(list(self.run.glob('response-*.json'))))
        self.assertFalse((self.run / 'S3').exists())

    def test_native_parameter_shape_gets_one_specific_correction(self):
        malformed = request()
        malformed['variables']['income']['value'] = '100'
        def tool(item):
            return envelope({'role': 'assistant', 'content': None,
                'tool_calls': [{'id': 'call_1', 'type': 'function', 'function': {'name': 'calculate',
                    'arguments': json.dumps({'requests': [item]})}}]}, 'tool_calls')
        replies = [tool(malformed), tool(request()), envelope({'role': 'assistant',
                    'content': json.dumps({'kind': 'final', 'report': report()})}), review()]
        payloads = []
        def transport(url, payload, *args):
            payloads.append(json.loads(payload))
            return replies.pop(0)
        client = ModelClient('deepseek', 'test-secret', 'test-model', transport=transport)
        with self.renderer():
            self.runner().run_api([self.source], self.run, client=client, merchant='测试店',
                                 scope='单店', period='本周', synthetic=True)
        self.assertEqual(4, len(payloads))
        self.assertIn('variable_value', payloads[1]['messages'][-1]['content'])
        self.assertEqual(1, json.loads((self.run / 'execution.json').read_text())['corrections'])

    def test_rejected_business_review_repairs_once_with_real_tools_in_six_calls(self):
        corrected_request = request('c2')
        corrected_request['expression'] = 'income-cost-extra'
        corrected_request['variables']['extra'] = {'value': 10, 'assumption': '追加试行费用，情景假设'}
        corrected = report()
        corrected['money']['calc_id'] = 'c2'
        corrected['charts'][0]['series'][0]['calc_id'] = 'c2'
        corrected['actions'][0]['stop'] = '相对可比基线的贡献差额转负时停止'
        issues = ['主金额须扣除新增试行费用；继续条件应看相对可比基线的贡献差额。']
        values = [{'kind': 'calculate', 'requests': [request()]},
                  {'kind': 'final', 'report': report()},
                  {'kind': 'review', 'approved': False, 'issues': issues},
                  {'kind': 'calculate', 'requests': [corrected_request]},
                  {'kind': 'final', 'report': corrected},
                  {'kind': 'review', 'approved': True, 'issues': []}]
        payloads = []
        def transport(url, payload, *args):
            payloads.append(json.loads(payload))
            return envelope({'role': 'assistant', 'content': json.dumps(values.pop(0))})
        client = ModelClient('deepseek', 'test-secret', 'test-model', transport=transport)
        with self.renderer():
            self.runner().run_api([self.source], self.run, client=client, merchant='测试店', synthetic=True)
        self.assertEqual(6, len(payloads))
        self.assertIn(issues[0], payloads[3]['messages'][-1]['content'])
        self.assertEqual(50, json.loads((self.run / 'report.json').read_text())['money']['value'])
        execution = json.loads((self.run / 'execution.json').read_text())
        self.assertEqual(1, execution['business_revisions'])
        self.assertEqual(6, execution['model_calls'])
        self.assertEqual(4, execution['analysis_calls'])
        self.assertEqual(2, execution['review_calls'])
        self.assertEqual(2, len(execution['business_reviews']))
        self.assertEqual('approved', execution['business_review']['status'])

    def test_second_business_rejection_never_exports_or_rewrites_again(self):
        values = [{'kind': 'calculate', 'requests': [request()]},
                  {'kind': 'final', 'report': report()},
                  {'kind': 'review', 'approved': False, 'issues': ['变量并非来源中的原始数值']},
                  {'kind': 'final', 'report': report()},
                  {'kind': 'review', 'approved': False, 'issues': ['仍未解决变量原值问题']}]
        client = ModelClient('deepseek', 'test-secret', 'test-model', transport=lambda *args:
            envelope({'role': 'assistant', 'content': json.dumps(values.pop(0))}))
        with self.assertRaises(ValueError), self.renderer():
            self.runner().run_api([self.source], self.run, client=client, merchant='测试店', synthetic=True)
        self.assertFalse((self.run / 'report.html').exists())
        execution = json.loads((self.run / 'execution.json').read_text())
        self.assertEqual('failed', execution['status'])
        self.assertEqual('rejected', execution['business_review']['status'])
        self.assertEqual(5, execution['model_calls'])

    def test_reviewer_cannot_call_tools_or_invent_a_new_report(self):
        values = [{'kind': 'calculate', 'requests': [request()]},
                  {'kind': 'final', 'report': report()},
                  {'kind': 'calculate', 'requests': [request('unauthorised-review-calculation')]}]
        client = ModelClient('deepseek', 'test-secret', 'test-model', transport=lambda *args:
            envelope({'role': 'assistant', 'content': json.dumps(values.pop(0))}))
        with self.assertRaises(ValueError):
            self.runner().run_api([self.source], self.run, client=client, merchant='测试店', synthetic=True)
        self.assertFalse((self.run / 'report.html').exists())
        self.assertEqual(['c1'], [c['id'] for c in json.loads((self.run / 'calculations.json').read_text())])

    def test_final_without_remaining_review_budget_is_not_exported(self):
        final = report()
        final['money'].pop('calc_id')
        final['money']['value'] = None
        final['charts'] = []
        client = ModelClient('deepseek', 'test-secret', 'test-model', transport=lambda *args:
            envelope({'role': 'assistant', 'content': json.dumps({'kind': 'final', 'report': final})}))
        with self.assertRaises(ValueError), self.renderer():
            self.runner().run_api([self.source], self.run, client=client, merchant='测试店',
                                 synthetic=True, max_calls=1)
        self.assertFalse((self.run / 'report.html').exists())

    def test_api_export_io_failure_keeps_approved_same_draft_recoverable(self):
        values = [{'kind': 'calculate', 'requests': [request()]}, {'kind': 'final', 'report': report()},
                  {'kind': 'review', 'approved': True, 'issues': []}]
        client = ModelClient('deepseek', 'test-secret', 'test-model', transport=lambda *args:
            envelope({'role': 'assistant', 'content': json.dumps(values.pop(0))}))
        def fail(*args, **kwargs):
            raise OSError('temporary exporter failure')
        with patch.dict(sys.modules, {'boss_report': types.SimpleNamespace(export_boss=fail)}), self.assertRaises(OSError):
            self.runner().run_api([self.source], self.run, client=client, merchant='测试店', synthetic=True)
        state = json.loads((self.run / 'execution.json').read_text())
        self.assertEqual('export_failed', state['status'])
        self.assertEqual('approved', state['business_review']['status'])
        with self.renderer():
            self.runner().finish_run(self.run, report())
        self.assertEqual(3, json.loads((self.run / 'execution.json').read_text())['model_calls'])

    def test_two_batches_then_forced_final_and_review_extra_fields_are_tolerated(self):
        values = [{'kind': 'calculate', 'requests': [request()]},
                  {'kind': 'calculate', 'requests': [request('c2')]},
                  {'kind': 'calculate', 'requests': [request('must-not-execute')]},
                  {'kind': 'final', 'report': report()},
                  {'kind': 'review', 'approved': True, 'issues': [], 'calculations_checked': True}]
        payloads = []
        def transport(url, payload, *args):
            payloads.append(json.loads(payload))
            return envelope({'role': 'assistant', 'content': json.dumps(values.pop(0))})
        client = ModelClient('deepseek', 'test-secret', 'test-model', transport=transport)
        with self.renderer():
            self.runner().run_api([self.source], self.run, client=client, merchant='测试店', synthetic=True)
        self.assertEqual(['auto', 'auto', 'none', 'none', 'none'], [p['tool_choice'] for p in payloads])
        self.assertEqual(['c1', 'c2'], [c['id'] for c in json.loads((self.run / 'calculations.json').read_text())])
        state = json.loads((self.run / 'execution.json').read_text())
        self.assertEqual(['calculations_checked'], state['business_review']['ignored_fields'])
        self.assertEqual('none', json.loads((self.run / 'request-003.json').read_text())['settings']['tool_choice'])
        self.assertNotIn('\n', payloads[0]['messages'][2]['content'])

    def test_two_initial_batches_and_one_revision_batch_fit_total_budget(self):
        values = [{'kind': 'calculate', 'requests': [request()]},
                  {'kind': 'calculate', 'requests': [request('c2')]},
                  {'kind': 'final', 'report': report()},
                  {'kind': 'review', 'approved': False, 'issues': ['核查费用口径'], 'extra': True},
                  {'kind': 'calculate', 'requests': [request('c3')]},
                  {'kind': 'final', 'report': report()},
                  {'kind': 'review', 'approved': True, 'issues': []}]
        payloads = []
        def transport(url, payload, *args):
            payloads.append(json.loads(payload))
            return envelope({'role': 'assistant', 'content': json.dumps(values.pop(0))})
        client = ModelClient('deepseek', 'test-secret', 'test-model', transport=transport)
        with self.renderer():
            self.runner().run_api([self.source], self.run, client=client, merchant='测试店', synthetic=True)
        self.assertEqual(['auto', 'auto', 'none', 'none', 'auto', 'none', 'none'], [p['tool_choice'] for p in payloads])
        self.assertEqual(7, json.loads((self.run / 'execution.json').read_text())['model_calls'])
        self.assertIn('有证据驳回', payloads[4]['messages'][-1]['content'])


if __name__ == '__main__':
    unittest.main()
