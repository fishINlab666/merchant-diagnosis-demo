"""Recalculate explicit monthly assumptions; this module makes no diagnosis."""
from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
from typing import Any


def _number(value: Any, path: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path} must be a finite non-negative number")
    number = Decimal(str(value))
    if not number.is_finite() or number < 0:
        raise ValueError(f"{path} must be a finite non-negative number")
    return number


def _money(value: Decimal | None) -> float | None:
    return None if value is None else float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def calculate(payload: dict[str, Any]) -> dict[str, Any]:
    """Return arithmetic only, preserving unknown costs and negative outcomes.

    Inputs must already use the same 30-day scope and net merchant receipt
    definition. Metadata and source citations are not interpreted as formulas.
    """
    baseline = payload["baseline"]
    receipts = _number(baseline["net_merchant_receipts"], "baseline.net_merchant_receipts")
    a_budget = _number(baseline["tool_a_budget"], "baseline.tool_a_budget")
    b_budget = _number(baseline["tool_b_budget"], "baseline.tool_b_budget")
    transfer = _number(payload["reallocation"]["monthly_transfer"], "reallocation.monthly_transfer")
    cap = _number(payload["reallocation"]["transfer_cap"], "reallocation.transfer_cap")
    if transfer > cap:
        raise ValueError("monthly_transfer exceeds transfer_cap")
    if transfer > a_budget:
        raise ValueError("monthly_transfer exceeds available tool_a_budget")
    missing: list[str] = []

    def cost(value: Any, path: str) -> Decimal | None:
        if value is None:
            missing.append(path)
            return None
        return _number(value, path)

    variable_cost = cost(baseline.get("order_variable_costs"), "baseline.order_variable_costs")
    total_budget = a_budget + b_budget
    contribution_before = None if variable_cost is None else receipts - variable_cost - total_budget
    derived = []
    for index, scenario in enumerate(payload["scenarios"]):
        path = f"scenarios[{index}]"
        added = transfer * _number(scenario["added_b_receipts_per_budget"], f"{path}.added_b_receipts_per_budget")
        lost = transfer * _number(scenario["lost_a_receipts_per_budget"], f"{path}.lost_a_receipts_per_budget")
        added_ratio = cost(scenario.get("added_order_cost_ratio"), f"{path}.added_order_cost_ratio")
        avoided_ratio = cost(scenario.get("avoided_order_cost_ratio"), f"{path}.avoided_order_cost_ratio")
        execution = cost(scenario.get("extra_execution_cost"), f"{path}.extra_execution_cost")
        added_cost = None if added_ratio is None else added * added_ratio
        avoided_cost = None if avoided_ratio is None else lost * avoided_ratio
        contribution_change = None
        contribution_after = None
        variable_cost_after = None
        if added_cost is not None and avoided_cost is not None and execution is not None:
            contribution_change = added - lost - added_cost + avoided_cost - execution
            if variable_cost is not None:
                variable_cost_after = variable_cost + added_cost - avoided_cost
                contribution_after = receipts + added - lost - variable_cost_after - total_budget - execution
        derived.append({
            "name": scenario["name"],
            "added_receipts": _money(added),
            "lost_receipts": _money(lost),
            "receipts_change": _money(added - lost),
            "receipts_after": _money(receipts + added - lost),
            "added_order_costs": _money(added_cost),
            "avoided_order_costs": _money(avoided_cost),
            "order_variable_costs_after": _money(variable_cost_after),
            "extra_execution_cost": _money(execution),
            "contribution_change": _money(contribution_change),
            "monthly_contribution_after": _money(contribution_after),
        })
    return {
        "case_id": payload.get("case_id"),
        "status": "needs_cost_data" if missing else "calculated",
        "unit": "CNY",
        "metric": "monthly_contribution_before_fixed_costs",
        "scope": dict(payload.get("scope", {})),
        "baseline": {"net_merchant_receipts": _money(receipts), "order_variable_costs": _money(variable_cost), "promotion_budget": _money(total_budget), "monthly_contribution": _money(contribution_before)},
        "budget_after": {"tool_a": _money(a_budget - transfer), "tool_b": _money(b_budget + transfer), "total": _money(total_budget)},
        "scenarios": derived,
        "missing_cost_fields": missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="explicit scenario JSON; no embedded defaults")
    args = parser.parse_args()
    try:
        result = calculate(json.loads(args.input.read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"Calculation failed: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
