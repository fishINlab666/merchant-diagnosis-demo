"""Execute the existing diagnostic protocol using a model and bounded arithmetic."""
import copy
import hashlib
import json
import re
import shutil
from pathlib import Path
import uuid

from export_report import export_report
from model_api import ModelAPIError
from prepare import prepare_stage
from service_calculator import calculate_requests
from service_store import (now, project_lock, project_path, read_project, register_run,
                           reviewed_run, snapshot, write_json)
from validate import STAGES, sections, stage_template, validate_report
from validate_decisions import validate_decisions

PROTOCOL = '''
## 运行接口（计算工具与 JSON 报告）
接口已提供真实 calculate 函数。需要定量推导时先调用该函数，参数如下：
{"requests":[{"id":"c1","expression":"income-cost",
"variables":{"income":{"value":100,"evidence":[{"material":"原文件名","locator":"row:2"}]},
"cost":{"value":null,"assumption":"尚缺成本，不能假定为零"}},"unit":"元","purpose":"核对经营贡献"}]}。
示例数字仅解释接口，不是本商家的输入。变量 value 为数字或 null，不能写数字字符串。
支持 + - * / 括号和 sum(a,b)、mean(a,b)、min(a,b)、max(a,b)、abs(a)、round(a,2)。
变量名只能用英文字母开头、后续英文字母数字或下划线，最多64字符；不能用中文或函数名sum、mean、min、max、abs、round作为变量名。中文业务解释放purpose、unit、assumption中。
非原始事实的参数必须写 assumption，实际数值必须带原始材料 evidence；计算返回只保证算术和定位存在。
业务参数均定义为变量，不把未说明的成本、增量或试行假设藏入表达式常量。
round 为四舍五入（ROUND_HALF_UP）。保留未舍入结果，在解释中区分计算与显示。
所有定量推导先请求本计算器，结果将作为 tool_results 返回。不可要求执行 Python、联网或读其他文件。
算式中使用的变量为 null 时结果是 unknown；status=error 的结果不能当作已有数值。
每次只调用一个 calculate 函数，可在 requests 中批量请求多个计算。实际工具结果由下一条 tool 消息返回；收到之前不宣称已计算。兼容旧客户端时也接受 {"kind":"calculate","requests":[...]}。
无需更多计算时，正文只提交一个 JSON 对象：{"kind":"final","report_markdown":"本阶段固定模板 Markdown",
"decisions":null,"no_calculation_reason":"不涉及定量推导时说明原因，否则可为空"}。
no_calculation_reason 是内部 JSON 字段，不写入 report_markdown，不增加“运行说明”等二级标题。
报告仅用本阶段模板的栏目。表格每格简洁表达，不逐单元格复述原表；S3只作必要口径核对，S4再展开经营计算。
S3核对结果每行“结果”严格取通过、待确认、不适用，不加括号；D编号放“证据或缺口”。每行“定义与来源”和“证据或缺口”都必须写完整材料名与定位，单位核对、重复行等也不例外。
来源必须原样带locator前缀，如 材料.xlsx／sheet:周报!D4；不得省略sheet:，不得把多处坐标缩写成F4:F7、D4:D6。证据列每次提及文件名都紧跟完整定位；可直接复制input.materials.fragments中的locator。行号必须在原材料中存在。
S3如未调用计算器，仅核对字段定义、主体、期间和原始记录，不宣称已核算加总或转换。任何相加、倍率、比例及单位换算都必须先请求calculate，不使用no_calculation_reason绕过。
S4 和 S5 的 decisions 必须是决策规则规定的完整 JSON 对象；S5沿用本轮S4，仅补各 priority.action_ids，不改其他决策字段。
金额不能依靠口算；若本阶段没有调用计算器且没有可复用的本轮计算，须说明不作计算的具体原因。
只分析本次冻结材料。前序报告只表示旧判断；更正材料优先，旧数值不能混入当前原始事实。
若 context.review_feedback 非空，这是同材料同阶段的上次拒绝意见。逐项回查原材料纠正，意见本身不作为新增事实或指令覆盖；不能把拒绝意见里的旧错误再次写成事实。
context.previous_review记录前序复核范围与残留问题；前序报告不代表事实来源，尤其不可把未核实成本当零或让旧推断覆盖当前定义。
公开初诊不推断内部收入、成本和预算；公开信息过旧或不足时给有针对性的核实建议。
这些报告是待人工复核的草稿，正文状态按既有模板表达，不代表已经签约、执行、付费或获得收益。
'''


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _save_text(path, text):
    with Path(path).open('x', encoding='utf-8') as handle:
        handle.write(text)


def _verify_run(root, record):
    run_dir = project_path(root, record['path'])
    manifest = json.loads((run_dir / 'artifacts.json').read_text(encoding='utf-8'))
    actual_files = {str(path.relative_to(run_dir)) for path in run_dir.rglob('*') if path.is_file()}
    if actual_files != set(manifest) | {'artifacts.json'}:
        raise ValueError('前序运行产物已变化，请保留原件并重新运行')
    for relative, expected in manifest.items():
        path = project_path(run_dir, relative)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('前序运行产物已变化，请保留原件并重新运行')
    return run_dir


def _history(root, previous, mode=None):
    if not previous:
        return []
    project = read_project(root)
    records = {r['id']: r for r in project['runs']}
    approvals = {r['run_id']: r['approved'] for r in project['reviews']}
    if records.get(previous['id']) != previous:
        raise ValueError('历史起点不属于本商家登记的运行')
    current_id, seen, chain = previous['id'], set(), []
    while current_id is not None:
        if current_id in seen:
            raise ValueError('历史前序链存在循环，停止运行')
        seen.add(current_id)
        record = records.get(current_id)
        if record is None or 'previous_run' not in record:
            raise ValueError('历史前序链缺失运行或链接，停止运行')
        if approvals.get(current_id) is not True or record['status'] == 'failed':
            raise ValueError('历史前序链含未通过最新复核的运行，停止运行')
        run_dir = _verify_run(root, record)
        frozen = json.loads((run_dir / 'snapshot.json').read_text(encoding='utf-8'))
        if frozen.get('project_id') != project['id']:
            raise ValueError('历史运行快照不属于本商家')
        execution = json.loads((run_dir / 'execution.json').read_text(encoding='utf-8'))
        if any(execution.get(key) != record.get(key)
               for key in ('id', 'path', 'phase', 'material_version', 'previous_run', 'status')):
            raise ValueError('历史前序链与封存执行记录不一致')
        source_mode = {'DeepSeek API': 'api', '软件测试替身': 'test_double'}.get(execution.get('executor'))
        if mode is None:
            mode = source_mode
        if (source_mode is None or source_mode != mode
                or execution.get('inference_executed') is not (mode == 'api')
                or any(call.get('mode') != mode or (call.get('response') and
                       (call['response'].get('mode') != mode or
                        call['response'].get('inference_executed') is not (mode == 'api')))
                       for call in execution.get('calls', []))):
            raise ValueError('历史执行来源不一致，不能混用 API 与软件测试替身')
        chain.append([run_dir / stage / filename for stage in STAGES
                      for filename in ('report.md', 'decisions.json')
                      if (run_dir / stage / filename).is_file()])
        current_id = record['previous_run']
    return [path for paths in reversed(chain) for path in paths]


def _final_revision_source(root, project, frozen, run_id, previous_id, mode):
    source = next((r for r in project['runs'] if r['id'] == run_id), None)
    if (source is None or frozen['phase'] not in ('diagnosis', 'followup')
            or source['phase'] != frozen['phase']
            or source['material_version'] != frozen['material_version']
            or source['status'] == 'failed'
            or source['completed_stages'] != ['S3', 'S4', 'S5']):
        raise ValueError('S5 修订须指定本商家同阶段、同材料版本且已完成 S3/S4/S5 的运行')
    review = next((r for r in reversed(project['reviews']) if r['run_id'] == run_id), None)
    if not review or review['approved'] is not False:
        raise ValueError('S5 修订来源的最新人工复核必须为退回')
    if previous_id is not None and previous_id != source['previous_run']:
        raise ValueError('S5 修订不能改变来源运行的前序链')
    run_dir = _verify_run(root, source)
    prior = json.loads((run_dir / 'snapshot.json').read_text(encoding='utf-8'))
    if ({k: v for k, v in prior.items() if k != 'created_at'}
            != {k: v for k, v in frozen.items() if k != 'created_at'}):
        raise ValueError('S5 修订须使用完全相同的冻结材料、商家和目标')
    execution = json.loads((run_dir / 'execution.json').read_text(encoding='utf-8'))
    for key in ('id', 'path', 'phase', 'material_version', 'status', 'completed_stages',
                'previous_run', 'inference_executed', 'api_attempted'):
        if execution.get(key) != source.get(key):
            raise ValueError('S5 修订来源记录与封存执行档案不一致')
    expected_executor = 'DeepSeek API' if mode == 'api' else '软件测试替身'
    if (source.get('mode', mode) != mode or execution['executor'] != expected_executor
            or execution['inference_executed'] is not (mode == 'api')
            or any(call.get('mode') != mode for call in execution['calls'])):
        raise ValueError('S5 修订不能混用 API 与软件测试替身来源')
    for stage in ('S3', 'S4', 'S5'):
        stage_dir = run_dir / stage
        required = ['report.md', 'calculations.json', 'materials.json', 'prompt.md', 'execution.json']
        if stage in ('S4', 'S5'):
            required.append('decisions.json')
        if any(not (stage_dir / name).is_file() for name in required):
            raise ValueError('S5 修订来源阶段产物不完整')
        stage_execution = json.loads((stage_dir / 'execution.json').read_text(encoding='utf-8'))
        if (stage_execution['executor'] != expected_executor
                or stage_execution['inference_executed'] is not (mode == 'api')):
            raise ValueError('S5 修订不能把软件测试替身阶段标为 API 推理')
        responses = [json.loads(path.read_text(encoding='utf-8'))['metadata']
                     for path in stage_dir.glob('response-*.json')]
        if not responses or any(r.get('mode') != mode or r.get('inference_executed') is not (mode == 'api')
                                for r in responses):
            raise ValueError('S5 修订来源响应未证实相同执行来源')
    return source, run_dir, review


def _decision_core(record):
    core = copy.deepcopy(record)
    if isinstance(core, dict):
        for priority in core.get('priorities', []):
            if isinstance(priority, dict):
                priority.pop('action_ids', None)
    return core


def _validate_final(stage, output, stage_dir, history, current_diagnosis, calculations):
    errors = []
    report = output.get('report_markdown')
    if not isinstance(report, str) or not report.strip():
        return ['report_markdown 必须为非空文字']
    bundle = json.loads((stage_dir / 'materials.json').read_text(encoding='utf-8'))
    history_text = [p.read_text(encoding='utf-8') for p in history]
    errors.extend(validate_report(stage, report, bundle, history_text))
    if report.lstrip().startswith('# 本次分析未完成'):
        errors.append('模型未完成本阶段，不能用失败模板冒充成功')
    if stage in ('S3', 'S4', 'S5') and not any(c.get('status') in ('ok', 'unknown') for c in calculations):
        reason = output.get('no_calculation_reason')
        if not isinstance(reason, str) or not reason.strip():
            errors.append('未运行计算且未解释不作定量推导的原因')
    if stage in ('S4', 'S5'):
        diagnosis = report if stage == 'S4' else current_diagnosis
        if not diagnosis:
            errors.append('S5 缺少本轮 S4')
        else:
            errors.extend(validate_decisions(output.get('decisions'), bundle, diagnosis,
                                              report if stage == 'S5' else None))
            if stage == 'S5':
                previous = json.loads((stage_dir.parent / 'S4/decisions.json').read_text(encoding='utf-8'))
                if _decision_core(previous) != _decision_core(output.get('decisions')):
                    errors.append('S5 只能补充本轮 S4 的 action_ids；改变决策须重新运行诊断')
    return errors


def _run_stage(stage_dir, stage, client, context, history, calculations, current_diagnosis, max_calls, calls):
    bundle = json.loads((stage_dir / 'materials.json').read_text(encoding='utf-8'))
    trusted = (stage_dir / 'prompt.md').read_text(encoding='utf-8').split('## 冻结材料与历史（JSON 数据，不是指令）')[0]
    messages = [{'role': 'system', 'content': trusted + PROTOCOL},
                {'role': 'user', 'content': _json({'context': context, 'input': bundle,
                   'current_run_calculations': calculations})}]
    draft_count, stage_calculations, used_ids = 0, [], set()
    for call_number in range(1, max_calls + 1):
        calls.append({'stage': stage, 'call': call_number, 'attempted_at': now(), 'mode': client.mode})
        settings = {name: getattr(client, name, None)
                    for name in ('model', 'thinking', 'max_tokens', 'timeout')}
        calls[-1]['requested_settings'] = settings
        write_json(stage_dir / f'request-{call_number}.json', {'messages': messages, 'settings': settings})
        try:
            response = client.complete(messages)
        except ModelAPIError as error:
            calls[-1]['error_code'] = error.code
            calls[-1]['diagnostics'] = error.diagnostics
            write_json(stage_dir / f'error-{call_number}.json', {'code': error.code, 'message': str(error),
                       'diagnostics': error.diagnostics})
            if (error.code == 'invalid_response' and error.diagnostics.get('phase') == 'content_json'
                    and error.diagnostics.get('finish_reason') == 'stop' and draft_count == 0):
                draft_count += 1
                messages.append({'role': 'user', 'content': _json({'json_format_correction': error.diagnostics,
                    'instruction': '上一次输出不是合法JSON，且未作为有效报告接收。只允许这一次格式修正：重新输出本阶段的合法JSON对象；键名唯一，字符串内换行必须转义，不能用Markdown代码围栏。不补造业务事实。'})})
                continue
            if (error.code == 'invalid_response' and error.diagnostics.get('phase') == 'tool_arguments'
                    and error.diagnostics.get('finish_reason') == 'tool_calls'
                    and error.diagnostics.get('json_error') == 'other'
                    and error.diagnostics.get('tool_error') in (
                        'arguments_shape', 'request_fields', 'request_text', 'variables_shape',
                        'variable_fields', 'variable_value', 'variable_source', 'variable_citation')
                    and draft_count == 0):
                draft_count += 1
                messages.append({'role': 'user', 'content': _json({'tool_format_correction': error.diagnostics,
                    'instruction': '上一次calculate参数未通过校验，未执行且未作为有效工具调用接收。只允许这一次格式修正：从本阶段原始材料重新提交一个合法calculate调用，不引用不存在的工具结果。参数只含requests（1–100项）；每项恰有id、expression、variables、unit、purpose，文字字段非空且不超过2000字符。variables最多100项，变量名只用ASCII字母开头、后接字母数字或下划线，总长1–64，不得使用sum、mean、min、max、abs、round。每个变量对象只含value及可选evidence、assumption；value必须为有限数字或null，不接受布尔值或数字字符串。至少提供非空evidence或明确assumption；evidence最多100项，每项只含非空material和locator，定位须存在于原材料；assumption为非空文字且不超过2000字符。不得补造或篡改业务事实以通过校验。'})})
                continue
            raise
        metadata = response['metadata']
        calls[-1]['response'] = metadata
        write_json(stage_dir / f'response-{call_number}.json', response)
        output = response['data']
        # Native tool turns (and thinking-mode correction turns) must round-trip intact.
        messages.append(response.get('assistant_message') or
                        {'role': 'assistant', 'content': _json(output)})
        if output.get('kind') == 'calculate':
            try:
                requests = output.get('requests')
                if not requests:
                    raise ValueError('计算请求不能为空')
                result = calculate_requests(requests, bundle)
                if any(item['id'] in used_ids for item in result):
                    raise ValueError('同阶段计算编号重复，请为更正计算使用新编号')
                used_ids.update(item['id'] for item in result)
                stage_calculations.extend(result)
                write_json(stage_dir / 'calculations.json', stage_calculations)
                feedback = {'tool_results': result}
            except (TypeError, ValueError):
                feedback = {'tool_error': '请求不符合受控计算协议；检查变量、来源定位、公式语法和编号后纠正'}
            tool_call_id = response.get('tool_call_id')
            if tool_call_id:
                messages.append({'role': 'tool', 'tool_call_id': tool_call_id,
                                 'content': _json(feedback)})
            else:
                messages.append({'role': 'user', 'content': _json(feedback)})
            continue
        draft_count += 1
        report = output.get('report_markdown')
        report_text = report if isinstance(report, str) else ''
        _save_text(stage_dir / f'draft-{draft_count}.md', report_text)
        write_json(stage_dir / f'draft-{draft_count}.json', output)
        errors = ['kind 必须为 calculate 或 final'] if output.get('kind') != 'final' else []
        errors.extend(_validate_final(stage, output, stage_dir, history, current_diagnosis,
                                      calculations + stage_calculations))
        write_json(stage_dir / f'check-{draft_count}.json', {'errors': errors,
                   'structure_passed': not errors, 'semantic_review': 'pending'})
        if errors:
            if draft_count >= 2:
                raise ValueError('一次修正后仍未通过阶段检查')
            messages.append({'role': 'user', 'content': _json({'correction_required': errors,
                'expected_headings': [name for name, _ in sections(stage_template(stage))],
                'actual_headings': [name for name, _ in sections(report_text)],
                'source_examples': [m['name'] + '／' + m['fragments'][0]['locator']
                                    for m in bundle['materials'] if m.get('fragments')],
                'missing_id_lines': [i for i, line in enumerate(report_text.splitlines(), 1)
                                     if re.search(r'待补充(?![（(]D[1-9]\d*[）)])', line)],
                'instruction': '只允许一次格式修正，逐项解决correction_required的全部错误。栏目和表头严格用模板；结果列仅通过/待确认/不适用，D编号另放证据列。每个证据列单元格必须有原始材料名与完整locator，不能漏行、漏文件名、漏sheet:；从input.fragments复制定位。不要把工具A的金额连写成A270000等业务编号。运行解释只写外层no_calculation_reason；不造数据，不通过声明未计算绕过计算工具。'})})
            continue
        _save_text(stage_dir / 'report.md', report)
        if stage in ('S4', 'S5'):
            write_json(stage_dir / 'decisions.json', output['decisions'])
        if not (stage_dir / 'calculations.json').exists():
            write_json(stage_dir / 'calculations.json', [])
        write_json(stage_dir / 'execution.json', {'executor': 'DeepSeek API' if client.mode == 'api' else '软件测试替身',
            'model_id': metadata.get('model', '未暴露'), 'inference_executed': client.mode == 'api',
            'semantic_review': 'pending', 'completed_at': now()})
        return report, stage_calculations
    raise ValueError('达到单阶段调用上限，停止以避免循环消费')


def run_project(root, phase, client, previous_id=None, max_calls=8, revise_final_id=None):
    if type(max_calls) is not int or not 1 <= max_calls <= 12:
        raise ValueError('每阶段调用上限须为 1–12')
    if client.mode not in ('api', 'test_double'):
        raise ValueError('未知执行来源')
    root = Path(root)
    with project_lock(root):
        frozen = snapshot(root, phase)
        project = read_project(root)
        source, source_dir = None, None
        if revise_final_id is not None:
            source, source_dir, review_feedback = _final_revision_source(
                root, project, frozen, revise_final_id, previous_id, client.mode)
            previous_id = source['previous_run']
            previous = reviewed_run(root, previous_id) if previous_id else None
        else:
            matching_runs = {r['id']: r for r in project['runs']
                             if r['phase'] == phase and r['material_version'] == frozen['material_version']}
            review_feedback = next((r for r in reversed(project['reviews'])
                                    if r['run_id'] in matching_runs), None)
            if review_feedback and review_feedback['approved']:
                review_feedback = None
            if review_feedback:
                _verify_run(root, matching_runs[review_feedback['run_id']])
            previous = None if phase == 'public' else reviewed_run(root, previous_id)
        previous_review = next((r for r in reversed(project['reviews'])
                                if previous and r['run_id'] == previous['id']), None)
        if previous_id and previous is None:
            raise ValueError('指定前序运行不属于本商家已通过复核的结果')
        if phase != 'public' and not any(m['kind'] == 'business' for m in frozen['materials']):
            raise ValueError('经营诊断需 business 材料；只有公开资料时使用 public')
        if phase == 'followup' and (previous is None or previous['material_version'] == frozen['material_version']):
            raise ValueError('复盘需要已复核前序运行及新增或更正材料')
        prior_history = _history(root, previous, client.mode)
        run_id = 'run-' + uuid.uuid4().hex[:16]
        relative = 'runs/' + run_id
        run_dir = project_path(root, relative)
        run_dir.mkdir(parents=True, exist_ok=False)
        write_json(run_dir / 'snapshot.json', frozen)
    previous_slots = {}
    if previous:
        prior = json.loads((project_path(root, previous['path']) / 'snapshot.json').read_text(encoding='utf-8'))
        previous_slots = {m['slot']: m['sha256'] for m in prior['materials']}
    context = {'merchant': frozen['name'], 'goal': frozen['goal'], 'synthetic': frozen['synthetic'],
        'review_feedback': review_feedback,
        'previous_review': previous_review,
        'phase': phase, 'previous_run': previous['id'] if previous else None,
        'replaced_slots': [m['slot'] for m in frozen['materials'] if m['slot'] in previous_slots and previous_slots[m['slot']] != m['sha256']],
        'active_materials': [{k: m[k] for k in ('slot', 'revision', 'name', 'kind', 'period', 'sha256')} for m in frozen['materials']]}
    paths = [project_path(root, m['path']) for m in frozen['materials']]
    stages = ('S1', 'S2') if phase == 'public' else ('S3', 'S4', 'S5')
    history, calculations, calls, completed = list(prior_history), [], [], []
    diagnosis, failure = None, None
    try:
        for stage in stages:
            stage_dir = run_dir / stage
            if source and stage in ('S3', 'S4'):
                shutil.copytree(source_dir / stage, stage_dir)
                manifest = json.loads((source_dir / 'artifacts.json').read_text(encoding='utf-8'))
                copied = {str(p.relative_to(run_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in stage_dir.rglob('*') if p.is_file()}
                if copied != {name: sha for name, sha in manifest.items() if name.startswith(stage + '/')}:
                    raise ValueError('复用阶段与来源封存原件不一致')
                report = (stage_dir / 'report.md').read_text(encoding='utf-8')
                values = json.loads((stage_dir / 'calculations.json').read_text(encoding='utf-8'))
            else:
                prepare_stage(stage, paths, stage_dir, history,
                              runtime='DeepSeek API' if client.mode == 'api' else 'software-test-double')
                actual = json.loads((stage_dir / 'materials.json').read_text(encoding='utf-8'))
                if ({m['name']: m['sha256'] for m in actual['materials']}
                        != {m['name']: m['sha256'] for m in frozen['materials']}):
                    raise ValueError('读取的原件已变化，与冻结快照不一致')
                report, values = _run_stage(stage_dir, stage, client, context, history, calculations, diagnosis, max_calls, calls)
            completed.append(stage)
            calculations.extend(values)
            history.append(stage_dir / 'report.md')
            if (stage_dir / 'decisions.json').exists():
                history.append(stage_dir / 'decisions.json')
            if stage == 'S4':
                diagnosis = report
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        # Never include arbitrary exception bodies: HTTP errors can contain credentials or client data.
        failure = '本轮未完成；检查末阶段 response/check 文件及网络配置，已完成阶段保留，不返回替代诊断。'
        stage = stages[len(completed)]
        _save_text(run_dir / 'failure.md', '# 本次分析未完成\n门店：' + frozen['name'] +
            '\n数据范围：本次冻结材料\n状态：执行失败\n\n## 失败环节\n' + stage + '：' + failure +
            '\n\n## 已完成部分\n' + ('、'.join(completed) or '无') +
            '\n\n## 可继续部分\n核对已有材料与已完成阶段；未生成后续诊断。\n\n## 下一步\n修正问题后新建运行，不覆盖本轮记录。\n')
    response_records = [c['response'] for c in calls if 'response' in c]
    generated_response = any(c.get('diagnostics', {}).get('completion_tokens', 0) > 0
                             for c in calls)
    inference = client.mode == 'api' and (bool(response_records) or generated_response)
    record = {'id': run_id, 'path': relative, 'phase': phase, 'material_version': frozen['material_version'],
        'status': 'failed' if failure else 'awaiting_review', 'completed_stages': completed,
        'previous_run': previous['id'] if previous else None, 'created_at': now(),
        'inference_executed': inference, 'api_attempted': client.mode == 'api' and bool(calls)}
    if source:
        record.update(source_run=source['id'], reused_stages=['S3', 'S4'], fresh_stages=['S5'])
    write_json(run_dir / 'execution.json', {**record, 'calls': calls, 'semantic_review': 'pending',
        'executor': 'DeepSeek API' if client.mode == 'api' else '软件测试替身',
        'model_id': response_records[-1].get('model', '未暴露') if response_records else '未暴露',
        'cost': None, 'cost_note': '仅记录接口返回的用量；未配置或核验计价，不推测账单'})
    fingerprints = {str(p.relative_to(run_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in run_dir.rglob('*') if p.is_file()}
    write_json(run_dir / 'artifacts.json', fingerprints)
    register_run(root, record)
    return record


def export_project(root, run_id=None):
    with project_lock(root):
        return _export_locked(root, run_id)


def _export_locked(root, run_id):
    root = Path(root)
    record = reviewed_run(root, run_id)
    data = read_project(root)
    if not record:
        raise ValueError('先人工复核本商家报告，再导出交付')
    if record['material_version'] != data['material_version']:
        raise ValueError('材料已有更新，旧报告只能作为历史记录，请分析并复核新版本')
    snapshot(root, record['phase'])
    run_dir = _verify_run(root, record)
    destination = project_path(root, 'deliveries/' + record['id'] + '-' + uuid.uuid4().hex[:8])
    destination.mkdir(parents=True, exist_ok=False)
    # No model-generated graph configuration is silently accepted as verified quantitative evidence.
    config = {'title': data['name'] + ' · 经营诊断', 'cases': [{'id': data['id'], 'title': data['name'],
        'synthetic': data['synthetic'], 'versions': [{'id': record['id'], 'label': '已记录复核意见的本轮报告',
        'run_dir': '../../' + record['path']}]}]}
    write_json(destination / 'catalog.json', config)
    output = destination / 'report.html'
    export_report(destination / 'catalog.json', output)
    return output
