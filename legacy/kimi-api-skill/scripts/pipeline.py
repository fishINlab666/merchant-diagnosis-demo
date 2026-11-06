"""AI-guided merchant diagnosis pipeline with source-faithful calculations."""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from file_readers import read_table_file
from llm_client import LlmClient, LlmResult

CANONICAL_FIELDS = {
    'store_id', 'week_start', 'exported_at', 'orders', 'net_gmv', 'merchant_subsidy',
    'platform_subsidy', 'exposure', 'visits', 'repeat_customer_rate', 'member_share',
    'tool_name', 'spend', 'attributed_gmv', 'roi', 'attribution_window_days',
    'attribution_definition',
}
SUMMARY_FIELDS = (
    'orders', 'net_gmv', 'merchant_subsidy', 'platform_subsidy', 'exposure', 'visits',
    'repeat_customer_rate', 'member_share',
)
RATE_FIELDS = {'repeat_customer_rate', 'member_share'}


class InputError(RuntimeError):
    pass


def map_tables(previews: list[dict[str, Any]], client: LlmClient) -> dict[str, Any]:
    """Ask the model for semantics only; cell values are never supplied as canonical output."""
    llm_result = client.complete_json('table_mapping', {
        'task': '识别每个工作表的粒度和字段语义。fields 的键只能是允许的标准字段，值必须是原表头，不得编造列名或数据值。',
        'allowed_fields': sorted(CANONICAL_FIELDS),
        'tables': previews,
        'output_shape': {
            'mappings': [{'file_name': '原文件名', 'sheet_name': '原工作表名', 'grain': 'store_week 或 store_week_tools 或 unknown', 'fields': {'net_gmv': '原表头'}}],
            'missing_fields': ['无法可靠映射的标准字段'],
            'notes': '粒度、单位、歧义与数据质量说明',
        },
    })
    result = llm_result.data
    result['_llm'] = usage_metadata(llm_result, 'table_mapping')
    mappings = result.get('mappings')
    if not isinstance(mappings, list):
        raise InputError('表格语义映射结果缺少 mappings。')
    result.setdefault('missing_fields', [])
    result.setdefault('notes', '')
    return result


def parse_number(value: Any, rate: bool = False) -> float | None:
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip().replace(',', '').replace('，', '')
        is_percent = '%' in text or '％' in text
        for token in ('¥', '￥', '元', '￥', '$', ' ', '％', '%'):
            text = text.replace(token, '')
        if text.startswith('(') and text.endswith(')'):
            text = f'-{text[1:-1]}'
        try:
            number = float(text)
        except ValueError:
            return None
        if rate and (is_percent or number > 1):
            number /= 100
    return number if math.isfinite(number) else None


def text_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def apply_mappings(previews: list[dict[str, Any]], mapping_result: dict[str, Any]) -> dict[str, Any]:
    preview_by_key = {(item['file_name'], item['sheet_name']): item for item in previews}
    summary_records: dict[tuple[str, str], dict[str, Any]] = {}
    tool_records: dict[tuple[str, str, str], dict[str, Any]] = {}
    warnings: list[str] = []
    store_ids: set[str] = set()
    source_rows = 0
    inherited_tool_sheets = 0

    for mapping in mapping_result.get('mappings', []):
        key = (mapping.get('file_name'), mapping.get('sheet_name'))
        preview = preview_by_key.get(key)
        grain = mapping.get('grain')
        fields = mapping.get('fields') or {}
        if preview and grain == 'unknown' and fields.get('tool_name') and fields.get('spend'):
            known_weeks = {week for _, week in summary_records}
            if len(store_ids) <= 1 and len(known_weeks) <= 1:
                grain = 'store_week_tools'
                inherited_tool_sheets += 1
                warnings.append(f'{key[0]}／{key[1]} 未提供门店／周期，已按本次唯一门店和周期关联，请确认。')
            else:
                warnings.append(f'{key[0]}／{key[1]} 缺少门店／周期且无法唯一关联，未纳入。')
        if not preview or grain not in ('store_week', 'store_week_tools'):
            if mapping.get('file_name'):
                warnings.append(f'{key[0]}／{key[1]} 未纳入：表粒度或文件无法确认。')
            continue
        headers = preview['headers']
        index_by_name = {name: index for index, name in enumerate(headers)}

        def cell(row: list[Any], canonical: str) -> Any:
            source_name = fields.get(canonical)
            index = index_by_name.get(source_name)
            return row[index] if index is not None and index < len(row) else None

        for row in preview['rows']:
            source_rows += 1
            store_id = text_value(cell(row, 'store_id')) or next(iter(store_ids), '未命名门店')
            known_weeks = {week for _, week in summary_records} | {week for _, week, _ in tool_records}
            week_start = text_value(cell(row, 'week_start')) or (next(iter(known_weeks)) if len(known_weeks) == 1 else '未知周期')
            store_ids.add(store_id)
            if len(store_ids) > 1:
                raise InputError('检测到多个门店，请按门店分别运行，避免混合计算。')
            record = summary_records.setdefault((store_id, week_start), {})
            for field in SUMMARY_FIELDS:
                value = parse_number(cell(row, field), rate=field in RATE_FIELDS)
                if value is None:
                    continue
                if field in record and record[field] != value:
                    warnings.append(f'{store_id}／{week_start}／{field} 存在多个值，保留首个。')
                else:
                    record.setdefault(field, value)
            record.setdefault('exported_at', text_value(cell(row, 'exported_at')))
            if grain == 'store_week_tools':
                tool_name = text_value(cell(row, 'tool_name'))
                if not tool_name:
                    warnings.append(f'{key[0]}／{key[1]} 有一行缺少工具名，已跳过。')
                    continue
                tool_key = (store_id, week_start, tool_name)
                tool = tool_records.setdefault(tool_key, {
                    'tool_name': tool_name,
                    'spend': 0.0,
                    'attributed_gmv': 0.0,
                    'roi': None,
                    'attribution_window_days': None,
                    'attribution_definition': None,
                })
                tool['spend'] += parse_number(cell(row, 'spend')) or 0.0
                tool['attributed_gmv'] += parse_number(cell(row, 'attributed_gmv')) or 0.0
                roi = parse_number(cell(row, 'roi'))
                if roi is not None:
                    tool['roi'] = roi
                window = parse_number(cell(row, 'attribution_window_days'))
                if window is not None:
                    tool['attribution_window_days'] = window
                definition = text_value(cell(row, 'attribution_definition'))
                if definition:
                    tool['attribution_definition'] = definition

    if not store_ids:
        raise InputError('没有可生成的门店记录。请检查 AI 映射和原始表格。')
    store_id = next(iter(store_ids))
    week_candidates = {week for _, week in summary_records} | {week for _, week, _ in tool_records}
    if inherited_tool_sheets and len(week_candidates) > 1:
        raise InputError('工具表未提供周期且存在多个周期，请人工确认关联后再运行。')
    week_start = max(week_candidates) if week_candidates else '未知周期'
    summary = summary_records.get((store_id, week_start), {})
    tools = [tool for (store, week, _), tool in tool_records.items() if store == store_id and week == week_start]
    for tool in tools:
        if tool['spend'] > 0 and tool['attributed_gmv'] > 0:
            tool['roi'] = round(tool['attributed_gmv'] / tool['spend'], 4)
        elif tool['spend'] == 0 and tool['attributed_gmv'] > 0:
            warnings.append(f'{tool["tool_name"]} 消耗为 0 但归因 GMV 大于 0，ROI 不计算。')
            tool['roi'] = None
        tool['spend'] = round(tool['spend'], 2)
        tool['attributed_gmv'] = round(tool['attributed_gmv'], 2)
    tools.sort(key=lambda item: item['tool_name'])

    missing = set(mapping_result.get('missing_fields') or [])
    for field in ('orders', 'net_gmv'):
        if summary.get(field) is None:
            missing.add(field)
    if not tools:
        missing.add('tools')
    elif all(tool['roi'] is not None for tool in tools):
        missing.discard('roi')
    return {
        'store_id': store_id,
        'week_start': week_start,
        **{field: summary.get(field) for field in SUMMARY_FIELDS},
        'exported_at': summary.get('exported_at'),
        'tools': tools,
        'missing_fields': sorted(missing),
        'warnings': sorted(set(warnings)),
        'source_rows': source_rows,
    }


def round_number(value: float) -> float:
    rounded = round(value, 2)
    return 0.0 if rounded == 0 else rounded


def tool_roi(tool: dict[str, Any]) -> float | None:
    roi = tool.get('roi')
    if roi is not None:
        return float(roi)
    if tool.get('spend', 0) > 0 and tool.get('attributed_gmv') is not None:
        return tool['attributed_gmv'] / tool['spend']
    return None


def calculate_scenario(report: dict[str, Any], recommendation: dict[str, Any]) -> dict[str, Any]:
    tools = report.get('tools') or []
    if report.get('net_gmv') is None or not tools:
        return {'status': 'blocked', 'warnings': ['缺少门店净 GMV 或工具明细，无法复算。']}
    by_name = {tool['tool_name']: tool for tool in tools}
    mode = recommendation.get('mode', 'reallocate')
    source = by_name.get(recommendation.get('source_tool')) if mode == 'reallocate' else None
    target = by_name.get(recommendation.get('target_tool'))
    amount = parse_number(recommendation.get('amount')) or 0
    if not target or amount <= 0 or (mode == 'reallocate' and not source):
        return {'status': 'blocked', 'warnings': ['建议中的来源／目标工具或金额无效，无法复算。']}
    if mode == 'reallocate' and source['tool_name'] == target['tool_name']:
        return {'status': 'blocked', 'warnings': ['来源与目标工具相同，无法复算。']}
    if mode == 'reallocate' and amount >= source['spend']:
        return {'status': 'blocked', 'warnings': ['调整金额会清空来源工具基本盘，无法复算。']}
    if mode == 'reallocate' and tool_roi(source) is None:
        return {'status': 'blocked', 'warnings': ['来源工具缺少可比较的 ROI。']}
    if tool_roi(target) is None:
        return {'status': 'blocked', 'warnings': ['目标工具缺少可比较的 ROI。']}
    attribution = {(tool.get('attribution_definition'), tool.get('attribution_window_days')) for tool in tools}
    if len(attribution) > 1 or any(definition is None or window is None for definition, window in attribution):
        return {'status': 'blocked', 'warnings': ['工具归因定义或窗口不完整／不一致，不做 ROI 排名或预算复算。']}

    multiplier = 4.3 if recommendation.get('period') == 'month' else 1.0
    margin = parse_number(recommendation.get('gross_margin')) or 0.45
    marginal_factor = parse_number(recommendation.get('marginal_factor')) or 0.8
    subsidy_delta = (parse_number(recommendation.get('merchant_subsidy_delta')) or 0.0) * multiplier
    total_spend = sum(tool['spend'] for tool in tools) * multiplier
    spend_delta = (0 if mode == 'reallocate' else amount) * multiplier
    budget_gmv_delta = amount * (
        tool_roi(target) - tool_roi(source) if mode == 'reallocate' else tool_roi(target)
    ) * marginal_factor * multiplier
    order_loss_gmv = max(0, -subsidy_delta) * 0.4
    delta_gmv = budget_gmv_delta - order_loss_gmv
    current_gmv = report['net_gmv'] * multiplier
    subsidy = (report.get('merchant_subsidy') or 0) * multiplier
    current_profit = current_gmv * margin - subsidy - total_spend
    projected_gmv = current_gmv + delta_gmv
    projected_profit = projected_gmv * margin - (subsidy + subsidy_delta) - (total_spend + spend_delta)
    warnings = [] if projected_profit >= current_profit else ['按当前假设毛利下降，先优化结构，不建议追加。']
    return {
        'status': 'ok',
        'current_gmv': round_number(current_gmv),
        'projected_gmv': round_number(projected_gmv),
        'delta_gmv': round_number(delta_gmv),
        'current_gross_profit': round_number(current_profit),
        'projected_gross_profit': round_number(projected_profit),
        'delta_gross_profit': round_number(projected_profit - current_profit),
        'spend_delta': round_number(spend_delta),
        'budget_contribution': round_number(budget_gmv_delta * margin - spend_delta),
        'subsidy_contribution': round_number(-subsidy_delta),
        'order_loss_contribution': round_number(-order_loss_gmv * margin),
        'warnings': warnings,
    }


def unsupported_claims(data: Any) -> list[str]:
    terms = (
        '系统性', '摧毁', '销毁', '恶性循环', '直接原因', '确证', '足以', '平台排序',
        '首要结构性', '任何菜单', '必然', '保证收益', '根治', '实锤', '连续', '环比',
        '同比', '自然单回补', '疑似按', '复购疲软', '分摊',
    )
    text = json.dumps(data, ensure_ascii=False)
    return [f'包含无数据支撑的表述：{term}' for term in terms if term in text]


def public_diagnosis(public_text: str, client: LlmClient) -> dict[str, Any]:
    if not public_text.strip():
        raise InputError('店铺页公开信息不能为空。')
    prompt = {
        'task': '根据店铺页公开信息做初步经营判断，吸引商家继续提供数据。指出具体问题及业务价值，但不要假装知道内部 ROI、利润或预算结果。禁止夸大、绝对化和平台排序因果，不使用摧毁、系统性、直接原因、确证、恶性循环等措辞。最多 3 个观察，每个都要给下一步核查。数据需求必须说明能回答什么新问题。全篇只保留一处边界说明。',
        'public_text': public_text,
        'output_shape': {
            'headline': '具体、有生意判断的标题',
            'observations': [{'title': '初步判断', 'evidence': '公开证据', 'why_it_matters': '为什么影响生意', 'next_check': '下一步核查'}],
            'data_request': {'summary': '为什么值得提供周报', 'items': ['需要的后台数据及其用途'], 'boundary_note': '一次性边界说明'},
        },
    }
    llm_result = client.complete_json('public_diagnosis', prompt)
    result = llm_result.data
    calls = [usage_metadata(llm_result, 'public_diagnosis')]
    for attempt in range(2):
        violations = unsupported_claims(result)
        if not violations:
            break
        repair_stage = 'public_diagnosis_repair' if attempt == 0 else 'public_diagnosis_repair_2'
        repair = client.complete_json(repair_stage, {
            **prompt,
            'validation_errors': violations,
            'invalid_output': result,
            'repair_instruction': '保留可验证的公开证据，删除夸大、绝对化、平台排序和无依据因果。改成具体、可信、有行动价值的表达，不要换成另一种夸张说法。',
        })
        result = repair.data
        calls.append(usage_metadata(repair, repair_stage))
    else:
        raise InputError(f'公开初诊两次重改后仍未通过：{"；".join(unsupported_claims(result))}')
    result['_llm_calls'] = calls
    observations = result.get('observations') or []
    if not isinstance(observations, list):
        raise InputError('公开初诊 observations 格式错误。')
    result['observations'] = observations[:3]
    result.setdefault('data_request', {'summary': '', 'items': [], 'boundary_note': '公开信息先用于确定核查方向。'})
    return result


def render_public_markdown(data: dict[str, Any]) -> str:
    lines = [f'# {data["headline"]}', '', '## 初步判断', '']
    for index, item in enumerate(data['observations'], start=1):
        lines.extend([
            f'### {index}. {item["title"]}',
            f'- 公开证据：{item["evidence"]}',
            f'- 为什么重要：{item["why_it_matters"]}',
            f'- 下一步：{item["next_check"]}',
            '',
        ])
    request = data['data_request']
    lines.extend(['## 拿到这些数据，就能继续算清楚', '', request.get('summary', ''), ''])
    for item in request.get('items') or []:
        lines.append(f'- {item}')
    lines.extend(['', request.get('boundary_note', '公开信息先用于确定核查方向。'), ''])
    return '\n'.join(lines)


def render_full_markdown(data: dict[str, Any]) -> str:
    lines = [f'# {data["headline"]}', '', '## 钱漏在哪', '']
    for index, issue in enumerate(data.get('issues') or [], start=1):
        lines.extend([f'### {index}. {issue["title"]}', f'- 证据：{issue["evidence"]}', f'- 影响：{issue["why_it_matters"]}', ''])
    recommendation = data.get('recommendation') or {}
    if recommendation:
        if recommendation.get('mode') == 'add':
            action = f'向{recommendation.get("target_tool")}追加 {recommendation.get("amount")} 元'
        else:
            action = f'从{recommendation.get("source_tool")}向{recommendation.get("target_tool")}挪移 {recommendation.get("amount")} 元'
        lines.extend(['## 建议动作', '', action, ''])
    calculation = data.get('calculation') or {}
    lines.extend(['## 调整前后复算', ''])
    if calculation.get('status') == 'ok':
        lines.extend([
            f'- 净 GMV：{calculation["current_gmv"]} → {calculation["projected_gmv"]}（变化 {calculation["delta_gmv"]}）',
            f'- 经营毛利：{calculation["current_gross_profit"]} → {calculation["projected_gross_profit"]}（变化 {calculation["delta_gross_profit"]}）',
            f'- 消耗变化：{calculation["spend_delta"]}',
            f'- 预算贡献：{calculation["budget_contribution"]}；补贴贡献：{calculation["subsidy_contribution"]}；订单流失贡献：{calculation["order_loss_contribution"]}',
            '',
        ])
    for warning in calculation.get('warnings') or data.get('warnings') or []:
        lines.append(f'- 注意：{warning}')
    lines.extend(['', '## 给店里的三句话', ''])
    for index, track in enumerate(data.get('client_talk_tracks') or [], start=1):
        lines.append(f'{index}. {track}')
    lines.extend(['', '## 下周跟进', '', '| 动作 | 负责人 | 复核指标 | 日期 | 停止条件 |', '| --- | --- | --- | --- | --- |'])
    for item in data.get('follow_ups') or []:
        lines.append(f'| {item["action"]} | {item["owner"]} | {item["metric"]} | {item["review_date"]} | {item["stop_condition"]} |')
    lines.extend(['', data.get('boundary_note', '测算用于比较方案，不替代实际复盘。'), ''])
    return '\n'.join(lines)


def usage_metadata(result: LlmResult, stage: str) -> dict[str, Any]:
    return {'stage': stage, 'provider': getattr(result, 'provider', 'moonshot'), 'model': getattr(result, 'model', 'unknown'), 'usage': getattr(result, 'usage', {})}


def full_plan_violations(data: dict[str, Any]) -> list[str]:
    """Reject unsupported time-series and attribution claims before customer delivery."""
    return unsupported_claims({
        'headline': data.get('headline'),
        'issues': data.get('issues'),
        'client_talk_tracks': data.get('client_talk_tracks'),
        'boundary_note': data.get('boundary_note'),
    })


def normalize_follow_ups(data: dict[str, Any], week_start: str) -> None:
    follow_ups = (data.get('follow_ups') or [])[:3]
    try:
        review_date = (datetime.fromisoformat(week_start) + timedelta(days=7)).date().isoformat()
    except ValueError:
        review_date = ''
    for item in follow_ups:
        if review_date:
            item['review_date'] = review_date
    data['follow_ups'] = follow_ups


def run_pipeline(public_text: str, file_paths: list[Path], client: LlmClient, out_dir: Path) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    public = public_diagnosis(public_text, client)
    calls.extend(public.pop('_llm_calls'))
    result: dict[str, Any] = {'public': public}
    if file_paths:
        previews = []
        for path in file_paths:
            previews.extend(read_table_file(path))
        mapping = map_tables(previews, client)
        calls.append(mapping.pop('_llm'))
        canonical = apply_mappings(previews, mapping)
        full_payload = {
            'task': '结合公开初诊和真实周报给出可执行经营方案。最多 3 个问题、3 项跟进；建议必须引用真实工具名。只有当前周数据时禁止说连续、环比、同比或历史趋势；不得猜测归因分摊、自然单回补或复购疲软。只给结构化建议，计算由程序复算。话术面向客户，避免重复免责声明。',
            'public_diagnosis': public,
            'canonical_report': canonical,
            'mapping_preview': mapping,
            'output_shape': {
                'headline': '方案标题',
                'issues': [{'title': '问题', 'evidence': '数据证据', 'why_it_matters': '业务影响'}],
                'recommendation': {'mode': 'reallocate 或 add', 'source_tool': '来源工具或 null', 'target_tool': '目标工具', 'amount': 400, 'gross_margin': 0.45, 'marginal_factor': 0.8, 'merchant_subsidy_delta': 0, 'period': 'week 或 month'},
                'client_talk_tracks': ['三句话'],
                'follow_ups': [{'action': '动作', 'owner': '负责人', 'metric': '复核指标', 'review_date': '日期', 'stop_condition': '停止条件'}],
                'boundary_note': '全篇唯一边界说明',
            },
        }
        full = client.complete_json('full_diagnosis', full_payload)
        calls.append(usage_metadata(full, 'full_diagnosis'))
        for attempt in range(2):
            violations = full_plan_violations(full.data)
            if not violations:
                break
            repair_stage = 'full_diagnosis_repair' if attempt == 0 else 'full_diagnosis_repair_2'
            repair = client.complete_json(repair_stage, {
                **full_payload,
                'validation_errors': violations,
                'invalid_output': full.data,
                'repair_instruction': '删除或改写所有无数据支撑的趋势、归因猜测和因果断言。只保留输入能证明的事实与明确标注的当前周判断，不得换一套类似措辞继续猜测。',
            })
            calls.append(usage_metadata(repair, repair_stage))
            full = repair
        else:
            raise InputError(f'完整方案两次重改后仍未通过：{"；".join(full_plan_violations(full.data))}')
        full_data = full.data
        normalize_follow_ups(full_data, canonical['week_start'])
        full_data['calculation'] = calculate_scenario(canonical, full_data.get('recommendation') or {})
        mapping_preview = {**mapping, 'canonical_warnings': canonical['warnings']}
        result.update({'mapping_preview': mapping_preview, 'canonical_report': canonical, 'full': full_data})

    if out_dir.exists() and any(out_dir.iterdir()):
        raise InputError('输出目录已包含文件，请更换目录，避免覆盖已有结果。')
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'public-diagnosis.md').write_text(render_public_markdown(public), encoding='utf-8')
    (out_dir / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    if file_paths:
        (out_dir / 'mapping-preview.json').write_text(json.dumps(result['mapping_preview'], ensure_ascii=False, indent=2), encoding='utf-8')
        (out_dir / 'full-diagnosis.md').write_text(render_full_markdown(result['full']), encoding='utf-8')
    total_tokens = sum(call['usage'].get('total_tokens', 0) for call in calls)
    metadata = {
        'actual_ai_calls': len(calls),
        'calls': calls,
        'token_usage': {'total_tokens': total_tokens},
        'input_files': [str(path) for path in file_paths],
        'mapping_missing': result.get('canonical_report', {}).get('missing_fields', []),
        'warnings': result.get('canonical_report', {}).get('warnings', []),
    }
    (out_dir / 'run-metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    return result
