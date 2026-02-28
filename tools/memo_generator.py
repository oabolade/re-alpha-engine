"""Skill 3: Investment Memo Generator — produces institutional-grade memos via Claude."""

import json
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL


MEMO_SYSTEM_PROMPT = """You are an institutional multifamily underwriting analyst.

Generate a concise institutional-grade investment memo based on the provided property data and financial analysis.

## Required Sections

1. **Executive Summary** — 2-3 sentences on the opportunity
2. **Financial Snapshot** — Key metrics table (NOI, Cap Rate, IRR, Cash-on-Cash, DSCR)
3. **Market Context** — Synthesize provided market intelligence (rent growth trends, cap rate environment, comparable sales, supply pipeline). Cite specific data points when available.
4. **Scenario Analysis** — Bull/Base/Bear IRR comparison with key assumptions
5. **Risk Factors** — 3-5 specific, data-backed risks (incorporate market-level risks from research)
6. **Upside Potential** — 2-4 concrete value-add or market-driven opportunities
7. **Negotiation Leverage** — Specific points that give the buyer bargaining power
8. **Investment Verdict** — Clear GO / NO-GO / CONDITIONAL recommendation with rationale

## Rules

- No emojis.
- No hype language.
- No speculative claims beyond stated assumptions.
- Use bullet points for clarity.
- Keep memo under 800 words.
- Use professional underwriting tone.
- Show all assumptions explicitly.
- If data is missing, state it clearly rather than fabricating."""


def generate_memo(
    normalized_data: dict,
    financial_results: dict,
    scenario_results: dict,
    negotiation_points: list[str] | None = None,
    market_context: str = "",
) -> str:
    """Generate an institutional investment memo from analysis results."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    market_section = ""
    if market_context:
        market_section = f"""
Market Intelligence Research:
{market_context}
"""

    user_content = f"""Property Data:
{json.dumps(normalized_data, indent=2)}

Financial Analysis (Base Case):
{json.dumps(financial_results, indent=2)}

Scenario Analysis:
{json.dumps(scenario_results, indent=2)}

Negotiation Leverage Points:
{json.dumps(negotiation_points or [], indent=2)}
{market_section}
Generate the investment memo now. Integrate the market intelligence data into the Market Context section and reference it in Risk Factors and Upside Potential where relevant."""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        system=MEMO_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    return response.content[0].text


def generate_negotiation_leverage(
    normalized_data: dict,
    financial_results: dict,
) -> list[str]:
    """Identify negotiation leverage points from the analysis."""
    points = []

    cap_rate = financial_results.get("cap_rate")
    if cap_rate is not None and cap_rate < 0.05:
        points.append(f"Below-market cap rate ({cap_rate:.1%}) — seller pricing aggressively.")

    vacancy = normalized_data.get("vacancy_rate", 0)
    if vacancy > 0.1:
        points.append(f"Elevated vacancy ({vacancy:.0%}) — negotiate price reduction to reflect lease-up risk.")

    dscr = financial_results.get("dscr")
    if dscr is not None and dscr < 1.25:
        points.append(f"Tight DSCR ({dscr:.2f}x) — lenders may require lower LTV, weakening seller's buyer pool.")

    coc = financial_results.get("cash_on_cash")
    if coc is not None and coc < 0.06:
        points.append(f"Low cash-on-cash ({coc:.1%}) at asking — weak current yield supports price reduction.")

    irr = financial_results.get("irr_5yr")
    if irr is not None and irr < 0.12:
        points.append(f"5-year IRR of {irr:.1%} is below institutional hurdle rates — supports bid below asking.")

    units = normalized_data.get("units", [])
    rents = [u["monthly_rent"] for u in units if u.get("monthly_rent")]
    if rents:
        avg = sum(rents) / len(rents)
        low_units = [u for u in units if u.get("monthly_rent") and u["monthly_rent"] < avg * 0.75]
        if low_units:
            points.append(f"{len(low_units)} units renting 25%+ below average — signals deferred rent increases or problem units.")

    if not points:
        points.append("No significant leverage points identified at current pricing.")

    return points
