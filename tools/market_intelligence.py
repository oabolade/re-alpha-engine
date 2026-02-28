"""Market Intelligence Layer — Tavily-powered research for micro-market context.

Runs 4 targeted queries after extraction once city/submarket/asset type are known:
  1. Rent growth trends
  2. Cap rate trends
  3. Recent comparable transactions
  4. Supply pipeline risk
"""

import re
from tavily import TavilyClient

from config import TAVILY_API_KEY

CURRENT_YEAR = 2025


def _get_client() -> TavilyClient:
    return TavilyClient(api_key=TAVILY_API_KEY)


def _extract_city_state(address: str) -> tuple[str, str]:
    """Pull city and state from an address string."""
    # Try "City, ST ZIP" or "City, ST"
    match = re.search(r"([A-Za-z\s]+),\s*([A-Z]{2})\s*\d*", address)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    # Fallback: return last two comma-separated parts
    parts = [p.strip() for p in address.split(",")]
    if len(parts) >= 2:
        return parts[-2], parts[-1].split()[0] if parts[-1] else ""
    return address, ""


def research_market(address: str, asset_type: str = "multifamily") -> dict:
    """Run 4 Tavily searches for market intelligence. Returns structured results."""
    city, state = _extract_city_state(address)
    market = f"{city}, {state}" if state else city

    client = _get_client()

    queries = {
        "rent_growth": f"{asset_type} rent growth trends in {market} {CURRENT_YEAR}",
        "cap_rates": f"{asset_type} cap rate trends in {market} {CURRENT_YEAR}",
        "comparable_sales": f"recent {asset_type} apartment building sales transactions in {market} {CURRENT_YEAR}",
        "supply_pipeline": f"new {asset_type} apartment construction pipeline supply in {market} {CURRENT_YEAR} {CURRENT_YEAR + 1}",
    }

    results = {}
    for key, query in queries.items():
        try:
            response = client.search(
                query=query,
                search_depth="basic",
                max_results=5,
                include_answer=True,
            )
            results[key] = {
                "query": query,
                "answer": response.get("answer", ""),
                "sources": [
                    {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")[:300]}
                    for r in response.get("results", [])[:3]
                ],
            }
        except Exception as e:
            results[key] = {"query": query, "answer": "", "sources": [], "error": str(e)}

    return {
        "market": market,
        "asset_type": asset_type,
        "research": results,
    }


def format_market_context(market_data: dict) -> str:
    """Format market research into a concise text block for the memo generator."""
    if not market_data or not market_data.get("research"):
        return "No market intelligence available."

    market = market_data["market"]
    research = market_data["research"]
    sections = []

    sections.append(f"## Market Intelligence: {market} ({market_data['asset_type'].title()})")

    labels = {
        "rent_growth": "Rent Growth Trends",
        "cap_rates": "Cap Rate Trends",
        "comparable_sales": "Recent Comparable Transactions",
        "supply_pipeline": "Supply Pipeline Risk",
    }

    for key, label in labels.items():
        data = research.get(key, {})
        answer = data.get("answer", "")
        if data.get("error"):
            sections.append(f"**{label}:** Data unavailable ({data['error']})")
        elif answer:
            sections.append(f"**{label}:** {answer}")
        else:
            sections.append(f"**{label}:** No data found.")

        sources = data.get("sources", [])
        if sources:
            source_lines = [f"  - [{s['title']}]({s['url']})" for s in sources if s.get("title")]
            if source_lines:
                sections.append("  Sources: " + "; ".join(s["title"] for s in sources if s.get("title")))

    return "\n\n".join(sections)
