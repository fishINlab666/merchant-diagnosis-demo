"""Local merchant projects with explicit, immutable material revisions."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import uuid

from ingest import MAX_FILE_BYTES, read_material

KINDS = {'public', 'business', 'definition', 'receipt'}
PHASES = {'public', 'diagnosis', 'followup'}


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,79}', value):
        raise ValueError('编号须以小写字母开头，仅含小写字母、数字、连字符或下划线')
    return value


def required_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + '不能为空')
    return value.strip()


def project_path(root, relative):
    root = Path(root).resolve()
    rel = Path(relative)
    target = root / rel
    if rel.is_absolute() or '..' in rel.parts or not target.resolve().is_relative_to(root):
        raise ValueError('项目路径必须位于本商家目录内')
    return target


def write_json(path, data):
    """Atomic replacement for indexes; callers hold the project lock."""
    path = Path(path)
    payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextmanager
def project_lock(root):
    path = project_path(root, '.write.lock')
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('项目正在写入或上次操作中断；确认没有运行中的任务后再处理 .write.lock') from None
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        path.unlink()


def read_project(root):
    path = project_path(root, 'project.json')
    if not path.is_file():
        raise ValueError('商家项目不存在，请先 init')
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version') != '1.0':
        raise ValueError('不支持该项目版本')
    return data


def create_project(path, name, goal, synthetic=False):
    name, goal = required_text(name, '商家名称'), required_text(goal, '经营目标')
    if type(synthetic) is not bool:
        raise ValueError('synthetic 必须为布尔值')
    path = Path(path)
    if path.exists():
        raise ValueError('目录已存在，不能覆盖商家项目')
    path.mkdir(parents=True, mode=0o700)
    data = {'schema_version': '1.0', 'id': 'merchant-' + uuid.uuid4().hex[:12],
            'name': name, 'goal': goal, 'synthetic': synthetic, 'created_at': now(),
            'material_version': 0, 'materials': {}, 'runs': [], 'reviews': []}
    (path / '.gitignore').write_text('*\n', encoding='utf-8')
    write_json(path / 'project.json', data)
    return data


def add_material(root, source, slot, kind, period, replace=False):
    identifier(slot)
    if kind not in KINDS:
        raise ValueError('kind 须为 public/business/definition/receipt')
    period = required_text(period, '材料期间')
    source = Path(source)
    if not source.is_file() or source.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('材料不存在或超出读取上限')
    name = source.name
    if '\\' in name or any(ord(c) < 32 for c in name):
        raise ValueError('文件名含不支持的分隔符或控制字符')
    raw = source.read_bytes()
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError('材料超出读取上限')
    sha = hashlib.sha256(raw).hexdigest()
    # Parse exactly the bytes we will archive, rather than rereading a changing source.
    with tempfile.TemporaryDirectory() as temp:
        check = Path(temp) / name
        check.write_bytes(raw)
        read_material(check)
    with project_lock(root):
        data = read_project(root)
        previous = data['materials'].get(slot)
        if previous:
            active = previous['versions'][-1]
            if (active['sha256'], active['name'], previous['kind'], previous['period']) == (sha, name, kind, period):
                return active
            if not replace:
                raise ValueError('该 slot 已有材料；更正请显式 --replace，新期间请使用新 slot 和不同文件名')
            if previous['kind'] != kind:
                raise ValueError('更正不能改变材料 kind；请另建相应材料槽位')
        elif replace:
            raise ValueError('没有可替换的旧材料')
        for key, item in data['materials'].items():
            if key != slot:
                active = item['versions'][-1]
                if active['sha256'] == sha:
                    raise ValueError('相同内容已作为另一份材料登记，不能重复累加')
                if active['name'] == name:
                    raise ValueError('不同材料使用了相同文件名；请在原文件名中区分期间或内容')
        revision = len(previous['versions']) + 1 if previous else 1
        relative = f'materials/{slot}/v{revision:04d}/{name}'
        target = project_path(root, relative)
        target.parent.mkdir(parents=True, exist_ok=False)
        try:
            with target.open('xb') as handle:
                handle.write(raw)
            target.chmod(0o600)
            record = {'revision': revision, 'name': name, 'sha256': sha, 'path': relative,
                      'kind': kind, 'period': period, 'created_at': now()}
            item = previous or {'kind': kind, 'period': period, 'versions': []}
            item['period'] = period
            item['versions'].append(record)
            data['materials'][slot] = item
            data['material_version'] += 1
            write_json(project_path(root, 'project.json'), data)
        except Exception:
            target.unlink(missing_ok=True)
            target.parent.rmdir()
            raise
        return record


def snapshot(root, phase):
    if phase not in PHASES:
        raise ValueError('未知运行阶段')
    data = read_project(root)
    materials = []
    for slot, item in sorted(data['materials'].items()):
        if phase == 'public' and item['kind'] != 'public':
            continue
        record = item['versions'][-1]
        path = project_path(root, record['path'])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('已归档材料发生变化，停止运行：' + slot)
        materials.append({'slot': slot, 'kind': item['kind'], 'period': item['period'], **record})
    if not materials:
        raise ValueError('当前阶段没有可读取的材料')
    return {'project_id': data['id'], 'name': data['name'], 'goal': data['goal'],
            'synthetic': data['synthetic'], 'material_version': data['material_version'],
            'phase': phase, 'materials': materials, 'created_at': now()}


def register_run(root, record):
    identifier(record['id'])
    project_path(root, record['path'])
    with project_lock(root):
        data = read_project(root)
        if any(r['id'] == record['id'] for r in data['runs']):
            raise ValueError('运行编号已存在，不能覆盖')
        data['runs'].append(record)
        write_json(project_path(root, 'project.json'), data)


def record_review(root, run_id, reviewer, note, approved):
    reviewer, note = required_text(reviewer, '复核人'), required_text(note, '复核依据')
    if type(approved) is not bool:
        raise ValueError('复核结果必须为布尔值')
    with project_lock(root):
        data = read_project(root)
        record = next((r for r in data['runs'] if r['id'] == run_id), None)
        if record is None or record['status'] != 'awaiting_review':
            raise ValueError('只能复核已完成校验的本商家运行')
        if approved and record['material_version'] != data['material_version']:
            raise ValueError('材料已有更新，请重新分析后再确认当前交付')
        review = {'run_id': run_id, 'reviewer': reviewer, 'note': note, 'approved': approved, 'created_at': now()}
        data['reviews'].append(review)
        write_json(project_path(root, 'project.json'), data)
        return review


def reviewed_run(root, run_id=None):
    data = read_project(root)
    decisions = {}
    for item in data['reviews']:
        decisions[item['run_id']] = item['approved']
    for record in reversed(data['runs']):
        if (run_id is None or record['id'] == run_id) and decisions.get(record['id']) is True:
            return record
    return None
