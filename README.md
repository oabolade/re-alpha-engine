# RE Alpha Engine

**Institutional Deal Intelligence Agent** for multifamily real estate underwriting.

An autonomous system that ingests Offering Memorandum PDFs, extracts rent rolls, runs institutional-grade financial modeling, researches live market intelligence, and produces investment memos with voice narration — all in one pipeline.

## What It Does

| Capability | Description |
|---|---|
| **PDF Extraction** | Extracts rent rolls, unit data, and property details from Offering Memorandum PDFs via Reka or Claude Vision |
| **Financial Modeling** | 8-step underwriting model: NOI, cap rate, DSCR, cash-on-cash, 5-year IRR with exit valuation |
| **Scenario Analysis** | Bull/base/bear projections varying rent growth, exit cap compression, and vacancy |
| **Market Intelligence** | Tavily-powered research on rent growth trends, cap rates, comparable sales, and supply pipeline |
| **Investment Memo** | Claude-generated institutional-grade memo with risk factors, upside drivers, and GO/NO-GO verdict |
| **Negotiation Leverage** | Automated detection of pricing weaknesses, vacancy risk, and below-market signals |
| **Voice Brief** | 45-second spoken summary via OpenAI TTS for investment committee presentations |
| **Knowledge Graph** | Neo4j-backed graph storing properties, submarkets, financials, and market trends across analyses |

## Architecture

```
OM PDF
  |
Reka / Claude Vision --> Rent Roll Extraction
  |
Rent Roll Normalizer --> Structured JSON
  |
Financial Engine --> NOI, IRR, Cap Rate, Scenarios
  |
Tavily --> Market Intelligence (rent growth, cap rates, comps, supply)
  |
Claude --> Contextual Investment Memo + Negotiation Leverage
  |
OpenAI TTS --> Voice Brief
  |
Neo4j --> Knowledge Graph (persistent across analyses)
  |
Streamlit --> Interactive Dashboard (7 tabs)
```

## Quick Start

### Prerequisites

- Python 3.10+
- API keys: Anthropic (required), Tavily, OpenAI, Reka (optional)
- Docker (optional, for Neo4j knowledge graph)

### Setup

```bash
# Clone
git clone https://github.com/oabolade/re-alpha-engine.git
cd re-alpha-engine

# Virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env with your keys
```

### Run

```bash
# Streamlit UI
streamlit run app.py

# CLI: from extracted JSON
python main.py data/sample_om.json

# CLI: from PDF
python main.py path/to/offering_memo.pdf

# CLI: full agent orchestration loop
python main.py data/sample_om.json --agent
```

### Neo4j (Optional)

```bash
docker run -d --name re-alpha-neo4j \
  --publish=7474:7474 --publish=7687:7687 \
  --env NEO4J_AUTH=neo4j/realpha2025 \
  neo4j:latest
```

The Knowledge Graph tab activates automatically when Neo4j is available.

## Project Structure

```
re-alpha-engine/
├── app.py                         # Streamlit UI (7 tabs)
├── main.py                        # CLI entry point
├── config.py                      # API keys, default assumptions
├── render.yaml                    # Render deployment config
├── requirements.txt
├── agents/
│   └── orchestrator.py            # Claude tool-use orchestrator (5 tools)
├── tools/
│   ├── pdf_extractor.py           # Reka / Claude Vision PDF extraction
│   ├── rent_roll_normalizer.py    # Rent roll validation & normalization
│   ├── financial_engine.py        # 8-step financial model + scenarios
│   ├── market_intelligence.py     # Tavily market research (4 queries)
│   ├── memo_generator.py          # Claude investment memo + leverage detection
│   ├── voice_brief.py             # OpenAI TTS / ElevenLabs voice narration
│   └── knowledge_graph.py         # Neo4j graph storage & queries
├── data/
│   ├── sample_om.json             # Oakwood Terrace, Dallas (12 units)
│   ├── sample_om_2.json           # Pine Valley, Austin (8 units)
│   └── sample_om_3.json           # Magnolia Heights, Houston (20 units)
├── system_prompt.md               # Orchestrator agent system prompt
├── agent_skills.md                # Skill definitions (4 skills)
├── agent_rules.md                 # Data integrity & communication rules
├── agent_memory_schema.md         # Session memory schema
├── financial_model.md             # Financial model specification
└── reka_extraction_prompt.md      # PDF extraction prompt template
```

## Financial Model

The engine implements a transparent 8-step underwriting model:

1. **Gross Annual Rent** — Sum of all unit rents x 12
2. **Effective Gross Income** — Adjusted for vacancy
3. **Operating Expenses** — EGI x expense ratio (default 35%)
4. **Net Operating Income** — EGI minus OpEx
5. **Cap Rate** — NOI / purchase price
6. **Equity Invested** — Purchase price x (1 - LTV)
7. **Debt Service & Cash Flow** — Interest-only, annual cash flow
8. **5-Year IRR** — NPV-based with exit cap compression
9. **Scenario Analysis** — Bull/base/bear with variable rent growth, exit cap, vacancy

### Default Assumptions

| Parameter | Default |
|---|---|
| Hold Period | 5 years |
| Rent Growth | 3% annually |
| LTV | 70% |
| Interest Rate | 6.5% |
| Expense Ratio | 35% |
| Exit Cap Compression | 2% |

All assumptions are adjustable via the sidebar sliders.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API for memos, extraction fallback, voice scripts |
| `TAVILY_API_KEY` | No | Market intelligence research |
| `OPENAI_API_KEY` | No | TTS voice briefs |
| `REKA_API_KEY` | No | PDF extraction (falls back to Claude Vision) |
| `ELEVENLABS_API_KEY` | No | Alternative TTS provider |
| `NEO4J_URI` | No | Knowledge graph (e.g. `bolt://localhost:7687`) |
| `NEO4J_USER` | No | Neo4j username |
| `NEO4J_PASSWORD` | No | Neo4j password |

## Deployment

Deployed on Render via `render.yaml` blueprint. To deploy your own:

1. Fork this repo
2. Go to [Render Dashboard](https://dashboard.render.com/select-repo?type=blueprint)
3. Connect your fork
4. Set environment variables
5. Deploy

## Tech Stack

- **LLM**: Claude (Anthropic) — extraction, modeling, memos
- **PDF Processing**: Reka Flash / Claude Vision
- **Market Research**: Tavily Search API
- **Voice**: OpenAI TTS / ElevenLabs
- **Graph DB**: Neo4j
- **UI**: Streamlit
- **Deployment**: Render

## License

MIT
