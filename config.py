import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
REKA_API_KEY = os.getenv("REKA_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Nevermined — agent economy
NEVERMINED_API_KEY = os.getenv("NEVERMINED_API_KEY", "")
NEVERMINED_ENVIRONMENT = os.getenv("NEVERMINED_ENVIRONMENT", "staging")
NEVERMINED_AGENT_DID = os.getenv("NEVERMINED_AGENT_DID", "")

# Apify — deal scraping
APIFY_API_KEY = os.getenv("APIFY_API_KEY", "")

# Exa — deep research
EXA_API_KEY = os.getenv("EXA_API_KEY", "")

# ZeroClick — AI-native ads
ZEROCLICK_API_KEY = os.getenv("ZEROCLICK_API_KEY", "")

# AWS — storage & deployment
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Monetization API
MONETIZATION_API_URL = os.getenv("MONETIZATION_API_URL", "")
INTELLIGENCE_BUDGET_PER_QUERY = float(os.getenv("INTELLIGENCE_BUDGET_PER_QUERY", "1.0"))

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "realpha2025")
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"

DEFAULT_ASSUMPTIONS = {
    "rent_growth": 0.03,
    "hold_period": 5,
    "ltv": 0.70,
    "interest_rate": 0.065,
    "expense_ratio": 0.35,
    "exit_cap_compression": 0.02,
}

SCENARIO_OVERRIDES = {
    "bull": {"rent_growth": 0.04, "exit_cap_compression": 0.03, "vacancy_adj": -0.02},
    "base": {"rent_growth": 0.03, "exit_cap_compression": 0.02, "vacancy_adj": 0.0},
    "bear": {"rent_growth": 0.01, "exit_cap_compression": 0.0, "vacancy_adj": 0.05},
}
