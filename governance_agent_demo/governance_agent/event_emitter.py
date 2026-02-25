"""
Event Emitter — single canonical function for all agent events.

All events follow the envelope:
  event_type  : one of the 10 stable types
  entity_type : business_term | rule | tde | dbt_model | recommendation | system
  entity_id   : the primary identifier of the entity being described
  entity_name : human-readable name
  context     : JSON dict — situational facts (what the agent observed)
  metrics     : JSON dict — quantitative measurements
  explanation : natural-language reasoning narrative

Events describe reasoning, not code steps.
"""

import json
import sqlite3
from datetime import datetime, timezone
from governance_agent.config import DB_PATH

# Allowed event types — any other type raises ValueError
VALID_EVENT_TYPES = frozenset({
    "rule_breached",
    "risk_assessed",
    "focus_selected",
    "investigation_started",
    "lineage_traced",
    "sql_analysis_completed",
    "policy_gap_detected",
    "recommendation_created",
    "outcome_measured",
    "learning_updated",
})


def emit_event(
    conn: sqlite3.Connection,
    event_type: str,
    entity_type: str,
    entity_id: str,
    entity_name: str,
    context_dict: dict,
    metrics_dict: dict,
    explanation_text: str,
) -> int:
    """
    Write a governance reasoning event to EVENT_LOG.

    Returns the new event_id (INTEGER).
    Raises ValueError for unknown event_type.
    """
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(
            f"Unknown event_type '{event_type}'. "
            f"Must be one of: {sorted(VALID_EVENT_TYPES)}"
        )

    ts = datetime.now(timezone.utc).isoformat()
    context_json  = json.dumps(context_dict,  default=str)
    metrics_json  = json.dumps(metrics_dict,  default=str)

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO EVENT_LOG
            (timestamp, event_type, entity_type, entity_id, entity_name,
             context, metrics, explanation)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ts, event_type, entity_type, entity_id, entity_name,
         context_json, metrics_json, explanation_text),
    )
    conn.commit()
    return cur.lastrowid
