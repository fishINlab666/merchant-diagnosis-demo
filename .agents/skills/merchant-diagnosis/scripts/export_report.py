"""Export existing merchant analysis as a portable HTML report, without inference."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile

from validate import STAGES, stage_template, tables

ASSETS = Path(__file__).resolve().parents[1] / "assets"
EXPORT_KIND = "merchant-diagnosis-report-export"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    def reject_constant(value):
        raise ValueError("JSON 不允许非有限数值：" + value)
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), parse_constant=reject_constant)


def text(value, label, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(label + "必须为文字" + ("" if allow_empty else "，且不能为空"))
    return value


def identifier(value, label):
    value = text(value, label)
    if not re.fullmatch(r"[\w.-]+", value) or value in (".", ".."):
        raise ValueError(label + "只能包含字母、数字、下划线、点和连字符")
    return value


def boolean(value, label):
    if not isinstance(value, bool):
        raise ValueError(label + "必须为布尔值")
    return value


def objects(value, label, allow_empty=False):
    if not isinstance(value, list) or (not value and not allow_empty) or any(not isinstance(v, dict) for v in value):
        raise ValueError(label + "必须为对象列表")
    return value


def finite_or_unknown(value, label):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(label + "必须为有限数值或 null；未知值不能填零")
    return value


def parse_blocks(lines):
    """Preserve ordered paragraphs around tables, including financial assumptions."""
    blocks, index = [], 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        heading = re.match(r"^#{2,6}\s+(.+)$", line)
        if heading:
            blocks.append({"type": "heading", "text": heading.group(1).strip()})
            index += 1
        elif line.strip().startswith("|"):
            group = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                group.append(lines[index])
                index += 1
            parsed = tables("\n".join(group))[0]
            if len(parsed) < 2 or any(not re.fullmatch(r":?-+:?", c) for c in parsed[1]):
                raise ValueError("报告表格缺少有效表头分隔行")
            if any(len(row) != len(parsed[0]) for row in parsed[1:]):
                raise ValueError("报告表格列数不一致")
            blocks.append({"type": "table", "headers": parsed[0], "rows": parsed[2:]})
        elif re.match(r"^\s*(?:\d+[.)]|[-*+])\s+", line):
            items = []
            while index < len(lines):
                item = re.match(r"^\s*(?:\d+[.)]|[-*+])\s+(.+)$", lines[index])
                if not item:
                    break
                items.append(item.group(1))
                index += 1
            blocks.append({"type": "list", "items": items})
        else:
            paragraph = []
            while index < len(lines) and lines[index].strip():
                if paragraph and (re.match(r"^#{2,6}\s+|^\s*(?:\d+[.)]|[-*+])\s+", lines[index])
                                  or lines[index].strip().startswith("|")):
                    break
                paragraph.append(lines[index])
                index += 1
            blocks.append({"type": "paragraph", "text": "\n".join(paragraph)})
    return blocks


def parse_stage(stage, raw):
    markdown = raw.decode("utf-8-sig")
    lines = markdown.splitlines()
    nonblank = [(index, line.strip()) for index, line in enumerate(lines) if line.strip()]
    expected = stage_template(stage).splitlines()[0]
    if len(nonblank) < 4 or nonblank[0][1] not in (expected, "# 本次分析未完成"):
        raise ValueError(stage + " 报告标题或公共字段缺失")
    metadata = {}
    for (key, label), (_, line) in zip((("merchant", "门店："), ("scope", "数据范围："), ("status", "状态：")), nonblank[1:4]):
        if not line.startswith(label) or not line[len(label):].strip():
            raise ValueError(stage + " 报告公共字段缺失：" + label)
        metadata[key] = line[len(label):].strip()
    if metadata["status"] not in ("可交付", "待补数", "执行失败"):
        raise ValueError(stage + " 报告状态不合法")
    blocks = parse_blocks(lines[nonblank[3][0] + 1:])
    if not blocks:
        raise ValueError(stage + " 报告没有正文")
    return {"stage": stage, "title": nonblank[0][1][2:], "metadata": metadata,
            "blocks": blocks, "markdown": markdown, "sha256": digest(raw)}


def validate_visuals(value):
    if not isinstance(value, dict):
        raise ValueError("visuals 必须为对象")
    result = {"highlights": [], "charts": []}
    for item in objects(value.get("highlights", []), "highlights", allow_empty=True):
        result["highlights"].append({
            "label": text(item.get("label"), "highlight.label"),
            "value": finite_or_unknown(item.get("value"), "highlight.value"),
            "unit": text(item.get("unit"), "highlight.unit"),
            "note": text(item.get("note", ""), "highlight.note", allow_empty=True),
            "evidence": text(item.get("evidence"), "highlight.evidence")})
    seen = set()
    for item in objects(value.get("charts", []), "charts", allow_empty=True):
        chart_id = identifier(item.get("id"), "chart.id")
        if chart_id in seen:
            raise ValueError("chart.id 重复")
        seen.add(chart_id)
        if item.get("type") not in ("bars", "stacked", "waterfall"):
            raise ValueError("chart.type 必须为 bars、stacked 或 waterfall")
        chart = {"id": chart_id, "type": item["type"],
                 "title": text(item.get("title"), "chart.title"),
                 "unit": text(item.get("unit"), "chart.unit"),
                 "caption": text(item.get("caption", ""), "chart.caption", allow_empty=True),
                 "series": [], "evidence": text(item.get("evidence"), "chart.evidence")}
        for point in objects(item.get("series"), "chart.series"):
            record = {"label": text(point.get("label"), "series.label"),
                      "value": finite_or_unknown(point.get("value"), "series.value")}
            for key in ("group", "role"):
                if key in point:
                    record[key] = text(point[key], "series." + key)
            chart["series"].append(record)
        result["charts"].append(chart)
    return result


def read_version(config_dir, case_id, spec, inputs):
    version_id = identifier(spec.get("id"), "version.id")
    logical = case_id + "/" + version_id
    run_dir = config_dir / text(spec.get("run_dir"), "version.run_dir")
    if not run_dir.is_dir():
        raise ValueError(logical + " 的运行目录不存在")
    stages, sources, source_keys = [], [], set()
    for stage in STAGES:
        report = run_dir / stage / "report.md"
        if not report.exists():
            continue
        raw = report.read_bytes()
        stages.append(parse_stage(stage, raw))
        inputs.append({"source": logical + "/" + stage + "/report.md", "sha256": digest(raw)})
        material_path = report.parent / "materials.json"
        if material_path.exists():
            material_bundle = read_json(material_path)
            if not isinstance(material_bundle, dict):
                raise ValueError("materials.json 必须为对象")
            for source in objects(material_bundle.get("materials", []), "materials", allow_empty=True):
                name = text(source.get("name"), "source.name")
                sha = text(source.get("sha256"), "source.sha256")
                if "/" in name or "\\" in name or not re.fullmatch(r"[0-9a-fA-F]{64}", sha):
                    raise ValueError("材料来源必须为文件名及有效 SHA-256，不得包含私有路径")
                if (name, sha) not in source_keys:
                    source_keys.add((name, sha))
                    sources.append({"name": name, "sha256": sha})
            inputs.append({"source": logical + "/" + stage + "/materials.json",
                           "sha256": digest(material_path.read_bytes())})
    if not stages:
        raise ValueError(logical + " 没有实际阶段 report.md")
    execution = {}
    for candidate, source in ((run_dir / "execution.json", "execution.json"),
                              (run_dir / "S5" / "execution.json", "S5/execution.json")):
        if candidate.exists():
            execution = read_json(candidate)
            if not isinstance(execution, dict):
                raise ValueError("execution.json 必须为对象")
            inputs.append({"source": logical + "/" + source, "sha256": digest(candidate.read_bytes())})
            break
    latest = stages[-1]
    summary, takeaways, section = "", [], ""
    for block in latest["blocks"]:
        if block["type"] == "heading":
            section = block["text"]
        elif block["type"] == "paragraph" and (section == "一句话结论" or not summary):
            summary = block["text"]
        elif block["type"] == "list" and section == "给老板的三句话":
            takeaways.extend(block["items"])
    visuals = {"highlights": [], "charts": []}
    if spec.get("view_file") is not None:
        view_path = config_dir / text(spec["view_file"], "version.view_file")
        visuals = validate_visuals(read_json(view_path))
        inputs.append({"source": logical + "/visuals.json", "sha256": digest(view_path.read_bytes())})
    return {"id": version_id, "label": text(spec.get("label", version_id), "version.label"),
            "superseded": boolean(spec.get("superseded", False), "version.superseded"),
            **latest["metadata"], "executor": text(execution.get("executor", "未记录"), "executor"),
            "model_id": text(execution.get("model_id", "未记录"), "model_id"),
            "summary": summary, "takeaways": takeaways, "stages": stages,
            "visuals": visuals, "sources": sources}


def build_report(config_path):
    config_path = Path(config_path)
    config = read_json(config_path)
    if not isinstance(config, dict):
        raise ValueError("config 必须为对象")
    inputs = [{"source": "catalog.json", "sha256": digest(config_path.read_bytes())}]
    result = {"schema_version": "1.0", "title": text(config.get("title", "商户经营诊断"), "title"), "cases": []}
    case_ids = set()
    for case in objects(config.get("cases"), "cases"):
        case_id = identifier(case.get("id"), "case.id")
        if case_id in case_ids:
            raise ValueError("case.id 重复")
        case_ids.add(case_id)
        versions, version_ids = [], set()
        for spec in objects(case.get("versions"), "versions"):
            version = read_version(config_path.parent, case_id, spec, inputs)
            if version["id"] in version_ids:
                raise ValueError("version.id 重复")
            version_ids.add(version["id"])
            versions.append(version)
        active = identifier(case.get("active_version", versions[-1]["id"]), "case.active_version")
        if active not in version_ids:
            raise ValueError("active_version 不存在")
        result["cases"].append({"id": case_id, "title": text(case.get("title"), "case.title"),
                                "label": text(case.get("label", case["title"]), "case.label"),
                                "synthetic": boolean(case.get("synthetic", False), "case.synthetic"),
                                "active_version": active, "versions": versions})
    return result, inputs


def safe_inline_json(value):
    serialized = json.dumps(value, ensure_ascii=False, allow_nan=False)
    for char, replacement in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"),
                              ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        serialized = serialized.replace(char, replacement)
    return serialized


def check_existing(paths, force):
    if not any(path.exists() for path in paths):
        return
    if not force:
        raise ValueError("输出已存在；请使用新路径，或显式 --force 覆盖未改动的本工具导出")
    if not all(path.is_file() for path in paths):
        raise ValueError("--force 只能覆盖完整的本工具导出")
    manifest = read_json(paths[-1])
    expected_names = {path.name for path in paths[:-1]}
    if not isinstance(manifest, dict) or manifest.get("export_kind") != EXPORT_KIND or set(manifest.get("outputs", {})) != expected_names:
        raise ValueError("不能覆盖不属于本工具的文件")
    if any(manifest["outputs"][path.name] != digest(path.read_bytes()) for path in paths[:-1]):
        raise ValueError("已有导出被外部修改；请使用新路径，保留修改内容")


def export_report(config_path, output_path, force=False, assets_dir=None):
    """Validate and prepare every byte before replacing any output artifact."""
    output_path = Path(output_path)
    if output_path.suffix.lower() != ".html":
        raise ValueError("输出文件扩展名必须为 .html")
    paths = (output_path, output_path.with_suffix(".json"), output_path.with_suffix(".manifest.json"))
    check_existing(paths, force)
    data, inputs = build_report(config_path)
    assets = Path(assets_dir) if assets_dir is not None else ASSETS
    template = (assets / "report.html").read_text(encoding="utf-8")
    replacements = {"__REPORT_CSS__": (assets / "report.css").read_text(encoding="utf-8"),
                    "__REPORT_JS__": (assets / "report.js").read_text(encoding="utf-8"),
                    "__REPORT_DATA__": safe_inline_json(data)}
    if any(template.count(marker) != 1 for marker in replacements):
        raise ValueError("HTML 模板必须各含一次 CSS、JS、DATA 标记")
    # One replacement pass prevents report text containing a marker being interpreted.
    rendered = re.sub(r"__REPORT_(?:CSS|JS|DATA)__", lambda match: replacements[match.group()], template)
    for name in ("report.html", "report.css", "report.js"):
        inputs.append({"source": "assets/" + name, "sha256": digest((assets / name).read_bytes())})
    payloads = {paths[0]: rendered.encode("utf-8"),
                paths[1]: (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")}
    manifest = {"export_kind": EXPORT_KIND, "schema_version": "1.0",
                "exported_at": datetime.now(timezone.utc).isoformat(), "inference_executed": False,
                "validation_scope": "展现数据类型、内容转换与文件指纹；未自动验证业务语义、原始计算或商家执行效果",
                "inputs": inputs, "outputs": {path.name: digest(raw) for path, raw in payloads.items()}}
    payloads[paths[2]] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary, installed = {}, []
    previous = {path: path.read_bytes() for path in paths if path.exists()}
    try:
        for path, raw in payloads.items():
            with tempfile.NamedTemporaryFile(dir=output_path.parent, prefix=".report-export-", delete=False) as handle:
                temporary[path] = Path(handle.name)
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
        check_existing(paths, force)
        for path in paths:
            if force and path.exists():
                os.replace(temporary[path], path)
            else:
                # Exclusive link refuses an unrelated file appearing after preflight.
                os.link(temporary[path], path)
                temporary[path].unlink()
            installed.append(path)
    except BaseException:
        for path in reversed(installed):
            if path in previous:
                path.write_bytes(previous[path])
            else:
                path.unlink(missing_ok=True)
        raise
    finally:
        for path in temporary.values():
            path.unlink(missing_ok=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        manifest = export_report(args.config, args.output, args.force)
        print(json.dumps({"export_kind": manifest["export_kind"], "inference_executed": False,
                          "outputs": list(manifest["outputs"])}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("导出失败：" + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
