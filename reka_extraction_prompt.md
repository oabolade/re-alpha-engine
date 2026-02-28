# Reka Extraction Prompt — Offering Memorandum

Extract the following information from the provided Offering Memorandum PDF:

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