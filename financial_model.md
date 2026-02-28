# Financial Model Specification — MVP

## Default Assumptions

- Rent Growth: 3% annually
- Hold Period: 5 years
- LTV: 70%
- Interest Rate: 6.5%
- Expense Ratio: 35%
- Exit Cap Compression: 2%

---

## Step 1: Gross Annual Rent

Gross Annual Rent =
Sum(all monthly rents) * 12

---

## Step 2: Effective Gross Income

Effective Gross Income =
Gross Annual Rent * (1 - Vacancy Rate)

---

## Step 3: Operating Expenses

Operating Expenses =
Effective Gross Income * Expense Ratio

---

## Step 4: Net Operating Income (NOI)

NOI =
Effective Gross Income - Operating Expenses

---

## Step 5: Cap Rate

Cap Rate =
NOI / Purchase Price

---

## Step 6: Equity Invested

Equity =
Purchase Price * (1 - LTV)

---

## Step 7: Annual Cash Flow

Debt Service =
Loan Amount * Interest Rate (interest-only assumption for MVP simplicity)

Loan Amount =
Purchase Price * LTV

Annual Cash Flow =
NOI - Debt Service

---

## Step 8: 5-Year IRR

Estimate:
- 3% annual rent growth
- Exit value calculated using:
  Year 5 NOI / (Cap Rate - 2%)

IRR computed using numpy-financial.irr() over projected cash flows:
- Year 0: Negative equity invested (initial outflow)
- Years 1–5: Annual cash flow (with rent growth applied)
- Year 5: Add exit proceeds (Year 5 NOI / exit cap rate) minus loan payoff

---

## Step 9: Scenario Analysis

Run 3 scenarios with these overrides:

| Scenario | Rent Growth | Exit Cap Compression | Vacancy Adj |
|----------|-------------|---------------------|-------------|
| Bull     | 4%          | 3%                  | -2%         |
| Base     | 3%          | 2%                  | 0%          |
| Bear     | 1%          | 0%                  | +5%         |

Each scenario outputs: NOI trajectory, annual cash flows, exit value, IRR.