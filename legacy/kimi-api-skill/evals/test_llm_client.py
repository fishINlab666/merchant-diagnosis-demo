import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from llm_client import LlmClient, LlmError


class LlmClientTest(unittest.TestCase):
    def test_sends_json_mode_and_returns_data_with_usage(self):
        captured = {}

        def transport(url, body, headers, timeout):
            captured.update(url=url, body=body, headers=headers, timeout=timeout)
            return {
                'model': 'kimi-k3.1-pro',
                'choices': [{'message': {'content': '{"ok": true}'}}],
                'usage': {'prompt_tokens': 20, 'completion_tokens': 22, 'total_tokens': 42},
            }

        client = LlmClient(api_key='secret', base_url='https://api.moonshot.cn/v1', model='kimi-k3.1-pro', transport=transport)
        result = client.complete_json('unit-test', {'question': '测试'})

        self.assertEqual(result.data, {'ok': True})
        self.assertEqual(result.usage['total_tokens'], 42)
        self.assertEqual(result.model, 'kimi-k3.1-pro')
        self.assertEqual(captured['url'], 'https://api.moonshot.cn/v1/chat/completions')
        self.assertEqual(captured['body']['response_format'], {'type': 'json_object'})
        self.assertEqual(captured['body']['model'], 'kimi-k3.1-pro')
        self.assertEqual(captured['headers']['Authorization'], 'Bearer secret')

    def test_rejects_non_json_content_without_a_fallback(self):
        client = LlmClient(api_key='secret', transport=lambda *_: {'choices': [{'message': {'content': 'not json'}}]})
        with self.assertRaises(LlmError):
            client.complete_json('bad-json', {})

    def test_http_error_is_explicit_and_never_becomes_a_preset_answer(self):
        def failing_transport(*_):
            raise RuntimeError('network unavailable')

        client = LlmClient(api_key='secret', transport=failing_transport)
        with self.assertRaisesRegex(LlmError, 'network unavailable'):
            client.complete_json('offline', {})

    def test_coding_base_url_normalizes_openai_path_and_model(self):
        captured = {}

        def transport(url, body, headers, timeout):
            captured['url'] = url
            captured['model'] = body['model']
            return {'choices': [{'message': {'content': '{}'}}], 'usage': {}}

        client = LlmClient(api_key='secret', base_url='https://agent-gw.kimi.com/coding/', transport=transport)
        client.complete_json('coding', {})
        self.assertEqual(captured['url'], 'https://agent-gw.kimi.com/coding/v1/chat/completions')
        self.assertEqual(captured['model'], 'k3.1-pro')

    def test_missing_credentials_fails_before_calling_transport(self):
        with patch.dict(os.environ, {}, clear=True):
            client = LlmClient(transport=lambda *_: self.fail('transport must not run'))
            with self.assertRaisesRegex(LlmError, 'KIMI_API_KEY'):
                client.complete_json('credentials', {})


if __name__ == '__main__':
    unittest.main()
