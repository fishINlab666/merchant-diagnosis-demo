"""Command-line entry for the real AI merchant-diagnosis Skill."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from llm_client import LlmClient, LlmError
from pipeline import InputError, run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description='使用真实 Kimi API 生成商户公开初诊、AI 表格映射和完整经营方案。')
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--public-file', type=Path, help='店铺页公开文本文件')
    source.add_argument('--public-text', help='直接传入店铺页公开文本')
    parser.add_argument('--files', type=Path, nargs='*', default=[], help='一份或多份 CSV／XLSX 周报')
    parser.add_argument('--out', type=Path, required=True, help='新的输出目录')
    parser.add_argument('--model', help='覆盖 KIMI_MODEL，默认 kimi-k3.1-pro')
    args = parser.parse_args()
    if args.public_file:
        if not args.public_file.is_file():
            parser.error(f'公开文本不存在：{args.public_file}')
        public_text = args.public_file.read_text(encoding='utf-8')
    else:
        public_text = args.public_text
    try:
        run_pipeline(public_text, args.files, LlmClient(model=args.model), args.out)
        metadata = json.loads((args.out / 'run-metadata.json').read_text(encoding='utf-8'))
        print(json.dumps({
            'status': 'succeeded',
            'output': str(args.out),
            'actual_ai_calls': metadata['actual_ai_calls'],
            'token_usage': metadata['token_usage'],
            'models': sorted({call['model'] for call in metadata['calls']}),
        }, ensure_ascii=False, indent=2))
        return 0
    except (LlmError, InputError, OSError, ValueError) as error:
        print(f'诊断失败：{error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
