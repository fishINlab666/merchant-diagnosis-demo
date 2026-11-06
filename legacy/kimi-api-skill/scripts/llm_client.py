"""Minimal real Kimi Chat Completions client. No fallback answers."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

Transport = Callable[[str, dict[str, Any], dict[str, str], int], dict[str, Any]]


class LlmError(RuntimeError):
    pass


@dataclass
class LlmResult:
    data: dict[str, Any]
    model: str
    usage: dict[str, int]
    provider: str = 'moonshot'


def http_transport(url: str, body: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
        headers=headers,
        method='POST',
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


class LlmClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        transport: Transport | None = None,
        timeout: int = 90,
    ) -> None:
        self.api_key = api_key or os.environ.get('KIMI_API_KEY') or os.environ.get('MOONSHOT_API_KEY')
        configured_base = (base_url or os.environ.get('KIMI_BASE_URL') or 'https://api.moonshot.cn/v1').rstrip('/')
        if configured_base.endswith('/coding'):
            configured_base = f'{configured_base}/v1'
        self.base_url = configured_base
        coding_model = '/coding/' in configured_base
        self.model = model or os.environ.get('KIMI_MODEL') or ('k3.1-pro' if coding_model else 'kimi-k3.1-pro')
        self.transport = transport or http_transport
        self.timeout = timeout

    def complete_json(self, stage: str, payload: dict[str, Any]) -> LlmResult:
        if not self.api_key:
            raise LlmError('缺少 KIMI_API_KEY（或 MOONSHOT_API_KEY），无法执行真实模型调用。')
        endpoint = self.base_url if self.base_url.endswith('/chat/completions') else f'{self.base_url}/chat/completions'
        body = {
            'model': self.model,
            'messages': [
                {
                    'role': 'system',
                    'content': '你是外卖商户经营诊断专家。只输出一个合法 JSON 对象，不要输出 Markdown、代码围栏或额外解释。所有结论必须区分输入事实与分析判断，不得编造缺失数据。',
                },
                {'role': 'user', 'content': json.dumps({'stage': stage, 'input': payload}, ensure_ascii=False)},
            ],
            'response_format': {'type': 'json_object'},
        }
        headers = {'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'}
        try:
            response = self.transport(endpoint, body, headers, self.timeout)
            content = response['choices'][0]['message']['content']
            if not isinstance(content, str):
                raise LlmError(f'{stage} 返回了非文本内容，无法解析。')
            normalized = content.strip()
            if normalized.startswith('```'):
                normalized = normalized.removeprefix('```json').removeprefix('```').removesuffix('```').strip()
            data = json.loads(normalized)
            if not isinstance(data, dict):
                raise LlmError(f'{stage} 返回的 JSON 不是对象。')
            usage = response.get('usage') or {}
            return LlmResult(
                data=data,
                model=response.get('model') or self.model,
                usage={key: int(value) for key, value in usage.items() if isinstance(value, (int, float))},
            )
        except LlmError:
            raise
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError, IndexError, TypeError, ValueError, RuntimeError) as error:
            raise LlmError(f'{stage} 真实模型调用失败：{error}') from error
