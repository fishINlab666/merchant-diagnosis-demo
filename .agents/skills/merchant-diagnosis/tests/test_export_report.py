"""Portable report exports preserve completed analysis; fixtures are synthetic."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

S3 = """# 数据接收与核对
门店：测试门店
数据范围：两个完整周
状态：待补数

## 数据覆盖
已读取周报，园区成本未知。

## 字段与口径
| 原字段 | 分析字段 | 单位 | 定义与来源 |
|---|---|---|---|
| 金额 | 净收入 | 元 | 周报.csv／row:2 |

表后的定义不能丢失。
"""
S5 = """# 一页行动方案
门店：测试门店
数据范围：仅三店、28天情景
状态：待补数

## 一句话结论
先查成本，再决定试行。

## 问题与证据
| 问题编号 | 问题 | 证据 |
|---|---|---|
| F1 | 商品 A\\|B 的贡献减少 | 周报.csv／row:2 |

## 现在／建议
| 动作编号 | 关联问题 | 现在 | 建议 | 负责人 | 开始时间 | 投入 |
|---|---|---|---|---|---|---|
| A1 | F1 | 成本未知 | 补账 | 财务 | 下周 | 待补充（D1） |

## 预期改善
| 动作编号 | 指标与单位 | 基线与来源 | 试行目标 | 测算与假设 |
|---|---|---|---|---|
| A1 | 贡献元 | 周报.csv／row:2 | 核清成本 | -18000.00元 |

这是固定成本前贡献，不是净利润；执行费只扣一次。

第二段公式：60000×(1.50－2.00)×0.40－6000＝-18000。

## 下周跟进
| 动作编号 | 回传数据 | 复盘时间 | 继续条件 | 调整或停止条件 | 待补事项 |
|---|---|---|---|---|---|
| A1 | 成本凭据 | 下周 | 账务齐全 | 仍缺成本则暂停收益结论 | D1：两期成本 |

## 给老板的三句话
1. 发现贡献下降。
2. 先补账。
3. 核实以后再决定。
"""


class ExportReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = self.root / "assets"
        self.assets.mkdir()
        (self.assets / "report.html").write_text(
            '<!doctype html><html><head><style>__REPORT_CSS__</style></head>'
            '<body><script id="report-data" type="application/json">__REPORT_DATA__</script>'
            '<script>__REPORT_JS__</script></body></html>', encoding="utf-8")
        (self.assets / "report.css").write_text("body{color:#123}", encoding="utf-8")
        (self.assets / "report.js").write_text("window.reportReady=true;", encoding="utf-8")
        self.run = self.root / "runs" / "商家 a"
        self.write_stage(self.run, "S3", S3)
        self.write_stage(self.run, "S5", S5)
        (self.run / "execution.json").write_text(json.dumps({
            "executor": "Example Agent", "model_id": "visible-model-id",
            "private_path": str(self.root / "secrets")}), encoding="utf-8")
        self.config = self.root / "catalog.json"
        self.config_data = {"title": "商户诊断", "cases": [{
            "id": "shop", "title": "测试商户", "label": "经营诊断", "synthetic": False,
            "versions": [{"id": "initial", "label": "初次分析", "run_dir": "runs/商家 a"}]}]}
        self.save_config()
        self.output = self.root / "output" / "report.html"

    def exporter(self):
        source = SCRIPTS / "export_report.py"
        self.assertTrue(source.is_file(), "通用网页报告导出器尚未实现")
        spec = importlib.util.spec_from_file_location("export_report", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def save_config(self):
        self.config.write_text(json.dumps(self.config_data, ensure_ascii=False), encoding="utf-8")

    def write_stage(self, root, stage, text):
        directory = root / stage
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "report.md").write_text(text, encoding="utf-8")
        (directory / "materials.json").write_text(json.dumps({"materials": [{
            "name": "周报.csv", "sha256": "a" * 64,
            "fragments": [{"locator": "row:2", "text": "不得内嵌的原始商家明细"}]}]}), encoding="utf-8")

    def export(self, **kwargs):
        self.exporter().export_report(self.config, self.output, assets_dir=self.assets, **kwargs)
        return json.loads(self.output.with_suffix(".json").read_text(encoding="utf-8"))

    def test_preserves_complete_ordered_content_and_exact_markdown(self):
        data = self.export()
        version = data["cases"][0]["versions"][0]
        self.assertEqual("1.0", data["schema_version"])
        self.assertEqual(["S3", "S5"], [s["stage"] for s in version["stages"]])
        final = version["stages"][-1]
        self.assertEqual(S5, final["markdown"])
        self.assertEqual(hashlib.sha256(S5.encode()).hexdigest(), final["sha256"])
        blocks = final["blocks"]
        index = next(i for i, b in enumerate(blocks) if b.get("text") == "预期改善")
        self.assertEqual(["heading", "table", "paragraph", "paragraph", "heading"],
                         [b["type"] for b in blocks[index:index + 5]])
        self.assertIn("不是净利润", blocks[index + 2]["text"])
        self.assertIn("-18000", blocks[index + 3]["text"])
        self.assertEqual("商品 A|B 的贡献减少", next(b for b in blocks if b["type"] == "table")["rows"][0][1])
        self.assertEqual(["发现贡献下降。", "先补账。", "核实以后再决定。"], version["takeaways"])
        self.assertEqual("先查成本，再决定试行。", version["summary"])
        self.assertEqual("待补数", version["status"])

    def test_no_s5_uses_latest_actual_paragraph_without_fabricating_stages(self):
        shutil.rmtree(self.run / "S5")
        data = self.export()
        version = data["cases"][0]["versions"][0]
        self.assertEqual(["S3"], [s["stage"] for s in version["stages"]])
        self.assertEqual("已读取周报，园区成本未知。", version["summary"])
        self.assertEqual([], version["takeaways"])

    def test_root_execution_is_used_and_raw_materials_are_not_embedded(self):
        version = self.export()["cases"][0]["versions"][0]
        self.assertEqual("Example Agent", version["executor"])
        self.assertEqual("visible-model-id", version["model_id"])
        self.assertEqual([{"name": "周报.csv", "sha256": "a" * 64}], version["sources"])
        for path in (self.output, self.output.with_suffix(".json"), self.output.with_suffix(".manifest.json")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(str(self.root), text)
            self.assertNotIn("不得内嵌的原始商家明细", text)
            self.assertNotIn("private_path", text)

    def test_missing_execution_is_not_inferred_from_prepare_manifest(self):
        (self.run / "execution.json").unlink()
        (self.run / "S5" / "manifest.json").write_text('{"runtime":"Codex","inference_executed":false}')
        version = self.export()["cases"][0]["versions"][0]
        self.assertEqual("未记录", version["executor"])
        self.assertEqual("未记录", version["model_id"])

    def test_s5_execution_fallback_keeps_exposed_metadata(self):
        (self.run / "execution.json").rename(self.run / "S5" / "execution.json")
        self.assertEqual("Example Agent", self.export()["cases"][0]["versions"][0]["executor"])

    def test_synthetic_flag_defaults_false_and_rejects_string_boolean(self):
        del self.config_data["cases"][0]["synthetic"]
        self.save_config()
        self.assertFalse(self.export()["cases"][0]["synthetic"])
        self.config_data["cases"][0]["synthetic"] = "false"
        self.save_config()
        with self.assertRaises(ValueError):
            self.export(force=True)

    def test_last_version_is_default_and_explicit_active_version_is_checked(self):
        case = self.config_data["cases"][0]
        case["versions"][0]["superseded"] = True
        case["versions"].append({"id": "revised", "label": "更正后", "run_dir": "runs/商家 a"})
        self.save_config()
        result = self.export()["cases"][0]
        self.assertEqual("revised", result["active_version"])
        self.assertTrue(result["versions"][0]["superseded"])
        case["active_version"] = "unknown"
        self.save_config()
        old = self.output.read_bytes()
        with self.assertRaises(ValueError):
            self.export(force=True)
        self.assertEqual(old, self.output.read_bytes())

    def test_multiple_cases_keep_their_own_versions(self):
        case = dict(self.config_data["cases"][0], id="other", title="另一个商家")
        self.config_data["cases"].append(case)
        self.save_config()
        self.assertEqual(["shop", "other"], [c["id"] for c in self.export()["cases"]])

    def test_visuals_preserve_negative_zero_and_unknown_values(self):
        visuals = {"highlights": [{"label": "未知贡献", "value": None, "unit": "元", "note": "成本缺失", "evidence": "周报.csv／row:2"}],
                   "charts": [{"id": "scenario", "type": "waterfall", "title": "贡献变化", "unit": "元", "caption": "条件情景", "series": [
                       {"label": "变化", "value": -18000, "role": "delta"}, {"label": "新增", "value": 0},
                       {"label": "未知", "value": None}], "evidence": "周报.csv／row:2"}]}
        view = self.root / "view.json"
        view.write_text(json.dumps(visuals, ensure_ascii=False), encoding="utf-8")
        self.config_data["cases"][0]["versions"][0]["view_file"] = "view.json"
        self.save_config()
        self.assertEqual(visuals, self.export()["cases"][0]["versions"][0]["visuals"])

    def test_invalid_visuals_fail_before_writing_any_outputs(self):
        valid = {"label": "指标", "value": 1, "unit": "元", "note": "说明", "evidence": "周报.csv／row:2"}
        self.config_data["cases"][0]["versions"][0]["view_file"] = "view.json"
        self.save_config()
        for changes in ({"value": True}, {"value": "1"}, {"value": float("inf")}, {"value": float("nan")}, {"evidence": ""}):
            with self.subTest(changes=changes):
                (self.root / "view.json").write_text(json.dumps({"highlights": [dict(valid, **changes)], "charts": []}))
                with self.assertRaises(ValueError):
                    self.export()
                self.assertFalse(self.output.exists())
                self.assertFalse(self.output.with_suffix(".json").exists())
                self.assertFalse(self.output.with_suffix(".manifest.json").exists())

    def test_inline_json_cannot_close_script_or_inject_markup(self):
        payload = '</script><script>alert("x")</script>&\u2028\u2029'
        self.config_data["title"] = payload
        self.write_stage(self.run, "S5", S5.replace("先查成本，再决定试行。", payload))
        self.save_config()
        data = self.export()
        html = self.output.read_text(encoding="utf-8")
        self.assertNotIn(payload, html)
        self.assertIn("\\u003c/script\\u003e", html)
        self.assertIn("\\u0026", html)
        self.assertIn("\\u2028", html)
        self.assertIn("\\u2029", html)
        self.assertEqual(payload, data["title"])
        self.assertNotIn("__REPORT_", html)
        self.assertIn("body{color:#123}", html)
        self.assertIn("window.reportReady=true;", html)

    def test_refuses_overwrite_and_force_only_replaces_untampered_own_export(self):
        self.export()
        original = self.output.read_bytes()
        with self.assertRaises(ValueError):
            self.export()
        self.assertEqual(original, self.output.read_bytes())
        self.config_data["title"] = "新版"
        self.save_config()
        self.assertEqual("新版", self.export(force=True)["title"])
        self.output.write_text("human edit", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.export(force=True)
        self.assertEqual("human edit", self.output.read_text())

    def test_foreign_sidecar_is_not_overwritten(self):
        self.output.parent.mkdir()
        self.output.with_suffix(".json").write_text("unrelated")
        with self.assertRaises(ValueError):
            self.export(force=True)
        self.assertFalse(self.output.exists())
        self.assertEqual("unrelated", self.output.with_suffix(".json").read_text())

    def test_config_paths_are_relative_to_config_and_relocatable(self):
        first = self.export()
        moved = self.root / "moved"
        moved.mkdir()
        shutil.copytree(self.root / "runs", moved / "runs")
        shutil.copy2(self.config, moved / "catalog.json")
        exported = moved / "new.html"
        self.exporter().export_report(moved / "catalog.json", exported, assets_dir=self.assets)
        self.assertEqual(first, json.loads(exported.with_suffix(".json").read_text()))

    def test_manifest_identifies_export_not_new_model_run_and_hashes_outputs(self):
        self.export()
        manifest = json.loads(self.output.with_suffix(".manifest.json").read_text())
        self.assertEqual("merchant-diagnosis-report-export", manifest["export_kind"])
        self.assertFalse(manifest["inference_executed"])
        self.assertIn("未自动验证", manifest["validation_scope"])
        for name, expected in manifest["outputs"].items():
            self.assertEqual(hashlib.sha256((self.output.parent / name).read_bytes()).hexdigest(), expected)
        self.assertTrue(any(x["source"] == "shop/initial/S5/report.md" for x in manifest["inputs"]))

    def test_empty_run_invalid_stage_and_duplicate_ids_are_rejected(self):
        case = self.config_data["cases"][0]
        for change in ("empty", "metadata", "duplicate"):
            with self.subTest(change=change):
                if change == "empty":
                    case["versions"][0]["run_dir"] = "runs/absent"
                elif change == "metadata":
                    case["versions"][0]["run_dir"] = "runs/商家 a"
                    (self.run / "S5" / "report.md").write_text("# Empty\n")
                else:
                    (self.run / "S5" / "report.md").write_text(S5)
                    self.config_data["cases"].append(dict(case))
                self.save_config()
                with self.assertRaises((ValueError, OSError)):
                    self.export()
                self.assertFalse(self.output.exists())

    def test_missing_asset_marker_is_an_error_without_output(self):
        (self.assets / "report.html").write_text("<!doctype html><p>bad template</p>")
        with self.assertRaises(ValueError):
            self.export()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
