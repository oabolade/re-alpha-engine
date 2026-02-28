"""Knowledge Graph Layer — Neo4j-backed property and market intelligence graph.

Stores properties, submarkets, cities, financial metrics, market trends,
and comparable relationships. Builds a growing knowledge base across analyses.

Node types:
  - Property (name, address, units, vacancy, purchase_price)
  - Submarket (name)
  - City (name, state)
  - FinancialSnapshot (noi, cap_rate, irr, coc, dscr, timestamp)
  - MarketTrend (category, summary, source)

Relationship types:
  - LOCATED_IN (Property -> Submarket)
  - IN_CITY (Submarket -> City)
  - HAS_FINANCIALS (Property -> FinancialSnapshot)
  - HAS_TREND (City -> MarketTrend)
  - COMPARABLE_TO (Property -> Property)
"""

import re
from datetime import datetime
from neo4j import GraphDatabase

from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def _get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def _extract_city_state(address: str) -> tuple[str, str]:
    match = re.search(r"([A-Za-z\s]+),\s*([A-Z]{2})\s*\d*", address)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    parts = [p.strip() for p in address.split(",")]
    if len(parts) >= 2:
        return parts[-2], parts[-1].split()[0] if parts[-1] else ""
    return address, ""


def init_constraints():
    """Create uniqueness constraints for key node types."""
    driver = _get_driver()
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Property) REQUIRE p.address IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (c:City) REQUIRE c.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Submarket) REQUIRE s.name IS UNIQUE",
    ]
    with driver.session() as session:
        for c in constraints:
            session.run(c)
    driver.close()


def store_deal(
    normalized_data: dict,
    financial_results: dict,
    scenario_results: dict | None = None,
    market_data: dict | None = None,
    leverage_points: list[str] | None = None,
):
    """Store a complete deal analysis into the knowledge graph."""
    driver = _get_driver()
    address = normalized_data.get("address", "Unknown")
    city, state = _extract_city_state(address)
    submarket = f"{city} Metro"
    timestamp = datetime.now().isoformat()

    with driver.session() as session:
        # Create City node
        session.run(
            "MERGE (c:City {name: $name}) SET c.state = $state",
            name=f"{city}, {state}" if state else city,
            state=state,
        )

        # Create Submarket node
        session.run(
            "MERGE (s:Submarket {name: $name}) "
            "WITH s "
            "MATCH (c:City {name: $city}) "
            "MERGE (s)-[:IN_CITY]->(c)",
            name=submarket,
            city=f"{city}, {state}" if state else city,
        )

        # Create/update Property node
        session.run(
            "MERGE (p:Property {address: $address}) "
            "SET p.name = $name, p.total_units = $units, "
            "    p.vacancy_rate = $vacancy, p.purchase_price = $price, "
            "    p.last_analyzed = $ts "
            "WITH p "
            "MATCH (s:Submarket {name: $submarket}) "
            "MERGE (p)-[:LOCATED_IN]->(s)",
            address=address,
            name=normalized_data.get("property_name", "Unknown"),
            units=normalized_data.get("total_units", 0),
            vacancy=normalized_data.get("vacancy_rate", 0),
            price=normalized_data.get("purchase_price"),
            ts=timestamp,
            submarket=submarket,
        )

        # Create FinancialSnapshot
        if financial_results and not financial_results.get("error"):
            session.run(
                "MATCH (p:Property {address: $address}) "
                "CREATE (f:FinancialSnapshot {"
                "  noi: $noi, cap_rate: $cap_rate, irr_5yr: $irr, "
                "  cash_on_cash: $coc, dscr: $dscr, "
                "  exit_value: $exit_val, timestamp: $ts"
                "}) "
                "MERGE (p)-[:HAS_FINANCIALS]->(f)",
                address=address,
                noi=financial_results.get("noi"),
                cap_rate=financial_results.get("cap_rate"),
                irr=financial_results.get("irr_5yr"),
                coc=financial_results.get("cash_on_cash"),
                dscr=financial_results.get("dscr"),
                exit_val=financial_results.get("exit_value"),
                ts=timestamp,
            )

        # Store scenario results as properties on snapshot
        if scenario_results:
            for scenario_name, data in scenario_results.items():
                session.run(
                    "MATCH (p:Property {address: $address}) "
                    "CREATE (s:Scenario {name: $scenario, irr: $irr, noi: $noi, "
                    "  cash_on_cash: $coc, exit_value: $exit_val, timestamp: $ts}) "
                    "MERGE (p)-[:HAS_SCENARIO]->(s)",
                    address=address,
                    scenario=scenario_name,
                    irr=data.get("irr_5yr"),
                    noi=data.get("noi"),
                    coc=data.get("cash_on_cash"),
                    exit_val=data.get("exit_value"),
                    ts=timestamp,
                )

        # Store market trends on City node
        if market_data and market_data.get("research"):
            for category, data in market_data["research"].items():
                answer = data.get("answer", "")
                if answer:
                    sources = ", ".join(
                        s.get("title", "") for s in data.get("sources", []) if s.get("title")
                    )
                    session.run(
                        "MATCH (c:City {name: $city}) "
                        "CREATE (t:MarketTrend {"
                        "  category: $category, summary: $summary, "
                        "  sources: $sources, timestamp: $ts"
                        "}) "
                        "MERGE (c)-[:HAS_TREND]->(t)",
                        city=f"{city}, {state}" if state else city,
                        category=category,
                        summary=answer[:500],
                        sources=sources,
                        ts=timestamp,
                    )

        # Store leverage points
        if leverage_points:
            for point in leverage_points:
                session.run(
                    "MATCH (p:Property {address: $address}) "
                    "CREATE (l:LeveragePoint {text: $text, timestamp: $ts}) "
                    "MERGE (p)-[:HAS_LEVERAGE]->(l)",
                    address=address,
                    text=point,
                    ts=timestamp,
                )

    driver.close()


def find_comparables(address: str, max_results: int = 5) -> list[dict]:
    """Find comparable properties in the same submarket."""
    driver = _get_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (p:Property {address: $address})-[:LOCATED_IN]->(s:Submarket)"
            "<-[:LOCATED_IN]-(comp:Property) "
            "WHERE comp.address <> $address "
            "OPTIONAL MATCH (comp)-[:HAS_FINANCIALS]->(f:FinancialSnapshot) "
            "RETURN comp.name AS name, comp.address AS address, "
            "  comp.total_units AS units, comp.purchase_price AS price, "
            "  f.cap_rate AS cap_rate, f.noi AS noi "
            "ORDER BY f.timestamp DESC "
            "LIMIT $limit",
            address=address,
            limit=max_results,
        )
        return [dict(r) for r in result]
    driver.close()


def get_full_graph() -> dict:
    """Retrieve all nodes and relationships for visualization."""
    driver = _get_driver()
    nodes = []
    edges = []
    seen_nodes = set()

    with driver.session() as session:
        # Get all nodes with labels
        result = session.run(
            "MATCH (n) "
            "WHERE n:Property OR n:Submarket OR n:City OR n:FinancialSnapshot "
            "   OR n:MarketTrend OR n:Scenario OR n:LeveragePoint "
            "RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS props "
            "LIMIT 200"
        )
        for record in result:
            node_id = record["id"]
            if node_id not in seen_nodes:
                seen_nodes.add(node_id)
                label = record["labels"][0] if record["labels"] else "Unknown"
                props = dict(record["props"])
                # Pick a display name
                display = (
                    props.get("name")
                    or props.get("address")
                    or props.get("category")
                    or props.get("text", "")[:40]
                    or label
                )
                nodes.append({
                    "id": node_id,
                    "label": display,
                    "type": label,
                    "properties": props,
                })

        # Get all relationships
        result = session.run(
            "MATCH (a)-[r]->(b) "
            "WHERE (a:Property OR a:Submarket OR a:City OR a:FinancialSnapshot "
            "   OR a:MarketTrend OR a:Scenario OR a:LeveragePoint) "
            "AND (b:Property OR b:Submarket OR b:City OR b:FinancialSnapshot "
            "   OR b:MarketTrend OR b:Scenario OR b:LeveragePoint) "
            "RETURN elementId(a) AS source, elementId(b) AS target, type(r) AS rel_type "
            "LIMIT 500"
        )
        for record in result:
            edges.append({
                "source": record["source"],
                "target": record["target"],
                "label": record["rel_type"],
            })

    driver.close()
    return {"nodes": nodes, "edges": edges}


def get_graph_stats() -> dict:
    """Get summary stats of the knowledge graph."""
    driver = _get_driver()
    with driver.session() as session:
        counts = {}
        for label in ["Property", "City", "Submarket", "MarketTrend"]:
            result = session.run(f"MATCH (n:{label}) RETURN count(n) AS c")
            record = result.single()
            counts[label.lower() if label != "MarketTrend" else "trends"] = record["c"] if record else 0
        # Rename keys for display
        return {
            "properties": counts.get("property", 0),
            "cities": counts.get("city", 0),
            "submarkets": counts.get("submarket", 0),
            "trends": counts.get("trends", 0),
        }
    driver.close()
