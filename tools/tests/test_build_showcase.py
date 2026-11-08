"""Run the real build and copy gate in isolated repositories, without publishing."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SOURCE_ROOT = Path(__file__).resolve().parents[2]
CURRENT_REPORTS = ('public/reports/audience-chain.html',
                   'public/reports/audience-chain-v183.html',
                   'public/reports/single-v183.html',
                   'public/reports/api-chain-v183.html')
RECORDING_CONSOLE = 'tools/recording-console.html'


class BuildShowcaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='showcase-build-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in ('scripts/build-showcase.py', 'tools/check_product_copy.py'):
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SOURCE_ROOT / name, destination)
        for name in ('index.html', 'README.md', '.agents/skills/merchant-diagnosis/README.md',
                     RECORDING_CONSOLE, *CURRENT_REPORTS):
            self.write(name, '<h1>老板看板／产品讲解</h1>\n')
        self.write('.agents/skills/merchant-diagnosis/assets/boss-report.js',
                   'const title = "产品讲解";\n')
        self.write('public/assets/current.css', 'body { color: black; }\n')
        self.write('dist/index.html', '<h1>上次已发布内容</h1>\n')
        self.write('dist/assets/existing.bin', '原有产物不得在失败时被覆盖\n')

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def build(self):
        return subprocess.run([sys.executable, '-B', str(self.root / 'scripts/build-showcase.py')],
                              cwd=self.root / 'tools', text=True, capture_output=True)

    def dist_snapshot(self):
        return {str(path.relative_to(self.root / 'dist')): path.read_bytes()
                for path in (self.root / 'dist').rglob('*') if path.is_file()}

    def test_valid_current_surfaces_build_and_copy_current_content(self):
        result = self.build()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual((self.root / 'index.html').read_bytes(),
                         (self.root / 'dist/index.html').read_bytes())
        for name in CURRENT_REPORTS:
            output = self.root / 'dist' / Path(name).relative_to('public')
            self.assertEqual((self.root / name).read_bytes(), output.read_bytes())
        self.assertTrue((self.root / 'dist/assets/current.css').is_file())
        self.assertFalse((self.root / 'dist/assets/existing.bin').exists())

    def test_each_current_report_and_recording_entry_blocks_bad_positioning_before_dist_changes(self):
        before = self.dist_snapshot()
        for name in (*CURRENT_REPORTS, RECORDING_CONSOLE):
            with self.subTest(surface=name):
                path = self.root / name
                original = path.read_bytes()
                self.write(name, '<button aria-label="面试展示">打开</button>\n')
                result = self.build()
                self.assertNotEqual(0, result.returncode)
                self.assertIn(name + ':1: 面试', result.stdout)
                self.assertEqual(before, self.dist_snapshot())
                path.write_bytes(original)

    def test_report_json_positioning_and_dynamic_script_are_also_gated(self):
        before = self.dist_snapshot()
        for name, content in (
                ('public/reports/single-v183.html',
                 '<script id="boss-data" type="application/json">'
                 '{"headline":"\\u9762\\u8bd5展示"}</script>'),
                ('.agents/skills/merchant-diagnosis/assets/boss-report.js',
                 'const title = "面试展示";')):
            with self.subTest(surface=name):
                path = self.root / name
                original = path.read_bytes()
                self.write(name, content)
                result = self.build()
                self.assertNotEqual(0, result.returncode)
                self.assertIn(name + ':1: 面试', result.stdout)
                self.assertEqual(before, self.dist_snapshot())
                path.write_bytes(original)

    def test_each_missing_current_report_fails_without_overwriting_dist(self):
        before = self.dist_snapshot()
        for name in CURRENT_REPORTS:
            with self.subTest(surface=name):
                path = self.root / name
                original = path.read_bytes()
                path.unlink()
                result = self.build()
                self.assertNotEqual(0, result.returncode)
                self.assertIn(name + ': FileNotFoundError', result.stderr)
                self.assertEqual(before, self.dist_snapshot())
                path.write_bytes(original)

    def test_archived_report_is_not_relabelled_or_checked_as_a_current_product_surface(self):
        archived = self.write('public/reports/archived/old-report.html',
                              '<h1>历史原件：面试与求职背景</h1>\n'
                              '<p>版本 1.7，未启用新方法。</p>\n')
        original = archived.read_bytes()
        result = self.build()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(original, archived.read_bytes())
        self.assertEqual(original, (self.root / 'dist/reports/archived/old-report.html').read_bytes())


if __name__ == '__main__':
    unittest.main(verbosity=2)
