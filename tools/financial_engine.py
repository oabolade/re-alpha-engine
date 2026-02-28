"""Skill 2: Financial Modeling Engine — implements all 8 steps from financial_model.md plus scenario analysis."""

from typing import Any
import numpy_financial as npf
from config import DEFAULT_ASSUMPTIONS, SCENARIO_OVERRIDES


def run_financial_model(
    normalized_data: dict[str, Any],
    assumptions: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Run the full 8-step financial model on normalized rent roll data."""
    a = {**DEFAULT_ASSUMPTIONS, **(assumptions or {})}
    units = normalized_data["units"]
    purchase_price = normalized_data["purchase_price"]
    vacancy_rate = normalized_data["vacancy_rate"]

    # Step 1: Gross Annual Rent (can always compute this)
    monthly_total = sum(u["monthly_rent"] for u in units if u["monthly_rent"])
    gross_annual_rent = monthly_total * 12

    if not purchase_price or purchase_price <= 0:
        egi = gross_annual_rent * (1 - vacancy_rate)
        opex = egi * a["expense_ratio"]
        noi = egi - opex
        return {
            "error": "Purchase price missing or invalid — metrics requiring price are unavailable.",
            "gross_annual_rent": _r(gross_annual_rent),
            "effective_gross_income": _r(egi),
            "operating_expenses": _r(opex),
            "noi": _r(noi),
            "cap_rate": None,
            "equity_invested": None,
            "loan_amount": None,
            "debt_service": None,
            "annual_cash_flow_year1": None,
            "cash_on_cash": None,
            "dscr": None,
            "irr_5yr": None,
            "exit_value": None,
            "cash_flows": [],
            "assumptions_used": a,
        }

    # Step 2: Effective Gross Income
    egi = gross_annual_rent * (1 - vacancy_rate)

    # Step 3: Operating Expenses
    opex = egi * a["expense_ratio"]

    # Step 4: NOI
    noi = egi - opex

    # Step 5: Cap Rate
    cap_rate = noi / purchase_price if purchase_price else 0

    # Step 6: Equity Invested
    equity = purchase_price * (1 - a["ltv"])

    # Step 7: Debt Service & Cash Flow (interest-only)
    loan_amount = purchase_price * a["ltv"]
    debt_service = loan_amount * a["interest_rate"]
    annual_cash_flow = noi - debt_service

    # Step 8: 5-Year IRR
    cash_flows = [_neg(equity)]  # Year 0: equity outflow
    projected_noi = noi
    for year in range(1, a["hold_period"] + 1):
        projected_noi = projected_noi * (1 + a["rent_growth"])
        year_cf = projected_noi - debt_service
        if year == a["hold_period"]:
            exit_cap = cap_rate - a["exit_cap_compression"]
            exit_cap = max(exit_cap, 0.01)  # floor at 1%
            exit_value = projected_noi / exit_cap
            net_exit = exit_value - loan_amount
            year_cf += net_exit
        cash_flows.append(year_cf)

    irr = _safe_irr(cash_flows)

    # Cash-on-Cash (Year 1)
    coc = annual_cash_flow / equity if equity > 0 else 0

    # DSCR
    dscr = noi / debt_service if debt_service > 0 else 0

    return {
        "gross_annual_rent": _r(gross_annual_rent),
        "effective_gross_income": _r(egi),
        "operating_expenses": _r(opex),
        "noi": _r(noi),
        "cap_rate": _r4(cap_rate),
        "equity_invested": _r(equity),
        "loan_amount": _r(loan_amount),
        "debt_service": _r(debt_service),
        "annual_cash_flow_year1": _r(annual_cash_flow),
        "cash_on_cash": _r4(coc),
        "dscr": _r2(dscr),
        "irr_5yr": _r4(irr) if irr is not None else None,
        "exit_value": _r(projected_noi / max(cap_rate - a["exit_cap_compression"], 0.01)),
        "cash_flows": [_r(cf) for cf in cash_flows],
        "assumptions_used": a,
    }


def run_scenarios(normalized_data: dict[str, Any]) -> dict[str, Any]:
    """Run bull/base/bear scenarios."""
    results = {}
    for scenario_name, overrides in SCENARIO_OVERRIDES.items():
        vacancy_adj = overrides.pop("vacancy_adj", 0.0)
        adjusted_data = {**normalized_data}
        adjusted_data["vacancy_rate"] = max(
            0, min(1, normalized_data["vacancy_rate"] + vacancy_adj)
        )
        scenario_assumptions = {**DEFAULT_ASSUMPTIONS, **overrides}
        result = run_financial_model(adjusted_data, scenario_assumptions)
        result["vacancy_rate_adjusted"] = adjusted_data["vacancy_rate"]
        results[scenario_name] = result
        overrides["vacancy_adj"] = vacancy_adj  # restore for reuse
    return results


def _neg(x: float) -> float:
    return -abs(x)


def _safe_irr(cash_flows: list[float]) -> float | None:
    try:
        result = npf.irr(cash_flows)
        if result is not None and not (result != result):  # NaN check
            return float(result)
        return None
    except Exception:
        return None


def _r(x: float) -> float:
    return round(x, 2)

def _r2(x: float) -> float:
    return round(x, 2)

def _r4(x: float) -> float:
    return round(x, 4)
