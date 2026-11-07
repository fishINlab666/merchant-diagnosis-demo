"""Export a resolved business report as one offline, customer-facing HTML file."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile

ASSETS = Path(__file__).resolve().parents[1] / "assets"
PROTOCOL_TOKEN = r"(?:DEF\d+|[FAD]\d+|S[1-5])"


def _customer_text(value):
    # Only recognizable protocol references are removed; A1 套餐 / A1店 are names.
    value = re.sub(r"(^|[\n。；;])\s*" + PROTOCOL_TOKEN + r"\s*[:：、.)）]\s*", r"\1", value)
    value = re.sub(r"[（(]\s*" + PROTOCOL_TOKEN + r"\s*[）)]", "", value)
    value = re.sub(r"(?:依据|参见|参考|见)\s*DEF\d+\s*[:：]?\s*", "", value)
    value = re.sub(r"(?<![A-Za-z0-9])DEF\d+(?![A-Za-z0-9\u4e00-\u9fff])", "", value)
    value = re.sub(r"(问题|动作|缺口|待补充|针对|关联)\s*(?:[FAD]\d+)(?![A-Za-z0-9\u4e00-\u9fff])", r"\1", value)
    def remove_reference(match):
        before = value[max(0, match.start() - 10):match.start()]
        after = value[match.end():match.end() + 10]
        if re.search(r"(?:商品|套餐|门店|型号|品牌|SKU)\s*$", before, re.I) or re.match(r"\s*(?:套餐|门店|型号|品牌|店|款)", after):
            return match.group()
        return ""
    value = re.sub(r"(?<![A-Za-z0-9\u4e00-\u9fff])" + PROTOCOL_TOKEN + r"(?![A-Za-z0-9\u4e00-\u9fff])", remove_reference, value)
    return re.sub(r"[ \t]{2,}", " ", value).strip()


def _object(value, name):
    if not isinstance(value, dict):
        raise ValueError(name + "必须为对象")
    return value


def _text(value, name, *, optional=False, clean=True):
    if value is None and optional:
        return ""
    if not isinstance(value, str) or (not optional and not value.strip()):
        raise ValueError(name + "必须为文字" + ("" if optional else "且不能为空"))
    result = _customer_text(value) if clean else value.strip()
    if not optional and not result:
        raise ValueError(name + "清理协议编号后为空，请补充实际内容")
    return result


def _texts(value, fields, name, *, optional=(), clean=True):
    value = _object(value, name)
    return {key: _text(value.get(key), name + "." + key, optional=key in optional, clean=clean) for key in fields}


def _items(value, name, *, maximum=None, required=False):
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(name + "必须为对象列表")
    if required and not value:
        raise ValueError(name + "至少需要一项可执行动作")
    if maximum is not None and len(value) > maximum:
        raise ValueError(name + "最多包含" + str(maximum) + "项，请保留最重要的内容")
    return value


def _number(value, name):
    if "calc_id" in value and "value" not in value:
        raise ValueError(name + "的计算结果尚未绑定，请先完成报告处理")
    number = value.get("value")
    if number is None:
        return None
    if isinstance(number, bool) or not isinstance(number, (int, float)):
        raise ValueError(name + ".value 必须为有限数值或 null；未知金额不能填零")
    try:
        finite = math.isfinite(number)
    except OverflowError:
        raise ValueError(name + ".value 超出可展示的数值范围，请核对金额与单位") from None
    if not finite:
        raise ValueError(name + ".value 必须为有限数值或 null；未知金额不能填零")
    return number


def customer_data(report):
    """Whitelist customer copy; never embed analysis, locators or execution metadata."""
    report = _object(report, "report")
    merchant = _texts(report.get("merchant"), ("name", "scope", "period"), "merchant", clean=False)
    synthetic = report["merchant"].get("synthetic", False)
    if not isinstance(synthetic, bool):
        raise ValueError("merchant.synthetic 必须为布尔值")
    merchant["synthetic"] = synthetic
    money_source = _object(report.get("money"), "money")
    money = _texts(money_source, ("label", "unit", "period", "note", "basis"), "money", optional=("note", "basis"))
    money["value"] = _number(money_source, "money")
    findings = [_texts(item, ("title", "detail", "basis"), "findings", optional=("basis",))
                for item in _items(report.get("findings", []), "findings", maximum=3)]
    actions = [_texts(item, ("title", "owner", "timing", "budget", "success", "stop"), "actions")
               for item in _items(report.get("actions"), "actions", required=True)]
    charts = []
    for item in _items(report.get("charts", []), "charts", maximum=3):
        chart = _texts(item, ("type", "title", "unit", "caption"), "charts", optional=("caption",))
        if chart["type"] == "bars":
            chart["type"] = "bar"
        if chart["type"] not in ("bar", "stacked", "waterfall"):
            raise ValueError("图表 type 必须为 bar、stacked 或 waterfall")
        chart["series"] = []
        for point in _items(item.get("series"), "series", required=True):
            record = {"label": _text(point.get("label"), "series.label"), "value": _number(point, "series")}
            for key in ("group", "role"):
                if key in point:
                    record[key] = _text(point[key], "series." + key, optional=True)
            chart["series"].append(record)
        if chart["type"] == "stacked" and any(point["value"] is not None and point["value"] < 0 for point in chart["series"]):
            chart["type"] = "bar"
        charts.append(chart)
    followup = _texts(report.get("followup"), ("when", "decision"), "followup")
    collect = report["followup"].get("collect", [])
    if isinstance(collect, str):
        collect = [collect] if collect.strip() else []
    if not isinstance(collect, list):
        raise ValueError("followup.collect 必须为文字列表")
    followup["collect"] = [_text(item, "followup.collect") for item in collect]
    return {"merchant": merchant, "headline": _text(report.get("headline"), "headline"), "money": money,
            "findings": findings, "actions": actions, "charts": charts,
            "followup": followup,
            "gaps": [_texts(item, ("item", "why"), "gaps") for item in _items(report.get("gaps", []), "gaps")]}


def _inline_json(value):
    serialized = json.dumps(value, ensure_ascii=False, allow_nan=False)
    for char, escaped in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"), ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        serialized = serialized.replace(char, escaped)
    return serialized


def export_boss(report, output, *, metadata=None) -> Path:
    """Export already-resolved values. Metadata stays internal and is never embedded."""
    output = Path(output)
    if output.suffix.lower() != ".html":
        raise ValueError("输出文件扩展名必须为 .html")
    if output.exists():
        raise FileExistsError("输出已存在，请指定新文件：" + str(output))
    payload = customer_data(report)
    template = (ASSETS / "boss-report.html").read_text(encoding="utf-8")
    replacements = {"__BOSS_CSS__": (ASSETS / "boss-report.css").read_text(encoding="utf-8"),
                    "__BOSS_JS__": (ASSETS / "boss-report.js").read_text(encoding="utf-8"),
                    "__BOSS_DATA__": _inline_json(payload)}
    if any(template.count(marker) != 1 for marker in replacements):
        raise ValueError("老板 HTML 模板必须各含一次 CSS、JS、DATA 标记")
    rendered = re.sub(r"__BOSS_(?:CSS|JS|DATA)__", lambda match: replacements[match.group()], template)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".boss-export-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(rendered.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        # Linking is exclusive, including if another process created the destination.
        os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return output


def _read_json(path):
    def reject_constant(value):
        raise ValueError("JSON 不允许非有限数值：" + value)
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"), parse_constant=reject_constant)
    if isinstance(value, dict) and value.get("kind") == "final":
        return value.get("report")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description="将已计算的经营方案导出为老板 HTML")
    parser.add_argument("--input", required=True, help="已绑定真实数值的 report.json")
    parser.add_argument("--output", required=True, help="新的 .html 文件路径")
    args = parser.parse_args(argv)
    try:
        result = export_boss(_read_json(args.input), args.output)
    except (OSError, ValueError, TypeError) as error:
        print("导出失败：" + str(error), file=sys.stderr)
        return 1
    print("老板报告已导出：" + str(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
