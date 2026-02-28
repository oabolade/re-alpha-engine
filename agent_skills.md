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