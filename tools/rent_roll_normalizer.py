"""Skill 1: Rent Roll Normalization — validates and normalizes extracted OM data."""

from typing import Any


def normalize_rent_roll(raw_extraction: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize raw Reka extraction into structured rent roll JSON."""
    property_name = raw_extraction.get("property_name", "Unknown Property")
    address = raw_extraction.get("address", "Unknown Address")
    purchase_price = _to_number(raw_extraction.get("purchase_price"))
    reported_units = _to_number(raw_extraction.get("total_units"))

    units = []
    warnings = []

    for i, raw_unit in enumerate(raw_extraction.get("rent_roll", [])):
        unit = {
            "unit_id": raw_unit.get("unit_number") or raw_unit.get("unit_id") or f"Unit-{i+1}",
            "monthly_rent": _to_number(raw_unit.get("monthly_rent", 0)),
            "occupied": _parse_occupancy(raw_unit.get("occupancy_status", raw_unit.get("occupied", True))),
            "square_feet": _to_number(raw_unit.get("square_footage") or raw_unit.get("square_feet")),
        }

        if unit["monthly_rent"] is not None and unit["monthly_rent"] <= 0:
            warnings.append(f"{unit['unit_id']}: rent is ${unit['monthly_rent']} — verify")

        units.append(unit)

    actual_count = len(units)
    if reported_units and actual_count != reported_units:
        warnings.append(
            f"Unit count mismatch: reported {reported_units}, extracted {actual_count}"
        )

    occupied = sum(1 for u in units if u["occupied"])
    vacancy_rate = round(1 - (occupied / actual_count), 4) if actual_count > 0 else 0.0

    return {
        "property_name": property_name,
        "address": address,
        "purchase_price": purchase_price,
        "total_units": actual_count,
        "units": units,
        "vacancy_rate": vacancy_rate,
        "warnings": warnings,
    }


def _to_number(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = val.replace("$", "").replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _parse_occupancy(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("occupied", "yes", "true", "1", "leased")
    return bool(val)
