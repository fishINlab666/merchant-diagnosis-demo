"""Local recording fixture: upload actual materials, run the real Skill, show its output.

Not a hosted product. Binds only loopback; does not accept credentials from the browser.
"""
import argparse
import base64
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / '.agents' / 'skills' / 'merchant-diagnosis'
HERE = Path(__file__).parent
STATE = {'status': 'ready', 'backend': 'deepseek'}
LOCK = threading.Lock()
OPTIONS = None
GOAL = '本轮只做预算调拨方案。老板主卡必须回答本次策略在审慎情况下每月多留多少钱：用扣齐费用的月度经营贡献改善差额，不用全店原有贡献存量，也不用7日金额替代月度主卡。基准与审慎情景分开，参数和对应结果不可混用。每店新增预算上限与每店总额分开说；继续条件必须是相对可比基线的贡献差额为正，不以绝对贡献仍盈利代替。公开页问题本轮仅记补数，不顺带承诺改页面零投入或人数标注。给首轮动作、负责人、明确止损与两轮复盘条件。首批围绕主要决定批量计算8–12项；所有派生在公式中用原始数值完成，原值引用要真实。图表也围绕预算分配、边际观察和月度改善拆解，文字简洁，不写材料编号。'


def console_html(backend):
    page = (HERE / 'recording-console.html').read_text()
    if backend == 'codex':
        page = page.replace('真实 API 流程录制', '真实 Codex 会话录制')
        page = page.replace('调用 DeepSeek 分析和计算',
                            '由真实 Codex CLI 会话分析，并调用本地工具计算')
        page = page.replace('平时可直接在 Claude / Codex 中交材料，或运行 quick_run.py api',
                            '本轮由独立 Codex 会话读取新材料，按 Skill 的 quick 流程实际运行')
        page = page.replace('报告、实际计算与模型响应均已保存。',
                            '报告、实际计算与 Codex 会话事件均已保存。')
    return page


def run_codex(directory, inputs, merchant, log):
    # A fresh git root prevents discovery of the parent workspace's old runs.
    subprocess.run(['git', 'init', '--quiet', str(directory)], check=True,
                   stdout=log, stderr=subprocess.STDOUT)
    local_skill = directory / 'skills' / 'merchant-diagnosis'
    skill = getattr(OPTIONS, 'skill_dir', SKILL)
    local_skill.mkdir(parents=True)
    for name in ('SKILL.md', 'README.md', 'requirements.txt'):
        shutil.copy2(skill / name, local_skill / name)
    excluded = shutil.ignore_patterns('examples', 'tests', '__pycache__', '*.pyc',
                                     '.venv', 'venv', '.git', 'runs', 'reports', 'showcase')
    for name in ('references', 'scripts', 'assets'):
        shutil.copytree(skill / name, local_skill / name, ignore=excluded)
    python = Path(sys.executable)
    prompt = f'''这是新的真实 Codex CLI 分析会话。当前你就是分析模型，按本轮复制的 Skill 完成诊断。
只读本目录里的 Skill 规则、默认 quick 流程所需脚本/资源和本轮 input 原件，不读取父目录、旧稿、旧报告、参考答案、测试或其他实例。不调用独立模型 API 或网络数据源，不读取凭证，不修改 Skill 代码。
先读 {local_skill / 'SKILL.md'} 和 {local_skill / 'README.md'}，按 prepare → calculate → finish 实际运行，不停在建议或逐阶段询问。
本轮商家名称（数据）：{json.dumps(merchant, ensure_ascii=False)}。合成演示标记必须为 true，runtime 声明为“Codex CLI 独立会话”。
本轮原始输入绝对路径：{json.dumps([str(p) for p in inputs], ensure_ascii=False)}。
唯一输出目录：{directory / 'run'}。保留首次草稿、计算、格式错误与导出记录，不借用任何既有报告。
依赖已准备，所有 Python 脚本必须使用 {python}；此服务端解释器已准备解析依赖，不安装新依赖、不跳过工作簿。
目标：{getattr(OPTIONS, 'goal', GOAL)}
完成前自行对照原件检查业务口径、来源、成本、停止条件；最终只说明实际产物路径与返工情况。'''
    (directory / 'input-prompt.txt').write_text(prompt)
    env = os.environ.copy()
    env['PATH'] = str(python.parent) + os.pathsep + env.get('PATH', '')
    command = [OPTIONS.codex_bin, 'exec', '--ephemeral', '--ignore-user-config',
               '--json', '--skip-git-repo-check', '--sandbox', 'workspace-write',
               '--color', 'never', '-']
    with (directory / 'host-events.jsonl').open('w') as events:
        return subprocess.run(command, input=prompt, text=True, cwd=directory,
                              env=env, stdout=events, stderr=log)


def checked_file(directory, path):
    """Reject lexical escapes and symlinks before resolving any run artifact."""
    path = Path(path)
    if not path.is_absolute():
        path = directory / path
    if '..' in path.parts or not path.is_relative_to(directory / 'run'):
        raise ValueError('报告路径不在本轮 run 根内')
    if any(part.is_symlink() for part in (path, *path.parents)
           if part.is_relative_to(directory)) or not path.is_file():
        raise ValueError('报告关联文件缺失或使用了软链接')
    return path


def verify_report(directory, relative):
    report = checked_file(directory, relative)
    if report.name != 'report.html':
        raise ValueError('交付链接须指向 report.html')
    root = report.parent
    manifest = json.loads(checked_file(directory, root / 'manifest.json').read_text())
    state = json.loads(checked_file(directory, root / 'execution.json').read_text())
    if state.get('status') != 'completed' or state.get('report') != 'report.html':
        raise ValueError('所选报告尚未完成')
    names = ['report.json', 'calculations.json', 'ali-ka-playbook.md', *manifest['files']]
    if state.get('method_usage_sha256'):
        names.append('method-usage.json')
    for name in names:
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError('报告关联文件名无效')
        checked_file(directory, root / name)
    # Use installed, trusted validators, never execute code delivered in the run.
    code = '''import json, re, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from quick_run import _previous_history
from boss_report import customer_data
root = Path(sys.argv[2])
bundle = json.loads((root / 'materials.json').read_text())
record = _previous_history(root / 'report.json', bundle['merchant'])
payloads = re.findall(r'<script id="boss-data" type="application/json">(.*?)</script>',
                     (root / 'report.html').read_text(), re.S)
if len(payloads) != 1 or json.loads(payloads[0]) != customer_data(record['report']):
    raise ValueError('HTML/report binding mismatch')
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-c', code,
        str(ROOT / '.agents/skills/merchant-diagnosis/scripts'), str(root)],
        capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError('报告、计算、HTML 或冻结规则关联校验失败')
    return report


def delivery_targets(text):
    links = []
    def markdown(match):
        links.append(match.group(1) or match.group(2))
        return ' '
    text = re.sub(r'\[[^\]]*\]\((?:<([^>]+)>|([^\s)]+))\)', markdown, text)
    def quoted(match):
        links.append(match.group(1))
        return ' '
    text = re.sub(r'`+([^`]+)`+', quoted, text)
    links.extend(re.findall(r'''[^\s`<>\[\](){}，。；：!?'"]+\.html(?:[:?#][^\s`<>\[\](){}，。；：!?'"]*)?''', text, re.I))
    targets = set()
    for link in links:
        link = unquote(link.strip())
        if not re.search(r'\.html(?=[:?#\s]|$)', link, re.I):
            continue
        link = re.sub(r'(\.html):[0-9]+(?::[0-9]+)?$', r'\1', link, flags=re.I)
        parsed = urlsplit(link)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError('交付报告链接须为本轮本地文件')
        targets.add(parsed.path)
    return targets


def select_report(directory, backend):
    targets = set()
    events = directory / 'host-events.jsonl'
    if backend == 'codex' and events.is_file():
        final = ''
        for line in events.read_text(encoding='utf-8').splitlines():
            event = json.loads(line)
            item = event.get('item', {})
            if event.get('type') == 'item.completed' and item.get('type') == 'agent_message':
                final = item.get('text', '')
        targets = delivery_targets(final)
    if not targets:
        targets = {str(path.relative_to(directory)) for path in (directory / 'run').rglob('report.html')}
    if len(targets) != 1:
        raise ValueError('未生成本次 report.html，或存在多个报告且没有唯一明确交付链接')
    report = verify_report(directory, targets.pop())
    return str(report.relative_to(directory))


def worker(directory, inputs, merchant):
    directory = directory.resolve()
    inputs = [path.resolve() for path in inputs]
    exit_code = None
    error = None
    selected = None
    with (directory / 'process.log').open('w') as stream:
        try:
            if OPTIONS.backend == 'codex':
                result = run_codex(directory, inputs, merchant, stream)
            else:
                skill = getattr(OPTIONS, 'skill_dir', SKILL)
                command = [sys.executable, str(skill / 'scripts/quick_run.py'), 'api',
                           '--input', *map(str, inputs), '--output', str(directory / 'run'),
                           '--merchant', merchant, '--synthetic', '--goal', getattr(OPTIONS, 'goal', GOAL),
                           '--model', OPTIONS.model, '--thinking', OPTIONS.thinking,
                           '--max-tokens', str(OPTIONS.max_tokens), '--max-calls', '8']
                if OPTIONS.config:
                    command.extend(['--config', OPTIONS.config])
                result = subprocess.run(command, cwd=skill, stdout=stream,
                                        stderr=subprocess.STDOUT)
            exit_code = result.returncode
            if exit_code == 0:
                try:
                    selected = select_report(directory, OPTIONS.backend)
                except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
                    error = '未生成本次 report.html，或最终交付路径/完成状态/产物关联无法确认；请查看本次过程日志。'
        except Exception as exc:
            stream.write(f'Backend preparation or execution failed: {type(exc).__name__}: {exc}\n')
            error = '后端准备或执行失败；请查看本次 process.log。'
    with LOCK:
        if STATE.get('directory') != directory:
            return
        STATE['status'] = 'complete' if exit_code == 0 and error is None else 'failed'
        STATE['elapsed'] = round(time.monotonic() - STATE['started'], 1)
        STATE['exit_code'] = exit_code
        STATE.pop('output_report', None)
        if STATE['status'] == 'complete':
            STATE['output_report'] = selected
        if error:
            STATE['error'] = error


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, body, content_type='application/json', status=200):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        if isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/':
            self.send(console_html(OPTIONS.backend), 'text/html')
        elif self.path == '/status':
            with LOCK:
                public = {key: value for key, value in STATE.items()
                          if key not in ('directory', 'started')}
                if STATE.get('started'):
                    public['elapsed'] = STATE.get('elapsed', round(time.monotonic() - STATE['started'], 1))
            self.send(public)
        elif self.path in ('/report.html', '/playbook.html') and STATE.get('status') == 'complete':
            with LOCK:
                directory, selected = STATE['directory'], STATE.get('output_report')
            try:
                report = verify_report(directory, selected)
            except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
                self.send({'error': 'not found'}, status=404)
                return
            if self.path == '/report.html':
                self.send(report.read_bytes(), 'text/html')
                return
            frozen = checked_file(directory, report.parent / 'ali-ka-playbook.md')
            source = escape(frozen.read_text(encoding='utf-8'))
            self.send('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
                      '<meta name="viewport" content="width=device-width, initial-scale=1">'
                      '<title>本轮方法一页纸</title><style>body{max-width:960px;margin:40px auto;'
                      'padding:0 24px;background:#f5f7f1;color:#173b32;font:17px/1.8 system-ui;}'
                      'pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}</style>'
                      '<a href="/report.html">返回本次看板</a><h1>本轮方法一页纸</h1>'
                      '<p>以下为本次 prepare 冻结的原文。</p><pre>' + source + '</pre></html>', 'text/html')
        else:
            self.send({'error': 'not found'}, status=404)

    def do_POST(self):
        origin = self.headers.get('Origin')
        if self.path != '/run' or origin != f'http://127.0.0.1:{OPTIONS.port}':
            self.send({'error': 'local origin required'}, status=403)
            return
        with LOCK:
            if STATE['status'] == 'running':
                self.send({'error': 'run already active'}, status=409)
                return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 25 * 1024 * 1024:
                raise ValueError('材料总大小超限')
            data = json.loads(self.rfile.read(size))
            merchant = data['merchant'].strip()
            if not merchant or len(merchant) > 100:
                raise ValueError('请填写商家名称')
            files = data['files']
            if not isinstance(files, list) or not 1 <= len(files) <= 12:
                raise ValueError('请选择1–12份原始材料')
            checked = []
            names = set()
            for item in files:
                name = item['name']
                if Path(name).name != name or name in names or Path(name).suffix.lower() not in {'.md', '.txt', '.csv', '.tsv', '.xlsx', '.pdf', '.html'}:
                    raise ValueError('文件名称重复或格式不支持')
                body = base64.b64decode(item['data'], validate=True)
                if len(body) > 20 * 1024 * 1024:
                    raise ValueError('单份材料超过20MB')
                names.add(name)
                checked.append((name, body))
            with LOCK:
                if STATE['status'] == 'running':
                    self.send({'error': 'run already active'}, status=409)
                    return
                directory = OPTIONS.output / ('live-' + uuid.uuid4().hex[:10])
                (directory / 'input').mkdir(parents=True)
                inputs = []
                for name, body in checked:
                    path = directory / 'input' / name
                    path.write_bytes(body)
                    inputs.append(path)
                STATE.clear()
                STATE.update(status='running', started=time.monotonic(), directory=directory,
                             merchant=merchant, files=[p.name for p in inputs],
                             backend=OPTIONS.backend)
            threading.Thread(target=worker, args=(directory, inputs, merchant), daemon=True).start()
            self.send({'status': 'running'})
        except (ValueError, KeyError, TypeError) as exc:
            self.send({'error': str(exc)}, status=400)


def parse_options(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--backend', choices=('codex', 'deepseek'), default='deepseek')
    parser.add_argument('--codex-bin', default=shutil.which('codex'))
    parser.add_argument('--model', default='deepseek-v4-pro')
    parser.add_argument('--config')
    parser.add_argument('--thinking', choices=('enabled', 'disabled'), default='enabled')
    parser.add_argument('--max-tokens', type=int, default=24576)
    parser.add_argument('--output', type=Path, default=HERE / 'recorded-runs')
    parser.add_argument('--skill-dir', type=Path, default=SKILL,
                        help='本轮已解压的 Skill 根目录（含 SKILL.md 和 README.md）')
    parser.add_argument('--goal-file', type=Path, help='逐字读取 UTF-8 诊断目标；省略则使用原默认目标')
    options = parser.parse_args(argv)
    options.skill_dir = options.skill_dir.resolve()
    required = ('SKILL.md', 'README.md', 'requirements.txt', 'references', 'scripts', 'assets')
    if any(not (options.skill_dir / name).exists() for name in required):
        parser.error('--skill-dir 缺少 Skill 必需文件或目录')
    try:
        options.goal = options.goal_file.read_text(encoding='utf-8') if options.goal_file else GOAL
    except (OSError, UnicodeError) as exc:
        parser.error(f'无法读取 UTF-8 --goal-file：{exc}')
    if not options.goal.strip():
        parser.error('--goal-file 不可为空')
    if options.backend == 'codex':
        executable = shutil.which(options.codex_bin) if options.codex_bin else None
        if not executable:
            parser.error('未找到可执行的 Codex CLI；请将 codex 加入 PATH，或用 --codex-bin 指定可执行文件。')
        options.codex_bin = str(Path(executable).resolve())
    options.output = options.output.resolve()
    return options


if __name__ == '__main__':
    OPTIONS = parse_options()
    OPTIONS.output.mkdir(parents=True, exist_ok=True)
    STATE['backend'] = OPTIONS.backend
    print(f'Recording fixture ({OPTIONS.backend}) on http://127.0.0.1:{OPTIONS.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', OPTIONS.port), Handler).serve_forever()
