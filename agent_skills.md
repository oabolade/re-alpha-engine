# UnderwritingAnalystAgent — Skills

## Skill 1: Rent Roll Normalization

### Input:
Raw JSON output from Reka extraction.

### Responsibilities:
- Validate rent roll structure
- Normalize unit entries
- Detect missing or inconsistent rows
- Compute vacancy rate

### Output Format:

{
  "property_name": "",
  "address": "",
  "purchase_price": 0,
  "total_units": 0,
  "units": [
    {
      "unit_id": "",
      "monthly_rent": 0,
      "occupied": true,
      "square_feet": null
    }
  ],
  "vacancy_rate": 0.0
}

---

## Skill 2: Financial Modeling Engine

### Input:
Normalized rent roll JSON

### Calculations:

1. Gross Annual Rent
2. Effective Gross Income (adjusted for vacancy)
3. Operating Expenses
4. Net Operating Income (NOI)
5. Cap Rate
6. 5-Year IRR
7. Cash-on-Cash Return

### Output:

{
  "gross_annual_rent": 0,
  "effective_gross_income": 0,
  "noi": 0,
  "cap_rate": 0.0,
  "irr_5yr": 0.0,
  "cash_on_cash": 0.0
}

---

## Skill 3: Investment Memo Generator

### Sections Required:

1. Executive Summary
2. Financial Snapshot
3. Risk Factors
4. Upside Potential
5. Exit Outlook
6. Investment Verdict

Tone:
Institutional, analytical, disciplined.

---

## Skill 4 (Optional): Voice Brief Generator

### Output:
45-second spoken summary version of Executive Summary.

Purpose:
Enable Modulate voice narration.

---

## Skill 5: Intelligence Discovery

### Input:
{
  "query": "multifamily market intelligence Dallas TX",
  "category": "market_intelligence"
}

### Process:
Search the Nevermined agent network for intelligence providers matching query and category. Filter by availability, price, and relevance.

### Output:
[
  {
    "did": "did:nvm:...",
    "name": "Provider Name",
    "description": "What they provide",
    "price": 0.50,
    "metadata": {}
  }
]

---

## Skill 6: Provider Evaluation

### Input:
{
  "providers": [<list from Skill 5>],
  "budget": 1.0
}

### Process:
- Filter providers within budget
- Sort by price (lowest first)
- Evaluate relevance to query

### Output:
Sorted list of affordable providers, best first.

---

## Skill 7: Intelligence Purchase

### Input:
{
  "provider_did": "did:nvm:...",
  "query_params": {
    "market": "Dallas, TX",
    "asset_type": "multifamily",
    "queries": ["rent_growth", "cap_rates", "comparable_sales", "supply_pipeline"]
  }
}

### Output:
{
  "data": { <provider-specific intelligence data> },
  "cost": 0.50,
  "transaction_id": "txn_...",
  "provider_did": "did:nvm:..."
}

---

## Skill 8: Market Intelligence Research

### Input:
{
  "address": "1234 Main St, Dallas, TX 75201",
  "asset_type": "multifamily"
}

### Process:
1. Try Nevermined agent network first (Skills 5-7)
2. Fall back to Tavily search if no providers available
3. Run 4 queries: rent_growth, cap_rates, comparable_sales, supply_pipeline

### Output:
{
  "market": "Dallas, TX",
  "asset_type": "multifamily",
  "research": { <4 query results> },
  "intelligence_source": "nevermined" | "tavily" | "none",
  "purchases": [ <purchase receipts if Nevermined> ]
}

---

## Skill 9: Deal Scraping

### Input:
{
  "location": "Dallas, TX",
  "asset_type": "multifamily",
  "max_results": 20
}

### Process:
Scrape LoopNet and Crexi via Apify actors. Normalize listings into standard deal format.

### Output:
{
  "loopnet": [ <normalized deal dicts> ],
  "crexi": [ <normalized deal dicts> ],
  "total": 40
}

Each deal dict:
{
  "source": "loopnet",
  "property_name": "...",
  "address": "...",
  "purchase_price": 0,
  "total_units": 0,
  "asset_type": "multifamily",
  "cap_rate": 0.0,
  "listing_url": "..."
}

---

## Skill 10: Investor Lead Scraping

### Input:
{
  "criteria": {
    "location": "Dallas, TX",
    "asset_type": "multifamily",
    "min_deal_size": 1000000
  },
  "max_results": 10
}

### Output:
[
  {
    "name": "Investor Name",
    "firm": "Firm Name",
    "location": "Dallas, TX",
    "focus_area": "multifamily",
    "contact_url": "https://..."
  }
]

---

## Skill 11: Deep Research (Exa)

### Input:
{
  "market": "Dallas, TX",
  "asset_type": "multifamily",
  "topics": ["economic outlook", "population migration", "regulatory changes", "institutional investor activity"]
}

### Output:
{
  "market": "Dallas, TX",
  "asset_type": "multifamily",
  "deep_research": {
    "economic outlook": {
      "query": "...",
      "summary": "...",
      "sources": [{"title": "...", "url": "...", "snippet": "..."}]
    },
    ...
  }
}

---

## Skill 12: Intelligence Monetization

### Input (via API):
POST /api/v1/analyze
Headers: x-nevermined-agreement-id: <agreement-id>
Body:
{
  "raw_extraction": { <OM data> },
  "assumptions": { <optional overrides> },
  "include_market_intel": true
}

### Process:
1. Verify Nevermined payment agreement
2. Run full underwriting pipeline
3. Store results in S3
4. Return analysis results

### Output:
{
  "job_id": "uuid",
  "status": "completed",
  "normalized_data": {...},
  "financial_results": {...},
  "scenario_results": {...},
  "negotiation_points": [...],
  "market_data": {...},
  "memo": "..."
}
