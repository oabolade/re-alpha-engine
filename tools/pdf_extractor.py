"""PDF Extraction — extracts structured data from Offering Memorandum PDFs.

Supports two backends:
  - Reka API (if REKA_API_KEY is set)
  - Claude Vision fallback (uses ANTHROPIC_API_KEY)
"""

import json
import re
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
        try:
            return _extract_pdf_reka(pdf_path)
        except Exception as e:
            print(f"[PDF Extractor] Reka failed ({e}), falling back to Claude.")
            if ANTHROPIC_API_KEY:
                return _extract_pdf_claude(pdf_path)
            raise
    return _extract_pdf_claude(pdf_path)


def extract_from_text(text_content: str) -> dict:
    """Extract structured data from pasted OM text."""
    if REKA_API_KEY:
        try:
            return _extract_text_reka(text_content)
        except Exception as e:
            print(f"[PDF Extractor] Reka failed ({e}), falling back to Claude.")
            if ANTHROPIC_API_KEY:
                return _extract_text_claude(text_content)
            raise
    return _extract_text_claude(text_content)


# --- Claude Vision backend ---

def _extract_pdf_claude(pdf_path: str) -> dict:
    """Extract from PDF using Claude's native PDF support."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    with open(pdf_path, "rb") as f:
        pdf_b64 = base64.b64encode(f.read()).decode("utf-8")

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=16384,
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
        max_tokens=16384,
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
            "max_new_tokens": 8192,
        },
        timeout=300.0,
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
    """Parse JSON from API response, handling markdown fences and truncation."""
    text = raw_text.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Extract the largest JSON object from the text
    match = re.search(r"\{", text)
    if match:
        text = text[match.start():]

    # Try parsing again after trimming
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt to repair truncated JSON by closing open structures
    repaired = _repair_truncated_json(text)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse extraction response as JSON. "
            f"The model returned text that could not be parsed even after repair. "
            f"Raw response starts with: {raw_text[:200]!r}... "
            f"Parse error: {e}"
        )


def _repair_truncated_json(text: str) -> str:
    """Attempt to repair truncated JSON by finding the last valid structure point."""
    # Walk the string tracking structural state
    in_string = False
    escape_next = False
    stack = []  # track open { and [
    last_complete_pos = 0  # position after last complete value

    i = 0
    while i < len(text):
        ch = text[i]
        if escape_next:
            escape_next = False
            i += 1
            continue
        if ch == "\\":
            if in_string:
                escape_next = True
            i += 1
            continue
        if ch == '"':
            in_string = not in_string
            i += 1
            continue
        if in_string:
            i += 1
            continue

        # Outside string
        if ch == "{":
            stack.append("{")
        elif ch == "[":
            stack.append("[")
        elif ch == "}":
            if stack and stack[-1] == "{":
                stack.pop()
                last_complete_pos = i + 1
        elif ch == "]":
            if stack and stack[-1] == "[":
                stack.pop()
                last_complete_pos = i + 1
        elif ch in "0123456789":
            # skip past number
            j = i
            while j < len(text) and text[j] in "0123456789.eE+-":
                j += 1
            last_complete_pos = j
            i = j
            continue
        elif text[i:i+4] in ("true", "null"):
            last_complete_pos = i + 4
        elif text[i:i+5] == "false":
            last_complete_pos = i + 5

        i += 1

    # If we ended inside a string or with unclosed structures, truncate to last good point
    if not stack and not in_string:
        return text  # already valid structurally

    # Truncate to last complete value, then close remaining structures
    truncated = text[:last_complete_pos].rstrip().rstrip(",")

    # Recount what's still open after truncation
    open_stack = []
    in_str = False
    esc = False
    for ch in truncated:
        if esc:
            esc = False
            continue
        if ch == "\\":
            if in_str:
                esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            open_stack.append("}")
        elif ch == "[":
            open_stack.append("]")
        elif ch in "}]" and open_stack:
            open_stack.pop()

    # Close in reverse order
    truncated += "".join(reversed(open_stack))
    return truncated
