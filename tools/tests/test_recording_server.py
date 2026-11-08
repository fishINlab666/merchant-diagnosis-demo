"""Offline recording-server regressions; no model calls, credentials or network.

Run from the release root:
    python3 -m unittest discover -s tools/tests -p 'test_recording_server.py' -v
"""
import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SOURCES = [Path(__file__).resolve().parents[1] / 'recording-server.py']
PARENT_VENV_TEST = '--parent-venv-test' in sys.argv


def load(source, index):
    spec = importlib.util.spec_from_file_location('recording_fixture_' + str(index), source)
    module = importlib.util.module_from_spec(spec)
    with patch.object(sys, 'dont_write_bytecode', True):
        spec.loader.exec_module(module)
    return module


def completed_fixture(directory, headline='本轮已完成判断'):
    scripts = SOURCES[0].parents[1] / '.agents/skills/merchant-diagnosis/scripts'
    code = '''import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from quick_run import prepare_run, finish_run
root = Path(sys.argv[2])
source = root.parent / ('fixture-' + root.name + '.txt')
source.parent.mkdir(parents=True, exist_ok=True)
source.write_text('仅有公开资料，金额未知。')
prepare_run([source], root, merchant='测试商家', synthetic=True)
report = {'merchant': {'name':'测试商家','scope':'本次提供材料覆盖的门店','period':'本次材料所示期间','synthetic':True},
'headline':sys.argv[3], 'money':{'label':'待核金额','value':None,'unit':'元','period':'本期'},
'actions':[{'title':'核对当前菜单','owner':'店长','timing':'今日','budget':'先确认工时',
'success':'完成原件核对','stop':'无依据不修改'}],
'followup':{'when':'核对后','collect':['当前菜单'],'decision':'决定是否更新页面'},
'analysis':{'goal':'改善经营','chosen_strategy':'先核对','execution':'尚未执行'},
'method_usage':[{'method':name,'status':'not_applicable','reason':'当前没有相关经营数据',
'decision':'当前仅核对公开资料','evidence':[],'targets':[]} for name in
('store_segmentation','audience_offer','tool_mix','execution_followup')]}
finish_run(root, report)
'''
    subprocess.run([sys.executable, '-B', '-c', code, str(scripts), str(directory), headline],
                   check=True, capture_output=True, text=True)


def final_message(directory, text):
    (directory / 'host-events.jsonl').write_text(json.dumps({
        'type': 'item.completed', 'item': {'type': 'agent_message', 'text': text}}, ensure_ascii=False) + '\n')


class RecordingRegression(unittest.TestCase):
    def test_explicit_wrong_html_filename_does_not_fall_back_to_only_old_report(self):
        module = load(SOURCES[0], 70)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            completed_fixture(root / 'run', '首稿保留')
            final_message(root, '[最终看板](run/revision-final/missing.html)')
            with self.assertRaises(ValueError):
                module.select_report(root, 'codex')

    def test_plain_backtick_and_codex_line_links_never_fall_back_and_select_existing_revision(self):
        module = load(SOURCES[0], 71)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            completed_fixture(root / 'run', '首稿保留')
            messages = ('最终交付：run/revision-final/report.html；原稿已作废。',
                        '最终交付：`run/revision-final/report.html`；原稿已作废。',
                        '[最终交付](run/revision-final/report.html:1)',
                        '[最终交付](run/revision-final/report.html:1:2)')
            for text in messages:
                with self.subTest(text=text, exists=False):
                    final_message(root, text)
                    with self.assertRaises(ValueError):
                        module.select_report(root, 'codex')
            completed_fixture(root / 'run/revision-final', '最终修订稿')
            for text in messages:
                with self.subTest(text=text, exists=True):
                    final_message(root, text)
                    self.assertEqual('run/revision-final/report.html', module.select_report(root, 'codex'))
            final_message(root, '`run/report.html` 和 run/revision-final/report.html')
            with self.assertRaises(ValueError):
                module.select_report(root, 'codex')

    def test_final_nested_revision_selects_report_and_playbook_from_same_completed_run(self):
        module = load(SOURCES[0], 40)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            completed_fixture(root / 'run', '首稿保留')
            completed_fixture(root / 'run/revision-final', '最终修订稿')
            final_message(root, '[老板看板／产品讲解](run/revision-final/report.html)')
            module.OPTIONS = SimpleNamespace(backend='codex')
            module.STATE.update(status='running', directory=root, started=time.monotonic())
            with patch.object(module, 'run_codex', return_value=SimpleNamespace(returncode=0)):
                module.worker(root, [], '测试商家')
            self.assertEqual('complete', module.STATE['status'])
            self.assertEqual('run/revision-final/report.html', module.STATE.get('output_report'))
            handler = module.Handler.__new__(module.Handler)
            replies = []
            handler.send = lambda body, content_type='application/json', status=200: replies.append((status, body))
            handler.path = '/report.html'
            handler.do_GET()
            self.assertEqual((200, (root / 'run/revision-final/report.html').read_bytes()), replies.pop())
            (root / 'run/ali-ka-playbook.md').write_text('旧稿规则改动不应影响修订稿')
            handler.path = '/playbook.html'
            handler.do_GET()
            status, content = replies.pop()
            self.assertEqual(200, status)
            self.assertNotIn('旧稿规则改动', content)
            handler.path = '/status'
            handler.do_GET()
            public = replies.pop()[1]
            self.assertEqual('run/revision-final/report.html', public['output_report'])
            self.assertNotIn(str(root), json.dumps(public))

    def test_explicit_invalid_or_ambiguous_delivery_never_falls_back_to_first_report(self):
        for index, mode in enumerate(('incomplete', 'outside', 'symlink', 'ambiguous', 'no_link_ambiguous',
                                      'html_mismatch', 'rules_changed', 'report_changed')):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                module = load(SOURCES[0], 50 + index)
                completed_fixture(root / 'run', '首稿保留')
                selected = root / 'run/revision-final'
                completed_fixture(selected, '修订稿')
                text = '[看板](run/revision-final/report.html)'
                if mode == 'incomplete':
                    path = selected / 'execution.json'
                    state = json.loads(path.read_text())
                    state['status'] = 'analysing'
                    path.write_text(json.dumps(state))
                elif mode == 'outside':
                    text = '[看板](../outside/report.html)'
                elif mode == 'symlink':
                    (root / 'run/alias').symlink_to(selected, target_is_directory=True)
                    text = '[看板](run/alias/report.html)'
                elif mode == 'ambiguous':
                    text += ' [另一看板](run/report.html)'
                elif mode == 'no_link_ambiguous':
                    text = '已完成。'
                elif mode == 'html_mismatch':
                    (selected / 'report.html').write_bytes((root / 'run/report.html').read_bytes())
                elif mode == 'rules_changed':
                    (selected / 'ali-ka-playbook.md').write_text('改写规则')
                elif mode == 'report_changed':
                    (selected / 'report.json').write_text('{}')
                final_message(root, text)
                module.OPTIONS = SimpleNamespace(backend='codex')
                module.STATE.update(status='running', directory=root, started=time.monotonic())
                with patch.object(module, 'run_codex', return_value=SimpleNamespace(returncode=0)):
                    module.worker(root, [], '测试商家')
                self.assertEqual('failed', module.STATE['status'])
                self.assertNotIn('output_report', module.STATE)

    def test_explicit_package_and_exact_utf8_goal(self):
        module = load(SOURCES[0], 30)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            skill = root / 'current-package'
            skill.mkdir()
            for name in ('SKILL.md', 'README.md', 'requirements.txt'):
                (skill / name).write_text('current ' + name, encoding='utf-8')
            for name in ('references', 'scripts', 'assets'):
                (skill / name).mkdir()
            goal = '按人群分配商品与权益。\n不适合补贴的人群不追加补贴。\n'
            goal_file = root / 'goal.txt'
            goal_file.write_text(goal, encoding='utf-8')
            options = module.parse_options(['--skill-dir', str(skill), '--goal-file', str(goal_file)])
            self.assertEqual(options.skill_dir, skill.resolve())
            self.assertEqual(options.goal, goal)
            self.assertEqual(module.parse_options([]).goal, module.GOAL)
            module.OPTIONS = options
            module.OPTIONS.codex_bin = '/fake/codex'
            directory = root / 'fresh-run'
            directory.mkdir()
            with patch.object(module.subprocess, 'run', return_value=SimpleNamespace(returncode=0)):
                module.run_codex(directory, [], '禾序饭盒', io.StringIO())
            local = directory / 'skills' / 'merchant-diagnosis'
            self.assertEqual((local / 'README.md').read_text(), 'current README.md')
            prompt = (directory / 'input-prompt.txt').read_text()
            self.assertIn('目标：' + goal, prompt)
            self.assertNotIn(module.GOAL, prompt)

    def test_invalid_goal_and_package_fail_before_startup(self):
        module = load(SOURCES[0], 32)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            goal = root / 'goal.txt'
            for body in (b'', b' \n', b'\xff'):
                goal.write_bytes(body)
                with self.subTest(body=body), patch('sys.stderr', new=io.StringIO()), self.assertRaises(SystemExit):
                    module.parse_options(['--goal-file', str(goal)])
            with patch('sys.stderr', new=io.StringIO()), self.assertRaises(SystemExit):
                module.parse_options(['--skill-dir', str(root / 'missing')])

    def test_frozen_playbook_only_after_completion_and_escaped(self):
        module = load(SOURCES[0], 31)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            completed_fixture(root / 'run')
            frozen = root / 'run' / 'ali-ka-playbook.md'
            frozen.write_text('# 本轮方法\n<script>alert(1)</script> & 原文', encoding='utf-8')
            manifest = json.loads((root / 'run/manifest.json').read_text())
            manifest['files'][frozen.name] = hashlib.sha256(frozen.read_bytes()).hexdigest()
            (root / 'run/manifest.json').write_text(json.dumps(manifest))
            handler = module.Handler.__new__(module.Handler)
            handler.path = '/playbook.html'
            responses = []
            handler.send = lambda body, content_type='application/json', status=200: responses.append((status, body))
            module.STATE.update(status='running', directory=root, output_report='run/report.html')
            handler.do_GET()
            self.assertEqual(responses.pop()[0], 404)
            module.STATE['status'] = 'complete'
            handler.do_GET()
            status, page = responses.pop()
            self.assertEqual(status, 200)
            self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt; &amp; 原文', page)
            self.assertNotIn('<script>', page)
            frozen.unlink()
            handler.do_GET()
            self.assertEqual(responses.pop()[0], 404)
            outside = root / 'private.txt'
            outside.write_text('must not be served')
            frozen.symlink_to(outside)
            handler.do_GET()
            self.assertEqual(responses.pop()[0], 404)
            handler.path = '/playbook.html?path=/etc/passwd'
            handler.do_GET()
            self.assertEqual(responses.pop()[0], 404)

    def test_parent_venv_and_fake_codex_results(self):
        if not PARENT_VENV_TEST:
            with tempfile.TemporaryDirectory(prefix='recording-parent-') as temporary:
                parent = Path(temporary) / 'parent-venv'
                subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(parent)], check=True)
                python = parent / 'bin' / 'python'
                purelib = subprocess.check_output([str(python), '-c', 'import sysconfig; print(sysconfig.get_path("purelib"))'], text=True).strip()
                (Path(purelib) / 'fixture_parent_only.py').write_text("MARKER = 'parent-only'\n")
                base = subprocess.run([sys.executable, '-I', '-c', 'import fixture_parent_only'], capture_output=True)
                self.assertNotEqual(base.returncode, 0, 'fixture must be exclusive to the parent venv')
                result = subprocess.run([str(python), '-B', str(Path(__file__).resolve()),
                                         '--parent-venv-test',
                                         'RecordingRegression.test_parent_venv_and_fake_codex_results'],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return
        import fixture_parent_only
        self.assertEqual(fixture_parent_only.MARKER, 'parent-only')
        for index, source in enumerate(SOURCES):
            with self.subTest(source=source.name), tempfile.TemporaryDirectory(prefix='recording-backend-') as temporary:
                root = Path(temporary).resolve()
                module = load(source, index)
                skill = root / 'source-skill'
                skill.mkdir()
                for name in ('SKILL.md', 'README.md', 'requirements.txt'):
                    (skill / name).write_text('fixture rules')
                for name in ('references', 'scripts', 'assets', 'examples', 'tests', '.venv', 'runs'):
                    (skill / name).mkdir()
                    (skill / name / 'marker.txt').write_text(name)
                (skill / 'scripts' / '__pycache__').mkdir()
                (skill / 'scripts' / '__pycache__' / 'stale.pyc').write_bytes(b'old')
                fake = root / 'fake-codex'
                fake.write_text('#!' + sys.executable + '\n' + '''import json, os, re, subprocess, sys
from pathlib import Path
p = Path.cwd()
prompt = sys.stdin.read()
(p / 'seen-prompt.txt').write_text(prompt)
(p / 'seen-argv.json').write_text(json.dumps(sys.argv[1:]))
python = re.search(r'所有 Python 脚本必须使用 ([^；]+)；', prompt).group(1)
result = subprocess.run([python, '-I', '-c', 'import fixture_parent_only; print(fixture_parent_only.MARKER)'], capture_output=True, text=True)
(p / 'dependency.json').write_text(json.dumps({'python': python, 'returncode': result.returncode, 'stdout': result.stdout, 'path': os.environ['PATH'].split(os.pathsep)[0]}))
print(json.dumps({'type': 'fixture.event'}))
if result.returncode:
    sys.exit(7)
mode = os.environ['FAKE_CODEX_MODE']
if mode != 'missing':
    sys.path.insert(0, os.environ['FIXTURE_HELPER_DIR'])
    from test_recording_server import completed_fixture
    completed_fixture(p / 'run')
sys.exit(3 if mode == 'nonzero' else 0)
''')
                fake.chmod(0o755)
                module.SKILL = skill
                module.OPTIONS = SimpleNamespace(backend='codex', codex_bin=str(fake), model='fixture', thinking='enabled', max_tokens=1000, config='/not-read/credentials.json')
                old = root / 'unrelated-old-run' / 'run'
                old.mkdir(parents=True)
                (old / 'report.html').write_text('old report must not satisfy this run')
                for mode in ('success', 'missing', 'nonzero'):
                    directory = root / mode
                    (directory / 'input').mkdir(parents=True)
                    inputs = []
                    for name in ('public.md', 'definitions.md', '经营周报.xlsx'):
                        path = directory / 'input' / name
                        path.write_text('raw fixture')
                        inputs.append(path)
                    module.STATE.clear()
                    module.STATE.update(status='running', started=time.monotonic(), directory=directory, backend='codex')
                    with patch.dict(os.environ, {'FAKE_CODEX_MODE': mode,
                                                'FIXTURE_HELPER_DIR': str(Path(__file__).parent)}):
                        module.worker(directory, inputs, '商家测试')
                    dependency = json.loads((directory / 'dependency.json').read_text())
                    self.assertEqual(dependency['returncode'], 0, (source.name, mode, dependency))
                    self.assertEqual(dependency['stdout'].strip(), 'parent-only')
                    self.assertEqual(dependency['python'], sys.executable)
                    self.assertEqual(dependency['path'], str(Path(sys.executable).parent))
                    self.assertNotEqual(str(Path(dependency['python']).resolve()), dependency['python'])
                    self.assertEqual(module.STATE['status'], 'complete' if mode == 'success' else 'failed')
                    self.assertEqual(module.STATE['exit_code'], 3 if mode == 'nonzero' else 0)
                    if mode == 'missing':
                        self.assertIn('未生成本次 report.html', module.STATE['error'])
                        self.assertFalse((directory / 'run' / 'report.html').exists())
                    if mode == 'nonzero':
                        self.assertTrue((directory / 'run' / 'report.html').is_file())
                    local = directory / 'skills' / 'merchant-diagnosis'
                    self.assertFalse((local / '.venv').exists())
                    self.assertTrue((directory / '.git').is_dir())
                    self.assertTrue((local / 'scripts' / 'marker.txt').is_file())
                    self.assertTrue((local / 'assets' / 'marker.txt').is_file())
                    for excluded in ('examples', 'tests', 'runs'):
                        self.assertFalse((local / excluded).exists())
                    self.assertFalse((local / 'scripts' / '__pycache__').exists())
                    prompt = (directory / 'seen-prompt.txt').read_text()
                    self.assertTrue(all(str(path) in prompt for path in inputs))
                    self.assertIn(str(directory / 'run'), prompt)
                    self.assertIn('不读取凭证', prompt)
                    self.assertNotIn(str(skill), prompt)
                    self.assertEqual(json.loads((directory / 'seen-argv.json').read_text()), ['exec', '--ephemeral', '--ignore-user-config', '--json', '--skip-git-repo-check', '--sandbox', 'workspace-write', '--color', 'never', '-'])
                    self.assertEqual((directory / 'host-events.jsonl').read_text().strip(), '{"type": "fixture.event"}')
                self.assertIn('真实 Codex', module.console_html('codex'))
                self.assertNotIn('DeepSeek', module.console_html('codex'))
                self.assertIn('DeepSeek', module.console_html('deepseek'))

    def test_concurrent_posts_reserve_exactly_one_run(self):
        original_thread = threading.Thread
        original_decode = base64.b64decode
        for index, source in enumerate(SOURCES):
            with self.subTest(source=source.name), tempfile.TemporaryDirectory(prefix='recording-race-') as temporary:
                root = Path(temporary).resolve()
                module = load(source, index + 10)
                module.OPTIONS = SimpleNamespace(port=8767, backend='codex', output=root)
                module.STATE.clear()
                module.STATE.update(status='ready', backend='codex')
                data = json.dumps({'merchant': '并发夹具', 'files': [{'name': 'raw.txt', 'data': base64.b64encode(b'raw').decode()}]}).encode()
                barrier = threading.Barrier(2)
                starts = []
                failures = []
                handlers = []
                def decoding(*args, **kwargs):
                    barrier.wait(timeout=5)
                    return original_decode(*args, **kwargs)
                class FakeWorkerThread:
                    def __init__(self, target, args, daemon):
                        self.target, self.args = target, args
                    def start(self):
                        starts.append(self.args)
                for _ in range(2):
                    handler = module.Handler.__new__(module.Handler)
                    handler.path = '/run'
                    handler.headers = {'Origin': 'http://127.0.0.1:8767', 'Content-Length': str(len(data))}
                    handler.rfile = io.BytesIO(data)
                    handler.responses = []
                    handler.send = lambda body, content_type='application/json', status=200, h=handler: h.responses.append((status, body))
                    handlers.append(handler)
                def request(handler):
                    try:
                        handler.do_POST()
                    except BaseException as exc:
                        failures.append(repr(exc))
                with patch.object(module.base64, 'b64decode', decoding), patch.object(module.threading, 'Thread', FakeWorkerThread):
                    threads = [original_thread(target=request, args=(handler,)) for handler in handlers]
                    for thread in threads:
                        thread.start()
                    for thread in threads:
                        thread.join(timeout=8)
                    self.assertFalse(any(thread.is_alive() for thread in threads))
                self.assertEqual(failures, [])
                self.assertEqual(sorted(h.responses[0][0] for h in handlers), [200, 409])
                self.assertEqual(len(starts), 1)
                self.assertEqual(len(list(root.glob('live-*'))), 1)
                self.assertEqual(module.STATE['status'], 'running')
                self.assertEqual(module.STATE['directory'], starts[0][0])
                self.assertEqual((starts[0][0] / 'input' / 'raw.txt').read_bytes(), b'raw')

    def test_stale_worker_does_not_overwrite_current_run(self):
        for index, source in enumerate(SOURCES):
            with self.subTest(source=source.name), tempfile.TemporaryDirectory(prefix='recording-stale-') as temporary:
                root = Path(temporary).resolve()
                module = load(source, index + 20)
                module.OPTIONS = SimpleNamespace(backend='codex')
                old = root / 'old'
                (old / 'run').mkdir(parents=True)
                (old / 'run' / 'report.html').write_text('old completed report')
                current = root / 'current'
                current.mkdir()
                module.STATE.clear()
                module.STATE.update(status='running', started=time.monotonic(), directory=current, merchant='new')
                before = dict(module.STATE)
                with patch.object(module, 'run_codex', return_value=SimpleNamespace(returncode=0)):
                    module.worker(old, [], 'old')
                self.assertEqual(module.STATE, before)


if __name__ == '__main__':
    if PARENT_VENV_TEST:
        sys.argv.remove('--parent-venv-test')
    unittest.main(verbosity=2)
