"""Market Intelligence Layer — Nevermined-first with Tavily fallback.

Tries Nevermined agent network for market intelligence first.
Falls back to Tavily-powered research if Nevermined unavailable or returns no results.

Runs 4 targeted queries after extraction once city/submarket/asset type are known:
  1. Rent growth trends
  2. Cap rate trends
  3. Recent comparable transactions
  4. Supply pipeline risk
"""

import re
from tavily import TavilyClient

from config import TAVILY_API_KEY, NEVERMINED_API_KEY, INTELLIGENCE_BUDGET_PER_QUERY
from tools.nevermined_client import (
    NEVERMINED_AVAILABLE,
    search_providers,
    evaluate_providers,
    purchase_intelligence,
)

CURRENT_YEAR = 2026


def _get_tavily_client() -> TavilyClient:
    return TavilyClient(api_key=TAVILY_API_KEY)


def _extract_city_state(address: str) -> tuple[str, str]:
    """Pull city and state from an address string."""
    match = re.search(r"([A-Za-z\s]+),\s*([A-Z]{2})\s*\d*", address)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    parts = [p.strip() for p in address.split(",")]
    if len(parts) >= 2:
        return parts[-2], parts[-1].split()[0] if parts[-1] else ""
    return address, ""


def research_market(address: str, asset_type: str = "multifamily") -> dict:
    """Run market intelligence research. Tries Nevermined first, falls back to Tavily.

    Returns structured results including intelligence_source and purchases list.
    """
    city, state = _extract_city_state(address)
    market = f"{city}, {state}" if state else city

    # Try Nevermined first
    nvm_result = _research_via_nevermined(market, asset_type)
    if nvm_result and nvm_result.get("research"):
        return nvm_result

    # Fall back to Tavily
    tavily_result = _research_via_tavily(market, asset_type)
    return tavily_result


def _research_via_nevermined(market: str, asset_type: str) -> dict | None:
    """Attempt to acquire market intelligence via Nevermined agent network."""
    if not NEVERMINED_AVAILABLE or not NEVERMINED_API_KEY:
        return None

    try:
        query = f"{asset_type} market intelligence {market}"
        providers = search_providers(query, category="market_intelligence")

        if not providers or (len(providers) == 1 and providers[0].get("error")):
            return None

        # Evaluate and pick best provider within budget
        affordable = evaluate_providers(providers, INTELLIGENCE_BUDGET_PER_QUERY)
        if not affordable:
            return None

        best = affordable[0]
        result = purchase_intelligence(
            provider_did=best["did"],
            query_params={
                "market": market,
                "asset_type": asset_type,
                "queries": ["rent_growth", "cap_rates", "comparable_sales", "supply_pipeline"],
            },
        )

        if result.get("error") or not result.get("data"):
            return None

        data = result["data"]
        research = data if isinstance(data, dict) else {}

        return {
            "market": market,
            "asset_type": asset_type,
            "research": research.get("research", research),
            "intelligence_source": "nevermined",
            "purchases": [{
                "provider_did": result["provider_did"],
                "provider_name": best.get("name", "Unknown"),
                "cost": result.get("cost", 0),
                "transaction_id": result.get("transaction_id", ""),
            }],
        }
    except Exception:
        return None


def _research_via_tavily(market: str, asset_type: str) -> dict:
    """Fall back to Tavily-powered market research."""
    if not TAVILY_API_KEY:
        return {
            "market": market,
            "asset_type": asset_type,
            "research": {},
            "intelligence_source": "none",
            "purchases": [],
        }

    client = _get_tavily_client()

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
        "intelligence_source": "tavily",
        "purchases": [],
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
