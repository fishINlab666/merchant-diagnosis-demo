import importlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


class ServiceCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def module(self):
        return importlib.import_module('service')

    def test_configure_hidden_no_echo_private_and_no_overwrite(self):
        m = self.module()
        path = self.base / 'private' / 'credentials.json'
        with patch('service.sys.stdin.isatty', return_value=True), patch('service.getpass.getpass', return_value='test-placeholder-only'), patch('sys.stdout', new_callable=io.StringIO) as out:
            m.configure(path, 'test-model')
        self.assertNotIn('test-placeholder-only', out.getvalue())
        self.assertEqual(0o600, path.stat().st_mode & 0o777)
        self.assertEqual(0o700, path.parent.stat().st_mode & 0o777)
        self.assertEqual('test-model', m.load_client(path).model)
        before = path.read_bytes()
        self.assertEqual('comparison-model', m.load_client(path, model='comparison-model').model)
        self.assertEqual(before, path.read_bytes())
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test-placeholder-only'}, clear=True):
            self.assertEqual('comparison-model', m.load_client(model='comparison-model').model)
        with self.assertRaises(ValueError):
            m.configure(path, 'test-model')

    def test_config_refuses_nonterminal_bad_permissions_and_symlink(self):
        m = self.module()
        path = self.base / 'credentials.json'
        with patch('service.sys.stdin.isatty', return_value=False), self.assertRaises(ValueError):
            m.configure(path, 'test-model')
        path.write_text(json.dumps({'provider': 'deepseek', 'api_key': 'test-placeholder-only', 'model': 'test-model'}))
        path.chmod(0o644)
        with self.assertRaises(ValueError):
            m.load_client(path)
        path.chmod(0o600)
        link = self.base / 'link'
        link.symlink_to(path)
        with self.assertRaises(ValueError):
            m.load_client(link)

    def test_cli_init_add_status_missing_key_fails_before_run(self):
        m = self.module()
        project = self.base / 'shop'
        raw = self.base / 'public.md'
        raw.write_text('门店公开信息')
        with patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(0, m.main(['init', '--project', str(project), '--name', '测试店', '--goal', '核对公开信息', '--synthetic']))
            self.assertEqual(0, m.main(['add', '--project', str(project), '--file', str(raw), '--slot', 'public', '--kind', 'public', '--period', 'W1']))
            self.assertEqual(0, m.main(['status', '--project', str(project)]))
        with patch.dict('os.environ', {}, clear=True), patch('sys.stderr', new_callable=io.StringIO):
            self.assertEqual(1, m.main(['run', '--project', str(project), '--phase', 'public']))
        self.assertFalse((project / 'runs').exists())

    def test_invalid_config_never_echoes_contents(self):
        m = self.module()
        path = self.base / 'bad.json'
        path.write_text('test-placeholder-only')
        path.chmod(0o600)
        with self.assertRaises(ValueError) as error:
            m.load_client(path)
        self.assertNotIn('test-placeholder-only', str(error.exception))

    def test_load_client_keeps_default_output_limits(self):
        m = self.module()
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test-placeholder-only',
                                     'DEEPSEEK_MODEL': 'test-model'}, clear=True):
            self.assertEqual(8192, m.load_client().max_tokens)
            self.assertEqual(8192, m.load_client(thinking='disabled').max_tokens)
            self.assertEqual(16384, m.load_client(thinking='enabled').max_tokens)

    def test_load_client_accepts_explicit_output_limit_without_changing_config(self):
        m = self.module()
        path = self.base / 'config.json'
        path.write_text(json.dumps({'provider': 'deepseek', 'api_key': 'test-placeholder-only',
                                    'model': 'test-model'}))
        path.chmod(0o600)
        before = path.read_bytes()
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test-placeholder-only',
                                     'DEEPSEEK_MODEL': 'test-model'}, clear=True):
            for config in (None, path):
                for thinking in ('enabled', 'disabled'):
                    with self.subTest(config=config is not None, thinking=thinking):
                        try:
                            client = m.load_client(config, thinking=thinking, max_tokens=32768)
                        except TypeError as error:
                            self.fail(f'load_client 必须接受 max_tokens：{error}')
                        self.assertEqual(32768, client.max_tokens)
                        self.assertEqual(thinking, client.thinking)
        self.assertEqual(before, path.read_bytes())

    def test_cli_run_forwards_explicit_output_limit(self):
        m = self.module()
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test-placeholder-only',
                                     'DEEPSEEK_MODEL': 'test-model'}, clear=True), \
                patch('service.run_project', return_value={}) as run, \
                patch('model_api._http_transport') as transport, \
                patch('sys.stdout', new_callable=io.StringIO), \
                patch('sys.stderr', new_callable=io.StringIO):
            try:
                result = m.main(['run', '--project', str(self.base / 'shop'), '--phase', 'diagnosis',
                                 '--thinking', 'enabled', '--max-tokens', '32768'])
            except SystemExit as error:
                result = error.code
            self.assertEqual(0, result)
            client = run.call_args.args[2]
            self.assertEqual(32768, client.max_tokens)
            self.assertEqual('enabled', client.thinking)
            transport.assert_not_called()

    def test_cli_invalid_output_limits_fail_before_run_or_network(self):
        m = self.module()
        for limit in (0, 32769):
            with self.subTest(limit=limit), \
                    patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test-placeholder-only',
                                             'DEEPSEEK_MODEL': 'test-model'}, clear=True), \
                    patch('service.run_project') as run, \
                    patch('model_api._http_transport') as transport, \
                    patch('sys.stderr', new_callable=io.StringIO):
                try:
                    result = m.main(['run', '--project', str(self.base / 'shop'), '--phase', 'diagnosis',
                                     '--max-tokens', str(limit)])
                except SystemExit as error:
                    result = error.code
                self.assertEqual(1, result)
                run.assert_not_called()
                transport.assert_not_called()

    def test_cli_forwards_optional_final_revision_without_changing_default_call(self):
        m = self.module()
        for source in (None, 'run-rejected'):
            with self.subTest(source=source), patch('service.load_client') as load, \
                    patch('service.run_project', return_value={}) as run, \
                    patch('sys.stdout', new_callable=io.StringIO), \
                    patch('sys.stderr', new_callable=io.StringIO):
                args = ['run', '--project', str(self.base / 'shop'), '--phase', 'diagnosis']
                if source:
                    args.extend(['--revise-final', source])
                try:
                    code = m.main(args)
                except SystemExit as error:
                    code = error.code
                self.assertEqual(0, code)
                expected = {'revise_final_id': source} if source else {}
                run.assert_called_once_with(self.base / 'shop', 'diagnosis', load.return_value,
                                            None, 8, **expected)


if __name__ == '__main__':
    unittest.main()
