"""
Mock metadata and DQ score generator.

Scenario narrative:
  Days  1-10  Revenue Amount heavily breaches threshold (score 0.82-0.88 vs 0.90)
  Days 11-18  After agent recommendations, Revenue recovers; Customer Email degrades
  Days 19-25  Email recovers; Transaction ID hits a uniqueness crisis
  Days 26-30  All terms stabilising after reinforced recommendations
"""

import sqlite3
import math
import random
from datetime import date, timedelta
from governance_agent.config import DB_PATH, DBT_MODELS_DIR, SIMULATION_START_DATE, SIMULATION_DAYS
import os


# ---------------------------------------------------------------------------
# Static reference data
# ---------------------------------------------------------------------------

BUSINESS_TERMS = [
    ("BT001", "Customer Email",  0.90),
    ("BT002", "Revenue Amount",  0.95),
    ("BT003", "Transaction ID",  0.85),
]

RULES = [
    ("R001", "BT001",
     "Email addresses must be non-null and conform to RFC 5322 format specification",
     0.95),
    ("R002", "BT001",
     "Email domain must belong to an approved allowlist; unknown domains must be flagged",
     0.90),
    ("R003", "BT002",
     "Revenue values must be numeric and within the expected business range of 0 to 10,000,000 USD",
     0.90),
    ("R004", "BT002",
     "Revenue fields must not be null and must not carry negative values",
     0.95),
    ("R005", "BT003",
     "Transaction identifiers must be globally unique within each 24-hour processing window",
     0.98),
    ("R006", "BT003",
     "Transaction IDs must follow the canonical format TXN-YYYYMMDD-NNNNNN with zero-padded sequence",
     0.92),
]

TDES = [
    ("TDE001", "customer_email_raw",       "BT001"),
    ("TDE002", "customer_email_cleansed",  "BT001"),
    ("TDE003", "revenue_usd",              "BT002"),
    ("TDE004", "revenue_local_currency",   "BT002"),
    ("TDE005", "transaction_id_raw",       "BT003"),
    ("TDE006", "transaction_id_normalized","BT003"),
]

DBT_COLUMN_MAPPINGS = [
    ("dim_customer",    "email",              "TDE001"),
    ("dim_customer",    "cleansed_email",     "TDE002"),
    ("fct_revenue",     "revenue_usd",        "TDE003"),
    ("fct_revenue",     "revenue_local",      "TDE004"),
    ("fct_transactions","transaction_id",     "TDE005"),
    ("fct_transactions","normalized_txn_id",  "TDE006"),
]


# ---------------------------------------------------------------------------
# DQ score profiles — piecewise-linear with minor noise
# ---------------------------------------------------------------------------

def _interpolate(day: int, breakpoints: list) -> float:
    """
    Linearly interpolate between (day, score) breakpoints.
    day is 1-indexed (1..30).
    """
    if day <= breakpoints[0][0]:
        return breakpoints[0][1]
    if day >= breakpoints[-1][0]:
        return breakpoints[-1][1]
    for i in range(len(breakpoints) - 1):
        d0, s0 = breakpoints[i]
        d1, s1 = breakpoints[i + 1]
        if d0 <= day <= d1:
            t = (day - d0) / (d1 - d0)
            return s0 + t * (s1 - s0)
    return breakpoints[-1][1]


# Breakpoints: (day, score)
SCORE_PROFILES = {
    # Revenue — starts below threshold, recovers after day 10
    "TDE003": [(1, 0.820), (5, 0.835), (10, 0.865), (14, 0.905), (20, 0.930), (30, 0.945)],
    "TDE004": [(1, 0.800), (5, 0.818), (10, 0.850), (14, 0.895), (20, 0.920), (30, 0.940)],

    # Customer Email — fine early, degrades days 10-17, recovers
    "TDE001": [(1, 0.960), (9,  0.952), (13, 0.880), (17, 0.910), (22, 0.950), (30, 0.970)],
    "TDE002": [(1, 0.970), (9,  0.960), (13, 0.900), (17, 0.930), (22, 0.960), (30, 0.980)],

    # Transaction ID — mostly fine, crisis days 20-25, recovers
    "TDE005": [(1, 0.984), (18, 0.982), (21, 0.960), (24, 0.945), (27, 0.985), (30, 0.990)],
    "TDE006": [(1, 0.990), (18, 0.985), (21, 0.965), (24, 0.950), (27, 0.988), (30, 0.995)],
}

NOISE_SEED = 42  # reproducible simulation
random.seed(NOISE_SEED)

_NOISE_TABLE = {
    tde_id: [random.uniform(-0.008, 0.008) for _ in range(SIMULATION_DAYS)]
    for tde_id in SCORE_PROFILES
}


def _score_for(tde_id: str, day: int) -> float:
    base = _interpolate(day, SCORE_PROFILES[tde_id])
    noisy = base + _NOISE_TABLE[tde_id][day - 1]
    return round(max(0.0, min(1.0, noisy)), 4)


# ---------------------------------------------------------------------------
# Population helpers
# ---------------------------------------------------------------------------

def _populate_reference(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.executemany("INSERT OR REPLACE INTO BUSINESS_TERMS VALUES (?,?,?)", BUSINESS_TERMS)
    cur.executemany("INSERT OR REPLACE INTO RULES VALUES (?,?,?,?)", RULES)
    cur.executemany("INSERT OR REPLACE INTO TDE VALUES (?,?,?)", TDES)
    cur.executemany("INSERT OR REPLACE INTO DBT_COLUMN_MAPPING VALUES (?,?,?)", DBT_COLUMN_MAPPINGS)


def _populate_dbt_sql_models(conn: sqlite3.Connection) -> None:
    """Load SQL files from dbt_models/ directory into DBT_SQL_MODELS table."""
    cur = conn.cursor()
    for fname in os.listdir(DBT_MODELS_DIR):
        if not fname.endswith(".sql"):
            continue
        model_name = fname.replace(".sql", "")
        with open(os.path.join(DBT_MODELS_DIR, fname), "r") as fh:
            sql_text = fh.read()
        cur.execute(
            "INSERT OR REPLACE INTO DBT_SQL_MODELS (model_name, sql_text) VALUES (?,?)",
            (model_name, sql_text),
        )


def _populate_dq_scores(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    start = date.fromisoformat(SIMULATION_START_DATE)
    rows = []
    for day_num in range(1, SIMULATION_DAYS + 1):
        d = (start + timedelta(days=day_num - 1)).isoformat()
        for tde_id in SCORE_PROFILES:
            rows.append((d, tde_id, _score_for(tde_id, day_num)))
    cur.executemany("INSERT OR REPLACE INTO DQ_SCORES VALUES (?,?,?)", rows)


def populate_all(db_path: str = None) -> None:
    """Idempotent: safe to call multiple times."""
    from governance_agent.database import get_connection
    conn = get_connection(db_path)
    _populate_reference(conn)
    _populate_dbt_sql_models(conn)
    _populate_dq_scores(conn)
    conn.commit()
    conn.close()
    print("[mock_data] Reference data, SQL models and DQ scores loaded.")
