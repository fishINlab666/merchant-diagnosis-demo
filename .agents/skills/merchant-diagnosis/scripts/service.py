"""Operator CLI; credentials are entered locally and never accepted as arguments."""
import argparse
import getpass
import json
import os
from pathlib import Path
import stat
import sys
import warnings

from model_api import ModelClient
from service_runner import export_project, run_project
from service_store import (KINDS, PHASES, add_material, create_project, read_project,
                           record_review)

DEFAULT_CONFIG = Path.home() / '.config' / 'merchant-diagnosis' / 'credentials.json'


def configure(path, model):
    path = Path(path).expanduser()
    if path.exists() or path.is_symlink():
        raise ValueError('配置文件已存在；需要换钥时先在本机移走旧文件，再重新配置')
    if not sys.stdin.isatty():
        raise ValueError('请在本机交互式终端运行 configure，不从聊天或管道接收密钥')
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            key = getpass.getpass('DeepSeek API key（隐藏输入）：')
        except getpass.GetPassWarning:
            raise ValueError('终端不支持隐藏输入，配置已取消') from None
    ModelClient('deepseek', key, model)
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if path.parent.stat().st_mode & 0o077:
        raise ValueError('配置目录须仅当前用户可访问（权限 700），请使用独立私有目录')
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        json.dump({'provider': 'deepseek', 'model': model, 'api_key': key}, handle)
    print('配置已保存；密钥未回显。配置本身不代表 API 已验证。')


def load_client(config=None, model=None, thinking='disabled', max_tokens=None):
    options = {'thinking': thinking}
    if thinking == 'enabled':
        options.update(timeout=120, max_tokens=16384)
    if max_tokens is not None:
        options['max_tokens'] = max_tokens
    if config is None:
        return ModelClient('deepseek', os.environ.get('DEEPSEEK_API_KEY'),
                           model if model is not None else os.environ.get('DEEPSEEK_MODEL'), **options)
    path = Path(config).expanduser()
    try:
        if path.is_symlink():
            raise ValueError()
        info = path.stat()
        if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077
                or info.st_uid != os.getuid() or info.st_size > 16384):
            raise ValueError()
        data = json.loads(path.read_text(encoding='utf-8'))
        return ModelClient(data['provider'], data['api_key'], model if model is not None else data['model'], **options)
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError('配置不可用；请检查文件、权限 600 及 provider/model/api_key 字段，不要贴出内容') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description='商户诊断服务：材料版本、真实 API 分析、复核与交付')
    commands = parser.add_subparsers(dest='command', required=True)
    config = commands.add_parser('configure', help='仅在本机终端隐藏输入凭证')
    config.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    config.add_argument('--model', required=True)
    for command in ('init', 'add', 'status', 'run', 'review', 'export'):
        sub = commands.add_parser(command)
        sub.add_argument('--project', type=Path, required=True)
        if command == 'init':
            sub.add_argument('--name', required=True)
            sub.add_argument('--goal', required=True)
            sub.add_argument('--synthetic', action='store_true')
        elif command == 'add':
            sub.add_argument('--file', type=Path, required=True)
            sub.add_argument('--slot', required=True)
            sub.add_argument('--kind', choices=sorted(KINDS), required=True)
            sub.add_argument('--period', required=True)
            sub.add_argument('--replace', action='store_true')
        elif command == 'run':
            sub.add_argument('--phase', choices=sorted(PHASES), required=True)
            sub.add_argument('--config', type=Path)
            sub.add_argument('--model', help='本次显式选择模型，不修改配置，不自动切换')
            sub.add_argument('--thinking', choices=['enabled', 'disabled'], default='disabled',
                             help='显式启用低强度思考；默认上限16384 tokens，网络等待超时120秒')
            sub.add_argument('--max-tokens', type=int, default=None,
                             help='本次输出 token 上限（1–32768）；默认思考16384、非思考8192')
            sub.add_argument('--previous')
            sub.add_argument('--revise-final', help='同材料同阶段的退回运行编号；复用 S3/S4，仅重做 S5')
            sub.add_argument('--max-calls', type=int, default=8)
        elif command == 'review':
            sub.add_argument('--run', required=True)
            sub.add_argument('--reviewer', required=True)
            sub.add_argument('--note', required=True)
            sub.add_argument('--decision', choices=['approve', 'reject'], required=True)
        elif command == 'export':
            sub.add_argument('--run')
    args = parser.parse_args(argv)
    try:
        if args.command == 'configure':
            configure(args.config, args.model)
            return 0
        if args.command == 'init':
            result = create_project(args.project, args.name, args.goal, args.synthetic)
        elif args.command == 'add':
            result = add_material(args.project, args.file, args.slot, args.kind, args.period, args.replace)
        elif args.command == 'status':
            data = read_project(args.project)
            result = {k: data[k] for k in ('name', 'goal', 'synthetic', 'material_version')}
            result['materials'] = {k: {'kind': v['kind'], 'period': v['period'], 'revisions': len(v['versions'])} for k, v in data['materials'].items()}
            result['runs'] = [{**r, 'current_materials': r['material_version'] == data['material_version']} for r in data['runs']]
            result['reviews'] = data['reviews']
        elif args.command == 'run':
            client = load_client(args.config, args.model, args.thinking, max_tokens=args.max_tokens)
            revision = {'revise_final_id': args.revise_final} if args.revise_final is not None else {}
            result = run_project(args.project, args.phase, client, args.previous, args.max_calls, **revision)
        elif args.command == 'review':
            result = record_review(args.project, args.run, args.reviewer, args.note, args.decision == 'approve')
        else:
            result = {'report': str(export_project(args.project, args.run).resolve())}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get('status') == 'failed' else 0
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    except OSError:
        print('文件操作失败；请检查路径与权限。', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
