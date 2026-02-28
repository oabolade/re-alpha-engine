"""PDF Extraction — extracts structured data from Offering Memorandum PDFs.

Supports two backends:
  - Reka API (if REKA_API_KEY is set)
  - Claude Vision fallback (uses ANTHROPIC_API_KEY)
"""

import json
import base64
import httpx
import anthropic

from config import REKA_API_KEY, ANTHROPIC_API_KEY, CLAUDE_MODEL

REKA_API_URL = "https://api.reka.ai/v1/chat"

EXTRACTION_PROMPT = """Extract the following information from the provided Offering Memorandum PDF:

1. Property name
2. Full address
3. Total unit count
4. Purchase price (if listed)
5. Complete rent roll table including:
   - Unit number
   - Monthly rent
   - Occupancy status
   - Square footage (if available)

Return output strictly in JSON format.

Rules:
- Do not summarize.
- Do not explain.
- Do not add commentary.
- If data is unclear or missing, set value to null.
- Ensure numeric values are returned as numbers, not strings.

Required JSON structure:
{
  "property_name": "",
  "address": "",
  "total_units": 0,
  "purchase_price": 0,
  "rent_roll": [
    {
      "unit_number": "",
      "monthly_rent": 0,
      "occupancy_status": "",
      "square_footage": null
    }
  ]
}"""


def extract_from_pdf(pdf_path: str) -> dict:
    """Extract structured OM data from a PDF. Uses Reka if available, else Claude."""
    if REKA_API_KEY:
        return _extract_pdf_reka(pdf_path)
    return _extract_pdf_claude(pdf_path)


def extract_from_text(text_content: str) -> dict:
    """Extract structured data from pasted OM text."""
    if REKA_API_KEY:
        return _extract_text_reka(text_content)
    return _extract_text_claude(text_content)


# --- Claude Vision backend ---

def _extract_pdf_claude(pdf_path: str) -> dict:
    """Extract from PDF using Claude's native PDF support."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    with open(pdf_path, "rb") as f:
        pdf_b64 = base64.b64encode(f.read()).decode("utf-8")

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": EXTRACTION_PROMPT,
                    },
                ],
            }
        ],
    )

    raw_text = response.content[0].text
    return _parse_json_response(raw_text)


def _extract_text_claude(text_content: str) -> dict:
    """Extract from pasted text using Claude."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": f"{EXTRACTION_PROMPT}\n\n---\n\n{text_content}",
            }
        ],
    )

    raw_text = response.content[0].text
    return _parse_json_response(raw_text)


# --- Reka backend ---

def _reka_chat(messages: list[dict], model: str = "reka-flash") -> str:
    """Call Reka chat API directly via REST."""
    response = httpx.post(
        REKA_API_URL,
        headers={
            "X-Api-Key": REKA_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
        },
        timeout=120.0,
    )
    response.raise_for_status()
    data = response.json()
    return data["responses"][0]["message"]["content"]


def _extract_pdf_reka(pdf_path: str) -> dict:
    """Extract from PDF using Reka API."""
    with open(pdf_path, "rb") as f:
        pdf_b64 = base64.b64encode(f.read()).decode("utf-8")

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "pdf_url",
                    "pdf_url": f"data:application/pdf;base64,{pdf_b64}",
                },
                {
                    "type": "text",
                    "text": EXTRACTION_PROMPT,
                },
            ],
        }
    ]

    raw_text = _reka_chat(messages)
    return _parse_json_response(raw_text)


def _extract_text_reka(text_content: str) -> dict:
    """Extract from pasted text using Reka."""
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"{EXTRACTION_PROMPT}\n\n---\n\n{text_content}",
                },
            ],
        }
    ]

    raw_text = _reka_chat(messages)
    return _parse_json_response(raw_text)


def _parse_json_response(raw_text: str) -> dict:
    """Parse JSON from API response, handling markdown code fences."""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return json.loads(text)
