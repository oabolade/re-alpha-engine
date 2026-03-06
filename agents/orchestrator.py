"""RE Alpha Engine — Orchestrator Agent using Claude tool-use pattern."""

import json
from typing import Any
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from tools.rent_roll_normalizer import normalize_rent_roll
from tools.financial_engine import run_financial_model, run_scenarios
from tools.memo_generator import generate_memo, generate_negotiation_leverage
from tools.market_intelligence import research_market, format_market_context
from tools.nevermined_client import NEVERMINED_AVAILABLE, search_providers, evaluate_providers, purchase_intelligence
from tools.deal_scraper import APIFY_AVAILABLE, scrape_loopnet_deals, scrape_crexi_deals, scrape_investor_leads
from tools.exa_research import EXA_AVAILABLE, deep_research

SYSTEM_PROMPT = """You are an institutional multifamily underwriting analyst and autonomous agent economy participant.

Your responsibilities:

1. Validate extracted rent roll data.
2. Normalize it into structured JSON.
3. Perform simplified but accurate financial modeling.
4. Generate a concise institutional-grade investment memo.
5. Clearly state all financial assumptions.
6. Discover and purchase intelligence from the Nevermined agent network when available.
7. Scrape live deal listings from LoopNet and Crexi when requested.
8. Research investor leads for deal distribution.
9. Conduct deep market research using Exa when additional context is needed.

## Modeling Assumptions (Default)

If not explicitly provided, assume:

- Hold Period: 5 years
- Rent Growth: 3% annually
- Exit Cap Compression: 2%
- Loan-to-Value (LTV): 70%
- Interest Rate: 6.5%
- Operating Expense Ratio: 35%

## Behavioral Constraints

- Never fabricate missing financial data.
- If data is missing, explicitly state the assumption used.
- Show formula transparency when calculating financial metrics.
- Flag inconsistencies in extracted rent roll data.
- Maintain institutional, concise tone.
- Avoid marketing language or exaggeration.
- Do not include emojis.
- Do not speculate beyond available data.
- When purchasing intelligence, prefer the lowest cost provider with sufficient quality.

You have access to tools for normalizing rent rolls, running financial models, running scenario analysis, generating investment memos, discovering intelligence providers, purchasing intelligence, scraping deals, and conducting deep research. Use them as appropriate to produce a complete deal analysis."""

TOOLS = [
    {
        "name": "normalize_rent_roll",
        "description": "Validate and normalize raw extracted rent roll data into structured format. Use this first on any raw extraction data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "raw_extraction": {
                    "type": "object",
                    "description": "Raw JSON data extracted from an offering memorandum",
                }
            },
            "required": ["raw_extraction"],
        },
    },
    {
        "name": "run_financial_model",
        "description": "Run the 8-step financial model on normalized rent roll data. Returns NOI, cap rate, IRR, cash-on-cash, and full cash flow projection.",
        "input_schema": {
            "type": "object",
            "properties": {
                "normalized_data": {
                    "type": "object",
                    "description": "Normalized rent roll data from normalize_rent_roll",
                },
                "assumptions": {
                    "type": "object",
                    "description": "Optional assumption overrides (rent_growth, ltv, interest_rate, expense_ratio, hold_period, exit_cap_compression)",
                },
            },
            "required": ["normalized_data"],
        },
    },
    {
        "name": "run_scenarios",
        "description": "Run bull/base/bear scenario analysis on normalized data. Returns IRR and key metrics under each scenario.",
        "input_schema": {
            "type": "object",
            "properties": {
                "normalized_data": {
                    "type": "object",
                    "description": "Normalized rent roll data",
                }
            },
            "required": ["normalized_data"],
        },
    },
    {
        "name": "generate_negotiation_leverage",
        "description": "Analyze the deal to identify negotiation leverage points for the buyer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "normalized_data": {"type": "object"},
                "financial_results": {"type": "object"},
            },
            "required": ["normalized_data", "financial_results"],
        },
    },
    {
        "name": "generate_memo",
        "description": "Generate an institutional-grade investment memo from all analysis results. Use this last after all other analysis is complete.",
        "input_schema": {
            "type": "object",
            "properties": {
                "normalized_data": {"type": "object"},
                "financial_results": {"type": "object"},
                "scenario_results": {"type": "object"},
                "negotiation_points": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "market_context": {
                    "type": "string",
                    "description": "Formatted market intelligence text",
                },
            },
            "required": ["normalized_data", "financial_results", "scenario_results"],
        },
    },
    {
        "name": "discover_intelligence_providers",
        "description": "Search the Nevermined agent network for intelligence providers matching a query. Returns list of providers with pricing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g., 'multifamily market intelligence Dallas TX')",
                },
                "category": {
                    "type": "string",
                    "description": "Provider category filter",
                    "default": "market_intelligence",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "purchase_intelligence",
        "description": "Purchase intelligence data from a Nevermined provider. Returns the purchased data and transaction receipt.",
        "input_schema": {
            "type": "object",
            "properties": {
                "provider_did": {
                    "type": "string",
                    "description": "DID of the provider to purchase from",
                },
                "query_params": {
                    "type": "object",
                    "description": "Parameters for the intelligence query",
                },
            },
            "required": ["provider_did", "query_params"],
        },
    },
    {
        "name": "research_market",
        "description": "Research market intelligence for a property address. Uses Nevermined first, falls back to Tavily.",
        "input_schema": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Property address to research",
                },
                "asset_type": {
                    "type": "string",
                    "description": "Asset type (default: multifamily)",
                    "default": "multifamily",
                },
            },
            "required": ["address"],
        },
    },
    {
        "name": "scrape_deals",
        "description": "Scrape live deal listings from LoopNet and Crexi for a given location and asset type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Target market (e.g., 'Dallas, TX')",
                },
                "asset_type": {
                    "type": "string",
                    "description": "Property type to search",
                    "default": "multifamily",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max listings per source",
                    "default": 20,
                },
            },
            "required": ["location"],
        },
    },
    {
        "name": "scrape_investors",
        "description": "Scrape investor and buyer leads matching given criteria.",
        "input_schema": {
            "type": "object",
            "properties": {
                "criteria": {
                    "type": "object",
                    "description": "Search criteria: {location, asset_type, min_deal_size}",
                    "properties": {
                        "location": {"type": "string"},
                        "asset_type": {"type": "string"},
                        "min_deal_size": {"type": "number"},
                    },
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max leads to return",
                    "default": 10,
                },
            },
            "required": ["criteria"],
        },
    },
    {
        "name": "deep_research",
        "description": "Conduct deep research on a market using Exa AI. Covers economic outlook, population migration, regulatory changes, and institutional investor activity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "market": {
                    "type": "string",
                    "description": "Target market (e.g., 'Dallas, TX')",
                },
                "asset_type": {
                    "type": "string",
                    "description": "Property type",
                    "default": "multifamily",
                },
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Research topics (defaults to standard set)",
                },
            },
            "required": ["market"],
        },
    },
]


def _execute_tool(name: str, input_data: dict) -> Any:
    """Route tool calls to actual implementations."""
    if name == "normalize_rent_roll":
        return normalize_rent_roll(input_data["raw_extraction"])
    elif name == "run_financial_model":
        return run_financial_model(
            input_data["normalized_data"],
            input_data.get("assumptions"),
        )
    elif name == "run_scenarios":
        return run_scenarios(input_data["normalized_data"])
    elif name == "generate_negotiation_leverage":
        return generate_negotiation_leverage(
            input_data["normalized_data"],
            input_data["financial_results"],
        )
    elif name == "generate_memo":
        return generate_memo(
            input_data["normalized_data"],
            input_data["financial_results"],
            input_data["scenario_results"],
            input_data.get("negotiation_points"),
            input_data.get("market_context", ""),
        )
    elif name == "discover_intelligence_providers":
        return search_providers(
            input_data["query"],
            input_data.get("category", "market_intelligence"),
        )
    elif name == "purchase_intelligence":
        return purchase_intelligence(
            input_data["provider_did"],
            input_data.get("query_params", {}),
        )
    elif name == "research_market":
        result = research_market(
            input_data["address"],
            input_data.get("asset_type", "multifamily"),
        )
        return result
    elif name == "scrape_deals":
        location = input_data["location"]
        asset_type = input_data.get("asset_type", "multifamily")
        max_results = input_data.get("max_results", 20)
        loopnet = scrape_loopnet_deals(location, asset_type, max_results)
        crexi = scrape_crexi_deals(location, asset_type, max_results)
        return {"loopnet": loopnet, "crexi": crexi, "total": len(loopnet) + len(crexi)}
    elif name == "scrape_investors":
        return scrape_investor_leads(
            input_data["criteria"],
            input_data.get("max_results", 10),
        )
    elif name == "deep_research":
        return deep_research(
            input_data["market"],
            input_data.get("asset_type", "multifamily"),
            input_data.get("topics"),
        )
    else:
        return {"error": f"Unknown tool: {name}"}


def analyze_deal(raw_extraction: dict, user_query: str | None = None) -> dict:
    """Run the full orchestrator loop: extraction → model → scenarios → memo.

    Returns a dict with all intermediate results and the final memo.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = "Analyze this offering memorandum data. "
    if user_query:
        prompt += f"The user also asks: {user_query}\n\n"
    prompt += f"Raw extraction data:\n```json\n{json.dumps(raw_extraction, indent=2)}\n```\n\n"
    prompt += "Use the tools in sequence: normalize → financial model → scenarios → negotiation leverage → market research → memo."

    messages = [{"role": "user", "content": prompt}]

    # Collect all intermediate results
    results = {
        "normalized_data": None,
        "financial_results": None,
        "scenario_results": None,
        "negotiation_points": None,
        "memo": None,
        "agent_messages": [],
        "market_data": None,
        "intelligence_purchases": [],
        "scraped_deals": None,
        "investor_leads": None,
        "deep_research": None,
    }

    max_turns = 15
    for _ in range(max_turns):
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Collect any text blocks from the response
        for block in response.content:
            if hasattr(block, "text"):
                results["agent_messages"].append(block.text)

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            # Process all tool calls in the response
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_output = _execute_tool(block.name, block.input)

                    # Store intermediate results
                    if block.name == "normalize_rent_roll":
                        results["normalized_data"] = tool_output
                    elif block.name == "run_financial_model":
                        results["financial_results"] = tool_output
                    elif block.name == "run_scenarios":
                        results["scenario_results"] = tool_output
                    elif block.name == "generate_negotiation_leverage":
                        results["negotiation_points"] = tool_output
                    elif block.name == "generate_memo":
                        results["memo"] = tool_output
                    elif block.name == "research_market":
                        results["market_data"] = tool_output
                        purchases = tool_output.get("purchases", []) if isinstance(tool_output, dict) else []
                        results["intelligence_purchases"].extend(purchases)
                    elif block.name == "purchase_intelligence":
                        if isinstance(tool_output, dict) and not tool_output.get("error"):
                            results["intelligence_purchases"].append(tool_output)
                    elif block.name == "scrape_deals":
                        results["scraped_deals"] = tool_output
                    elif block.name == "scrape_investors":
                        results["investor_leads"] = tool_output
                    elif block.name == "deep_research":
                        results["deep_research"] = tool_output

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(tool_output) if isinstance(tool_output, (dict, list)) else str(tool_output),
                        }
                    )

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

    return results
