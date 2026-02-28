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
from config import TAVILY_API_KEY, ELEVENLABS_API_KEY, OPENAI_API_KEY, NEO4J_URI

# Neo4j is optional — only import if configured
if NEO4J_URI:
    try:
        from tools.knowledge_graph import store_deal, get_full_graph, get_graph_stats, init_constraints
        NEO4J_AVAILABLE = True
    except Exception:
        NEO4J_AVAILABLE = False
else:
    NEO4J_AVAILABLE = False

st.set_page_config(page_title="RE Alpha Engine", page_icon="", layout="wide")

st.title("RE Alpha Engine")
st.markdown("**Institutional Deal Intelligence Agent** — Multifamily Underwriting")

# --- Sidebar: Input ---
st.sidebar.header("Deal Input")
input_mode = st.sidebar.radio("Input Source", ["Upload PDF", "Sample Deal", "Paste JSON"])

raw_data = None

if input_mode == "Upload PDF":
    uploaded = st.sidebar.file_uploader("Upload Offering Memorandum (PDF)", type=["pdf"])
    if uploaded:
        # Cache extraction by file hash to avoid re-running on every rerun
        file_bytes = uploaded.read()
        file_hash = hashlib.md5(file_bytes).hexdigest()

        if st.session_state.get("pdf_hash") != file_hash:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            with st.spinner("Extracting data from PDF..."):
                raw_data = extract_from_pdf(tmp_path)
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

# --- Analysis Mode ---
use_agent = st.sidebar.checkbox("Use Agent Orchestration", value=False,
                                 help="Run full Claude agent loop with tool-use (slower, more detailed)")

# --- Run Analysis ---
if raw_data and st.sidebar.button("Analyze Deal", type="primary"):
    if use_agent:
        with st.spinner("Agent analyzing deal..."):
            results = analyze_deal(raw_data)
        normalized = results["normalized_data"]
        financials = results["financial_results"]
        scenarios = results["scenario_results"]
        leverage = results["negotiation_points"]
        memo = results["memo"]
        market_data = None
        market_context = ""
    else:
        with st.spinner("Running analysis pipeline..."):
            normalized = normalize_rent_roll(raw_data)
            financials = run_financial_model(normalized, custom_assumptions)
            scenarios = run_scenarios(normalized)
            leverage = generate_negotiation_leverage(normalized, financials)

        market_data = None
        market_context = ""
        if TAVILY_API_KEY:
            with st.spinner("Researching market intelligence via Tavily..."):
                market_data = research_market(normalized.get("address", ""))
                market_context = format_market_context(market_data)

        with st.spinner("Generating investment memo..."):
            memo = generate_memo(normalized, financials, scenarios, leverage, market_context)

    # Store to Neo4j knowledge graph
    if NEO4J_AVAILABLE:
        try:
            init_constraints()
            store_deal(normalized, financials, scenarios, market_data, leverage)
        except Exception as e:
            st.warning(f"Knowledge graph storage failed: {e}")

    # Store all results in session state — no recomputation needed
    st.session_state["results"] = {
        "normalized": normalized,
        "financials": financials,
        "scenarios": scenarios,
        "leverage": leverage,
        "market_data": market_data,
        "market_context": market_context,
        "memo": memo,
    }
    # Clear voice brief from previous run
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

    # Warnings
    if normalized.get("warnings"):
        for w in normalized["warnings"]:
            st.warning(w)

    if financials.get("error"):
        st.warning(financials["error"])

    # Tabs
    tab_names = ["Summary", "Financial Detail", "Scenarios", "Market Intel", "Negotiation", "Investment Memo", "Knowledge Graph"]
    tab1, tab2, tab3, tab_market, tab4, tab5, tab_graph = st.tabs(tab_names)

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
        elif not TAVILY_API_KEY:
            st.info("Market intelligence unavailable — TAVILY_API_KEY not set.")
        else:
            st.info("No market data available for this property.")

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
                        "Property":          {"background": "#E74C3C", "border": "#C0392B", "font": "#FFFFFF"},
                        "Submarket":         {"background": "#1ABC9C", "border": "#16A085", "font": "#FFFFFF"},
                        "City":              {"background": "#2980B9", "border": "#1F6DA0", "font": "#FFFFFF"},
                        "FinancialSnapshot": {"background": "#27AE60", "border": "#1E8449", "font": "#FFFFFF"},
                        "MarketTrend":       {"background": "#F39C12", "border": "#D68910", "font": "#1A1A1A"},
                        "Scenario":          {"background": "#8E44AD", "border": "#6C3483", "font": "#FFFFFF"},
                        "LeveragePoint":     {"background": "#E67E22", "border": "#CA6F1E", "font": "#FFFFFF"},
                    }
                    size_map = {
                        "City": 40,
                        "Property": 35,
                        "Submarket": 28,
                        "MarketTrend": 22,
                        "FinancialSnapshot": 20,
                        "Scenario": 18,
                        "LeveragePoint": 16,
                    }
                    shape_map = {
                        "City": "dot",
                        "Property": "dot",
                        "Submarket": "diamond",
                        "FinancialSnapshot": "square",
                        "MarketTrend": "triangle",
                        "Scenario": "star",
                        "LeveragePoint": "triangleDown",
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
                    }
                    edge_colors = {
                        "LOCATED_IN": "#7F8C8D",
                        "IN_CITY": "#7F8C8D",
                        "HAS_FINANCIALS": "#27AE60",
                        "HAS_SCENARIO": "#8E44AD",
                        "HAS_TREND": "#F39C12",
                        "HAS_LEVERAGE": "#E67E22",
                        "COMPARABLE_TO": "#E74C3C",
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
