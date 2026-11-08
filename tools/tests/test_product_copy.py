"""Offline checks for the wording on explicitly selected product surfaces."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'check_product_copy.py'
DEFAULT_FILES = ('index.html', 'README.md', '.agents/skills/merchant-diagnosis/README.md')


class ProductCopyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='product-copy-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in DEFAULT_FILES:
            self.write(name, '老板看板／产品讲解')

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def check(self, *args, root=None, script=SOURCE, cwd=None):
        self.assertTrue(script.is_file(), 'product copy checker must exist')
        command = [sys.executable, '-B', str(script)]
        if root is not False:
            command.extend(['--root', str(self.root if root is None else root)])
        return subprocess.run(command + list(args), cwd=cwd, text=True, capture_output=True)

    def test_approved_product_modes_pass(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_chinese_and_english_positioning_is_rejected_without_context_dump(self):
        for term in ('面试', '求职', '应聘', 'interview', 'INTERVIEWS',
                     'job-seeking', 'job seeking', 'Job Hunting', 'job-hunting'):
            with self.subTest(term=term):
                self.write('README.md', '# 产品\n\n私人上下文前缀 ' + term + ' 私人上下文后缀\n')
                result = self.check()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout.strip(), 'README.md:3: ' + term)
                self.assertEqual(result.stderr, '')

    def test_html_visible_attributes_and_metadata_are_checked(self):
        examples = (
            '<head><title>面试展示</title></head>',
            '<head><meta name="description" content="求职作品"></head>',
            '<meta name="keywords" content="面试">',
            '<meta property="og:title" content="求职作品">',
            '<meta property="og:description" content="应聘展示">',
            '<meta name="twitter:title" content="interview demo">',
            '<meta name="twitter:description" content="job-seeking demo">',
            '<button aria-label="应聘展示">打开</button>',
            '<a title="Interview demo">打开</a>',
            '<img alt="job hunting demo">',
            '<button\n aria-label="面试">打开</button>',
        )
        for html in examples:
            with self.subTest(html=html):
                self.write('index.html', html)
                result = self.check()
                self.assertEqual(result.returncode, 1, result.stderr)
                line = 2 if '\n' in html else 1
                self.assertTrue(result.stdout.startswith(f'index.html:{line}: '), result.stdout)

    def test_html_entities_and_inline_fragments_are_checked(self):
        for html in ('<p>面<span>试</span>展示</p>', '<p>求&#32844;作品</p>',
                     '<p>job&nbsp;hunting</p>', '<p>job-<b>seeking</b></p>',
                     '<button aria-label="面&#35797;展示">打开</button>'):
            with self.subTest(html=html):
                self.write('index.html', '<!doctype html>\n' + html)
                result = self.check()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertTrue(result.stdout.startswith('index.html:2: '), result.stdout)

    def test_generated_report_payload_is_checked_after_json_decoding(self):
        self.write('index.html', '<h1>老板看板</h1>\n'
                   '<script id="boss-data" type="application/json">'
                   '{"headline":"\\u9762\\u8bd5展示","methods":[{"name":"求职作品"}]}'
                   '</script>')
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('index.html:2: 面试', result.stdout)
        self.assertIn('index.html:2: 求职', result.stdout)

    def test_invalid_report_payload_blocks_instead_of_skipping_copy_check(self):
        self.write('index.html', '<script id="boss-data" type="application/json">{broken}</script>')
        result = self.check()
        self.assertEqual(result.returncode, 2)
        self.assertIn('index.html', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_html_script_style_comments_and_noncopy_attributes_are_ignored(self):
        self.write('index.html', '''<!doctype html><html><head>
<script>const old = "面试 interview";</script>
<style>.job-seeking { color: red; } /* 求职 */</style>
<meta name="viewport" content="width=device-width, initial-scale=1">
</head><body><!-- 应聘 -->
<a href="old/面试.html" id="interview" class="job-seeking" data-old="求职">老板看板</a>
<p>产品讲解</p><p>面</p><p>试</p>
</body></html>''')
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_markdown_ignores_link_destinations_and_old_paths_in_code(self):
        self.write('README.md', '''# 老板看板
[产品讲解](docs/面试说明.md)
[报告][old]
[old]: docs/job-seeking.html
旧文件：`docs/应聘说明.md`、`interview.html`
```sh
python tools/job-seeking.py
```
''')
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_markdown_backticks_and_link_labels_cannot_hide_button_copy(self):
        for content in ('按钮：`面试展示`', '[求职展示](index.html)', '```text\n应聘展示\n```'):
            with self.subTest(content=content):
                self.write('README.md', content)
                result = self.check()
                self.assertEqual(result.returncode, 1, result.stderr)

    def test_default_scope_does_not_scan_rules_history_or_raw_materials(self):
        for name in ('AGENTS.md', 'ACCEPTANCE.md', 'docs/经历.md',
                     '.agents/skills/merchant-diagnosis/SKILL.md',
                     '.agents/skills/merchant-diagnosis/examples/chain/raw/public.md',
                     'public/reports/frozen.html', 'new-product-route.html'):
            self.write(name, '面试 求职 应聘 interview job-seeking job hunting')
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_explicit_files_extend_default_scope(self):
        self.write('new-product-route.html', '<h1>面试展示</h1>')
        self.write('second-route.md', '求职作品')
        result = self.check('--file', 'new-product-route.html', '--file', 'second-route.md')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            'new-product-route.html:1: 面试', 'second-route.md:1: 求职'])
        self.write('README.md', '应聘展示')
        result = self.check('--file', 'new-product-route.html')
        self.assertIn('README.md:1: 应聘', result.stdout)

    def test_missing_root_default_file_and_extra_file_fail(self):
        result = self.check(root=self.root / 'missing')
        self.assertEqual(result.returncode, 2)
        self.assertIn('missing', result.stderr)
        result = self.check('--file', 'absent.html')
        self.assertEqual(result.returncode, 2)
        self.assertIn('absent.html', result.stderr)
        (self.root / 'README.md').unlink()
        result = self.check()
        self.assertEqual(result.returncode, 2)
        self.assertIn('README.md', result.stderr)

    def test_default_root_is_derived_from_script_not_working_directory(self):
        self.assertTrue(SOURCE.is_file(), 'product copy checker must exist')
        copied = self.root / 'tools' / SOURCE.name
        copied.parent.mkdir()
        shutil.copyfile(SOURCE, copied)
        with tempfile.TemporaryDirectory(prefix='unrelated-cwd-') as unrelated:
            self.write('README.md', '面试展示')
            result = self.check(script=copied, cwd=unrelated, root=False)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout.strip(), 'README.md:1: 面试')


if __name__ == '__main__':
    unittest.main(verbosity=2)
