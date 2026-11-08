import importlib
import json
import os
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


def response(content='{"answer": 1}', finish='stop'):
    return json.dumps({'id': 'resp-1', 'model': 'actual-model',
        'usage': {'prompt_tokens': 12, 'completion_tokens': 4, 'total_tokens': 16},
        'choices': [{'finish_reason': finish, 'message': {'content': content}}]}).encode()


def calculation_arguments():
    return {'requests': [{'id': 'c1', 'expression': 'income-cost', 'variables': {
        'income': {'value': 100, 'evidence': [{'material': 'raw.csv', 'locator': 'row:2'}]},
        'cost': {'value': None, 'assumption': '成本尚缺'}}, 'unit': '元', 'purpose': '核对贡献'}]}


def native_response(arguments=None, **changes):
    call = {'id': 'call_1', 'type': 'function', 'function': {'name': 'calculate',
        'arguments': json.dumps(calculation_arguments() if arguments is None else arguments)}}
    message = {'role': 'assistant', 'content': None, 'tool_calls': [call],
               'reasoning_content': 'offline reasoning placeholder'}
    message.update(changes)
    envelope = json.loads(response(finish='tool_calls'))
    envelope['choices'][0]['message'] = message
    return json.dumps(envelope).encode()


class ModelAPITests(unittest.TestCase):
    def test_calculator_description_explains_binding_and_new_ids_for_recalculation(self):
        description = self.api().CALCULATE_TOOL['function']['description']
        self.assertIn('expression', description)
        self.assertIn('variables', description)
        self.assertIn('实际引用', description)
        self.assertIn('新calc_id', description)

    def test_review_profile_preserves_mode_and_writer_settings(self):
        for use_transport in (False, True):
            options = {'transport': lambda *args: response()} if use_transport else {}
            writer = self.api().ModelClient('deepseek', 'unit-test-secret', 'configured-model',
                thinking='enabled', max_tokens=24576, timeout=90, **options)
            reviewer = writer.for_review()
            self.assertIsNot(writer, reviewer)
            self.assertEqual(writer.mode, reviewer.mode)
            self.assertEqual(('enabled', 24576), (writer.thinking, writer.max_tokens))
            self.assertEqual(('disabled', 8192), (reviewer.thinking, reviewer.max_tokens))
            self.assertIs(writer._transport, reviewer._transport)
            self.assertEqual(writer.timeout, reviewer.timeout)
            self.assertEqual(writer.max_response_bytes, reviewer.max_response_bytes)

    def test_native_calculation_evidence_capacity_matches_schema_only(self):
        args = calculation_arguments()
        citations = [{'material': 'raw.csv', 'locator': f'row:{row}'} for row in range(2, 1003)]
        args['requests'][0]['variables']['income']['evidence'] = citations[:1000]
        result = self.client(lambda *unused: native_response(args)).complete([{'role': 'user', 'content': 'x'}])
        self.assertEqual(citations[:1000], result['data']['requests'][0]['variables']['income']['evidence'])
        schema = self.api().CALCULATE_TOOL['function']['parameters']['properties']['requests']
        self.assertEqual(100, schema['maxItems'])
        self.assertEqual(100, schema['items']['properties']['variables']['maxProperties'])
        self.assertEqual(1000, schema['items']['properties']['variables']['additionalProperties']['properties']['evidence']['maxItems'])
        args['requests'][0]['variables']['income']['evidence'] = citations
        with self.assertRaises(ValueError):
            self.client(lambda *unused: native_response(args)).complete([{'role': 'user', 'content': 'x'}])

    def test_tool_choice_none_and_default_auto_are_explicit_and_validated(self):
        payloads = []
        def transport(url, payload, *args):
            payloads.append(json.loads(payload))
            return response()
        client = self.client(transport)
        client.complete([{'role': 'user', 'content': 'x'}])
        client.complete([{'role': 'user', 'content': 'x'}], tool_choice='none')
        self.assertEqual(['auto', 'none'], [p['tool_choice'] for p in payloads])
        with self.assertRaises(ValueError):
            client.complete([{'role': 'user', 'content': 'x'}], tool_choice='required')
        self.assertEqual(2, len(payloads))

    def test_redundant_empty_sources_normalize_without_changing_raw_tool_message(self):
        for empty in (None, '', '  '):
            args = calculation_arguments()
            args['requests'][0]['variables']['income']['assumption'] = empty
            args['requests'][0]['variables']['cost']['evidence'] = None
            result = self.client(lambda *unused: native_response(args)).complete([{'role': 'user', 'content': 'x'}])
            normalized = result['data']['requests'][0]['variables']
            self.assertNotIn('assumption', normalized['income'])
            self.assertEqual([], normalized['cost']['evidence'])
            raw = json.loads(result['assistant_message']['tool_calls'][0]['function']['arguments'])
            self.assertEqual(args, raw)
        args = calculation_arguments()
        args['requests'][0]['variables']['income'].update(evidence=None, assumption=None)
        with self.assertRaises(ValueError):
            self.client(lambda *unused: native_response(args)).complete([{'role': 'user', 'content': 'x'}])

    def api(self):
        self.assertTrue((Path(__file__).resolve().parents[1] / 'scripts/model_api.py').exists(), 'model adapter missing')
        return importlib.import_module('model_api')

    def client(self, transport):
        return self.api().ModelClient('deepseek', 'unit-test-secret', 'configured-model', transport=transport)

    def test_missing_credentials_and_model_fail_before_transport(self):
        api = self.api()
        for env in ({}, {'DEEPSEEK_API_KEY': 'unit-test-secret'}, {'DEEPSEEK_MODEL': 'configured-model'}):
            with self.subTest(env=list(env)), patch.dict(os.environ, env, clear=True):
                with self.assertRaises(ValueError) as error:
                    api.ModelClient.from_env()
                self.assertNotIn('unit-test-secret', str(error.exception))

    def test_from_env_api_mode_and_no_default_model(self):
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'unit-test-secret', 'DEEPSEEK_MODEL': 'chosen-model'}, clear=True):
            client = self.api().ModelClient.from_env()
        self.assertEqual('api', client.mode)
        self.assertEqual('chosen-model', client.model)
        self.assertNotIn('unit-test-secret', repr(client))

    def test_transport_payload_and_safe_metadata(self):
        calls = []
        def transport(url, payload, headers, timeout, max_response_bytes):
            calls.append((url, json.loads(payload), headers, timeout, max_response_bytes))
            return response()
        client = self.client(transport)
        result = client.complete([{'role': 'user', 'content': 'analyse'}])
        self.assertEqual('test_double', client.mode)
        self.assertEqual({'answer': 1}, result['data'])
        self.assertEqual('actual-model', result['metadata']['model'])
        self.assertEqual('resp-1', result['metadata']['response_id'])
        self.assertFalse(result['metadata']['inference_executed'])
        self.assertEqual(16, result['metadata']['usage']['total_tokens'])
        self.assertGreaterEqual(result['metadata']['elapsed_seconds'], 0)
        self.assertNotIn('unit-test-secret', json.dumps(result))
        url, payload, headers, timeout, bound = calls[0]
        self.assertEqual('https://api.deepseek.com/chat/completions', url)
        self.assertEqual('configured-model', payload['model'])
        self.assertEqual({'type': 'json_object'}, payload['response_format'])
        self.assertIn('json', payload['messages'][0]['content'].lower())
        self.assertEqual({'type': 'disabled'}, payload['thinking'])
        self.assertLessEqual(timeout, 120)
        self.assertLessEqual(bound, 4000000)

    def test_reject_invalid_or_truncated_json_without_echo(self):
        invalid = ['', '[]', '{}', '{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{"a":1e999}', 'private malformed body']
        for content in invalid:
            with self.subTest(content=content):
                with self.assertRaises(ValueError) as error:
                    self.client(lambda *args: response(content)).complete([{'role':'user','content':'x'}])
                if content:
                    self.assertNotIn(content, str(error.exception))
        with self.assertRaises(ValueError):
            self.client(lambda *args: response(finish='length')).complete([{'role':'user','content':'x'}])

    def test_explicit_thinking_mode_keeps_json_and_records_mode(self):
        captured = []
        def transport(url, payload, *args):
            captured.append(json.loads(payload))
            return response()
        client = self.api().ModelClient('deepseek', 'unit-test-secret', 'model',
                                        transport=transport, thinking='enabled')
        result = client.complete([{'role': 'user', 'content': 'Return JSON'}])
        self.assertEqual({'type': 'enabled'}, captured[0]['thinking'])
        self.assertEqual('low', captured[0]['reasoning_effort'])
        self.assertEqual('enabled', result['metadata']['thinking'])
        with self.assertRaises(ValueError):
            self.api().ModelClient('deepseek', 'unit-test-secret', 'model', thinking='invalid')

    def test_native_calculate_schema_and_round_trip_preserve_reasoning(self):
        captured = []
        replies = [native_response(), response('{"kind":"final","report_markdown":"report"}')]
        def transport(url, payload, *args):
            captured.append(json.loads(payload))
            return replies.pop(0)
        client = self.client(transport)
        first = client.complete([{'role': 'user', 'content': '核对金额'}])
        self.assertEqual({'kind': 'calculate', **calculation_arguments()}, first['data'])
        self.assertEqual('call_1', first['tool_call_id'])
        expected = json.loads(native_response())['choices'][0]['message']
        self.assertEqual(expected, first['assistant_message'])
        tool = {'role': 'tool', 'tool_call_id': first['tool_call_id'],
                'content': '{"tool_results":[{"id":"c1","status":"unknown","value":null}]}'}
        client.complete([{'role': 'user', 'content': '核对金额'}, first['assistant_message'], tool])
        self.assertEqual(expected, captured[1]['messages'][-2])
        self.assertEqual(tool, captured[1]['messages'][-1])
        tools = captured[0]['tools']
        self.assertEqual(1, len(tools))
        self.assertEqual('calculate', tools[0]['function']['name'])
        params = tools[0]['function']['parameters']
        self.assertEqual(['requests'], params['required'])
        item = params['properties']['requests']['items']
        self.assertEqual({'id', 'expression', 'variables', 'unit', 'purpose'}, set(item['required']))
        variable = item['properties']['variables']['additionalProperties']
        self.assertEqual(['number', 'null'], variable['properties']['value']['type'])
        self.assertFalse(first['metadata']['inference_executed'])

    def test_variable_name_schema_matches_adapter_and_calculator(self):
        captured = []
        def transport(url, payload, *args):
            captured.append(json.loads(payload))
            return response()
        self.client(transport).complete([{'role': 'user', 'content': 'analyse'}])
        schema = captured[0]['tools'][0]['function']['parameters']['properties']['requests']['items']['properties']['variables']
        pattern = schema['propertyNames']['pattern']
        self.assertEqual('^[A-Za-z][A-Za-z0-9_]{0,63}$', pattern)
        self.assertIn('ASCII', schema['description'])
        calculator = importlib.import_module('service_calculator')
        for name in calculator.FUNCTIONS:
            self.assertIn(name, schema['description'])
        for name, valid in [('a', True), ('Sales_2026', True), ('a' * 64, True),
                            ('营收', False), ('1income', False), ('_income', False),
                            ('income-cost', False), ('a' * 65, False), ('a b', False)]:
            arguments = calculation_arguments()
            arguments['requests'][0].update(expression=name,
                variables={name: {'value': 2, 'assumption': 'offline fixture'}})
            with self.subTest(name=name):
                self.assertEqual(valid, re.search(pattern, name) is not None)
                if valid:
                    self.api()._calculation_arguments(json.dumps(arguments))
                    self.assertEqual(2, calculator.calculate_requests(arguments['requests'], [])[0]['value'])
                else:
                    with self.assertRaises(ValueError):
                        self.api()._calculation_arguments(json.dumps(arguments))
                    with self.assertRaises(ValueError):
                        calculator.calculate_requests(arguments['requests'], [])

    def test_provider_index_zero_is_removed_from_native_history(self):
        envelope = json.loads(native_response())
        envelope['choices'][0]['message']['tool_calls'][0]['index'] = 0
        envelope['choices'][0]['message']['tool_calls'][0]['id'] = '0123456789abcdef0123456789abcdef'
        captured = []
        replies = [json.dumps(envelope).encode(), response()]
        def transport(url, payload, *args):
            captured.append(json.loads(payload))
            return replies.pop(0)
        client = self.client(transport)
        first = client.complete([{'role': 'user', 'content': 'analyse'}])
        self.assertEqual('calculate', first['data']['kind'])
        self.assertEqual({'id', 'type', 'function'}, set(first['assistant_message']['tool_calls'][0]))
        client.complete([{'role': 'user', 'content': 'analyse'}, first['assistant_message'],
                         {'role': 'tool', 'tool_call_id': first['tool_call_id'], 'content': '{}'}])
        self.assertNotIn('index', captured[1]['messages'][-2]['tool_calls'][0])
        for field, value in [('index', True), ('index', -1), ('index', 1), ('index', 1000000),
                             ('index', 0.0), ('index', None), ('index', '0'), ('unknown', 'PRIVATE_FIELD')]:
            invalid = json.loads(native_response())
            invalid['choices'][0]['message']['tool_calls'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError) as error:
                self.client(lambda *args: json.dumps(invalid).encode()).complete([{'role': 'user', 'content': 'analyse'}])
            self.assertEqual('call_identifier', error.exception.diagnostics['tool_error'])

    def test_final_and_legacy_calculate_preserve_reasoning_without_extra_fields(self):
        for content in ('{"kind":"final","report_markdown":"report"}',
                        json.dumps({'kind': 'calculate', **calculation_arguments()})):
            envelope = json.loads(response(content))
            envelope['choices'][0]['message'].update(reasoning_content='offline final reasoning',
                                                     provider_private='discard this field')
            captured = []
            def transport(url, payload, *args):
                captured.append(json.loads(payload))
                return json.dumps(envelope).encode()
            client = self.client(transport)
            first = client.complete([{'role': 'user', 'content': 'analyse'}])
            self.assertIsNone(first['tool_call_id'])
            self.assertEqual({'role', 'content', 'reasoning_content'}, set(first['assistant_message']))
            client.complete([{'role': 'user', 'content': 'analyse'}, first['assistant_message'],
                             {'role': 'user', 'content': 'correct the report'}])
            self.assertEqual('offline final reasoning', captured[1]['messages'][-2]['reasoning_content'])

    def test_reject_unsafe_native_calls_and_arguments(self):
        base = json.loads(native_response())
        variants = []
        for name, value in (('name', 'shell'), ('arguments', '{"requests":[],"requests":[]}'),
                            ('arguments', '{"requests":[NaN]}'), ('arguments', '[]'),
                            ('arguments', '{"requests":[]}')):
            item = json.loads(json.dumps(base))
            item['choices'][0]['message']['tool_calls'][0]['function'][name] = value
            variants.append(item)
        for value in ('bad id', '../outside', '', None):
            item = json.loads(json.dumps(base))
            item['choices'][0]['message']['tool_calls'][0]['id'] = value
            variants.append(item)
        item = json.loads(json.dumps(base))
        item['choices'][0]['message']['tool_calls'] *= 2
        variants.append(item)
        for arguments in ({'requests': [{}]}, {'requests': [dict(calculation_arguments()['requests'][0],
                variables={'a': {'value': True, 'assumption': 'bad'}})]}):
            variants.append(json.loads(native_response(arguments)))
        for envelope in variants:
            with self.subTest(case=len(json.dumps(envelope))), self.assertRaises(ValueError) as error:
                self.client(lambda *args: json.dumps(envelope).encode()).complete([{'role': 'user', 'content': 'analyse'}])
            self.assertEqual('invalid_response', error.exception.code)
            self.assertNotIn('offline reasoning placeholder', str(error.exception))

    def test_message_whitelist_and_tool_links_reject_before_transport(self):
        assistant = json.loads(native_response())['choices'][0]['message']
        tool = {'role': 'tool', 'tool_call_id': 'call_1', 'content': '{}'}
        invalid = [[{'role': 'user', 'content': 'x', 'tool_calls': []}],
                   [{'role': 'assistant', 'content': 'x', 'reasoning_content': 5}],
                   [tool], [assistant], [assistant, dict(tool, tool_call_id='unknown')],
                   [assistant, dict(tool, arbitrary='unsafe')],
                   [{'role': 'developer', 'content': 'x'}]]
        calls = []
        def transport(*args):
            calls.append(1)
            return response()
        for messages in invalid:
            with self.subTest(messages=len(messages)), self.assertRaises(ValueError):
                self.client(transport).complete(messages)
        self.assertEqual([], calls)

    def test_native_call_id_cannot_echo_the_client_secret(self):
        envelope = json.loads(native_response())
        envelope['choices'][0]['message']['tool_calls'][0]['id'] = 'unit-test-secret'
        with self.assertRaises(ValueError) as error:
            self.client(lambda *args: json.dumps(envelope).encode()).complete([{'role': 'user', 'content': 'analyse'}])
        self.assertEqual('invalid_response', error.exception.code)
        self.assertNotIn('unit-test-secret', str(error.exception))

    def test_native_validation_diagnostics_are_fixed_codes_and_bounded_counts(self):
        cases = []
        for field, value, code in (('name', 'PRIVATE_FUNCTION', 'function_definition'),
                ('arguments', 'PRIVATE_ARGUMENTS', 'arguments_json'),
                ('arguments', '{"requests":[],"requests":[]}', 'duplicate_key'),
                ('arguments', '{"requests":[NaN]}', 'non_finite'),
                ('arguments', '{"requests":[{}]}', 'request_fields')):
            envelope = json.loads(native_response())
            envelope['choices'][0]['message']['tool_calls'][0]['function'][field] = value
            cases.append((envelope, code, 1))
        envelope = json.loads(native_response())
        envelope['choices'][0]['message']['tool_calls'] *= 2
        cases.append((envelope, 'call_count', 2))
        arguments = calculation_arguments()
        arguments['requests'][0]['variables']['income']['value'] = 'PRIVATE_VALUE'
        cases.append((json.loads(native_response(arguments)), 'variable_value', 1))
        for envelope, code, count in cases:
            with self.subTest(code=code), self.assertRaises(ValueError) as error:
                self.client(lambda *args: json.dumps(envelope).encode()).complete([{'role': 'user', 'content': 'analyse'}])
            diagnostics = error.exception.diagnostics
            self.assertEqual('tool_arguments', diagnostics['phase'])
            self.assertEqual(code, diagnostics.get('tool_error'))
            self.assertEqual(count, diagnostics.get('tool_call_count'))
            self.assertNotIn('PRIVATE_', json.dumps(diagnostics))
            self.assertNotIn('reasoning placeholder', json.dumps(diagnostics))
        for count in (-1, True, 1001, 'PRIVATE_COUNT'):
            self.assertEqual({}, self.api().ModelAPIError('invalid_response',
                {'tool_error': 'PRIVATE_ERROR', 'tool_call_count': count}).diagnostics)

    def test_response_diagnostics_distinguish_truncation_from_bad_json(self):
        for body, code, phase in ((response(finish='length'), 'output_truncated', 'completion'),
                                  (response('PRIVATE_BODY not json'), 'invalid_response', 'content_json'),
                                  (b'PRIVATE_BODY', 'invalid_response', 'envelope_json')):
            with self.assertRaises(ValueError) as error:
                self.client(lambda *args: body).complete([{'role':'user','content':'x'}])
            self.assertEqual(code, error.exception.code)
            self.assertEqual(phase, error.exception.diagnostics['phase'])
            self.assertNotIn('PRIVATE_BODY', json.dumps(error.exception.diagnostics))
        self.assertEqual({}, self.api().ModelAPIError('timeout', {'headers':'unit-test-secret','phase':'unit-test-secret'}).diagnostics)

    def test_malformed_envelope_and_response_size(self):
        for value in (b'bad private envelope', b'[]', b'{}', b'{"id":1,"id":2}', b'x' * 2000001):
            with self.subTest(size=len(value)), self.assertRaises(ValueError):
                self.client(lambda *args: value).complete([{'role':'user','content':'x'}])

    def test_transport_failure_is_sanitized_and_not_retried(self):
        calls = []
        def broken(*args):
            calls.append(1)
            raise OSError('unit-test-secret PRIVATE_BODY')
        with self.assertRaises(ValueError) as error:
            self.client(broken).complete([{'role':'user','content':'x'}])
        self.assertEqual(1, len(calls))
        self.assertNotIn('unit-test-secret', str(error.exception))
        self.assertNotIn('PRIVATE_BODY', str(error.exception))
        self.assertTrue(error.exception.__suppress_context__)

    def test_http_and_timeout_have_safe_diagnostic_codes(self):
        from urllib.error import HTTPError, URLError
        for exception, code in ((HTTPError('https://example.invalid', 429, 'unit-test-secret', {}, None), 'rate_limited'),
                                (HTTPError('https://example.invalid', 400, 'unit-test-secret', {}, None), 'bad_request'),
                                (HTTPError('https://example.invalid', 503, 'unit-test-secret', {}, None), 'provider_error'),
                                (TimeoutError('unit-test-secret'), 'timeout'),
                                (URLError(TimeoutError('unit-test-secret')), 'timeout')):
            def fail(*args):
                raise exception
            with self.assertRaises(ValueError) as error:
                self.client(fail).complete([{'role':'user','content':'Return JSON'}])
            self.assertEqual(code, error.exception.code)
            self.assertNotIn('unit-test-secret', str(error.exception))

    def test_invalid_config_and_messages_do_not_call_transport(self):
        api = self.api()
        for kwargs in ({'timeout': 0}, {'timeout': 121}, {'max_response_bytes': 0}, {'max_tokens': True}):
            with self.assertRaises(ValueError):
                api.ModelClient('deepseek', 'secret', 'model', **kwargs)
        with self.assertRaises(ValueError):
            api.ModelClient('other', 'secret', 'model')
        def forbidden(*args):
            self.fail('transport must not be called')
        for messages in ([], [{'role':'user','content': None}], [{'role':'tool','content':'x'}]):
            with self.assertRaises(ValueError):
                self.client(forbidden).complete(messages)

    def test_default_http_transport_bounds_read_and_disables_redirects(self):
        api = self.api()
        from unittest.mock import MagicMock
        opener = MagicMock()
        reply = opener.open.return_value.__enter__.return_value
        reply.status = 200
        reply.read.return_value = b'bounded'
        with patch.object(api.urllib.request, 'build_opener', return_value=opener) as build:
            self.assertEqual(b'bounded', api._http_transport(api.ENDPOINT, b'{}', {'Authorization':'Bearer fake'}, 5, 123))
        self.assertIsInstance(build.call_args.args[0], api.NoRedirect)
        reply.read.assert_called_once_with(124)
        self.assertEqual(5, opener.open.call_args.kwargs['timeout'])

    def test_metadata_rejects_invalid_types_and_never_copies_extra_fields(self):
        base = json.loads(response())
        for field, value in (('model', None), ('id', 'unit-test-secret'), ('usage', {'total_tokens': True})):
            invalid = dict(base, **{field:value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.client(lambda *args: json.dumps(invalid).encode()).complete([{'role':'user','content':'x'}])
        base['usage']['headers'] = 'PRIVATE_BODY'
        result = self.client(lambda *args: json.dumps(base).encode()).complete([{'role':'user','content':'x'}])
        self.assertNotIn('PRIVATE_BODY', json.dumps(result))

    def test_redirects_rejected_without_forwarding_credentials(self):
        api = self.api()
        handler = api.NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, 'redirect', {}, 'https://evil.example'))


if __name__ == '__main__':
    unittest.main()
