"""Check decision-record structure and traceability, not business truth."""
import argparse
import json
import math
from pathlib import Path
import sys

from validate import business_ids, definitions, sections, tables, valid_location


def validate_decisions(record, materials, diagnosis, action_plan=None):
    errors = []
    if not isinstance(record, dict):
        return ['决策记录必须是对象']

    def text(value, label):
        if not isinstance(value, str) or not value.strip():
            errors.append(label + '必须为非空文字')
            return False
        return True

    def objects(value, label, allow_empty=False):
        if not isinstance(value, list) or (not value and not allow_empty) or any(not isinstance(x, dict) for x in value):
            errors.append(label + '必须为对象列表' + ('（可为空）' if allow_empty else '（非空）'))
            return []
        return value

    def ids(value, label, allow_empty=False):
        if not isinstance(value, list) or (not value and not allow_empty) or any(not isinstance(x, str) or not x.strip() for x in value):
            errors.append(label + '必须为非空字符串列表')
            return []
        if len(value) != len(set(value)):
            errors.append(label + '存在重复')
        return value

    sources = {m['name']: m for m in materials.get('materials', [])}

    def evidence(value, label, allow_empty=False):
        for item in objects(value, label, allow_empty):
            filename, locator = item.get('material'), item.get('locator')
            if not isinstance(filename, str) or filename not in sources:
                errors.append(label + '引用未知材料')
            elif not isinstance(locator, str) or not locator.strip() or not valid_location(filename, filename + '／' + locator, sources[filename]):
                errors.append(label + '引用无效位置')

    if record.get('version') != '1.0':
        errors.append('决策记录版本必须为1.0')
    text(record.get('goal'), 'goal')
    scope = ids(record.get('scope'), 'scope')
    for baseline in objects(record.get('baseline'), 'baseline'):
        for key in ('metric', 'unit', 'period'):
            text(baseline.get(key), 'baseline.' + key)
        status, value = baseline.get('status'), baseline.get('value')
        if status == 'known':
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                errors.append('已知基线必须为有限数值')
        elif status == 'unknown':
            if value is not None:
                errors.append('未知基线必须为null，不能写0')
            text(baseline.get('reason'), '未知基线reason')
        else:
            errors.append('baseline.status必须为known或unknown')
        evidence(baseline.get('evidence'), 'baseline.evidence')

    segment_ids, members = [], []
    for segment in objects(record.get('segments'), 'segments'):
        if text(segment.get('id'), 'segment.id'):
            segment_ids.append(segment['id'])
        members.extend(ids(segment.get('members'), 'segment.members'))
        text(segment.get('basis'), 'segment.basis')
    if len(segment_ids) != len(set(segment_ids)):
        errors.append('segment.id重复')
    if len(members) != len(set(members)) or set(members) != set(scope):
        errors.append('门店分组须无重复且完整覆盖scope')

    findings = {x for x in definitions(diagnosis) if x.startswith('F')}
    actions = {x for x in definitions(action_plan or '') if x.startswith('A')}
    action_findings = {}
    for name, body in sections(action_plan or ''):
        if name == '现在／建议':
            for table in tables(body):
                for row in table[2:]:
                    if len(row) > 1:
                        for aid in business_ids(row[0]):
                            action_findings[aid] = business_ids(row[1])
    linked_findings, linked_actions = [], []
    priorities = objects(record.get('priorities'), 'priorities')
    if len(priorities) > 3:
        errors.append('优先问题最多3项')
    for priority in priorities:
        fid = priority.get('finding_id')
        if not isinstance(fid, str) or fid not in findings:
            errors.append('priority引用未知F编号')
        else:
            linked_findings.append(fid)
        group_ids = ids(priority.get('segment_ids'), 'priority.segment_ids')
        if not set(group_ids).issubset(segment_ids):
            errors.append('priority引用未知分组')
        text(priority.get('why_now'), 'priority.why_now')
        evidence(priority.get('evidence'), 'priority.evidence')
        options = objects(priority.get('options'), 'priority.options')
        if len(options) < 2:
            errors.append('每个优先问题至少比较2个策略方向')
        selected, strategies = 0, []
        for option in options:
            if text(option.get('strategy'), 'option.strategy'):
                strategies.append(option['strategy'].strip())
            text(option.get('reason'), 'option.reason')
            if option.get('status') not in ('selected', 'deferred', 'rejected'):
                errors.append('option.status不合法')
            selected += option.get('status') == 'selected'
        if selected != 1 or len(strategies) != len(set(strategies)):
            errors.append('每个问题须唯一选中一个策略，策略名称不能重复')
        aids = ids(priority.get('action_ids'), 'priority.action_ids', allow_empty=action_plan is None)
        linked_actions.extend(aids)
        if action_plan is not None and not set(aids).issubset(actions):
            errors.append('priority引用未知A编号')
        if action_plan is not None and any(fid not in action_findings.get(aid, set()) for aid in aids):
            errors.append('决策记录与S5动作关联的问题不一致')
    if set(linked_findings) != findings or len(linked_findings) != len(set(linked_findings)):
        errors.append('S4问题须完整且唯一映射到决策记录')
    if action_plan is not None and set(linked_actions) != actions:
        errors.append('S5动作须全部关联已选策略')
    execution = record.get('execution')
    if not isinstance(execution, dict):
        errors.append('execution必须为对象')
    else:
        status = execution.get('status')
        if status not in ('unknown', 'not_executed', 'partial', 'executed'):
            errors.append('execution.status不合法')
        evidence(execution.get('evidence'), 'execution.evidence', allow_empty=status == 'unknown')
        text(execution.get('review'), 'execution.review')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('record', 'materials', 'diagnosis', 'output'):
        parser.add_argument('--' + flag, type=Path, required=True)
    parser.add_argument('--plan', type=Path)
    args = parser.parse_args()
    try:
        errors = validate_decisions(json.loads(args.record.read_text()), json.loads(args.materials.read_text()),
                                    args.diagnosis.read_text(), args.plan.read_text() if args.plan else None)
        result = {'passed': not errors, 'errors': errors,
                  'scope': '结构与引用检查；不证明原因、分组或收益成立'}
        with args.output.open('x', encoding='utf-8') as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        return 1 if errors else 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print('检查失败：' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
