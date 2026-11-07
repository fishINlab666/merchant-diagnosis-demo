"""Offline recording-server regressions; no model calls, credentials or network.

Run from the release root:
    python3 -m unittest discover -s tools/tests -p 'test_recording_server.py' -v
"""
import base64
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


class RecordingRegression(unittest.TestCase):
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
    (p / 'run').mkdir()
    (p / 'run' / 'report.html').write_text('fresh fixture')
    (p / 'run' / 'report.json').write_text('{}')
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
                    with patch.dict(os.environ, {'FAKE_CODEX_MODE': mode}):
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
