"""Exa AI-powered deep research — supplementary market intelligence."""

from typing import Any

from config import EXA_API_KEY

EXA_AVAILABLE = False

try:
    from exa_py import Exa
    if EXA_API_KEY:
        EXA_AVAILABLE = True
except ImportError:
    pass

DEFAULT_TOPICS = [
    "economic outlook",
    "population migration",
    "regulatory changes",
    "institutional investor activity",
]


def _get_client() -> Any:
    if not EXA_AVAILABLE:
        raise RuntimeError("Exa not available — install exa-py and set EXA_API_KEY")
    return Exa(api_key=EXA_API_KEY)


def deep_research(
    market: str,
    asset_type: str = "multifamily",
    topics: list[str] | None = None,
) -> dict:
    """Run deep research across multiple topics for a given market.

    Args:
        market: Target market (e.g., "Dallas, TX")
        asset_type: Property type
        topics: Research topics (defaults to DEFAULT_TOPICS)

    Returns:
        {market, asset_type, deep_research: {topic: {query, summary, sources}}}
    """
    if not EXA_AVAILABLE:
        return {
            "market": market,
            "asset_type": asset_type,
            "deep_research": {},
            "error": "Exa not available — EXA_API_KEY not set or exa-py not installed",
        }

    topics = topics or DEFAULT_TOPICS
    client = _get_client()
    research = {}

    for topic in topics:
        query = f"{asset_type} real estate {topic} in {market} 2025 2026"
        try:
            results = client.search_and_contents(
                query=query,
                num_results=5,
                use_autoprompt=True,
                text={"max_characters": 1000},
            )

            sources = []
            summaries = []
            for result in results.results:
                sources.append({
                    "title": result.title or "",
                    "url": result.url or "",
                    "snippet": (result.text or "")[:300],
                })
                if result.text:
                    summaries.append(result.text[:500])

            research[topic] = {
                "query": query,
                "summary": " ".join(summaries)[:1000] if summaries else "No results found.",
                "sources": sources,
            }
        except Exception as e:
            research[topic] = {
                "query": query,
                "summary": "",
                "sources": [],
                "error": str(e),
            }

    return {
        "market": market,
        "asset_type": asset_type,
        "deep_research": research,
    }
