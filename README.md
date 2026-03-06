# RE Alpha Engine

**Institutional Deal Intelligence Agent** for multifamily real estate underwriting — now an autonomous agent economy participant.

An autonomous system that ingests Offering Memorandum PDFs, extracts rent rolls, runs institutional-grade financial modeling, researches live market intelligence, scrapes deal pipelines, and produces investment memos with voice narration. Participates in the Nevermined agent economy to both purchase and sell intelligence.

## What It Does

| Capability | Description |
|---|---|
| **PDF Extraction** | Extracts rent rolls, unit data, and property details from Offering Memorandum PDFs via Reka or Claude Vision |
| **Financial Modeling** | 8-step underwriting model: NOI, cap rate, DSCR, cash-on-cash, 5-year IRR with exit valuation |
| **Scenario Analysis** | Bull/base/bear projections varying rent growth, exit cap compression, and vacancy |
| **Market Intelligence** | Nevermined agent network (primary) + Tavily search (fallback) for rent growth, cap rates, comps, supply |
| **Deal Scraping** | Live deal pipeline from LoopNet and Crexi via Apify |
| **Investor Leads** | Investor/buyer lead scraping for deal distribution |
| **Deep Research** | Exa AI-powered research on economic outlook, population migration, regulatory changes |
| **Investment Memo** | Claude-generated institutional-grade memo with risk factors, upside drivers, and GO/NO-GO verdict |
| **Negotiation Leverage** | Automated detection of pricing weaknesses, vacancy risk, and below-market signals |
| **Voice Brief** | 45-second spoken summary via OpenAI TTS for investment committee presentations |
| **Knowledge Graph** | Neo4j-backed graph storing properties, submarkets, financials, and market trends across analyses |
| **Intelligence Monetization** | FastAPI service exposing deal analysis to external agents via Nevermined payment verification |
| **AWS Deployment** | SAM template for serverless deployment on Lambda + API Gateway + S3 |

## Architecture

```
                         Nevermined Agent Network
                        /                        \
                  Buy Intel                   Sell Intel
                  (market data)               (FastAPI API)
                       |                          |
OM PDF                 |                     External Agents
  |                    v                          |
Reka / Claude --> Rent Roll Extraction            |
  |                                               v
Normalizer --> Structured JSON              POST /api/v1/analyze
  |                                         (Nevermined payment)
Financial Engine --> NOI, IRR, Cap Rate, Scenarios
  |
Market Intelligence (Nevermined -> Tavily fallback)
  |
Apify --> Deal Scraping (LoopNet, Crexi)
  |
Exa --> Deep Market Research
  |
Claude --> Contextual Investment Memo + Negotiation Leverage
  |
OpenAI TTS --> Voice Brief
  |
Neo4j --> Knowledge Graph        S3 --> Persistent Storage
  |
Streamlit --> Interactive Dashboard (9 tabs)
```

## Quick Start

### Prerequisites

- Python 3.10+
- API keys: Anthropic (required), all others optional
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
# Streamlit UI (9 tabs including Deal Pipeline + Agent Network)
streamlit run app.py

# CLI: from extracted JSON
python main.py data/sample_om.json

# CLI: full agent orchestration loop
python main.py data/sample_om.json --agent

# CLI: from PDF
python main.py path/to/offering_memo.pdf

# CLI: scrape live deals
python main.py --scrape --market "Dallas, TX"

# FastAPI monetization service
uvicorn api.monetization:app --reload

# Register in Nevermined agent network
python -m api.register_service
```

### Neo4j (Optional)

```bash
docker run -d --name re-alpha-neo4j \
  --publish=7474:7474 --publish=7687:7687 \
  --env NEO4J_AUTH=neo4j/realpha2025 \
  neo4j:latest
```

### AWS Deployment (Optional)

```bash
cd infra
sam build
sam deploy --guided
```

## Project Structure

```
re-alpha-engine/
├── app.py                         # Streamlit UI (9 tabs)
├── main.py                        # CLI entry point (with --scrape)
├── config.py                      # API keys, default assumptions
├── requirements.txt
├── agents/
│   └── orchestrator.py            # Claude tool-use orchestrator (11 tools)
├── tools/
│   ├── pdf_extractor.py           # Reka / Claude Vision PDF extraction
│   ├── rent_roll_normalizer.py    # Rent roll validation & normalization
│   ├── financial_engine.py        # 8-step financial model + scenarios
│   ├── market_intelligence.py     # Nevermined-first, Tavily fallback
│   ├── memo_generator.py          # Claude investment memo + leverage detection
│   ├── voice_brief.py             # OpenAI TTS / ElevenLabs voice narration
│   ├── knowledge_graph.py         # Neo4j graph storage & queries
│   ├── nevermined_client.py       # Nevermined SDK — search, buy, sell intel
│   ├── deal_scraper.py            # Apify — LoopNet, Crexi scraping
│   ├── exa_research.py            # Exa AI deep research
│   └── s3_storage.py              # AWS S3 storage
├── api/
│   ├── monetization.py            # FastAPI — sell analysis to other agents
│   ├── lambda_handler.py          # Mangum adapter for AWS Lambda
│   └── register_service.py        # One-time Nevermined registration
├── infra/
│   └── template.yaml              # AWS SAM template (Lambda + API GW + S3)
├── data/
│   ├── sample_om.json             # Oakwood Terrace, Dallas (12 units)
│   ├── sample_om_2.json           # Pine Valley, Austin (8 units)
│   └── sample_om_3.json           # Magnolia Heights, Houston (20 units)
├── system_prompt.md               # Orchestrator agent system prompt
├── agent_skills.md                # Skill definitions (12 skills)
├── agent_rules.md                 # Data integrity & communication rules
├── agent_memory_schema.md         # Session memory schema
├── financial_model.md             # Financial model specification
├── reka_extraction_prompt.md      # PDF extraction prompt template
└── render.yaml                    # Render deployment config
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
| `TAVILY_API_KEY` | No | Market intelligence research (fallback) |
| `OPENAI_API_KEY` | No | TTS voice briefs |
| `REKA_API_KEY` | No | PDF extraction (falls back to Claude Vision) |
| `ELEVENLABS_API_KEY` | No | Alternative TTS provider |
| `NEVERMINED_API_KEY` | No | Agent economy — buy/sell intelligence |
| `NEVERMINED_ENVIRONMENT` | No | `staging` or `production` (default: staging) |
| `NEVERMINED_AGENT_DID` | No | Agent DID after registration |
| `APIFY_API_KEY` | No | Deal scraping from LoopNet, Crexi |
| `EXA_API_KEY` | No | Deep market research via Exa |
| `AWS_S3_BUCKET` | No | S3 bucket for persistent storage |
| `AWS_REGION` | No | AWS region (default: us-east-1) |
| `MONETIZATION_API_URL` | No | Deployed API URL for Nevermined registration |
| `INTELLIGENCE_BUDGET_PER_QUERY` | No | Max spend per intelligence query (default: $1.00) |
| `NEO4J_URI` | No | Knowledge graph (e.g. `bolt://localhost:7687`) |
| `NEO4J_USER` | No | Neo4j username |
| `NEO4J_PASSWORD` | No | Neo4j password |

## Graceful Degradation

Every new integration checks for its API key and skips if unavailable. The existing pipeline works unchanged with no new keys set:

- No `NEVERMINED_API_KEY` → market intel falls back to Tavily
- No `TAVILY_API_KEY` → market intel section is empty
- No `APIFY_API_KEY` → Deal Pipeline tab shows setup instructions
- No `EXA_API_KEY` → deep research tool returns empty
- No `AWS_S3_BUCKET` → storage operations return None silently
- No `NEO4J_URI` → Knowledge Graph tab shows setup instructions

## API Endpoints (FastAPI)

```
POST   /api/v1/analyze          Submit deal for analysis (requires Nevermined payment)
GET    /api/v1/status/{job_id}  Check job status
GET    /api/v1/result/{job_id}  Retrieve results (requires payment verification)
GET    /health                  Health check
```

## Deployment

### Render (Streamlit UI)

Deployed via `render.yaml` blueprint.

### AWS (Monetization API)

```bash
cd infra
sam build && sam deploy --guided
```

Deploys: Lambda + API Gateway + S3 bucket.

## Tech Stack

- **LLM**: Claude (Anthropic) — extraction, modeling, memos
- **PDF Processing**: Reka Flash / Claude Vision
- **Agent Economy**: Nevermined (payments-py) — discovery, purchase, monetization
- **Market Research**: Tavily Search API (fallback), Exa AI (deep research)
- **Deal Scraping**: Apify (LoopNet, Crexi actors)
- **Voice**: OpenAI TTS / ElevenLabs
- **Graph DB**: Neo4j
- **API**: FastAPI + Mangum (Lambda adapter)
- **Storage**: AWS S3
- **UI**: Streamlit (9 tabs)
- **Deployment**: Render (UI), AWS SAM (API)

## License

MIT
