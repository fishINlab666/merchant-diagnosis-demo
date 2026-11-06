"""Live acceptance for English aliases and split summary/tool tables."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))

from llm_client import LlmClient
from pipeline import run_pipeline

ROOT = Path(__file__).parents[1]
OUT = ROOT / 'tmp' / f'variant-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
result = run_pipeline(
    (ROOT / 'assets/public-shop.txt').read_text(encoding='utf-8'),
    [ROOT / 'assets/variant-summary.csv', ROOT / 'assets/variant-tools.csv'],
    LlmClient(),
    OUT,
)
metadata = json.loads((OUT / 'run-metadata.json').read_text(encoding='utf-8'))
canonical = result['canonical_report']

assert metadata['actual_ai_calls'] >= 3, metadata
assert metadata['token_usage']['total_tokens'] > 0, metadata
assert canonical['store_id'] == 'S1', canonical
assert canonical['orders'] == 1200, canonical
assert canonical['net_gmv'] == 60000, canonical
assert canonical['exposure'] == 120000, canonical
assert canonical['visits'] == 12000, canonical
assert len(canonical['tools']) == 3, canonical
assert {tool['tool_name'] for tool in canonical['tools']} == {'点金推广', '搜索推广', '品牌展示'}, canonical
assert result['full']['calculation']['status'] == 'ok', result['full']['calculation']

print(json.dumps({
    'status': 'variant-live-succeeded',
    'output': str(OUT),
    'actual_ai_calls': metadata['actual_ai_calls'],
    'token_usage': metadata['token_usage'],
    'models': [call['model'] for call in metadata['calls']],
    'mapped_fields': result['mapping_preview']['mappings'],
    'canonical_report': canonical,
}, ensure_ascii=False, indent=2))
