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
    "cash_on_cash": 0.0,
    "dscr": 0.0,
    "exit_value": 0,
    "equity_invested": 0
  },
  "assumptions_used": {
    "rent_growth": 0.03,
    "ltv": 0.70,
    "interest_rate": 0.065,
    "expense_ratio": 0.35,
    "hold_period": 5,
    "exit_cap_compression": 0.02
  },
  "scenarios": {
    "bull": { "irr_5yr": 0.0, "noi": 0, "exit_value": 0, "cash_on_cash": 0.0 },
    "base": { "irr_5yr": 0.0, "noi": 0, "exit_value": 0, "cash_on_cash": 0.0 },
    "bear": { "irr_5yr": 0.0, "noi": 0, "exit_value": 0, "cash_on_cash": 0.0 }
  },
  "negotiation_leverage": [],
  "investment_memo": "",

  "deal_context": {
    "property_location": "",
    "asset_class": "multifamily",
    "deal_size": 0,
    "sponsor": ""
  },

  "intelligence_purchases": [
    {
      "provider_did": "did:nvm:...",
      "provider_name": "",
      "cost": 0.0,
      "transaction_id": "",
      "data_received": {},
      "timestamp": ""
    }
  ],

  "market_signals": {
    "intelligence_source": "nevermined | tavily | none",
    "rent_growth": { "answer": "", "sources": [] },
    "cap_rate_trends": { "answer": "", "sources": [] },
    "comparable_sales": { "answer": "", "sources": [] },
    "supply_pipeline": { "answer": "", "sources": [] }
  },

  "scraped_deals": {
    "location": "",
    "loopnet": [],
    "crexi": [],
    "total": 0
  },

  "investor_leads": [],

  "deep_research": {
    "market": "",
    "asset_type": "",
    "topics": {}
  },

  "final_output": {
    "investment_verdict": "",
    "key_risks": [],
    "investment_rationale": ""
  }
}

## Purpose:
- Enable follow-up scenario adjustments
- Avoid recalculation from scratch
- Support "What if?" analysis
- Track intelligence spending across sessions
- Maintain deal pipeline state
- Support agent-to-agent intelligence exchange
