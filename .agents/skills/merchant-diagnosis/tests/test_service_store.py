import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


class ServiceStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.project = self.base / 'shop'

    def store(self):
        self.assertIsNotNone(importlib.util.find_spec('service_store'), 'service_store is not implemented')
        return importlib.import_module('service_store')

    def create(self):
        s = self.store()
        s.create_project(self.project, '合成店', '改善经营贡献', True)
        return s

    def material(self, name='weekly.csv', text='收入,成本\n100,60\n'):
        p = self.base / name
        p.write_text(text)
        return p

    def test_replacement_keeps_old_bytes_and_only_new_revision_is_active(self):
        s = self.create()
        source = self.material()
        first = s.add_material(self.project, source, 'weekly', 'business', 'W1')
        source.write_text('收入,成本\n100,90\n')
        with self.assertRaises(ValueError):
            s.add_material(self.project, source, 'weekly', 'business', 'W1')
        second = s.add_material(self.project, source, 'weekly', 'business', 'W1', replace=True)
        self.assertNotEqual(first['sha256'], second['sha256'])
        snap = s.snapshot(self.project, 'diagnosis')
        self.assertEqual([2], [m['revision'] for m in snap['materials']])
        self.assertEqual('收入,成本\n100,60\n', (self.project / first['path']).read_text())
        self.assertEqual(2, snap['material_version'])

    def test_duplicate_has_no_revision_and_duplicate_content_in_another_slot_rejected(self):
        s = self.create()
        source = self.material()
        a = s.add_material(self.project, source, 'weekly', 'business', 'W1')
        b = s.add_material(self.project, source, 'weekly', 'business', 'W1')
        self.assertEqual(a, b)
        with self.assertRaises(ValueError):
            s.add_material(self.project, source, 'copy', 'business', 'W1')
        self.assertEqual(1, s.read_project(self.project)['material_version'])

    def test_revision_keeps_original_period_after_correction(self):
        s = self.create()
        source = self.material()
        s.add_material(self.project, source, 'weekly', 'business', '误标期间')
        s.add_material(self.project, source, 'weekly', 'business', '更正期间', replace=True)
        versions = s.read_project(self.project)['materials']['weekly']['versions']
        self.assertEqual(['误标期间', '更正期间'], [v['period'] for v in versions])

    def test_public_snapshot_cannot_read_business_or_receipts(self):
        s = self.create()
        s.add_material(self.project, self.material('public.md', '店铺菜单与评价'), 'public', 'public', '本次')
        s.add_material(self.project, self.material(), 'weekly', 'business', 'W1')
        s.add_material(self.project, self.material('receipt.md', '执行回执'), 'receipt', 'receipt', 'W1')
        self.assertEqual(['public'], [m['slot'] for m in s.snapshot(self.project, 'public')['materials']])
        self.assertEqual(3, len(s.snapshot(self.project, 'diagnosis')['materials']))

    def test_bad_input_no_state_mutation_and_new_project_cannot_overwrite(self):
        s = self.create()
        before = (self.project / 'project.json').read_bytes()
        with self.assertRaises(ValueError):
            s.add_material(self.project, self.material('bad.png', 'not image'), 'weekly', 'business', 'W1')
        with self.assertRaises(ValueError):
            s.add_material(self.project, self.material(), '../escape', 'business', 'W1')
        self.assertEqual(before, (self.project / 'project.json').read_bytes())
        with self.assertRaises(ValueError):
            s.create_project(self.project, '覆盖', '覆盖', True)

    def test_snapshot_rejects_tampered_file_and_concurrent_lock(self):
        s = self.create()
        m = s.add_material(self.project, self.material(), 'weekly', 'business', 'W1')
        (self.project / m['path']).write_text('tampered')
        with self.assertRaises(ValueError):
            s.snapshot(self.project, 'diagnosis')
        (self.project / '.write.lock').write_text('another process')
        with self.assertRaises(ValueError):
            s.add_material(self.project, self.material('second.md', 'new'), 'new', 'public', 'W2')

    def test_same_filename_in_two_active_slots_rejected(self):
        s = self.create()
        source = self.material()
        s.add_material(self.project, source, 'weekly', 'business', 'W1')
        other = self.base / 'other'
        other.mkdir()
        (other / source.name).write_text('收入,成本\n200,50\n')
        with self.assertRaises(ValueError):
            s.add_material(self.project, other / source.name, 'next', 'business', 'W2')

    def test_review_is_append_only_and_stale_results_cannot_be_approved(self):
        s = self.create()
        s.add_material(self.project, self.material(), 'weekly', 'business', 'W1')
        record = {'id': 'run-a', 'material_version': 1, 'status': 'awaiting_review', 'path': 'runs/run-a',
                  'phase': 'diagnosis', 'inference_executed': False}
        s.register_run(self.project, record)
        s.record_review(self.project, 'run-a', 'Jim', '核对来源和公式', True)
        self.assertEqual('run-a', s.reviewed_run(self.project)['id'])
        s.add_material(self.project, self.material('extra.md', '成本更正'), 'extra', 'definition', 'W1')
        with self.assertRaises(ValueError):
            s.record_review(self.project, 'run-a', 'Jim', '再次确认', True)
        self.assertEqual('run-a', s.reviewed_run(self.project)['id'])
        self.assertEqual(1, len(s.read_project(self.project)['reviews']))

    def test_rejected_run_does_not_become_latest_approved(self):
        s = self.create()
        s.register_run(self.project, {'id': 'run-a', 'material_version': 0, 'status': 'awaiting_review', 'path': 'runs/run-a'})
        s.record_review(self.project, 'run-a', 'Jim', '证据不充分', False)
        self.assertIsNone(s.reviewed_run(self.project))
        self.assertEqual('*\n', (self.project / '.gitignore').read_text())


if __name__ == '__main__':
    unittest.main()
