"""Local structural checks; a passing result does not establish business truth."""
import argparse
import json
from pathlib import Path
import re
import sys

REFERENCES = Path(__file__).resolve().parents[1] / "references"
STAGES = ("S1", "S2", "S3", "S4", "S5")
IDS = re.compile(r"(?<![A-Za-z0-9])([FAD][1-9]\d*)(?!\d)")
FILES = re.compile(r"([^\s／/|`、,;，。；：:（）()\[\]<>]+\.(?:csv|tsv|txt|md|json|html?|xlsx|pdf|png|jpe?g))", re.I)
LOCATORS = re.compile(r"html:\d+\(line:\d+\)|(?:ocr:line|row|line|page):\d+(?:-\d+)?|sheet:[^\n|／]+?![A-Z]+\d+(?:[:-][A-Z]+\d+)?(?![A-Za-z0-9])")


def business_ids(text):
    # Spreadsheet coordinates use the same letters as F/A/D business identifiers.
    plain = LOCATORS.sub("", text)
    # A channel followed by a currency amount (A27万元) is not action A27.
    return [m.group(1) for m in IDS.finditer(plain)
            if not re.match(r'(?:,\d{3})*(?:\.\d+)?(?:亿|万)?元', plain[m.end():])]


def file_mentions(text, sources):
    """Prefer exact material names, then retain unknown names for rejection."""
    matches = []
    masked = list(text)
    if sources:
        names = "|".join(re.escape(name) for name in sorted(sources, key=len, reverse=True))
        for match in re.finditer(r"(?<![A-Za-z0-9_.-])(?:" + names + r")(?![A-Za-z0-9_.-])", text):
            matches.append((match.group(), match.start(), match.end()))
            masked[match.start():match.end()] = " " * (match.end() - match.start())
    for match in FILES.finditer("".join(masked)):
        matches.append((match.group(1), match.start(), match.end()))
    return sorted(matches, key=lambda item: item[1])


def stage_template(stage):
    text = (REFERENCES / "output-template.md").read_text(encoding="utf-8")
    if stage == "failure":
        return re.findall(r"```markdown\n(.*?)```", text, re.S)[-1].strip()
    if stage not in STAGES:
        raise ValueError("阶段必须为 S1–S5")
    found = re.search(r"### " + stage + r"：.*?```markdown\n(.*?)```", text, re.S)
    if not found:
        raise ValueError("输出模板缺少 " + stage)
    return found.group(1).strip()


def sections(text):
    matches = list(re.finditer(r"^## (.+)$", text, re.M))
    return [(m.group(1).strip(), text[m.end():matches[i + 1].start() if i + 1 < len(matches) else len(text)].strip())
            for i, m in enumerate(matches)]


def tables(body):
    groups, current = [], []
    for line in body.splitlines() + [""]:
        if line.strip().startswith("|"):
            current.append([v.strip().replace(r"\|", "|") for v in re.split(r"(?<!\\)\|", line.strip().strip("|"))])
        elif current:
            groups.append(current)
            current = []
    return groups


def definitions(text):
    result = set()
    for name, body in sections(text):
        for table in tables(body):
            if not table:
                continue
            header = table[0]
            defines = header[0] in ("缺口编号", "编号", "问题编号") or name == "现在／建议"
            if defines:
                for row in table[2:]:
                    if row:
                        result.update(business_ids(row[0]))
            if name == "下周跟进":
                for row in table[2:]:
                    if row and len(row[-1].strip()) > 3:
                        result.update(i for i in business_ids(row[-1]) if i.startswith("D"))
    return result


def valid_location(filename, cell, material, sources=None):
    """Check exact point references and both endpoints of a cited range."""
    matches = file_mentions(cell, sources or {filename: material})
    known = {item["locator"] for item in material["fragments"]}
    found_citation = False
    for index, (name, start, end) in enumerate(matches):
        if name != filename:
            continue
        part = cell[end:matches[index + 1][1] if index + 1 < len(matches) else len(cell)]
        citations = LOCATORS.findall(part)
        if not citations:
            # A prose mention may precede the actual citation in the same cell.
            # An explicit citation marker without a locator is still invalid.
            if re.match(r"\s*[／/]", part):
                return False
            continue
        found_citation = True
        for locator in citations:
            if locator in known:
                continue
            interval = re.fullmatch(r"((?:ocr:line|row|line|page):)(\d+)-(\d+)", locator)
            cells = re.fullmatch(r"(sheet:.+!)([A-Z]+\d+)[:-]([A-Z]+\d+)", locator)
            if interval:
                prefix, start, end = interval.groups()
                if int(start) <= int(end) and prefix + start in known and prefix + end in known:
                    continue
            elif cells:
                prefix, start, end = cells.groups()
                if prefix + start in known and prefix + end in known:
                    continue
            return False
    return found_citation


def validate_report(stage, text, materials, history=None):
    """Return errors for explicit protocol rules, not semantic/financial approval.

    Locator ranges require both endpoints; this does not prove every intervening
    row exists or that its business content supports the claim.
    """
    if stage not in STAGES:
        return ["阶段必须为 S1–S5"]
    errors = []
    failure = text.lstrip().startswith("# 本次分析未完成")
    template = stage_template("failure" if failure else stage)
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    expected_title = template.splitlines()[0]
    if not lines or lines[0] != expected_title or len(re.findall(r"^# ", text, re.M)) != 1:
        errors.append("报告标题或开头不符合模板")
    for index, label in enumerate(("门店：", "数据范围：", "状态："), 1):
        if len(lines) <= index or not lines[index].startswith(label) or not lines[index][len(label):].strip():
            errors.append("公共字段缺失、为空或顺序错误：" + label)
    status = next((line.split("：", 1)[1] for line in lines if line.startswith("状态：")), "")
    allowed_status = ("执行失败",) if failure else ("可交付", "待补数")
    if status not in allowed_status:
        errors.append("状态取值不合法")
    if re.search(r"\{\{|\}\}|```|~~~", text):
        errors.append("报告含占位符或代码围栏")
    if re.search(r"(?:^|\s|[|（(])(?:/(?:Users|home|tmp|private)/|[A-Za-z]:[\\/])", text):
        errors.append("证据不得包含本地绝对路径")
    expected, actual = sections(template), sections(text)
    if [name for name, _ in actual] != [name for name, _ in expected] or re.search(r"^#{3,} ", text, re.M):
        errors.append("二级标题名称或顺序不符合模板")
    material_list = materials.get("materials", []) if isinstance(materials, dict) else materials
    sources = {item["name"]: item for item in material_list}
    if history is None and isinstance(materials, dict):
        history = materials.get("history", [])
    historical = "\n".join(item.get("text", "") if isinstance(item, dict) else item for item in (history or []))
    defined = definitions(text) | definitions(historical)
    for ref in sorted(set(business_ids(text)) - defined):
        errors.append("编号没有定义：" + ref)
    if re.search(r"(?<![A-Za-z0-9])[FAD]0\b", LOCATORS.sub("", text)):
        errors.append("编号须从 1 开始")
    if not failure and re.search(r"待补充(?![（(]D[1-9]\d*[）)])", text):
        errors.append("待补充必须带已定义的 D 编号")
    found_tables = {}
    for name, expected_body in expected:
        bodies = [body for section, body in actual if section == name]
        if len(bodies) != 1:
            continue
        body = bodies[0]
        if not body:
            errors.append(name + "：内容不能为空")
        expected_tables, actual_tables = tables(expected_body), tables(body)
        if len(actual_tables) != len(expected_tables):
            errors.append(name + "：表格数量不符合模板")
        for want, got in zip(expected_tables, actual_tables):
            if not got or got[0] != want[0]:
                errors.append(name + "：表头名称或顺序不符合模板")
                continue
            header = got[0]
            rows = got[2:]
            found_tables[name] = rows
            if len(got) < 2 or len(got[1]) != len(header) or any(not re.fullmatch(r":?-+:?", c) for c in got[1]):
                errors.append(name + "：表格分隔行不合法")
            if not rows:
                errors.append(name + "：至少保留一行，无条目请使用无／不适用")
            if name in ("发现与依据", "优先问题", "问题与证据", "现在／建议", "预期改善", "下周跟进") and len(rows) > 3:
                errors.append(name + "：最多三项")
            seen = set()
            for row in rows:
                if len(row) != len(header) or any(not cell for cell in row):
                    errors.append(name + "：列数错误或必填单元格为空")
                    continue
                if row[0] == "无":
                    if any(not cell.startswith("不适用") for cell in row[1:]):
                        errors.append(name + "：无条目行其余列须写不适用")
                    continue
                if header[0] in ("编号", "问题编号", "动作编号", "缺口编号"):
                    prefix = "D" if header[0] == "缺口编号" else "A" if header[0] == "动作编号" else "F"
                    if not re.fullmatch(prefix + r"[1-9]\d*", row[0]) or row[0] in seen:
                        errors.append(name + "：编号类型错误或重复：" + row[0])
                    seen.add(row[0])
                for label, cell in zip(header, row):
                    options = {"优先级": ("必须", "可选") if stage == "S2" else ("高", "中", "低"),
                               "结果": ("通过", "待确认", "不适用"), "判断状态": ("事实判断", "原因假设", "待补数据"),
                               "处理": ("保留", "调整", "撤回")}
                    if label in options and cell not in options[label]:
                        errors.append(name + "（" + row[0] + "）：" + label + "取值不合法；允许：" + '／'.join(options[label]))
                    if label == "关联问题" and not any(i.startswith("F") for i in business_ids(cell)):
                        errors.append(name + "：必须关联 F 编号")
                    if label in ("证据", "定义与来源", "证据或缺口", "新依据", "基线与来源"):
                        cited = [item[0] for item in file_mentions(cell, sources)]
                        exempt = cell.startswith("不适用：") or any(i.startswith("D") or i in definitions(historical) for i in business_ids(cell))
                        if not cited and not exempt:
                            errors.append(name + "（" + row[0] + "）：来源须含材料名与定位，或已定义的编号")
                        for filename in cited:
                            if filename not in sources:
                                errors.append("引用不存在的材料：" + filename)
                            elif not valid_location(filename, cell, sources[filename], sources):
                                errors.append(name + "（" + row[0] + "）：来源定位无法回查：" + filename)
    for filename, start, end in file_mentions(text, sources):
        if filename not in sources and re.match(r"\s*[／/]", text[end:]):
            errors.append("引用不存在的材料：" + filename)
    if stage == "S5" and not failure:
        rows_by_action = [{row[0] for row in found_tables.get(name, []) if row and row[0] != "无"}
                          for name in ("现在／建议", "预期改善", "下周跟进")]
        if not rows_by_action[0] == rows_by_action[1] == rows_by_action[2]:
            errors.append("S5 三张行动表必须使用相同的 A 编号")
        speech = next((body for name, body in actual if name == "给老板的三句话"), "")
        speech_lines = [line.strip() for line in speech.splitlines() if line.strip()]
        if len(speech_lines) != 3 or any(not re.match(str(i) + r"\.\s+\S", line) for i, line in enumerate(speech_lines, 1)):
            errors.append("给老板的三句话必须恰好为 1、2、3 三条非空话术")
    return list(dict.fromkeys(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--materials", type=Path, required=True)
    parser.add_argument("--history", type=Path, nargs="*", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = args.report.read_text(encoding="utf-8")
        materials = json.loads(args.materials.read_text(encoding="utf-8"))
        history = [p.read_text(encoding="utf-8") for p in args.history] or materials.get("history", [])
        errors = validate_report(args.stage, report, materials, history)
        result = {"stage": args.stage, "valid": not errors, "errors": errors,
                  "scope": "结构、编号与来源定位；未自动验证业务语义、全部数值或执行效果"}
        output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(output)
        print(output, end="")
        return 1 if errors else 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("验收失败：" + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
