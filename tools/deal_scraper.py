"""Apify-based deal scraping — uses RAG Web Browser for deal discovery.

Uses apify/rag-web-browser (works on Apify free plan) to search Google
for commercial real estate listings and scrape the result pages.
LoopNet/Crexi dedicated scrapers require paid residential proxies.
"""

import re
from typing import Any
from urllib.parse import quote_plus

from config import APIFY_API_KEY

APIFY_AVAILABLE = False

try:
    from apify_client import ApifyClient
    if APIFY_API_KEY:
        APIFY_AVAILABLE = True
except ImportError:
    pass


def _get_client() -> Any:
    if not APIFY_AVAILABLE:
        raise RuntimeError("Apify not available — install apify-client and set APIFY_API_KEY")
    return ApifyClient(token=APIFY_API_KEY)


def _scrape_via_rag_browser(query: str, max_results: int = 10) -> list[dict]:
    """Run apify/rag-web-browser with a search query and return raw results."""
    client = _get_client()
    print(f"[DealScraper] RAG browser query: {query}")

    run = client.actor("apify/rag-web-browser").call(
        run_input={
            "query": query,
            "maxResults": max_results,
        }
    )

    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    print(f"[DealScraper] RAG browser returned {len(items)} pages")
    return items


def scrape_loopnet_deals(
    location: str,
    asset_type: str = "multifamily",
    max_results: int = 20,
) -> list[dict]:
    """Search for commercial real estate listings via web search.

    Uses apify/rag-web-browser to find deal listings across multiple
    CRE sites (CityFeet, LoopNet, Crexi, etc.) — works on free plan.
    """
    if not APIFY_AVAILABLE:
        return []

    try:
        query = f"{asset_type} apartment buildings for sale in {location}"
        items = _scrape_via_rag_browser(query, max_results=min(max_results, 10))

        deals = []
        for item in items:
            parsed = _parse_rag_result(item, "web-search")
            if parsed:
                deals.append(parsed)
        print(f"[DealScraper] Parsed {len(deals)} deal pages")
        return deals
    except Exception as e:
        print(f"[DealScraper] LoopNet/web error: {e}")
        return [{"error": str(e), "source": "loopnet"}]


def scrape_crexi_deals(
    location: str,
    asset_type: str = "multifamily",
    max_results: int = 20,
) -> list[dict]:
    """Search for additional CRE listings via web search.

    Runs a second query focused on investment properties.
    """
    if not APIFY_AVAILABLE:
        return []

    try:
        query = f"commercial real estate investment properties for sale {location} {asset_type}"
        items = _scrape_via_rag_browser(query, max_results=min(max_results, 5))

        deals = []
        for item in items:
            parsed = _parse_rag_result(item, "web-search")
            if parsed:
                deals.append(parsed)
        print(f"[DealScraper] Parsed {len(deals)} additional deal pages")
        return deals
    except Exception as e:
        print(f"[DealScraper] Crexi/web error: {e}")
        return [{"error": str(e), "source": "crexi"}]


def _parse_rag_result(item: dict, source: str) -> dict | None:
    """Parse an apify/rag-web-browser result into a deal dict."""
    search_result = item.get("searchResult", {})
    metadata = item.get("metadata", {})
    markdown = item.get("markdown", "")

    url = search_result.get("url", metadata.get("url", ""))
    title = search_result.get("title", metadata.get("title", ""))

    if not url or not title:
        return None

    # Skip bot-blocked pages
    if "akamai" in markdown.lower()[:200] or len(markdown) < 100:
        return None

    price = _extract_price_from_text(markdown)
    units = _extract_units_from_text(markdown)
    address = _extract_address_from_text(markdown, title)

    return {
        "source": source,
        "property_name": title[:100],
        "address": address,
        "purchase_price": price,
        "total_units": units,
        "asset_type": "multifamily",
        "cap_rate": None,
        "square_feet": 0,
        "listing_url": url,
        "broker": "",
        "content_preview": markdown[:500] if markdown else "",
        "raw": {"url": url, "title": title, "content_length": len(markdown)},
    }


def scrape_investor_leads(
    criteria: dict,
    max_results: int = 10,
) -> list[dict]:
    """Scrape investor/buyer leads via Google search.

    Uses apify/google-search-scraper to find investor profiles.
    """
    if not APIFY_AVAILABLE:
        return []

    try:
        client = _get_client()
        search_query = f"{criteria.get('asset_type', 'multifamily')} real estate investor {criteria.get('location', '')}"
        run = client.actor("apify/google-search-scraper").call(
            run_input={
                "queries": search_query,
                "maxPagesPerQuery": 1,
                "resultsPerPage": max_results,
            }
        )

        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        leads = []
        for item in items[:max_results]:
            leads.append({
                "name": item.get("title", ""),
                "firm": _extract_firm(item.get("title", "")),
                "location": criteria.get("location", ""),
                "focus_area": criteria.get("asset_type", "multifamily"),
                "contact_url": item.get("url", ""),
            })
        return leads
    except Exception as e:
        return [{"error": str(e), "source": "investor_leads"}]


def _extract_price_from_text(text: str) -> float | None:
    """Try to extract the first price from markdown text."""
    match = re.search(r'\$\s*([\d,]+(?:\.\d+)?)\s*(?:M|million)?', text[:3000])
    if match:
        raw = match.group(1).replace(",", "")
        try:
            val = float(raw)
            if "M" in text[match.start():match.end() + 5] or "million" in text[match.start():match.end() + 10].lower():
                val *= 1_000_000
            return val
        except ValueError:
            pass
    return None


def _extract_units_from_text(text: str) -> int:
    """Try to extract unit count from markdown text."""
    match = re.search(r'(\d+)\s*(?:units?|apts?|apartments?)', text[:3000], re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 0


def _extract_address_from_text(text: str, title: str) -> str:
    """Try to extract an address from markdown text or title."""
    match = re.search(r'\d+\s+[A-Z][a-zA-Z\s]+(?:St|Ave|Blvd|Dr|Rd|Ln|Way|Ct|Cir)[.,]?\s+[A-Z][a-zA-Z\s]+,\s*[A-Z]{2}', text[:2000])
    if match:
        return match.group(0).strip()
    for sep in [" - ", " | ", " — "]:
        if sep in title:
            parts = title.split(sep)
            for part in parts:
                if any(s in part for s in [",", "TX", "CA", "NY", "FL"]):
                    return part.strip()
    return ""


def _parse_price(val: Any) -> float | None:
    """Parse price from string or number."""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = val.replace("$", "").replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _extract_firm(title: str) -> str:
    """Extract firm name from search result title."""
    separators = [" - ", " | ", " — "]
    for sep in separators:
        if sep in title:
            return title.split(sep)[0].strip()
    return title
