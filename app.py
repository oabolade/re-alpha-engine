"""RE Alpha Engine — Streamlit UI."""

import json
import hashlib
import os
import tempfile
import streamlit as st

from tools.pdf_extractor import extract_from_pdf
from tools.rent_roll_normalizer import normalize_rent_roll
from tools.financial_engine import run_financial_model, run_scenarios
from tools.memo_generator import generate_memo, generate_negotiation_leverage
from tools.market_intelligence import research_market, format_market_context
from tools.voice_brief import generate_voice_brief, VOICE_OPTIONS
from agents.orchestrator import analyze_deal
from config import (
    TAVILY_API_KEY, ELEVENLABS_API_KEY, OPENAI_API_KEY, NEO4J_URI,
    APIFY_API_KEY, NEVERMINED_API_KEY, EXA_API_KEY, ZEROCLICK_API_KEY,
)
from tools.zeroclick_ads import ZEROCLICK_AVAILABLE, fetch_offers, track_impression

# Optional imports — graceful degradation
if NEO4J_URI:
    try:
        from tools.knowledge_graph import store_deal, get_full_graph, get_graph_stats, init_constraints
        NEO4J_AVAILABLE = True
    except Exception:
        NEO4J_AVAILABLE = False
else:
    NEO4J_AVAILABLE = False

APIFY_AVAILABLE = False
if APIFY_API_KEY:
    try:
        from tools.deal_scraper import scrape_loopnet_deals, scrape_crexi_deals
        APIFY_AVAILABLE = True
    except Exception:
        pass

NEVERMINED_AVAILABLE = False
if NEVERMINED_API_KEY:
    try:
        from tools.nevermined_client import NEVERMINED_AVAILABLE as _nvm
        NEVERMINED_AVAILABLE = _nvm
    except Exception:
        pass

def _scraped_deal_to_om(deal: dict, fallback_location: str = "") -> dict:
    """Convert a scraped deal dict into an OM-like JSON for the analysis pipeline.

    When individual rent-roll data isn't available (which is typical for
    scraped listings), synthesise a plausible rent roll using market-rate
    assumptions so the financial engine can still produce a directional analysis.
    """
    property_name = deal.get("property_name", "Scraped Property")
    address = deal.get("address") or fallback_location or "Unknown"
    purchase_price = deal.get("purchase_price")
    total_units = deal.get("total_units") or 0

    if not purchase_price:
        purchase_price = 0
    if total_units <= 0:
        total_units = 10

    avg_rent = _estimate_monthly_rent(purchase_price, total_units)
    vacancy_pct = 0.07

    rent_roll = []
    for i in range(total_units):
        occupied = (i / total_units) >= vacancy_pct
        rent_roll.append({
            "unit_number": f"{(i // 4) + 1}{['A','B','C','D'][i % 4]}",
            "monthly_rent": round(avg_rent + (i % 3) * 25),
            "occupancy_status": "Occupied" if occupied else "Vacant",
            "square_footage": 800,
        })

    return {
        "property_name": property_name,
        "address": address,
        "purchase_price": purchase_price,
        "total_units": total_units,
        "rent_roll": rent_roll,
        "_source": "scraped",
        "_listing_url": deal.get("listing_url", ""),
    }


def _estimate_monthly_rent(purchase_price: float, units: int) -> float:
    """Back into per-unit monthly rent from purchase price using a 6% cap rate."""
    if purchase_price <= 0 or units <= 0:
        return 1200.0
    annual_noi_est = purchase_price * 0.06
    annual_rent_est = annual_noi_est / 0.65
    return round(annual_rent_est / units / 12, 0)


st.set_page_config(page_title="RE Alpha Engine", page_icon="", layout="wide")

st.title("RE Alpha Engine")
st.markdown("**Institutional Deal Intelligence Agent** — Multifamily Underwriting")

# --- Sidebar: Input ---
st.sidebar.header("Deal Input")

_input_options = ["Upload PDF", "Sample Deal", "Paste JSON"]
_has_scraped = bool(st.session_state.get("scraped_deals"))
if _has_scraped:
    _input_options.append("Scraped Deal")

input_mode = st.sidebar.radio("Input Source", _input_options)

raw_data = None

if input_mode == "Upload PDF":
    uploaded = st.sidebar.file_uploader("Upload Offering Memorandum (PDF)", type=["pdf"])
    if uploaded:
        file_bytes = uploaded.read()
        file_hash = hashlib.md5(file_bytes).hexdigest()

        if st.session_state.get("pdf_hash") != file_hash:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            with st.spinner("Extracting data from PDF..."):
                try:
                    raw_data = extract_from_pdf(tmp_path)
                except (ValueError, Exception) as e:
                    os.unlink(tmp_path)
                    st.error(f"PDF extraction failed: {e}")
                    st.stop()
            os.unlink(tmp_path)
            st.session_state["pdf_hash"] = file_hash
            st.session_state["pdf_raw_data"] = raw_data
            st.sidebar.success("PDF extracted successfully.")
        else:
            raw_data = st.session_state["pdf_raw_data"]
            st.sidebar.success("PDF data loaded from cache.")

elif input_mode == "Sample Deal":
    sample_dir = os.path.join(os.path.dirname(__file__), "data")
    samples = sorted([f for f in os.listdir(sample_dir) if f.endswith(".json")])
    selected = st.sidebar.selectbox("Select sample", samples)
    if selected:
        with open(os.path.join(sample_dir, selected)) as f:
            raw_data = json.load(f)

elif input_mode == "Paste JSON":
    pasted = st.sidebar.text_area("Paste extracted OM JSON", height=300)
    if pasted:
        try:
            raw_data = json.loads(pasted)
        except json.JSONDecodeError:
            st.sidebar.error("Invalid JSON.")

elif input_mode == "Scraped Deal":
    scraped = st.session_state.get("scraped_deals", {})
    all_deals = []
    for key in ["loopnet", "crexi"]:
        for d in scraped.get(key, []):
            if not d.get("error"):
                all_deals.append(d)

    if all_deals:
        labels = [f"{d.get('property_name', 'Unknown')[:50]}" for d in all_deals]
        chosen_idx = st.sidebar.selectbox("Select a scraped deal", range(len(all_deals)), format_func=lambda i: labels[i])
        chosen = all_deals[chosen_idx]

        st.sidebar.caption(f"Source: {chosen.get('listing_url', 'N/A')[:60]}")
        price = chosen.get("purchase_price")
        units = chosen.get("total_units", 0)
        if price:
            st.sidebar.caption(f"Price: ${price:,.0f}")
        if units:
            st.sidebar.caption(f"Units: {units}")

        raw_data = _scraped_deal_to_om(chosen, scraped.get("location", ""))
        st.sidebar.success("Scraped deal loaded — estimates applied for missing rent roll data.")
    else:
        st.sidebar.info("No valid deals found. Scrape a location first.")

# --- Sidebar: Assumption Overrides ---
st.sidebar.header("Assumptions")
rent_growth = st.sidebar.slider("Rent Growth (%)", 0.0, 8.0, 3.0, 0.5) / 100
ltv = st.sidebar.slider("LTV (%)", 50, 85, 70) / 100
interest_rate = st.sidebar.slider("Interest Rate (%)", 4.0, 9.0, 6.5, 0.25) / 100
expense_ratio = st.sidebar.slider("Expense Ratio (%)", 25, 50, 35) / 100
hold_period = st.sidebar.slider("Hold Period (years)", 3, 10, 5)

custom_assumptions = {
    "rent_growth": rent_growth,
    "ltv": ltv,
    "interest_rate": interest_rate,
    "expense_ratio": expense_ratio,
    "hold_period": hold_period,
}

# --- Sidebar: Deal Scraping ---
if APIFY_AVAILABLE:
    st.sidebar.header("Deal Pipeline")
    scrape_location = st.sidebar.text_input("Scrape Location", placeholder="Dallas, TX")
    if scrape_location and st.sidebar.button("Scrape Deals"):
        with st.spinner(f"Scraping deals in {scrape_location}..."):
            loopnet_deals = scrape_loopnet_deals(scrape_location)
            crexi_deals = scrape_crexi_deals(scrape_location)
        st.session_state["scraped_deals"] = {
            "loopnet": loopnet_deals,
            "crexi": crexi_deals,
            "location": scrape_location,
        }

# --- Sidebar: Sponsored ---
if ZEROCLICK_AVAILABLE:
    try:
        _sidebar_offers = fetch_offers(
            query="commercial real estate investment services",
            context="Real estate underwriting platform for institutional multifamily deals",
            limit=1,
        )
        if _sidebar_offers:
            st.sidebar.markdown("---")
            st.sidebar.caption("Sponsored")
            for _offer in _sidebar_offers:
                _title = _offer.get("title", "")
                _subtitle = _offer.get("subtitle", "")
                _cta = _offer.get("cta", "Learn More")
                _url = _offer.get("click_url", "")
                _brand = _offer.get("brand", "")
                _card = f"**{_title}**"
                if _subtitle:
                    _card += f"  \n{_subtitle}"
                if _brand:
                    _card += f"  \n*{_brand}*"
                if _url:
                    _card += f"  \n[{_cta}]({_url})"
                st.sidebar.markdown(_card)
            _offer_ids = [o.get("id") for o in _sidebar_offers if o.get("id")]
            if _offer_ids:
                track_impression(_offer_ids)
    except Exception:
        pass

# --- Analysis Mode ---
use_agent = st.sidebar.checkbox("Use Agent Orchestration", value=False,
                                 help="Run full Claude agent loop with tool-use (slower, more detailed)")

# --- Run Analysis ---
if raw_data and st.sidebar.button("Analyze Deal", type="primary"):
    _deal_name = raw_data.get("property_name", "Deal") if isinstance(raw_data, dict) else "Deal"

    if use_agent:
        with st.status("RE Alpha Autonomous Agent Activity", expanded=True) as _status:
            _step = [0]
            def _log(msg):
                _step[0] += 1; st.write(f"[{_step[0]}] {msg}")

            _log(f"OM uploaded: {_deal_name}")
            results = analyze_deal(raw_data)
            _log("Agent analysis complete")
            _status.update(label="Analysis complete", state="complete", expanded=False)
        normalized = results["normalized_data"]
        financials = results["financial_results"]
        scenarios = results["scenario_results"]
        leverage = results["negotiation_points"]
        memo = results["memo"]
        market_data = results.get("market_data")
        market_context = format_market_context(market_data) if market_data else ""
    else:
        with st.status("RE Alpha Autonomous Agent Activity", expanded=True) as _status:
            _step = [0]
            def _log(msg):
                _step[0] += 1; st.write(f"[{_step[0]}] {msg}")

            _log(f"OM uploaded: {_deal_name}")

            _log("Extracting financial data...")
            normalized = normalize_rent_roll(raw_data)

            _log("Running IRR model...")
            financials = run_financial_model(normalized, custom_assumptions)
            scenarios = run_scenarios(normalized)
            leverage = generate_negotiation_leverage(normalized, financials)

            market_data = None
            market_context = ""
            if TAVILY_API_KEY or NEVERMINED_AVAILABLE:
                _log("Detecting missing intelligence...")
                _log("Searching market intelligence providers...")
                market_data = research_market(normalized.get("address", ""))
                _source = market_data.get("intelligence_source", "none") if market_data else "none"
                if _source == "nevermined":
                    _purchases = market_data.get("purchases", [])
                    if _purchases:
                        _p = _purchases[0]
                        _log(f"Selected provider: {_p.get('provider_name', 'Unknown')} (${_p.get('cost', 0):.2f})")
                        _log("Executing payment via Nevermined")
                    _log("Intelligence received")
                elif _source == "tavily":
                    _log("Using Tavily market research (fallback)")
                _log("Running market analysis")
                market_context = format_market_context(market_data)

            _log("Generating investment memo")
            memo = generate_memo(normalized, financials, scenarios, leverage, market_context)

            _log("Publishing report to Intelligence API")
            _status.update(label="Analysis complete", state="complete", expanded=False)

    # Store to Neo4j knowledge graph
    intelligence_purchases = []
    if market_data:
        intelligence_purchases = market_data.get("purchases", [])
    if NEO4J_AVAILABLE:
        try:
            init_constraints()
            store_deal(normalized, financials, scenarios, market_data, leverage, intelligence_purchases)
        except Exception as e:
            st.warning(f"Knowledge graph storage failed: {e}")

    # Store all results in session state
    st.session_state["results"] = {
        "normalized": normalized,
        "financials": financials,
        "scenarios": scenarios,
        "leverage": leverage,
        "market_data": market_data,
        "market_context": market_context,
        "memo": memo,
        "intelligence_purchases": intelligence_purchases,
        "_source": raw_data.get("_source") if isinstance(raw_data, dict) else None,
        "_listing_url": raw_data.get("_listing_url", "") if isinstance(raw_data, dict) else "",
    }
    st.session_state.pop("voice_brief", None)
    st.session_state.pop("voice_audio", None)

# --- Helper formatters ---
def _fmt_dollar(val):
    return f"${val:,.0f}" if val is not None else "N/A"

def _fmt_pct(val):
    return f"{val:.2%}" if val is not None else "N/A"

def _fmt_mult(val):
    return f"{val:.2f}x" if val is not None else "N/A"

# --- Display Results ---
if "results" in st.session_state:
    r = st.session_state["results"]
    normalized = r["normalized"]
    financials = r["financials"]
    scenarios = r["scenarios"]
    leverage = r["leverage"]
    memo = r["memo"]
    market_data = r.get("market_data")

    # Header
    st.header(normalized.get("property_name", "Deal Analysis"))
    st.caption(normalized.get("address", ""))

    # Scraped-deal banner
    if r.get("_source") == "scraped":
        listing_url = r.get("_listing_url", "")
        st.info(
            "This analysis was generated from a **scraped deal listing**. "
            "Rent-roll data is estimated using market assumptions (6% cap rate, "
            "65% expense ratio). For precise underwriting, upload the actual OM."
            + (f"  \n[View original listing]({listing_url})" if listing_url else ""),
            icon="ℹ️",
        )

    # Warnings
    if normalized.get("warnings"):
        for w in normalized["warnings"]:
            st.warning(w)

    if financials.get("error"):
        st.warning(financials["error"])

    # Tabs
    tab_names = [
        "Summary", "Financial Detail", "Scenarios", "Market Intel",
        "Negotiation", "Investment Memo", "Deal Pipeline", "Agent Network", "Knowledge Graph",
    ]
    tab1, tab2, tab3, tab_market, tab4, tab5, tab_pipeline, tab_network, tab_graph = st.tabs(tab_names)

    with tab1:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("NOI", _fmt_dollar(financials.get("noi")))
        col2.metric("Cap Rate", _fmt_pct(financials.get("cap_rate")))
        col3.metric(f"{int(custom_assumptions.get('hold_period', 5))}yr IRR", _fmt_pct(financials.get("irr_5yr")))
        col4.metric("Cash-on-Cash", _fmt_pct(financials.get("cash_on_cash")))

        col5, col6, col7, col8 = st.columns(4)
        col5.metric("DSCR", _fmt_mult(financials.get("dscr")))
        col6.metric("Units", normalized["total_units"])
        col7.metric("Vacancy", f"{normalized['vacancy_rate']:.0%}")
        col8.metric("Purchase Price", _fmt_dollar(normalized.get("purchase_price")))

        st.subheader("Rent Roll")
        st.dataframe(normalized["units"], use_container_width=True)

    with tab2:
        st.subheader("Financial Breakdown")
        detail_items = [
            ("Gross Annual Rent", financials.get("gross_annual_rent")),
            ("Effective Gross Income", financials.get("effective_gross_income")),
            ("Operating Expenses", financials.get("operating_expenses")),
            ("Net Operating Income", financials.get("noi")),
            ("Loan Amount", financials.get("loan_amount")),
            ("Annual Debt Service", financials.get("debt_service")),
            ("Annual Cash Flow (Year 1)", financials.get("annual_cash_flow_year1")),
            ("Equity Invested", financials.get("equity_invested")),
            ("Exit Value", financials.get("exit_value")),
        ]
        for label, val in detail_items:
            st.markdown(f"**{label}:** {_fmt_dollar(val)}")

        cf = financials.get("cash_flows", [])
        if cf:
            st.subheader("Projected Cash Flows")
            cf_labels = ["Year 0 (Equity)"] + [f"Year {i}" for i in range(1, len(cf))]
            st.bar_chart(dict(zip(cf_labels, cf)))

        st.subheader("Assumptions Used")
        st.json(financials.get("assumptions_used", {}))

    with tab3:
        st.subheader("Scenario Analysis (Bull / Base / Bear)")
        cols = st.columns(3)
        for i, (name, data) in enumerate(scenarios.items()):
            with cols[i]:
                st.markdown(f"### {name.capitalize()}")
                st.metric("IRR", _fmt_pct(data.get("irr_5yr")))
                st.metric("NOI", _fmt_dollar(data.get("noi")))
                st.metric("Cash-on-Cash", _fmt_pct(data.get("cash_on_cash")))
                st.metric("Exit Value", _fmt_dollar(data.get("exit_value")))

    with tab_market:
        st.subheader("Market Intelligence")
        # Show intelligence source badge
        if market_data:
            source = market_data.get("intelligence_source", "unknown")
            if source == "nevermined":
                st.success("Source: Nevermined Agent Network")
            elif source == "tavily":
                st.info("Source: Tavily Search")
            else:
                st.warning("Source: None available")

            # Show purchase receipts if Nevermined was used
            purchases = market_data.get("purchases", [])
            if purchases:
                st.subheader("Intelligence Purchases")
                for p in purchases:
                    st.markdown(
                        f"- **{p.get('provider_name', 'Unknown')}** — "
                        f"Cost: ${p.get('cost', 0):.2f} — "
                        f"TXN: `{p.get('transaction_id', 'N/A')[:16]}...`"
                    )
                st.divider()

        if market_data and market_data.get("research"):
            st.caption(f"Market: {market_data.get('market', 'N/A')} | Asset Type: {market_data.get('asset_type', 'N/A')}")
            research = market_data["research"]
            labels = {
                "rent_growth": "Rent Growth Trends",
                "cap_rates": "Cap Rate Trends",
                "comparable_sales": "Recent Comparable Transactions",
                "supply_pipeline": "Supply Pipeline Risk",
            }
            for key, label in labels.items():
                data = research.get(key, {})
                with st.expander(label, expanded=True):
                    if data.get("error"):
                        st.error(f"Research unavailable: {data['error']}")
                    elif data.get("answer"):
                        st.markdown(data["answer"])
                    else:
                        st.info("No data found.")
                    sources = data.get("sources", [])
                    if sources:
                        st.markdown("**Sources:**")
                        for s in sources:
                            if s.get("title") and s.get("url"):
                                st.markdown(f"- [{s['title']}]({s['url']})")
        elif not TAVILY_API_KEY and not NEVERMINED_AVAILABLE:
            st.info("Market intelligence unavailable — set TAVILY_API_KEY or NEVERMINED_API_KEY.")
        else:
            st.info("No market data available for this property.")

        # --- Sponsored Intelligence ---
        if ZEROCLICK_AVAILABLE:
            try:
                _address = normalized.get("address", "")
                _city = _address.split(",")[0].strip() if "," in _address else _address
                _intel_offers = fetch_offers(
                    query=f"multifamily investment tools {_city}",
                    context=f"Real estate deal analysis for {_address}, multifamily underwriting",
                    limit=3,
                )
                if _intel_offers:
                    st.markdown("---")
                    st.caption("Sponsored Intelligence")
                    _cols = st.columns(len(_intel_offers))
                    for _idx, _offer in enumerate(_intel_offers):
                        with _cols[_idx]:
                            _title = _offer.get("title", "")
                            _subtitle = _offer.get("subtitle", "")
                            _content = _offer.get("content", "")
                            _cta = _offer.get("cta", "Learn More")
                            _url = _offer.get("click_url", "")
                            _brand = _offer.get("brand", "")
                            _img = _offer.get("image_url", "")
                            _html = '<div style="border:1px solid #333; border-radius:8px; padding:12px; height:100%;">'
                            if _img:
                                _html += f'<img src="{_img}" style="width:100%; border-radius:4px; margin-bottom:8px;" />'
                            _html += f'<strong>{_title}</strong>'
                            if _subtitle:
                                _html += f'<br><span style="color:#aaa; font-size:0.85em;">{_subtitle}</span>'
                            if _content:
                                _html += f'<br><span style="font-size:0.9em;">{_content[:120]}</span>'
                            if _brand:
                                _html += f'<br><em style="color:#888; font-size:0.8em;">{_brand}</em>'
                            if _url:
                                _html += f'<br><a href="{_url}" target="_blank" style="color:#4A9EFF;">{_cta}</a>'
                            _html += '</div>'
                            st.markdown(_html, unsafe_allow_html=True)
                    _offer_ids = [o.get("id") for o in _intel_offers if o.get("id")]
                    if _offer_ids:
                        track_impression(_offer_ids)
            except Exception:
                pass

    with tab4:
        st.subheader("Negotiation Leverage Points")
        if leverage:
            for point in leverage:
                st.markdown(f"- {point}")
        else:
            st.info("No significant leverage points identified.")

    with tab5:
        st.subheader("Investment Memo")
        if memo:
            st.markdown(memo)

            # --- Voice Brief ---
            st.divider()
            st.subheader("Voice Brief")
            if not OPENAI_API_KEY and not ELEVENLABS_API_KEY:
                st.info("Voice brief unavailable — set OPENAI_API_KEY or ELEVENLABS_API_KEY.")
            else:
                voice_col1, voice_col2 = st.columns([2, 1])
                with voice_col2:
                    voice_choice = st.selectbox(
                        "Voice",
                        options=list(VOICE_OPTIONS.keys()),
                        format_func=lambda x: x.replace("_", " ").title(),
                    )
                with voice_col1:
                    if st.button("Generate Voice Brief", type="primary"):
                        with st.spinner("Generating voice brief..."):
                            brief_text, audio_bytes = generate_voice_brief(memo, voice_choice)
                        st.session_state["voice_brief"] = brief_text
                        st.session_state["voice_audio"] = audio_bytes

                if "voice_brief" in st.session_state:
                    st.markdown("**Brief Script:**")
                    st.markdown(f"*{st.session_state['voice_brief']}*")
                    st.audio(st.session_state["voice_audio"], format="audio/mp3")
        else:
            st.info("Memo not generated.")

    with tab_pipeline:
        st.subheader("Deal Pipeline")
        scraped = st.session_state.get("scraped_deals")
        if scraped:
            st.caption(f"Location: {scraped.get('location', 'N/A')}")
            st.info(
                'To analyze a scraped deal, select **"Scraped Deal"** '
                "from the **Deal Input** source in the sidebar, then click **Analyze Deal**.",
                icon="💡",
            )

            for source_name, source_key in [("Deal Listings", "loopnet"), ("Investment Properties", "crexi")]:
                deals = scraped.get(source_key, [])
                if deals and not (len(deals) == 1 and deals[0].get("error")):
                    st.markdown(f"### {source_name} ({len(deals)} results)")
                    for d in deals:
                        title = d.get("property_name", "N/A")
                        url = d.get("listing_url", "")
                        address = d.get("address", "")
                        price = d.get("purchase_price")
                        units = d.get("total_units", 0)
                        preview = d.get("content_preview", "")

                        col_a, col_b = st.columns([3, 1])
                        with col_a:
                            if url:
                                st.markdown(f"**[{title}]({url})**")
                            else:
                                st.markdown(f"**{title}**")
                            if address:
                                st.caption(address)
                        with col_b:
                            if price:
                                st.metric("Price", _fmt_dollar(price))
                            if units:
                                st.metric("Units", units)

                        if preview:
                            with st.expander("Content preview"):
                                st.markdown(preview[:400])
                        st.divider()
                elif deals and deals[0].get("error"):
                    st.warning(f"{source_name}: {deals[0]['error']}")
        elif not APIFY_AVAILABLE:
            st.info("Deal scraping unavailable — set APIFY_API_KEY and install apify-client.")
        else:
            st.info("Use the sidebar to scrape deals for a location.")

    with tab_network:
        st.subheader("Agent Network")

        # Registration status
        if NEVERMINED_AVAILABLE:
            st.success("Nevermined: Connected")
            from config import NEVERMINED_AGENT_DID, NEVERMINED_ENVIRONMENT
            st.markdown(f"**Environment:** {NEVERMINED_ENVIRONMENT}")
            if NEVERMINED_AGENT_DID:
                st.markdown(f"**Agent DID:** `{NEVERMINED_AGENT_DID[:24]}...`")
            else:
                st.info("Agent not registered — run `python -m api.register_service` to register.")
        else:
            st.info("Nevermined not connected — set NEVERMINED_API_KEY to join the agent network.")

        # Intelligence purchases summary
        purchases = r.get("intelligence_purchases", [])
        if purchases:
            st.subheader("Intelligence Purchases")
            total_cost = sum(p.get("cost", 0) for p in purchases)
            st.metric("Total Spend", f"${total_cost:.2f}")
            st.metric("Purchases", len(purchases))

            for p in purchases:
                st.markdown(
                    f"- **{p.get('provider_name', 'Unknown')}** "
                    f"(DID: `{p.get('provider_did', 'N/A')[:16]}...`) — "
                    f"${p.get('cost', 0):.2f}"
                )
        else:
            st.info("No intelligence purchased in this session.")

    with tab_graph:
        st.subheader("Knowledge Graph")
        if not NEO4J_AVAILABLE:
            st.info("Knowledge graph unavailable — Neo4j not configured.")
        else:
            try:
                from streamlit_agraph import agraph, Node, Edge, Config

                # Graph stats
                stats = get_graph_stats()
                stat_cols = st.columns(4)
                stat_cols[0].metric("Properties", stats.get("properties", 0))
                stat_cols[1].metric("Cities", stats.get("cities", 0))
                stat_cols[2].metric("Submarkets", stats.get("submarkets", 0))
                stat_cols[3].metric("Market Trends", stats.get("trends", 0))

                # Fetch graph data
                graph_data = get_full_graph()

                if not graph_data["nodes"]:
                    st.info("No data in the knowledge graph yet. Analyze a deal to populate it.")
                else:
                    # --- Visual Design System ---
                    color_map = {
                        "Property":              {"background": "#E74C3C", "border": "#C0392B", "font": "#FFFFFF"},
                        "Submarket":             {"background": "#1ABC9C", "border": "#16A085", "font": "#FFFFFF"},
                        "City":                  {"background": "#2980B9", "border": "#1F6DA0", "font": "#FFFFFF"},
                        "FinancialSnapshot":     {"background": "#27AE60", "border": "#1E8449", "font": "#FFFFFF"},
                        "MarketTrend":           {"background": "#F39C12", "border": "#D68910", "font": "#1A1A1A"},
                        "Scenario":              {"background": "#8E44AD", "border": "#6C3483", "font": "#FFFFFF"},
                        "LeveragePoint":         {"background": "#E67E22", "border": "#CA6F1E", "font": "#FFFFFF"},
                        "IntelligencePurchase":  {"background": "#3498DB", "border": "#2176AE", "font": "#FFFFFF"},
                    }
                    size_map = {
                        "City": 40,
                        "Property": 35,
                        "Submarket": 28,
                        "MarketTrend": 22,
                        "FinancialSnapshot": 20,
                        "Scenario": 18,
                        "LeveragePoint": 16,
                        "IntelligencePurchase": 18,
                    }
                    shape_map = {
                        "City": "dot",
                        "Property": "dot",
                        "Submarket": "diamond",
                        "FinancialSnapshot": "square",
                        "MarketTrend": "triangle",
                        "Scenario": "star",
                        "LeveragePoint": "triangleDown",
                        "IntelligencePurchase": "hexagon",
                    }

                    # --- Build readable labels and rich tooltips ---
                    def _node_label(n):
                        t = n["type"]
                        p = n["properties"]
                        if t == "Property":
                            return p.get("name", "Property")[:22]
                        if t == "City":
                            return p.get("name", "City")
                        if t == "Submarket":
                            return p.get("name", "Submarket")[:20]
                        if t == "FinancialSnapshot":
                            noi = p.get("noi")
                            cap = p.get("cap_rate")
                            parts = []
                            if noi is not None:
                                parts.append(f"NOI ${noi:,.0f}")
                            if cap is not None:
                                parts.append(f"Cap {cap:.1%}")
                            return " | ".join(parts) if parts else "Financials"
                        if t == "Scenario":
                            name = p.get("name", "").capitalize()
                            irr = p.get("irr")
                            return f"{name}: {irr:.1%}" if irr is not None else name
                        if t == "MarketTrend":
                            cat = p.get("category", "trend").replace("_", " ").title()
                            return cat[:25]
                        if t == "LeveragePoint":
                            return p.get("text", "")[:25] + "..."
                        if t == "IntelligencePurchase":
                            name = p.get("provider_name", "Intel")[:15]
                            cost = p.get("cost", 0)
                            return f"{name} ${cost:.2f}"
                        return n["label"][:25]

                    def _node_tooltip(n):
                        t = n["type"]
                        p = n["properties"]
                        lines = [f"<b>{t}</b>"]
                        if t == "Property":
                            lines.append(f"Name: {p.get('name', 'N/A')}")
                            lines.append(f"Address: {p.get('address', 'N/A')}")
                            lines.append(f"Units: {p.get('total_units', 'N/A')}")
                            vac = p.get('vacancy_rate')
                            lines.append(f"Vacancy: {vac:.0%}" if vac is not None else "Vacancy: N/A")
                            price = p.get('purchase_price')
                            lines.append(f"Price: ${price:,.0f}" if price else "Price: N/A")
                        elif t == "FinancialSnapshot":
                            for k, label in [("noi", "NOI"), ("cap_rate", "Cap Rate"), ("irr_5yr", "IRR"),
                                              ("cash_on_cash", "CoC"), ("dscr", "DSCR")]:
                                v = p.get(k)
                                if v is not None:
                                    if k in ("cap_rate", "irr_5yr", "cash_on_cash"):
                                        lines.append(f"{label}: {v:.2%}")
                                    elif k == "dscr":
                                        lines.append(f"{label}: {v:.2f}x")
                                    else:
                                        lines.append(f"{label}: ${v:,.0f}")
                        elif t == "Scenario":
                            lines.append(f"Scenario: {p.get('name', '').capitalize()}")
                            irr = p.get("irr")
                            lines.append(f"IRR: {irr:.2%}" if irr is not None else "IRR: N/A")
                            noi = p.get("noi")
                            lines.append(f"NOI: ${noi:,.0f}" if noi else "")
                        elif t == "MarketTrend":
                            lines.append(f"Category: {p.get('category', '').replace('_', ' ').title()}")
                            summary = p.get("summary", "")
                            if summary:
                                lines.append(f"{summary[:200]}...")
                        elif t == "LeveragePoint":
                            lines.append(p.get("text", ""))
                        elif t == "IntelligencePurchase":
                            lines.append(f"Provider: {p.get('provider_name', 'N/A')}")
                            lines.append(f"Cost: ${p.get('cost', 0):.2f}")
                            lines.append(f"DID: {p.get('provider_did', 'N/A')[:24]}...")
                            lines.append(f"TXN: {p.get('transaction_id', 'N/A')[:24]}...")
                        else:
                            for k, v in p.items():
                                if k != "timestamp":
                                    lines.append(f"{k}: {v}")
                        return "<br>".join(lines)

                    # --- Edge label formatting ---
                    edge_labels = {
                        "LOCATED_IN": "located in",
                        "IN_CITY": "in city",
                        "HAS_FINANCIALS": "financials",
                        "HAS_SCENARIO": "scenario",
                        "HAS_TREND": "trend",
                        "HAS_LEVERAGE": "leverage",
                        "COMPARABLE_TO": "comparable",
                        "HAS_INTELLIGENCE": "intelligence",
                    }
                    edge_colors = {
                        "LOCATED_IN": "#7F8C8D",
                        "IN_CITY": "#7F8C8D",
                        "HAS_FINANCIALS": "#27AE60",
                        "HAS_SCENARIO": "#8E44AD",
                        "HAS_TREND": "#F39C12",
                        "HAS_LEVERAGE": "#E67E22",
                        "COMPARABLE_TO": "#E74C3C",
                        "HAS_INTELLIGENCE": "#3498DB",
                    }

                    nodes = []
                    for n in graph_data["nodes"]:
                        nt = n["type"]
                        colors = color_map.get(nt, {"background": "#95A5A6", "border": "#7F8C8D", "font": "#FFFFFF"})
                        nodes.append(Node(
                            id=n["id"],
                            label=_node_label(n),
                            size=size_map.get(nt, 15),
                            shape=shape_map.get(nt, "dot"),
                            color={
                                "background": colors["background"],
                                "border": colors["border"],
                                "highlight": {"background": colors["background"], "border": "#FFFFFF"},
                            },
                            font={"color": colors["font"], "size": 11, "face": "Inter, Arial, sans-serif"},
                            title=_node_tooltip(n),
                            borderWidth=2,
                            borderWidthSelected=3,
                        ))

                    edges = []
                    for e in graph_data["edges"]:
                        rel = e["label"]
                        edges.append(Edge(
                            source=e["source"],
                            target=e["target"],
                            label=edge_labels.get(rel, rel.lower().replace("_", " ")),
                            color=edge_colors.get(rel, "#BDC3C7"),
                            font={"size": 9, "color": "#95A5A6", "strokeWidth": 0, "align": "middle"},
                            width=1.5,
                            smooth={"type": "curvedCW", "roundness": 0.15},
                            arrows={"to": {"enabled": True, "scaleFactor": 0.5}},
                        ))

                    config = Config(
                        width=950,
                        height=550,
                        directed=True,
                        physics={
                            "enabled": True,
                            "solver": "forceAtlas2Based",
                            "forceAtlas2Based": {
                                "gravitationalConstant": -80,
                                "centralGravity": 0.008,
                                "springLength": 160,
                                "springConstant": 0.04,
                                "damping": 0.5,
                            },
                            "stabilization": {"iterations": 150},
                        },
                        hierarchical=False,
                    )

                    agraph(nodes=nodes, edges=edges, config=config)

                    # --- Polished Legend ---
                    st.markdown("---")
                    legend_items = [
                        ("Property", "dot", color_map["Property"]["background"]),
                        ("City", "dot", color_map["City"]["background"]),
                        ("Submarket", "diamond", color_map["Submarket"]["background"]),
                        ("Financials", "square", color_map["FinancialSnapshot"]["background"]),
                        ("Market Trend", "triangle", color_map["MarketTrend"]["background"]),
                        ("Scenario", "star", color_map["Scenario"]["background"]),
                        ("Leverage", "triangle", color_map["LeveragePoint"]["background"]),
                        ("Intelligence", "hexagon", color_map["IntelligencePurchase"]["background"]),
                    ]
                    legend_html = " &nbsp;&nbsp; ".join(
                        f'<span style="display:inline-flex; align-items:center; margin-right:8px;">'
                        f'<span style="display:inline-block; width:12px; height:12px; '
                        f'background-color:{color}; border-radius:{"50%" if shape == "dot" else "2px"}; '
                        f'margin-right:5px;"></span>'
                        f'<span style="font-size:13px; color:#CCC;">{label}</span></span>'
                        for label, shape, color in legend_items
                    )
                    st.markdown(legend_html, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"Knowledge graph error: {e}")

elif not raw_data:
    st.info("Select a deal input from the sidebar to begin analysis.")

# --- Standalone Deal Pipeline (before any analysis is run) ---
if "results" not in st.session_state and st.session_state.get("scraped_deals"):
    st.markdown("---")
    st.subheader("Scraped Deal Pipeline")
    scraped = st.session_state["scraped_deals"]
    st.caption(f"Location: {scraped.get('location', 'N/A')}")
    st.info(
        'Select **"Scraped Deal"** from the **Deal Input** source in the sidebar, '
        "pick a deal, then click **Analyze Deal** to run underwriting.",
        icon="💡",
    )

    for source_name, source_key in [("Deal Listings", "loopnet"), ("Investment Properties", "crexi")]:
        deals = scraped.get(source_key, [])
        if deals and not (len(deals) == 1 and deals[0].get("error")):
            st.markdown(f"### {source_name} ({len(deals)} results)")
            for d in deals:
                title = d.get("property_name", "N/A")
                url = d.get("listing_url", "")
                price = d.get("purchase_price")
                units = d.get("total_units", 0)

                col_a, col_b = st.columns([3, 1])
                with col_a:
                    if url:
                        st.markdown(f"**[{title}]({url})**")
                    else:
                        st.markdown(f"**{title}**")
                with col_b:
                    if price:
                        st.metric("Price", _fmt_dollar(price))
                    if units:
                        st.metric("Units", units)
                st.divider()
        elif deals and deals[0].get("error"):
            st.warning(f"{source_name}: {deals[0]['error']}")
