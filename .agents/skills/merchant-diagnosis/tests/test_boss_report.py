"""Customer exports keep business content and exclude the analysis workspace."""
import copy
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def sample_report():
    return {
        "merchant": {"name": "演示饭堂", "scope": "30 家成熟直营店", "period": "未来 30 天", "synthetic": True},
        "headline": "先调整两类推广的投入，小范围验证后再扩大。",
        "money": {"label": "审慎情景增加经营贡献", "value": 12600, "unit": "元", "period": "30 天",
                  "note": "已扣试行费用，固定成本前；按本次假设测算。", "basis": "来自同周期收支与试行观察。",
                  "calc_id": "private-calculation", "evidence": "definitions.md／DEF03／line:2"},
        "findings": [{"title": "投入集中", "detail": "有小范围调整空间。", "basis": "来自同周期费用对照。", "evidence": "private-source"}],
        "actions": [{"title": "先在已有试点门店调整推广", "owner": "城市经理", "timing": "下周起试行 7 天", "budget": "总预算不增加",
                     "success": "贡献改善且订单稳定时继续", "stop": "贡献转负时撤回本次调整"}],
        "followup": {"when": "7 天后", "collect": ["订单", "实际费用", "执行记录"], "decision": "决定继续、调整或停止"},
        "charts": [{"type": "bar", "title": "不同假设下的贡献变化", "unit": "元", "caption": "与维持现状比较。", "series": [
            {"label": "审慎", "value": 12600, "calc_id": "private-chart-id", "evidence": "DEF01"},
            {"label": "基准", "value": 32400}, {"label": "压力", "value": -1800}]}],
        "analysis": {"goal": "INTERNAL_ONLY", "execution": "PRIVATE_EXECUTION"},
        "gaps": [{"item": "执行记录", "why": "确认实际是否按计划调整"}],
    }


class BossReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "nested" / "boss.html"

    def exporter(self):
        source = SCRIPTS / "boss_report.py"
        self.assertTrue(source.is_file(), "独立老板报告导出器尚未实现")
        spec = importlib.util.spec_from_file_location("boss_report", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def export(self, report=None):
        result = self.exporter().export_boss(report or sample_report(), self.output, metadata={"private": "SECRET_METADATA"})
        self.assertEqual(self.output, result)
        html = self.output.read_text(encoding="utf-8")
        payload = re.search(r'<script id="boss-data" type="application/json">(.*?)</script>', html, re.S)
        self.assertIsNotNone(payload)
        return html, json.loads(payload.group(1))

    def test_only_customer_fields_are_embedded_and_input_is_unchanged(self):
        report = sample_report()
        original = copy.deepcopy(report)
        html, data = self.export(report)
        self.assertEqual(original, report)
        for private in ("private-calculation", "private-chart-id", "private-source", "DEF03", "INTERNAL_ONLY", "PRIVATE_EXECUTION", "SECRET_METADATA", '"evidence"', '"calc_id"', '"analysis"'):
            self.assertNotIn(private, html)
        self.assertEqual(12600, data["money"]["value"])
        self.assertEqual(report["actions"][0], data["actions"][0])
        self.assertEqual(report["gaps"], data["gaps"])

    def test_null_negative_and_real_zero_remain_distinct(self):
        report = sample_report()
        report["money"]["value"] = None
        report["charts"][0]["series"] = [{"label": "未知", "value": None}, {"label": "零", "value": 0}, {"label": "负值", "value": -100}]
        html, data = self.export(report)
        self.assertIsNone(data["money"]["value"])
        self.assertEqual([None, 0, -100], [p["value"] for p in data["charts"][0]["series"]])
        self.assertIn("待确认", html)

    def test_json_cannot_close_script_or_inject_markup(self):
        report = sample_report()
        attack = '</script><img src=x onerror="alert(1)">&\u2028继续\u2029查看'
        report["headline"] = attack
        html, data = self.export(report)
        self.assertNotIn(attack, html)
        self.assertEqual(attack, data["headline"])
        self.assertIn('\\u003c/script\\u003e', html)
        self.assertNotIn("innerHTML", html)

    def test_rejects_nonfinite_boolean_and_unresolved_values_before_writing(self):
        exporter = self.exporter()
        for invalid in (float("nan"), float("inf"), True, "1200"):
            with self.subTest(value=invalid):
                report = sample_report()
                report["money"]["value"] = invalid
                with self.assertRaises(ValueError):
                    exporter.export_boss(report, self.output)
                self.assertFalse(self.output.exists())
        report = sample_report()
        del report["money"]["value"]
        with self.assertRaisesRegex(ValueError, "绑定"):
            exporter.export_boss(report, self.output)

    def test_normalizes_protocol_labels_and_preserves_product_names(self):
        report = sample_report()
        report["actions"][0]["title"] = "A1：先调整展示（F1）"
        report["money"]["basis"] = "依据 DEF05：成本口径由老板确认。"
        report["findings"][0]["title"] = "A1套餐在A1店销售，F1赛车品牌联名，商品 A1 与 A1 套餐"
        _, data = self.export(report)
        self.assertEqual("先调整展示", data["actions"][0]["title"])
        self.assertEqual("成本口径由老板确认。", data["money"]["basis"])
        self.assertEqual(report["findings"][0]["title"], data["findings"][0]["title"])

    def test_optional_display_fields_default_without_blocking_export(self):
        report = sample_report()
        for key in ("note", "basis"):
            del report["money"][key]
        del report["findings"][0]["basis"]
        del report["charts"][0]["caption"]
        del report["followup"]["collect"]
        del report["gaps"]
        _, data = self.export(report)
        self.assertEqual("", data["money"]["note"])
        self.assertEqual([], data["gaps"])
        self.assertEqual([], data["followup"]["collect"])

    def test_merchant_identity_is_not_cleaned_as_protocol_copy(self):
        report = sample_report()
        report["merchant"].update(name="A1", scope="F1", period="D1")
        _, data = self.export(report)
        self.assertEqual(report["merchant"], data["merchant"])

    def test_required_copy_cannot_become_empty_after_protocol_cleanup(self):
        report = sample_report()
        report["headline"] = "F1："
        with self.assertRaisesRegex(ValueError, "headline.*清理.*空"):
            self.exporter().export_boss(report, self.output)
        self.assertFalse(self.output.exists())

    def test_negative_stacked_chart_falls_back_to_bars_without_losing_values(self):
        report = sample_report()
        report["charts"][0]["type"] = "stacked"
        report["charts"][0]["series"] = [{"label": "收入", "value": 100}, {"label": "退款", "value": -20}, {"label": "待核费用", "value": None}]
        _, data = self.export(report)
        self.assertEqual("bar", data["charts"][0]["type"])
        self.assertEqual([100, -20, None], [point["value"] for point in data["charts"][0]["series"]])

    def test_oversized_integer_returns_validation_error_for_money_and_chart(self):
        for field in ("money", "chart"):
            report = sample_report()
            target = report["money"] if field == "money" else report["charts"][0]["series"][0]
            target["value"] = 10 ** 1000
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "数值范围"):
                self.exporter().export_boss(report, self.output)
            self.assertFalse(self.output.exists())

    def test_rejects_excess_findings_charts_or_missing_first_action(self):
        for key in ("findings", "charts"):
            report = sample_report()
            report[key] *= 4
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.exporter().export_boss(report, self.output)
        report = sample_report()
        report["actions"] = []
        with self.assertRaises(ValueError):
            self.exporter().export_boss(report, self.output)

    def test_existing_file_is_not_overwritten_and_no_sidecars_are_created(self):
        self.export()
        original = self.output.read_bytes()
        with self.assertRaises(FileExistsError):
            self.exporter().export_boss(sample_report(), self.output)
        self.assertEqual(original, self.output.read_bytes())
        self.assertEqual([self.output], list(self.output.parent.iterdir()))

    def test_cli_accepts_final_envelope_and_reports_invalid_input(self):
        self.exporter()
        source = Path(self.temp.name) / "report.json"
        source.write_text(json.dumps({"kind": "final", "report": sample_report()}, ensure_ascii=False))
        result = subprocess.run([sys.executable, str(SCRIPTS / "boss_report.py"), "--input", str(source), "--output", str(self.output)], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(self.output.is_file())
        result = subprocess.run([sys.executable, str(SCRIPTS / "boss_report.py"), "--input", str(source), "--output", str(self.output)], capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
