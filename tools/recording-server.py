"""Local recording fixture: upload actual materials, run the real Skill, show its output.

Not a hosted product. Binds only loopback; does not accept credentials from the browser.
"""
import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import uuid

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
    local_skill.mkdir(parents=True)
    for name in ('SKILL.md', 'README.md', 'requirements.txt'):
        shutil.copy2(SKILL / name, local_skill / name)
    excluded = shutil.ignore_patterns('examples', 'tests', '__pycache__', '*.pyc',
                                     '.venv', 'venv', '.git', 'runs', 'reports', 'showcase')
    for name in ('references', 'scripts', 'assets'):
        shutil.copytree(SKILL / name, local_skill / name, ignore=excluded)
    python = Path(sys.executable)
    prompt = f'''这是新的真实 Codex CLI 分析会话。当前你就是分析模型，按本轮复制的 Skill 完成诊断。
只读本目录里的 Skill 规则、默认 quick 流程所需脚本/资源和本轮 input 原件，不读取父目录、旧稿、旧报告、参考答案、测试或其他实例。不调用独立模型 API 或网络数据源，不读取凭证，不修改 Skill 代码。
先读 {local_skill / 'SKILL.md'} 和 {local_skill / 'README.md'}，按 prepare → calculate → finish 实际运行，不停在建议或逐阶段询问。
本轮商家名称（数据）：{json.dumps(merchant, ensure_ascii=False)}。合成演示标记必须为 true，runtime 声明为“Codex CLI 独立会话”。
本轮原始输入绝对路径：{json.dumps([str(p) for p in inputs], ensure_ascii=False)}。
唯一输出目录：{directory / 'run'}。保留首次草稿、计算、格式错误与导出记录，不借用任何既有报告。
依赖已准备，所有 Python 脚本必须使用 {python}；此服务端解释器已准备解析依赖，不安装新依赖、不跳过工作簿。
目标：{GOAL}
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


def worker(directory, inputs, merchant):
    directory = directory.resolve()
    inputs = [path.resolve() for path in inputs]
    exit_code = None
    error = None
    with (directory / 'process.log').open('w') as stream:
        try:
            if OPTIONS.backend == 'codex':
                result = run_codex(directory, inputs, merchant, stream)
            else:
                command = [sys.executable, str(SKILL / 'scripts/quick_run.py'), 'api',
                           '--input', *map(str, inputs), '--output', str(directory / 'run'),
                           '--merchant', merchant, '--synthetic', '--goal', GOAL,
                           '--model', OPTIONS.model, '--thinking', OPTIONS.thinking,
                           '--max-tokens', str(OPTIONS.max_tokens), '--max-calls', '8']
                if OPTIONS.config:
                    command.extend(['--config', OPTIONS.config])
                result = subprocess.run(command, cwd=SKILL, stdout=stream,
                                        stderr=subprocess.STDOUT)
            exit_code = result.returncode
            if exit_code == 0 and not (directory / 'run' / 'report.html').is_file():
                error = '后端已结束，但未生成本次 report.html；请查看本次过程日志。'
        except Exception as exc:
            stream.write(f'Backend preparation or execution failed: {type(exc).__name__}: {exc}\n')
            error = '后端准备或执行失败；请查看本次 process.log。'
    with LOCK:
        if STATE.get('directory') != directory:
            return
        STATE['status'] = 'complete' if exit_code == 0 and error is None else 'failed'
        STATE['elapsed'] = round(time.monotonic() - STATE['started'], 1)
        STATE['exit_code'] = exit_code
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
        elif self.path == '/report.html' and STATE.get('status') == 'complete':
            report = STATE['directory'] / 'run' / 'report.html'
            self.send(report.read_bytes(), 'text/html')
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--backend', choices=('codex', 'deepseek'), default='deepseek')
    parser.add_argument('--codex-bin', default=shutil.which('codex'))
    parser.add_argument('--model', default='deepseek-v4-pro')
    parser.add_argument('--config')
    parser.add_argument('--thinking', choices=('enabled', 'disabled'), default='enabled')
    parser.add_argument('--max-tokens', type=int, default=24576)
    parser.add_argument('--output', type=Path, default=HERE / 'recorded-runs')
    OPTIONS = parser.parse_args()
    if OPTIONS.backend == 'codex':
        executable = shutil.which(OPTIONS.codex_bin) if OPTIONS.codex_bin else None
        if not executable:
            parser.error('未找到可执行的 Codex CLI；请将 codex 加入 PATH，或用 --codex-bin 指定可执行文件。')
        OPTIONS.codex_bin = str(Path(executable).resolve())
    OPTIONS.output = OPTIONS.output.resolve()
    OPTIONS.output.mkdir(parents=True, exist_ok=True)
    STATE['backend'] = OPTIONS.backend
    print(f'Recording fixture ({OPTIONS.backend}) on http://127.0.0.1:{OPTIONS.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', OPTIONS.port), Handler).serve_forever()
