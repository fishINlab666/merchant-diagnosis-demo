"""Accounting truth tests for the explicit monthly scenario, not diagnosis rules."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "calculate_scenario.py"
DATA = ROOT / "examples" / "chain" / "numeric"


class ScenarioTests(unittest.TestCase):
    def calculate(self, payload):
        self.assertTrue(SCRIPT.exists(), "monthly contribution calculator is not implemented")
        spec = importlib.util.spec_from_file_location("calculate_scenario", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.calculate(payload)

    def read(self, name="scenario.json"):
        return json.loads((DATA / name).read_text(encoding="utf-8"))

    def test_base_accounts_for_lost_orders_avoided_costs_and_execution_cost(self):
        result = self.calculate(self.read())
        self.assertEqual(result["baseline"]["monthly_contribution"], 660000)
        self.assertEqual(result["budget_after"], {"tool_a": 210000, "tool_b": 90000, "total": 300000})
        base = result["scenarios"][1]
        self.assertEqual(base["added_receipts"], 180000)
        self.assertEqual(base["lost_receipts"], 84000)
        self.assertEqual(base["added_order_costs"], 108000)
        self.assertEqual(base["avoided_order_costs"], 50400)
        self.assertEqual(base["receipts_after"], 2496000)
        self.assertEqual(base["order_variable_costs_after"], 1497600)
        self.assertEqual(base["contribution_change"], 32400)
        self.assertEqual(base["monthly_contribution_after"], 692400)

    def test_conservative_case_is_a_hypothesis_not_probability_interval(self):
        result = self.calculate(self.read())
        scenario = result["scenarios"][0]
        self.assertEqual(scenario["contribution_change"], 18000)
        self.assertEqual(scenario["monthly_contribution_after"], 678000)

    def test_negative_result_is_not_clipped_to_zero(self):
        result = self.calculate(self.read("negative.json"))
        scenario = result["scenarios"][0]
        self.assertEqual(scenario["contribution_change"], -18000)
        self.assertEqual(scenario["monthly_contribution_after"], 642000)

    def test_missing_costs_refuse_contribution_but_keep_receipts_and_budget(self):
        result = self.calculate(self.read("missing_cost.json"))
        self.assertEqual(result["status"], "needs_cost_data")
        self.assertIsNone(result["baseline"]["monthly_contribution"])
        scenario = result["scenarios"][0]
        self.assertIsNone(scenario["contribution_change"])
        self.assertIsNone(scenario["monthly_contribution_after"])
        self.assertEqual(scenario["receipts_change"], 96000)
        self.assertEqual(len(result["missing_cost_fields"]), 4)

    def test_spend_cap_and_available_a_budget_are_enforced(self):
        payload = self.read()
        payload["reallocation"]["monthly_transfer"] = 60001
        with self.assertRaisesRegex(ValueError, "transfer_cap"):
            self.calculate(payload)
        payload["reallocation"] = {"monthly_transfer": 270001, "transfer_cap": 300000}
        with self.assertRaisesRegex(ValueError, "tool_a_budget"):
            self.calculate(payload)

    def test_invalid_numeric_costs_are_rejected_not_silently_treated_as_missing(self):
        for bad in (-1, "unknown", float("inf"), True):
            with self.subTest(bad=bad):
                payload = self.read()
                payload["scenarios"][0]["extra_execution_cost"] = bad
                with self.assertRaises(ValueError):
                    self.calculate(payload)

    def test_no_payload_mutation_or_brand_store_scaling(self):
        payload = self.read()
        before = copy.deepcopy(payload)
        result = self.calculate(payload)
        self.assertEqual(payload, before)
        payload["scope"]["brand_stores"] = 2000
        self.assertEqual(self.calculate(payload)["scenarios"], result["scenarios"])


if __name__ == "__main__":
    unittest.main()
