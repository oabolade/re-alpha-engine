import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
REKA_API_KEY = os.getenv("REKA_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

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
