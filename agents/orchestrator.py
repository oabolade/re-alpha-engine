"""RE Alpha Engine — Orchestrator Agent using Claude tool-use pattern."""

import json
from typing import Any
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from tools.rent_roll_normalizer import normalize_rent_roll
from tools.financial_engine import run_financial_model, run_scenarios
from tools.memo_generator import generate_memo, generate_negotiation_leverage

SYSTEM_PROMPT = """You are an institutional multifamily underwriting analyst.

Your responsibilities:

1. Validate extracted rent roll data.
2. Normalize it into structured JSON.
3. Perform simplified but accurate financial modeling.
4. Generate a concise institutional-grade investment memo.
5. Clearly state all financial assumptions.

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

You have access to tools for normalizing rent rolls, running financial models, running scenario analysis, and generating investment memos. Use them in sequence to produce a complete deal analysis."""

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
            },
            "required": ["normalized_data", "financial_results", "scenario_results"],
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
    prompt += "Use the tools in sequence: normalize → financial model → scenarios → negotiation leverage → memo."

    messages = [{"role": "user", "content": prompt}]

    # Collect all intermediate results
    results = {
        "normalized_data": None,
        "financial_results": None,
        "scenario_results": None,
        "negotiation_points": None,
        "memo": None,
        "agent_messages": [],
    }

    max_turns = 10
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
