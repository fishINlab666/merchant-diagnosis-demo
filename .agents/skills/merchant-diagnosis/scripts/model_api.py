"""Bounded DeepSeek JSON calls. No model defaults, retries or persisted secrets."""
import copy
import json
import math
import os
import re
import time
import urllib.request
import urllib.error

ENDPOINT = 'https://api.deepseek.com/chat/completions'

TOOL_ERROR_CODES = {
    '计算工具参数无效': 'arguments_shape',
    '计算请求字段无效': 'request_fields',
    '计算请求文字字段无效': 'request_text',
    '计算变量无效': 'variables_shape',
    '计算变量字段无效': 'variable_fields',
    '计算变量数值无效': 'variable_value',
    '计算变量来源无效': 'variable_source',
    '计算变量引用无效': 'variable_citation',
    '每次仅允许一个计算工具调用': 'call_count',
    '计算工具标识无效': 'call_identifier',
    '只允许calculate函数': 'function_definition',
    '模型消息角色无效': 'message_role',
    '工具调用正文无效': 'message_content',
    '响应正文必须为非空字符串': 'message_content',
    '工具调用字段无效': 'tool_calls_shape',
    '思考字段无效': 'reasoning_field',
    'JSON 含重复字段': 'duplicate_key',
    'JSON 含非有限数': 'non_finite',
    '需要非空 JSON 对象': 'not_object',
}

CALCULATE_TOOL = {'type': 'function', 'function': {
    'name': 'calculate',
    'description': '用受控算术核对金额、比例和单位。只能计算表达式，不能运行代码或读取文件。'
                   'expression 须实际引用有来源或明确假设的variables，不能只声明变量却写裸常数。'
                   '重算使用新calc_id（请求的id），不复用本轮已执行编号。',
    'parameters': {'type': 'object', 'additionalProperties': False, 'required': ['requests'],
        'properties': {'requests': {'type': 'array', 'minItems': 1, 'maxItems': 100,
            'items': {'type': 'object', 'additionalProperties': False,
                'required': ['id', 'expression', 'variables', 'unit', 'purpose'],
                'properties': {
                    **{key: {'type': 'string', 'minLength': 1, 'maxLength': 2000}
                       for key in ('id', 'expression', 'unit', 'purpose')},
                    'variables': {'type': 'object', 'maxProperties': 100,
                        'description': '变量名只允许 ASCII 字母开头，后接字母、数字或下划线，总长 1–64；不得使用中文、空格或连字符。sum、mean、min、max、abs、round 是保留函数名，不能作为变量名。',
                        'propertyNames': {'pattern': '^[A-Za-z][A-Za-z0-9_]{0,63}$'},
                        'additionalProperties': {'type': 'object', 'additionalProperties': False,
                            'required': ['value'], 'properties': {
                                'value': {'type': ['number', 'null']},
                                'assumption': {'type': 'string', 'minLength': 1, 'maxLength': 2000},
                                'evidence': {'type': 'array', 'maxItems': 1000, 'items': {
                                    'type': 'object', 'additionalProperties': False,
                                    'required': ['material', 'locator'], 'properties': {
                                        'material': {'type': 'string', 'minLength': 1},
                                        'locator': {'type': 'string', 'minLength': 1}}}}},
                            'anyOf': [{'required': ['assumption']}, {'required': ['evidence'],
                                'properties': {'evidence': {'minItems': 1}}}]}}}}}}}}}


class ModelAPIError(ValueError):
    MESSAGES = {'authentication': '模型认证失败', 'permission': '模型访问权限不足',
                'balance': '模型账户余额不足', 'rate_limited': '模型接口限流',
                'bad_request': '模型接口拒绝请求参数', 'model_unavailable': '模型接口或型号不可用',
                'provider_error': '模型服务端错误',
                'output_truncated': '模型输出达到长度上限，未生成完整报告',
                'timeout': '模型请求超时', 'network': '模型网络连接失败',
                'request_failed': '模型请求失败', 'invalid_response': '模型响应无效、超限或未完整结束'}

    def __init__(self, code, diagnostics=None):
        self.code = code if code in self.MESSAGES else 'request_failed'
        self.diagnostics = {}
        for key, value in (diagnostics or {}).items():
            if ((key == 'phase' and value in ('response_size', 'envelope_json', 'completion', 'content_json', 'tool_arguments', 'metadata'))
                    or (key == 'finish_reason' and value in ('stop', 'length', 'content_filter', 'tool_calls', 'other'))
                    or (key == 'json_error' and value in ('syntax', 'duplicate_key', 'non_finite', 'not_object', 'other'))
                    or (key == 'tool_error' and value in (*TOOL_ERROR_CODES.values(), 'arguments_json', 'other'))
                    or (key == 'tool_call_count' and type(value) is int and 0 <= value <= 1000)
                    or (key in ('response_bytes', 'content_characters', 'prompt_tokens', 'completion_tokens', 'total_tokens', 'json_error_line', 'json_error_column')
                        and type(value) is int and 0 <= value <= 10**12)
                    or (key == 'elapsed_seconds' and type(value) in (int, float) and math.isfinite(value) and 0 <= value < 10**6)):
                self.diagnostics[key] = value
        super().__init__(self.MESSAGES[self.code] + '；未自动重试，未记录接口错误原文')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never forward the Authorization header to a redirect target."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _http_transport(url, payload, headers, timeout, max_response_bytes):
    request = urllib.request.Request(url, data=payload, headers=headers, method='POST')
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError('模型接口未返回成功状态')
        return response.read(max_response_bytes + 1)


def _strict_object(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('JSON 含重复字段')
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError('JSON 含非有限数')

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)
    if not isinstance(value, dict) or not value:
        raise ValueError('需要非空 JSON 对象')
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, float) and not math.isfinite(item):
            raise ValueError('JSON 含非有限数')
    return value


def _calculation_arguments(raw):
    data = _strict_object(raw)
    requests = data.get('requests')
    if set(data) != {'requests'} or not isinstance(requests, list) or not 1 <= len(requests) <= 100:
        raise ValueError('计算工具参数无效')
    for request in requests:
        if not isinstance(request, dict) or set(request) != {'id', 'expression', 'variables', 'unit', 'purpose'}:
            raise ValueError('计算请求字段无效')
        for key in ('id', 'expression', 'unit', 'purpose'):
            if not isinstance(request[key], str) or not request[key].strip() or len(request[key]) > 2000:
                raise ValueError('计算请求文字字段无效')
        variables = request['variables']
        if not isinstance(variables, dict) or len(variables) > 100:
            raise ValueError('计算变量无效')
        for name, variable in variables.items():
            if (not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', name)
                    or not isinstance(variable, dict) or 'value' not in variable
                    or set(variable) - {'value', 'evidence', 'assumption'}):
                raise ValueError('计算变量字段无效')
            value = variable['value']
            if value is not None and (type(value) not in (int, float)
                                       or (type(value) is float and not math.isfinite(value))):
                raise ValueError('计算变量数值无效')
            evidence, assumption = variable.get('evidence', []), variable.get('assumption')
            if isinstance(evidence, list) and evidence and (
                    assumption is None or isinstance(assumption, str) and not assumption.strip()):
                variable.pop('assumption', None)
                assumption = None
            if evidence is None and isinstance(assumption, str) and assumption.strip():
                variable['evidence'] = evidence = []
            if (not isinstance(evidence, list) or len(evidence) > 1000
                    or ('assumption' in variable and (not isinstance(assumption, str)
                        or not assumption.strip() or len(assumption) > 2000))
                    or (not evidence and not assumption)):
                raise ValueError('计算变量来源无效')
            for citation in evidence:
                if (not isinstance(citation, dict) or set(citation) != {'material', 'locator'}
                        or any(not isinstance(citation[key], str) or not citation[key].strip()
                               for key in ('material', 'locator'))):
                    raise ValueError('计算变量引用无效')
    return data


def _native_call(calls):
    if not isinstance(calls, list) or len(calls) != 1:
        raise ValueError('每次仅允许一个计算工具调用')
    call = calls[0]
    if (not isinstance(call, dict) or not {'id', 'type', 'function'} <= set(call)
            or set(call) - {'id', 'type', 'function', 'index'}
            or ('index' in call and (type(call['index']) is not int or call['index'] != 0))
            or call['type'] != 'function' or not isinstance(call['id'], str)
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', call['id'])):
        raise ValueError('计算工具标识无效')
    function = call['function']
    if (not isinstance(function, dict) or set(function) != {'name', 'arguments'}
            or function['name'] != 'calculate' or not isinstance(function['arguments'], str)):
        raise ValueError('只允许calculate函数')
    return {key: call[key] for key in ('id', 'type', 'function')}, _calculation_arguments(function['arguments'])


def _assistant_message(message):
    if not isinstance(message, dict) or message.get('role', 'assistant') != 'assistant':
        raise ValueError('模型消息角色无效')
    content, calls = message.get('content'), message.get('tool_calls')
    if calls:
        call, _ = _native_call(calls)
        if content is not None and not isinstance(content, str):
            raise ValueError('工具调用正文无效')
    elif not isinstance(content, str) or not content.strip():
        raise ValueError('响应正文必须为非空字符串')
    elif calls not in (None, []):
        raise ValueError('工具调用字段无效')
    result = {'role': 'assistant', 'content': content}
    if calls:
        result['tool_calls'] = [call]
    if 'reasoning_content' in message:
        reasoning = message['reasoning_content']
        if reasoning is not None and not isinstance(reasoning, str):
            raise ValueError('思考字段无效')
        # This provider field is retained only for API history, not report content.
        result['reasoning_content'] = reasoning
    return result


def _clean_messages(messages):
    if not isinstance(messages, list) or not 1 <= len(messages) <= 200:
        raise ValueError('messages 必须为非空消息列表，最多 200 条')
    clean, used_ids, pending = [], set(), None
    for item in messages:
        if not isinstance(item, dict):
            raise ValueError('消息必须为对象')
        role = item.get('role')
        if pending and role != 'tool':
            raise ValueError('计算工具调用后必须先提供工具结果')
        if role == 'assistant':
            if set(item) - {'role', 'content', 'tool_calls', 'reasoning_content'}:
                raise ValueError('assistant消息含不支持字段')
            value = _assistant_message(item)
            if value.get('tool_calls'):
                pending = value['tool_calls'][0]['id']
                if pending in used_ids:
                    raise ValueError('计算工具调用标识重复')
                used_ids.add(pending)
        elif role == 'tool':
            if (set(item) != {'role', 'tool_call_id', 'content'} or not pending
                    or item['tool_call_id'] != pending or not isinstance(item['content'], str)
                    or not item['content'].strip()):
                raise ValueError('工具结果字段或关联无效')
            value = dict(item)
            pending = None
        elif role in ('system', 'user'):
            if (set(item) != {'role', 'content'} or not isinstance(item['content'], str)
                    or not item['content'].strip()):
                raise ValueError('消息角色或正文无效')
            value = dict(item)
        else:
            raise ValueError('消息角色无效')
        clean.append(value)
    if pending:
        raise ValueError('计算工具调用缺少结果')
    return clean


class ModelClient:
    def __init__(self, provider, api_key, model, *, transport=None, timeout=60,
                 max_response_bytes=2000000, max_tokens=8192, thinking='disabled'):
        if provider != 'deepseek':
            raise ValueError('当前仅支持 deepseek')
        if not isinstance(api_key, str) or not api_key.strip() or any(c.isspace() for c in api_key):
            raise ValueError('缺少或无效的 DEEPSEEK_API_KEY')
        if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,160}', model):
            raise ValueError('缺少或无效的 DEEPSEEK_MODEL')
        if (thinking not in ('enabled', 'disabled')
                or type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 120
                or type(max_response_bytes) is not int or not 1 <= max_response_bytes <= 4000000
                or type(max_tokens) is not int or not 1 <= max_tokens <= 32768
                or (transport is not None and not callable(transport))):
            raise ValueError('模型调用限制参数无效')
        self.provider = provider
        self.model = model
        self._api_key = api_key
        self._transport = transport if transport is not None else _http_transport
        self._mode = 'test_double' if transport is not None else 'api'
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self.max_tokens = max_tokens
        self.thinking = thinking

    @property
    def mode(self):
        return self._mode

    def for_review(self):
        """Keep transport provenance and writer settings; bound review separately."""
        reviewer = copy.copy(self)
        reviewer.thinking = 'disabled'
        reviewer.max_tokens = 8192
        return reviewer

    @classmethod
    def from_env(cls, provider='deepseek'):
        if provider != 'deepseek':
            raise ValueError('当前仅支持 deepseek')
        return cls(provider, os.environ.get('DEEPSEEK_API_KEY'), os.environ.get('DEEPSEEK_MODEL'))

    def complete(self, messages, *, tool_choice='auto'):
        if tool_choice not in ('auto', 'none'):
            raise ValueError('tool_choice 只允许 auto 或 none')
        clean = _clean_messages(messages)
        clean.insert(0, {'role': 'system', 'content': 'Use the calculate function for arithmetic when needed. Otherwise return a valid, nonempty JSON object only.'})
        request = {'model': self.model, 'messages': clean,
            'response_format': {'type': 'json_object'}, 'thinking': {'type': self.thinking},
            'max_tokens': self.max_tokens, 'stream': False, 'tools': [CALCULATE_TOOL],
            'tool_choice': tool_choice}
        if self.thinking == 'enabled':
            request['reasoning_effort'] = 'low'
        payload = json.dumps(request, ensure_ascii=False, allow_nan=False).encode('utf-8')
        if len(payload) > 4000000:
            raise ValueError('模型输入超过大小限制')
        headers = {'Authorization': 'Bearer ' + self._api_key, 'Content-Type': 'application/json'}
        started = time.monotonic()
        try:
            raw = self._transport(ENDPOINT, payload, headers, self.timeout, self.max_response_bytes)
        except urllib.error.HTTPError as error:
            code = {400: 'bad_request', 401: 'authentication', 402: 'balance', 403: 'permission',
                    404: 'model_unavailable', 422: 'bad_request', 429: 'rate_limited',
                    500: 'provider_error', 502: 'provider_error', 503: 'provider_error',
                    504: 'provider_error'}.get(error.code, 'request_failed')
            error.close()
            raise ModelAPIError(code) from None
        except TimeoutError:
            raise ModelAPIError('timeout') from None
        except urllib.error.URLError as error:
            raise ModelAPIError('timeout' if isinstance(error.reason, TimeoutError) else 'network') from None
        except Exception:
            raise ModelAPIError('request_failed') from None
        elapsed = time.monotonic() - started
        diagnostic = {'phase': 'response_size', 'elapsed_seconds': elapsed}
        try:
            if not isinstance(raw, bytes) or len(raw) > self.max_response_bytes:
                raise ValueError('响应超过大小限制')
            diagnostic.update(response_bytes=len(raw), phase='envelope_json')
            envelope = _strict_object(raw.decode('utf-8'))
            diagnostic['phase'] = 'completion'
            choices = envelope['choices']
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError('响应选择无效')
            finish = choices[0].get('finish_reason')
            diagnostic['finish_reason'] = finish if finish in ('stop', 'length', 'content_filter', 'tool_calls') else 'other'
            if isinstance(envelope.get('usage'), dict):
                diagnostic.update({k: envelope['usage'][k] for k in ('prompt_tokens', 'completion_tokens', 'total_tokens') if k in envelope['usage']})
            if finish == 'length':
                raise ModelAPIError('output_truncated', diagnostic)
            if finish not in ('stop', 'tool_calls'):
                raise ValueError('响应未完整结束')
            diagnostic['phase'] = 'tool_arguments' if finish == 'tool_calls' else 'content_json'
            message = choices[0].get('message')
            if finish == 'tool_calls' and isinstance(message, dict) and isinstance(message.get('tool_calls'), list):
                diagnostic['tool_call_count'] = len(message['tool_calls'])
            assistant = _assistant_message(choices[0]['message'])
            tool_call_id = None
            if finish == 'tool_calls':
                call, arguments = _native_call(assistant.get('tool_calls'))
                if self._api_key in call['id']:
                    raise ValueError('计算工具标识无效')
                data = {'kind': 'calculate', **arguments}
                tool_call_id = call['id']
            else:
                if assistant.get('tool_calls'):
                    raise ValueError('工具调用未使用对应结束状态')
                diagnostic['content_characters'] = len(assistant['content'])
                data = _strict_object(assistant['content'])
            diagnostic['phase'] = 'metadata'
            model, response_id = envelope['model'], envelope['id']
            if any(not isinstance(item, str) or not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,160}', item)
                   or self._api_key in item for item in (model, response_id)):
                raise ValueError('响应标识无效')
            usage = envelope.get('usage', {})
            if not isinstance(usage, dict):
                raise ValueError('用量字段无效')
            safe_usage = {}
            for key in ('prompt_tokens', 'completion_tokens', 'total_tokens',
                        'prompt_cache_hit_tokens', 'prompt_cache_miss_tokens'):
                if key in usage:
                    if type(usage[key]) is not int or not 0 <= usage[key] <= 10**12:
                        raise ValueError('用量字段无效')
                    safe_usage[key] = usage[key]
        except ModelAPIError:
            raise
        except json.JSONDecodeError as error:
            diagnostic.update(json_error='syntax', json_error_line=error.lineno, json_error_column=error.colno)
            if diagnostic['phase'] == 'tool_arguments':
                diagnostic['tool_error'] = 'arguments_json'
            raise ModelAPIError('invalid_response', diagnostic) from None
        except ValueError as error:
            diagnostic['json_error'] = {'JSON 含重复字段': 'duplicate_key', 'JSON 含非有限数': 'non_finite',
                                        '需要非空 JSON 对象': 'not_object'}.get(str(error), 'other')
            if diagnostic['phase'] == 'tool_arguments':
                diagnostic['tool_error'] = TOOL_ERROR_CODES.get(str(error), 'other')
            raise ModelAPIError('invalid_response', diagnostic) from None
        except Exception:
            if diagnostic['phase'] == 'tool_arguments':
                diagnostic['tool_error'] = 'other'
            raise ModelAPIError('invalid_response', diagnostic) from None
        return {'data': data, 'assistant_message': assistant, 'tool_call_id': tool_call_id,
            'metadata': {'provider': self.provider, 'model': model,
            'thinking': self.thinking,
            'response_id': response_id, 'usage': safe_usage, 'elapsed_seconds': elapsed,
            'inference_executed': self.mode == 'api', 'mode': self.mode}}
