"""Acceptance checks for the actual synthetic showcase and its recorded sources."""
from collections import defaultdict
from decimal import Decimal
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
SHOWCASE = SKILL / "examples" / "showcase"
sys.path.insert(0, str(SKILL / "scripts"))
from export_report import build_report, export_report


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def amount(value):
    return None if value is None else Decimal(str(value))


class ResourceParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.resources = []

    def handle_starttag(self, tag, attrs):
        resource_attributes = {
            "script": ("src",), "link": ("href",), "img": ("src", "srcset"),
            "iframe": ("src",), "object": ("data",), "embed": ("src",),
            "image": ("href", "xlink:href"), "use": ("href", "xlink:href"),
        }
        for key, value in attrs:
            if key in resource_attributes.get(tag, ()) and value:
                if not value.startswith(("data:", "#")):
                    self.resources.append((tag, key, value))


class ShowcaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report, cls.inputs = build_report(SHOWCASE / "catalog.json")
        cls.cases = {case["id"]: case for case in cls.report["cases"]}
        cls.versions = {(case["id"], version["id"]): version
                        for case in cls.report["cases"] for version in case["versions"]}

    def calculations(self, name):
        return read(SHOWCASE / "calculations" / (name + ".json"))

    def visuals(self, case, version):
        value = self.versions[(case, version)]["visuals"]
        return ({item["label"]: amount(item["value"]) for item in value["highlights"]},
                {chart["id"]: chart for chart in value["charts"]})

    def points(self, chart):
        return {point["label"]: amount(point["value"]) for point in chart["series"]}

    def test_current_and_historical_versions_keep_only_actual_stages(self):
        self.assertEqual({"chain", "messy"}, set(self.cases))
        self.assertEqual("revised", self.cases["chain"]["active_version"])
        self.assertEqual("current", self.cases["messy"]["active_version"])
        self.assertTrue(self.versions[("chain", "original")]["superseded"])
        self.assertFalse(self.versions[("chain", "revised")]["superseded"])
        expected = {("chain", "original"): ["S1", "S2", "S3", "S4", "S5"],
                    ("chain", "revised"): ["S3", "S4", "S5"],
                    ("messy", "current"): ["S3", "S4", "S5"]}
        for key, stages in expected.items():
            self.assertEqual(stages, [item["stage"] for item in self.versions[key]["stages"]])
        self.assertTrue(all(case["synthetic"] for case in self.cases.values()))

    def test_packaged_sources_preserve_recorded_calculations_and_report_bytes(self):
        provenance = read(SHOWCASE / "calculation-sources.json")
        self.assertEqual(3, len(provenance["sources"]))
        self.assertEqual(11, len(provenance["reports"]))
        expected_reports = {str(path.relative_to(SHOWCASE))
                            for path in (SHOWCASE / "runs").glob("*/S*/report.md")}
        self.assertEqual(expected_reports, {item["snapshot"] for item in provenance["reports"]})
        for item in provenance["sources"] + provenance["reports"]:
            with self.subTest(snapshot=item["snapshot"]):
                path = (SHOWCASE / item["snapshot"]).resolve()
                self.assertTrue(path.is_relative_to(SHOWCASE.resolve()))
                self.assertEqual(item["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        stage_hashes = {stage["sha256"] for version in self.versions.values() for stage in version["stages"]}
        self.assertEqual({item["sha256"] for item in provenance["reports"]}, stage_hashes)

    def test_chain_summary_and_scenarios_match_original_calculations(self):
        base = self.calculations("chain-original")
        corrected = self.calculations("chain-revised")
        old_metrics, old_charts = self.visuals("chain", "original")
        new_metrics, new_charts = self.visuals("chain", "revised")
        baseline = base["monthly_30_day_baseline"]
        old = base["monthly_scenarios"][0]
        new = corrected["continued_reallocation_scenarios"][0]
        self.assertEqual(amount(32400), amount(old["contribution_difference"]))
        self.assertEqual(amount(-18000), amount(new["contribution_difference"]))
        for metrics in (old_metrics, new_metrics):
            self.assertEqual(amount(baseline["ads"]), metrics["30 天规划广告总额"])
            self.assertEqual(amount(base["channel"][0]["spend_share"]) * 100,
                             metrics["A 渠道历史费用占比"])
        self.assertEqual(amount(old["contribution_difference"]), old_metrics["月度基准情景贡献差额"])
        self.assertEqual(amount(base["first_7_day_scenario"]["shift"]), old_metrics["首轮 7 天调拨上限"])
        self.assertEqual(amount(new["contribution_difference"]), new_metrics["继续旧方案的月度差额"])
        self.assertEqual(amount(0), new_metrics["本次新启动调拨"])
        self.assertEqual({row["name"] + "情景": amount(row["contribution_difference"])
                          for row in base["monthly_scenarios"]}, self.points(old_charts["scenarios"]))
        self.assertEqual({"原基准（失效）": amount(old["contribution_difference"]),
                          "更正后情景": amount(new["contribution_difference"])}, self.points(new_charts["scenario"]))
        self.assertEqual({"减 A 收入损失": amount(base["marginal_estimates"]["A_loss"]),
                          "增 B 收入增加": amount(base["marginal_estimates"]["B_gain"])},
                         self.points(old_charts["marginal"]))
        self.assertEqual({"减 A：旧观察": amount(base["marginal_estimates"]["A_loss"]),
                          "增 B：旧观察": amount(base["marginal_estimates"]["B_gain"]),
                          "减 A：更正后": amount(corrected["current_marginal_estimates"]["A_loss"]),
                          "增 B：更正后": amount(corrected["current_marginal_estimates"]["B_gain"])},
                         self.points(new_charts["marginal"]))

    def test_chain_budget_stays_constant_and_waterfalls_match_cost_calculations(self):
        base = self.calculations("chain-original")
        revised = self.calculations("chain-revised")
        ads = amount(base["monthly_30_day_baseline"]["ads"])
        a = ads * amount(base["channel"][0]["spend_share"])
        b = ads - a
        shift = amount(base["monthly_scenarios"][0]["shift"])
        for version, calculation, cost_key in (
                ("original", base["monthly_scenarios"][0], "variable_cost_difference"),
                ("revised", revised["continued_reallocation_scenarios"][0], "cost_difference")):
            _, charts = self.visuals("chain", version)
            groups = defaultdict(dict)
            for point in charts["budget"]["series"]:
                groups[point["group"]][point["label"]] = amount(point["value"])
            expected = ([{"A": a, "B": b}, {"A": a - shift, "B": b + shift}]
                        if version == "original" else [{"A": a, "B": b}])
            self.assertEqual(expected, list(groups.values()))
            self.assertTrue(all(sum(values.values()) == ads for values in groups.values()))
            expected_bridge = [amount(base["monthly_30_day_baseline"]["contribution"]),
                               amount(calculation["revenue_difference"]),
                               -amount(calculation[cost_key]), -amount(calculation["execution_fee"]),
                               amount(calculation["adjusted_contribution"])]
            self.assertEqual(expected_bridge, [amount(p["value"]) for p in charts["bridge"]["series"]])

    def test_weekly_numbers_keep_unknown_store_out_of_known_contribution(self):
        data = self.calculations("messy-weekly")
        metrics, charts = self.visuals("messy", "current")
        totals = data["totals"]["W1"]
        self.assertEqual(amount(totals["completed_orders_all4"]), metrics["四店本周完成订单"])
        self.assertEqual(amount(totals["net_receipts_all4"]), metrics["四店本周净结算"])
        self.assertEqual(amount(81000), metrics["已知三店本周贡献"])
        known = [row["W1"]["contribution"] for row in data["stores"].values()
                 if row["W1"]["contribution"] is not None]
        self.assertEqual(3, len(known))
        self.assertEqual(amount(sum(known)), amount(totals["contribution_known3"]))
        self.assertEqual(amount(totals["contribution_known3"]), metrics["已知三店本周贡献"])
        self.assertIsNone(metrics["园区店本周贡献"])
        store_names = {"M01": "国贸", "M02": "大学城", "M03": "社区", "M04": "园区"}
        expected_stores = {name + " " + week: amount(data["stores"][store][week]["contribution"])
                           for store, name in store_names.items() for week in ("W0", "W1")}
        self.assertEqual(expected_stores, self.points(charts["stores"]))
        for week in ("W0", "W1"):
            self.assertIsNone(data["stores"]["M04"][week]["variable_cost"])
            self.assertIsNone(self.points(charts["stores"])["园区 " + week])
        self.assertEqual({name: amount(data["stores"][store]["W1"]["completed_orders"]
                                      - data["stores"][store]["W0"]["completed_orders"])
                          for store, name in store_names.items()}, self.points(charts["volume"]))
        self.assertEqual({row["sku"] + " " + week: amount(row["pre_ad_contribution_unit"])
                          for week, rows in data["menu"].items() for row in rows}, self.points(charts["sku"]))
        bridge = data["M03_contribution_bridge"]
        self.assertEqual([amount(data["stores"]["M03"]["W0"]["contribution"]),
                          amount(bridge["volume"]), amount(bridge["mix"]), amount(bridge["unit"]),
                          amount(data["stores"]["M03"]["W1"]["contribution"])],
                         [amount(point["value"]) for point in charts["mix"]["series"]])

    def test_every_waterfall_closes_and_retains_negative_steps(self):
        waterfalls = [chart for version in self.versions.values()
                      for chart in version["visuals"]["charts"] if chart["type"] == "waterfall"]
        self.assertEqual(3, len(waterfalls))
        for chart in waterfalls:
            points = chart["series"]
            with self.subTest(chart=chart["title"]):
                self.assertEqual("total", points[0]["role"])
                self.assertEqual("total", points[-1]["role"])
                self.assertEqual(sum(amount(p["value"]) for p in points[:-1]), amount(points[-1]["value"]))
                self.assertTrue(any(amount(p["value"]) < 0 for p in points[1:-1]))

    def test_showcase_exports_offline_after_moving_outside_repository(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            copied = root / "example"
            shutil.copytree(SHOWCASE, copied)
            moved, _ = build_report(copied / "catalog.json")
            self.assertEqual(self.report, moved)
            output = root / "delivery" / "report.html"
            export_report(copied / "catalog.json", output)
            parser = ResourceParser()
            parser.feed(output.read_text(encoding="utf-8"))
            self.assertEqual([], parser.resources, "离线报告不能依赖外部脚本、字体、图片或页面")
            for filename in ("report.css", "report.js"):
                asset = (SKILL / "assets" / filename).read_text(encoding="utf-8")
                self.assertIsNone(re.search(r"@import\b|\burl\s*\(\s*['\"]?(?:https?:)?//", asset))
                self.assertIsNone(re.search(r"\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon)\s*\(", asset))


if __name__ == "__main__":
    unittest.main()
