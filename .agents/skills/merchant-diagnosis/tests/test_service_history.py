"""Offline regression coverage for reviewed, transitive diagnostic history."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from test_service_runner import FakeClient, S1, S2, S3, S4, S5, decisions, final
import service_runner as runner
import service_store as store


class ServiceHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.project = self.base / 'merchant'
        store.create_project(self.project, '演示店', '提高经营贡献', True)
        public = self.base / 'public.md'
        public.write_text('顾客提及变凉')
        store.add_material(self.project, public, 'public', 'public', '本次')
        self.public = runner.run_project(self.project, 'public', FakeClient([
            final(S1.replace('F1', 'F3')), final(S2.replace('F1', 'F3'))]))
        store.record_review(self.project, self.public['id'], 'Tester', '初诊已复核', True)
        self.raw = self.base / 'raw.csv'
        self.raw.write_text('store,income\nS01,10\n')
        store.add_material(self.project, self.raw, 'weekly', 'business', 'W1')
        self.diagnosis = runner.run_project(self.project, 'diagnosis', FakeClient([
            final(S3), final(S4, decisions()), final(S5, decisions())]))
        self.assertEqual('awaiting_review', self.diagnosis['status'])
        store.record_review(self.project, self.diagnosis['id'], 'Tester', '诊断已复核', True)

    def reseal_fixture(self, record):
        directory = self.project / record['path']
        store.write_json(directory / 'artifacts.json', {
            str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob('*') if p.is_file() and p.name != 'artifacts.json'})

    def replace_fixture_parent(self, record, parent_id):
        data = store.read_project(self.project)
        next(r for r in data['runs'] if r['id'] == record['id'])['previous_run'] = parent_id
        store.write_json(self.project / 'project.json', data)
        execution_path = self.project / record['path'] / 'execution.json'
        execution = json.loads(execution_path.read_text())
        execution['previous_run'] = parent_id
        store.write_json(execution_path, execution)
        record['previous_run'] = parent_id
        self.reseal_fixture(record)

    def test_followup_receives_public_ancestor_definitions_in_oldest_first_order(self):
        self.raw.write_text('store,income\nS01,2\n')
        store.add_material(self.project, self.raw, 'weekly', 'business', 'W2', replace=True)
        report = S4.replace('| F1 | 调整 |', '| F3 | 调整 |')
        client = FakeClient([final(S3), final(report, decisions()), final(S5, decisions())])
        record = runner.run_project(self.project, 'followup', client)
        self.assertEqual('awaiting_review', record['status'])
        first_history = json.loads(client.messages[0][1]['content'])['input']['history']
        expected = [S1.replace('F1', 'F3'), S2.replace('F1', 'F3'), S3, S4]
        self.assertEqual(expected, [item['text'] for item in first_history[:4]])
        self.assertEqual(7, len(first_history))
        self.assertEqual(['report.md', 'report.md', 'report.md', 'report.md',
                          'decisions.json', 'report.md', 'decisions.json'],
                         [item['original_name'] for item in first_history])

    def test_history_verifies_ancestor_hashes_and_file_set(self):
        stage = self.project / self.public['path'] / 'S1'
        report = stage / 'report.md'
        original = report.read_bytes()
        report.write_text('篡改公开祖先')
        with self.assertRaisesRegex(ValueError, '产物已变化'):
            runner._history(self.project, self.diagnosis)
        report.write_bytes(original)
        (stage / 'extra.md').write_text('未登记的祖先材料')
        with self.assertRaisesRegex(ValueError, '产物已变化'):
            runner._history(self.project, self.diagnosis)

    def test_history_rejects_missing_link(self):
        self.replace_fixture_parent(self.diagnosis, 'run-missing')
        with self.assertRaisesRegex(ValueError, '缺失|不存在'):
            runner._history(self.project, self.diagnosis)

    def test_history_requires_latest_approval_for_every_ancestor(self):
        store.record_review(self.project, self.public['id'], 'Tester', '祖先撤回复核', False)
        with self.assertRaisesRegex(ValueError, '复核'):
            runner._history(self.project, self.diagnosis)

    def test_history_rejects_cycle(self):
        self.replace_fixture_parent(self.public, self.diagnosis['id'])
        with self.assertRaisesRegex(ValueError, '循环'):
            runner._history(self.project, self.diagnosis)

    def test_history_rejects_foreign_project_ancestor(self):
        path = self.project / self.public['path'] / 'snapshot.json'
        snapshot = json.loads(path.read_text())
        snapshot['project_id'] = 'merchant-other'
        store.write_json(path, snapshot)
        self.reseal_fixture(self.public)
        with self.assertRaisesRegex(ValueError, '本商家|本项目'):
            runner._history(self.project, self.diagnosis)

    def test_api_run_refuses_test_double_history_before_calling_or_registering(self):
        self.raw.write_text('store,income\nS01,2\n')
        store.add_material(self.project, self.raw, 'weekly', 'business', 'W2', replace=True)
        client = FakeClient([final(S3), final(S4, decisions()), final(S5, decisions())])
        client.mode = 'api'
        before = store.read_project(self.project)['runs']
        with self.assertRaisesRegex(ValueError, '来源|替身'):
            runner.run_project(self.project, 'followup', client)
        self.assertEqual([], client.messages)
        self.assertEqual(before, store.read_project(self.project)['runs'])

    def test_history_rejects_mixed_ancestor_execution_sources(self):
        execution_path = self.project / self.public['path'] / 'execution.json'
        execution = json.loads(execution_path.read_text())
        execution['executor'] = 'DeepSeek API'
        store.write_json(execution_path, execution)
        self.reseal_fixture(self.public)
        with self.assertRaisesRegex(ValueError, '来源|替身'):
            runner._history(self.project, self.diagnosis)


if __name__ == '__main__':
    unittest.main()
