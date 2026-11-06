"""Live acceptance: three real Kimi stages on explicitly synthetic inputs."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))

from llm_client import LlmClient
from pipeline import run_pipeline

ROOT = Path(__file__).parents[1]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'tmp' / f'live-{datetime.now().strftime("%Y%m%d-%H%M%S")}'

public_text = (ROOT / 'assets/public-shop.txt').read_text(encoding='utf-8')
result = run_pipeline(public_text, [ROOT / 'assets/demo-weekly.csv'], LlmClient(), OUT)
metadata = json.loads((OUT / 'run-metadata.json').read_text(encoding='utf-8'))
full_text = (OUT / 'full-diagnosis.md').read_text(encoding='utf-8')

assert metadata['actual_ai_calls'] >= 3, metadata
assert metadata['token_usage']['total_tokens'] > 0, metadata
assert all(call['model'] for call in metadata['calls'])
assert result['public']['headline']
assert result['mapping_preview']['mappings']
assert result['full']['calculation']['status'] == 'ok', result['full']['calculation']
assert full_text.count('不是收益承诺') <= 1
assert '不是已经证实的结论' not in full_text

print(json.dumps({
    'status': 'live-succeeded',
    'output': str(OUT),
    'actual_ai_calls': metadata['actual_ai_calls'],
    'token_usage': metadata['token_usage'],
    'models': [call['model'] for call in metadata['calls']],
    'public_headline': result['public']['headline'],
    'full_headline': result['full']['headline'],
    'calculation': result['full']['calculation'],
}, ensure_ascii=False, indent=2))
