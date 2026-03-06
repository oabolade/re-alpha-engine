"""RE Alpha Engine — CLI entry point for deal analysis."""

import json
import sys
from tools.pdf_extractor import extract_from_pdf
from tools.rent_roll_normalizer import normalize_rent_roll
from tools.financial_engine import run_financial_model, run_scenarios
from tools.memo_generator import generate_memo, generate_negotiation_leverage
from tools.market_intelligence import research_market, format_market_context
from agents.orchestrator import analyze_deal
from config import TAVILY_API_KEY, APIFY_API_KEY


def run_from_json(json_path: str, use_agent: bool = False):
    """Run analysis from a pre-extracted JSON file."""
    with open(json_path) as f:
        raw_data = json.load(f)

    if use_agent:
        print("Running full agent orchestration loop...")
        results = analyze_deal(raw_data)
        print("\n" + "=" * 60)
        if results["memo"]:
            print(results["memo"])
        for msg in results["agent_messages"]:
            print(msg)
        return results

    # Direct pipeline (no agent loop)
    print(f"Analyzing: {raw_data.get('property_name', 'Unknown')}")
    print("=" * 60)

    # Step 1: Normalize
    normalized = normalize_rent_roll(raw_data)
    if normalized["warnings"]:
        print("\nWarnings:")
        for w in normalized["warnings"]:
            print(f"  - {w}")

    # Step 2: Financial Model
    financials = run_financial_model(normalized)
    print(f"\nFinancial Summary:")
    print(f"  NOI:           ${financials['noi']:,.0f}")
    print(f"  Cap Rate:      {financials['cap_rate']:.2%}")
    print(f"  Cash-on-Cash:  {financials['cash_on_cash']:.2%}")
    print(f"  DSCR:          {financials['dscr']:.2f}x")
    print(f"  5-Year IRR:    {financials['irr_5yr']:.2%}" if financials['irr_5yr'] else "  5-Year IRR:    N/A")

    # Step 3: Scenarios
    scenarios = run_scenarios(normalized)
    print(f"\nScenario IRRs:")
    for name, s in scenarios.items():
        irr_str = f"{s['irr_5yr']:.2%}" if s.get('irr_5yr') else "N/A"
        print(f"  {name.capitalize():6s}: {irr_str}")

    # Step 4: Market Intelligence (Nevermined → Tavily)
    market_data = None
    market_context = ""
    if TAVILY_API_KEY:
        print("\nResearching market intelligence...")
        market_data = research_market(normalized.get("address", ""))
        source = market_data.get("intelligence_source", "unknown") if market_data else "none"
        print(f"  Intelligence source: {source}")
        market_context = format_market_context(market_data)
        print(market_context)
    else:
        print("\nSkipping market intelligence (TAVILY_API_KEY not set)")

    # Step 5: Negotiation Leverage
    leverage = generate_negotiation_leverage(normalized, financials)
    print(f"\nNegotiation Leverage:")
    for point in leverage:
        print(f"  - {point}")

    # Step 6: Memo (requires API)
    print("\nGenerating investment memo...")
    memo = generate_memo(normalized, financials, scenarios, leverage, market_context)
    print("\n" + "=" * 60)
    print(memo)

    return {
        "normalized_data": normalized,
        "financial_results": financials,
        "scenario_results": scenarios,
        "negotiation_points": leverage,
        "market_data": market_data,
        "market_context": market_context,
        "memo": memo,
    }


def run_from_pdf(pdf_path: str):
    """Run full pipeline from PDF."""
    print(f"Extracting data from: {pdf_path}")
    raw_data = extract_from_pdf(pdf_path)
    print("Extraction complete. Running analysis...")

    normalized = normalize_rent_roll(raw_data)
    financials = run_financial_model(normalized)
    scenarios = run_scenarios(normalized)

    market_data = None
    market_context = ""
    if TAVILY_API_KEY:
        print("Researching market intelligence...")
        market_data = research_market(normalized.get("address", ""))
        market_context = format_market_context(market_data)

    leverage = generate_negotiation_leverage(normalized, financials)
    memo = generate_memo(normalized, financials, scenarios, leverage, market_context)

    print("\n" + "=" * 60)
    print(memo)

    return {
        "normalized_data": normalized,
        "financial_results": financials,
        "scenario_results": scenarios,
        "negotiation_points": leverage,
        "market_data": market_data,
        "market_context": market_context,
        "memo": memo,
    }


def run_scrape(location: str, asset_type: str = "multifamily"):
    """Scrape live deals from LoopNet and Crexi."""
    if not APIFY_API_KEY:
        print("Error: APIFY_API_KEY not set. Cannot scrape deals.")
        sys.exit(1)

    from tools.deal_scraper import scrape_loopnet_deals, scrape_crexi_deals

    print(f"Scraping {asset_type} deals in {location}...")
    print("=" * 60)

    print("\nLoopNet:")
    loopnet = scrape_loopnet_deals(location, asset_type)
    for d in loopnet:
        if d.get("error"):
            print(f"  Error: {d['error']}")
        else:
            price = f"${d['purchase_price']:,.0f}" if d.get("purchase_price") else "N/A"
            print(f"  {d.get('property_name', 'N/A'):30s} | {price:>15s} | {d.get('address', 'N/A')}")

    print(f"\nCrexi:")
    crexi = scrape_crexi_deals(location, asset_type)
    for d in crexi:
        if d.get("error"):
            print(f"  Error: {d['error']}")
        else:
            price = f"${d['purchase_price']:,.0f}" if d.get("purchase_price") else "N/A"
            print(f"  {d.get('property_name', 'N/A'):30s} | {price:>15s} | {d.get('address', 'N/A')}")

    total = len([d for d in loopnet if not d.get("error")]) + len([d for d in crexi if not d.get("error")])
    print(f"\nTotal: {total} deals found")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python main.py <path-to-json>                        # From extracted JSON")
        print("  python main.py <path-to-json> --agent                # Full agent loop")
        print("  python main.py <path-to-pdf>                         # From PDF (uses Reka)")
        print("  python main.py --scrape --market 'Dallas, TX'        # Scrape live deals")
        sys.exit(1)

    if "--scrape" in sys.argv:
        market_idx = None
        for i, arg in enumerate(sys.argv):
            if arg == "--market" and i + 1 < len(sys.argv):
                market_idx = i + 1
                break
        if market_idx is None:
            print("Error: --scrape requires --market <location>")
            sys.exit(1)
        run_scrape(sys.argv[market_idx])
    else:
        path = sys.argv[1]
        use_agent = "--agent" in sys.argv

        if path.endswith(".pdf"):
            run_from_pdf(path)
        else:
            run_from_json(path, use_agent=use_agent)
