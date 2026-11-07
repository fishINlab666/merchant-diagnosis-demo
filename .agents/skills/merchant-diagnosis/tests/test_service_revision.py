"""Offline S5 revision checks; fixture API labels never prove real inference."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_service_runner import FakeClient, S3, S4, S5, decisions, final
import service_runner as runner
import service_store as store


class FinalRevisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.project = self.base / 'merchant'
        store.create_project(self.project, '演示店', '提高经营贡献', True)
        self.raw = self.base / 'raw.csv'
        self.raw.write_text('store,income\nS01,10\n')
        store.add_material(self.project, self.raw, 'weekly', 'business', 'W1')

    def client(self, replies, mode='test_double'):
        client = FakeClient(replies)
        client.mode = mode
        original = client.complete
        def complete(messages):
            result = original(messages)
            result['metadata']['inference_executed'] = mode == 'api'
            return result
        client.complete = complete
        return client

    def source(self, phase='diagnosis', previous_id=None, mode='test_double'):
        request = {'kind': 'calculate', 'requests': [{'id': 'prior1', 'expression': 'a-b',
            'unit': '元', 'purpose': '合成核算', 'variables': {
                'a': {'value': 3, 'assumption': '测试输入'},
                'b': {'value': 1, 'assumption': '测试输入'}}}]}
        record = runner.run_project(self.project, phase, self.client([
            request, final(S3), final(S4, decisions()),
            final(S5.replace('先补成本，维持预算。', '错误原稿占位。'), decisions())], mode), previous_id)
        self.assertEqual('awaiting_review', record['status'])
        return record

    def reject(self, source, note='S5遗漏执行费与月度值'):
        return store.record_review(self.project, source['id'], 'Tester', note, False)

    def revise(self, source, client=None, **kwargs):
        try:
            return runner.run_project(self.project, source['phase'], client or self.client([
                final(S5, decisions())]), revise_final_id=source['id'], **kwargs)
        except TypeError as error:
            self.fail(f'run_project 必须接受 revise_final_id：{error}')

    def reject_before_run(self, source, **kwargs):
        before = store.read_project(self.project)['runs']
        client = kwargs.pop('client', self.client([final(S5, decisions())]))
        with self.assertRaises(ValueError):
            self.revise(source, client, **kwargs)
        self.assertEqual([], client.messages)
        self.assertEqual(before, store.read_project(self.project)['runs'])

    def test_revision_reuses_original_stages_calculations_and_latest_source_rejection(self):
        source = self.source()
        source_dir = self.project / source['path']
        before = {str(p.relative_to(source_dir)): p.read_bytes()
                  for p in source_dir.rglob('*') if p.is_file()}
        self.reject(source, '旧意见')
        latest = self.reject(source)
        unrelated = self.source()
        self.reject(unrelated, '其他运行意见不可混入')
        client = self.client([final(S5, decisions())])
        actual_prepare = runner.prepare_stage
        def new_rules(stage, *args, **kwargs):
            result = actual_prepare(stage, *args, **kwargs)
            prompt = Path(args[1]) / 'prompt.md'
            prompt.write_text('新规则仅作用本轮S5\n' + prompt.read_text())
            return result
        with patch('service_runner.prepare_stage', side_effect=new_rules) as prepare:
            revised = self.revise(source, client)
        self.assertEqual('awaiting_review', revised['status'])
        self.assertEqual(['S3', 'S4', 'S5'], revised['completed_stages'])
        self.assertEqual(['S3', 'S4'], revised['reused_stages'])
        self.assertEqual(['S5'], revised['fresh_stages'])
        self.assertEqual(source['id'], revised['source_run'])
        self.assertFalse(revised['inference_executed'])
        self.assertEqual(['S5'], [c.args[0] for c in prepare.call_args_list])
        destination = self.project / revised['path']
        for name, raw in before.items():
            self.assertEqual(raw, (source_dir / name).read_bytes())
            if name.startswith(('S3/', 'S4/')):
                self.assertEqual(raw, (destination / name).read_bytes())
        execution = json.loads((destination / 'execution.json').read_text())
        self.assertEqual(['S5'], [c['stage'] for c in execution['calls']])
        self.assertEqual(source['id'], execution['source_run'])
        request = json.loads(client.messages[0][1]['content'])
        self.assertEqual(latest, request['context']['review_feedback'])
        self.assertEqual(2, request['current_run_calculations'][0]['value'])
        history = request['input']['history']
        self.assertTrue(any(h['text'] == S4 for h in history))
        self.assertNotIn('错误原稿占位', json.dumps(history, ensure_ascii=False))
        runner._verify_run(self.project, revised)

    def test_revision_still_rejects_changed_s4_decision_core(self):
        source = self.source()
        self.reject(source)
        changed = decisions()
        changed['goal'] = '不可从S5改变目标'
        revised = self.revise(source, self.client([final(S5, changed), final(S5, changed)]))
        self.assertEqual('failed', revised['status'])
        self.assertEqual(['S3', 'S4'], revised['completed_stages'])
        self.assertIn('S5：', (self.project / revised['path'] / 'failure.md').read_text())

    def test_revision_requires_latest_rejection_and_complete_nonfailed_source(self):
        source = self.source()
        self.reject_before_run(source)
        self.reject(source)
        store.record_review(self.project, source['id'], 'Tester', '后来通过', True)
        self.reject_before_run(source)
        self.reject(source)
        for field, value in (('status', 'failed'), ('completed_stages', ['S3', 'S4'])):
            data = store.read_project(self.project)
            original = copy.deepcopy(data)
            data['runs'][0][field] = value
            store.write_json(self.project / 'project.json', data)
            self.reject_before_run(source)
            store.write_json(self.project / 'project.json', original)

    def test_revision_refuses_different_project_phase_and_material_version(self):
        source = self.source()
        self.reject(source)
        self.reject_before_run({**source, 'id': 'run-from-other-project'})
        for phase in ('public', 'followup'):
            self.reject_before_run({**source, 'phase': phase})
        self.raw.write_text('store,income\nS01,20\n')
        store.add_material(self.project, self.raw, 'weekly', 'business', 'W1', replace=True)
        self.reject_before_run(source)

    def test_revision_compares_full_snapshot_not_only_material_version(self):
        source = self.source()
        self.reject(source)
        original = store.read_project(self.project)
        for field, value in (('goal', '换一个目标'), ('name', '另一门店'), ('synthetic', False)):
            data = copy.deepcopy(original)
            data[field] = value
            store.write_json(self.project / 'project.json', data)
            self.reject_before_run(source)
        store.write_json(self.project / 'project.json', original)

    def test_revision_rejects_changed_or_extra_source_artifacts(self):
        source = self.source()
        self.reject(source)
        stage = self.project / source['path'] / 'S3'
        report = stage / 'report.md'
        original = report.read_bytes()
        report.write_text('篡改报告')
        self.reject_before_run(source)
        report.write_bytes(original)
        (stage / 'extra.md').write_text('未登记文件')
        self.reject_before_run(source)

    def test_revision_preserves_empty_previous_instead_of_choosing_latest_approved(self):
        source = self.source()
        self.reject(source)
        later = self.source()
        store.record_review(self.project, later['id'], 'Tester', '其他运行已复核', True)
        revised = self.revise(source)
        self.assertIsNone(revised['previous_run'])
        self.reject_before_run(source, previous_id=later['id'])

    def test_followup_revision_inherits_source_previous_and_rejects_different_previous(self):
        prior = self.source()
        store.record_review(self.project, prior['id'], 'Tester', '已复核前序', True)
        self.raw.write_text('store,income\nS01,2\n')
        store.add_material(self.project, self.raw, 'weekly', 'business', 'W2', replace=True)
        source = self.source('followup', prior['id'])
        self.reject(source)
        revised = self.revise(source)
        self.assertEqual('awaiting_review', revised['status'])
        self.assertEqual(prior['id'], revised['previous_run'])
        self.reject_before_run(source, previous_id=source['id'])

    def test_test_double_source_cannot_be_relabelled_as_api(self):
        source = self.source()
        self.reject(source)
        self.reject_before_run(source, client=self.client([], 'api'))
        data = store.read_project(self.project)
        data['runs'][0]['mode'] = 'api'
        store.write_json(self.project / 'project.json', data)
        self.reject_before_run(source, client=self.client([], 'api'))

    def test_revision_rejects_api_label_without_matching_response_provenance(self):
        client = FakeClient([final(S3), final(S4, decisions()), final(S5, decisions())])
        client.mode = 'api'
        source = runner.run_project(self.project, 'diagnosis', client)
        self.assertEqual('awaiting_review', source['status'])
        self.reject(source)
        self.reject_before_run(source, client=self.client([], 'api'))

    def test_api_revision_records_only_current_inference_even_when_source_inferred(self):
        from model_api import ModelAPIError
        source = self.source(mode='api')
        self.reject(source)
        client = self.client([ModelAPIError('timeout')], mode='api')
        revised = self.revise(source, client)
        self.assertFalse(revised['inference_executed'])
        self.assertTrue(revised['api_attempted'])
        self.assertEqual(['S3', 'S4'], revised['completed_stages'])
        self.assertEqual('failed', revised['status'])


if __name__ == '__main__':
    unittest.main()
