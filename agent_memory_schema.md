# UnderwritingAnalystAgent — Memory Schema

Session-based memory only.

## Structure:

{
  "property_name": "",
  "address": "",
  "purchase_price": 0,
  "total_units": 0,
  "normalized_units": [],
  "vacancy_rate": 0.0,
  "financial_metrics": {
    "gross_annual_rent": 0,
    "effective_gross_income": 0,
    "noi": 0,
    "cap_rate": 0.0,
    "irr_5yr": 0.0,
    "cash_on_cash": 0.0
  },
  "assumptions_used": {
    "rent_growth": 0.03,
    "ltv": 0.70,
    "interest_rate": 0.065,
    "expense_ratio": 0.35,
    "hold_period": 5
  },
  "scenarios": {
    "bull": { "irr_5yr": 0.0, "noi_year5": 0, "exit_value": 0, "assumptions": {} },
    "base": { "irr_5yr": 0.0, "noi_year5": 0, "exit_value": 0, "assumptions": {} },
    "bear": { "irr_5yr": 0.0, "noi_year5": 0, "exit_value": 0, "assumptions": {} }
  },
  "negotiation_leverage": [],
  "investment_memo": ""
}

Purpose:
- Enable follow-up scenario adjustments
- Avoid recalculation from scratch
- Support “What if?” analysis