"""Nevermined SDK wrapper — agent registration, plan ordering, and intelligence exchange.

Uses payments-py SDK: AgentsAPI for registration, PlansAPI for ordering.
Environments dict maps env names to EnvironmentInfo (backend, proxy URLs).
"""

from typing import Any

from config import NEVERMINED_API_KEY, NEVERMINED_ENVIRONMENT, NEVERMINED_AGENT_DID

NEVERMINED_AVAILABLE = False
_agents_api = None
_plans_api = None

try:
    from payments_py import (
        Environments,
        AgentsAPI,
        PlansAPI,
        PaymentOptions,
        AgentMetadata,
        AgentAPIAttributes,
        PlanMetadata,
    )
    from payments_py import (
        get_fiat_price_config,
        get_fixed_credits_config,
    )
    if NEVERMINED_API_KEY:
        NEVERMINED_AVAILABLE = True
except ImportError:
    pass


def _build_options() -> Any:
    """Build PaymentOptions for the configured environment."""
    env_key = NEVERMINED_ENVIRONMENT if NEVERMINED_ENVIRONMENT in Environments else "sandbox"
    return PaymentOptions(
        environment=env_key,
        nvm_api_key=NEVERMINED_API_KEY,
        app_id="re-alpha-engine",
    )


def get_agents_api() -> Any:
    """Return a cached AgentsAPI instance."""
    global _agents_api
    if _agents_api is not None:
        return _agents_api
    if not NEVERMINED_AVAILABLE:
        raise RuntimeError("Nevermined SDK not available — install payments-py and set NEVERMINED_API_KEY")
    _agents_api = AgentsAPI.get_instance(_build_options())
    return _agents_api


def get_plans_api() -> Any:
    """Return a cached PlansAPI instance."""
    global _plans_api
    if _plans_api is not None:
        return _plans_api
    if not NEVERMINED_AVAILABLE:
        raise RuntimeError("Nevermined SDK not available — install payments-py and set NEVERMINED_API_KEY")
    _plans_api = PlansAPI.get_instance(_build_options())
    return _plans_api


def search_providers(query: str, category: str = "market_intelligence") -> list[dict]:
    """Search for agents/plans via the Nevermined backend API.

    The SDK does not expose a search method directly, so this hits the
    backend REST endpoint for agent discovery.
    Returns list of {did, name, description, price, metadata}.
    """
    if not NEVERMINED_AVAILABLE:
        return []

    try:
        import requests
        env_key = NEVERMINED_ENVIRONMENT if NEVERMINED_ENVIRONMENT in Environments else "sandbox"
        backend = Environments[env_key].backend
        url = f"{backend}/api/v1/agents/search"
        resp = requests.get(
            url,
            params={"q": query, "tags": category},
            headers={
                "Authorization": f"Bearer {NEVERMINED_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()

        providers = []
        for item in (data if isinstance(data, list) else data.get("results", data.get("agents", []))):
            providers.append({
                "did": item.get("did", item.get("id", "")),
                "name": item.get("name", "Unknown Provider"),
                "description": item.get("description", ""),
                "price": item.get("price", 0),
                "metadata": item.get("metadata", {}),
            })
        return providers
    except Exception as e:
        print(f"[Nevermined] Search failed: {e}")
        return [{"error": str(e)}]


def evaluate_providers(providers: list[dict], budget: float) -> list[dict]:
    """Filter and sort providers by price within budget."""
    affordable = [p for p in providers if not p.get("error") and float(p.get("price", 0)) <= budget]
    return sorted(affordable, key=lambda p: float(p.get("price", 0)))


def purchase_intelligence(provider_did: str, query_params: dict) -> dict:
    """Order a plan from a provider and return the result.

    Returns {data, cost, transaction_id, provider_did}.
    """
    if not NEVERMINED_AVAILABLE:
        return {"error": "Nevermined not available", "data": None}

    try:
        plans = get_plans_api()
        result = plans.order_plan(plan_id=provider_did)
        return {
            "data": result,
            "cost": 0,
            "transaction_id": result.get("agreementId", "") if isinstance(result, dict) else "",
            "provider_did": provider_did,
        }
    except Exception as e:
        print(f"[Nevermined] Purchase failed: {e}")
        return {"error": str(e), "data": None, "provider_did": provider_did}


def register_service(
    name: str,
    description: str,
    price: float,
    endpoint_url: str,
    metadata: dict | None = None,
) -> str:
    """Register RE Alpha Engine as an agent in the Nevermined network.

    Creates an agent with a free credits plan and returns the agent DID.
    """
    if not NEVERMINED_AVAILABLE:
        raise RuntimeError("Nevermined not available")

    agents = get_agents_api()
    plans = get_plans_api()

    plan_meta = PlanMetadata(
        name=f"{name} — Analysis Plan",
        description=description,
    )
    price_config = get_fiat_price_config(amount=int(price * 100), receiver=agents.get_account_address() or "")
    credits_config = get_fixed_credits_config(credits_granted=100, credits_per_request=1)

    plan_result = plans.register_credits_plan(plan_meta, price_config, credits_config)
    plan_did = plan_result.get("did", plan_result.get("planDid", ""))

    agent_meta = AgentMetadata(
        name=name,
        description=description,
    )
    agent_api = AgentAPIAttributes(
        endpoints=[{"method": "POST", "url": endpoint_url}],
    )
    result = agents.register_agent(agent_meta, agent_api, payment_plans=[plan_did])
    return result.get("did", result.get("agentDid", str(result)))


def _safe_attr(obj: Any, key: str, default: Any = None) -> Any:
    """Safely get attribute from object or dict."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)
