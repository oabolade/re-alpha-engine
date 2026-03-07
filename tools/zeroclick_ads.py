"""ZeroClick AI-native ads — contextual ad offers for RE Alpha."""

import httpx
from config import ZEROCLICK_API_KEY

ZEROCLICK_AVAILABLE = bool(ZEROCLICK_API_KEY)

OFFERS_URL = "https://zeroclick.dev/api/v2/offers"


def fetch_offers(query: str, context: str = "", limit: int = 3) -> list[dict]:
    """Fetch contextual ad offers from ZeroClick.

    Args:
        query: Search query describing the ad context.
        context: Additional context about the user/deal.
        limit: Maximum number of offers to return.

    Returns:
        List of offer dicts with keys: id, title, subtitle, content, cta,
        click_url, image_url, brand.
    """
    if not ZEROCLICK_AVAILABLE:
        return []

    payload = {
        "method": "server",
        "query": query,
        "context": context,
        "limit": limit,
    }

    try:
        resp = httpx.post(
            OFFERS_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {ZEROCLICK_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=5.0,
        )
        resp.raise_for_status()
        data = resp.json()
        offers = data if isinstance(data, list) else data.get("offers", [])
        return offers[:limit]
    except Exception:
        return []


def track_impression(offer_ids: list[str]) -> None:
    """Report impressions back to ZeroClick."""
    if not ZEROCLICK_AVAILABLE or not offer_ids:
        return

    try:
        httpx.post(
            "https://zeroclick.dev/api/v2/impressions",
            json={"offer_ids": offer_ids},
            headers={
                "Authorization": f"Bearer {ZEROCLICK_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=3.0,
        )
    except Exception:
        pass
