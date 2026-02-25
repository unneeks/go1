import os

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "governance.db")
POLICY_ONTOLOGY_PATH = os.path.join(BASE_DIR, "policy_ontology.yaml")
DBT_MODELS_DIR = os.path.join(BASE_DIR, "dbt_models")

# Simulation
SIMULATION_START_DATE = "2026-01-01"
SIMULATION_DAYS = 30

# LLM
LLM_MODEL = "claude-haiku-4-5-20251001"
LLM_MAX_TOKENS_SHORT = 200
LLM_MAX_TOKENS_MEDIUM = 600
LLM_MAX_TOKENS_LONG = 400

# Risk scoring
TREND_WINDOW_DAYS = 5
MIN_TREND_FACTOR = 0.5
MAX_TREND_FACTOR = 3.0
