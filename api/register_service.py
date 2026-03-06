"""One-time script to register RE Alpha Engine in the Nevermined registry."""

import sys
from config import MONETIZATION_API_URL, NEVERMINED_AGENT_DID
from tools.nevermined_client import register_service, NEVERMINED_AVAILABLE


def main():
    if not NEVERMINED_AVAILABLE:
        print("Error: Nevermined not available. Set NEVERMINED_API_KEY and install payments-py.")
        sys.exit(1)

    if not MONETIZATION_API_URL:
        print("Error: MONETIZATION_API_URL not set. Deploy the API first, then set the URL.")
        sys.exit(1)

    print("Registering RE Alpha Engine in Nevermined registry...")

    did = register_service(
        name="RE Alpha Engine — Multifamily Underwriting Intelligence",
        description=(
            "Institutional-grade multifamily deal underwriting agent. "
            "Accepts raw offering memorandum data and returns normalized rent rolls, "
            "8-step financial modeling (NOI, cap rate, IRR, DSCR), bull/base/bear scenarios, "
            "negotiation leverage points, market intelligence, and investment memos."
        ),
        price=1.0,
        endpoint_url=f"{MONETIZATION_API_URL}/api/v1/analyze",
        metadata={
            "asset_type": "multifamily",
            "capabilities": [
                "rent_roll_normalization",
                "financial_modeling",
                "scenario_analysis",
                "market_intelligence",
                "memo_generation",
                "negotiation_leverage",
            ],
            "response_format": "json",
            "avg_response_time_seconds": 30,
        },
    )

    print(f"Registered successfully.")
    print(f"  DID: {did}")
    print(f"  Endpoint: {MONETIZATION_API_URL}/api/v1/analyze")
    print(f"\nSet NEVERMINED_AGENT_DID={did} in your .env file.")


if __name__ == "__main__":
    main()
