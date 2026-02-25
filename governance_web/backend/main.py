"""
FastAPI backend for the Governance Agent Cognition UI.

READ-ONLY access to the SQLite EVENT_LOG produced by the governance agent.
No business logic — only event grouping and aggregation.

Endpoints:
  GET /health              — DB connectivity check
  GET /events              — All events ordered by timestamp
  GET /investigations      — Events grouped into daily investigation cycles
  GET /latest_state        — Latest status per business term (derived from events)
  GET /learning_summary    — Recommendation effectiveness aggregation
"""

import json
import os
import sqlite3
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Governance Cognition API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# DB connection (read-only)
# ---------------------------------------------------------------------------

_DB_PATH = os.environ.get(
    "GOVERNANCE_DB_PATH",
    os.path.join(os.path.dirname(__file__), "../../governance_agent_demo/governance.db"),
)


def _db_path() -> str:
    return os.path.abspath(_DB_PATH)


def _connect() -> sqlite3.Connection:
    path = _db_path()
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Database not found at {path}. "
            "Run `python run_simulation.py` first from governance_agent_demo/."
        )
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _parse(row) -> dict:
    """Convert a DB row to a dict, JSON-parsing context and metrics."""
    d = dict(row)
    for field in ("context", "metrics"):
        raw = d.get(field, "{}")
        try:
            d[field] = json.loads(raw) if raw else {}
        except (json.JSONDecodeError, TypeError):
            d[field] = {}
    return d


def _db_guard(fn):
    """Decorator: wraps a handler, converts FileNotFoundError → 503."""
    import functools
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
    return wrapper


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _group_by_learning(events: list[dict]) -> list[list[dict]]:
    """
    Split the event stream into daily investigation cycles.
    Each cycle ends with a `learning_updated` event.
    Any trailing events without a closing learning_updated form the last group.
    """
    groups: list[list[dict]] = []
    current: list[dict] = []
    for evt in events:
        current.append(evt)
        if evt["event_type"] == "learning_updated":
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def _first(events: list[dict], *event_types: str) -> Optional[dict]:
    for t in event_types:
        for e in events:
            if e["event_type"] == t:
                return e
    return None


def _all_of(events: list[dict], event_type: str) -> list[dict]:
    return [e for e in events if e["event_type"] == event_type]


def _summarize(inv_id: int, events: list[dict]) -> dict:
    focus   = _first(events, "focus_selected")
    rec     = _first(events, "recommendation_created")
    outcome = _first(events, "outcome_measured")
    started = _first(events, "investigation_started")
    learning = _first(events, "learning_updated")

    breaches   = _all_of(events, "rule_breached")
    gaps       = _all_of(events, "policy_gap_detected")
    risk_events= _all_of(events, "risk_assessed")
    sql_events = _all_of(events, "sql_analysis_completed")

    date = (
        (focus or {}).get("context", {}).get("date")
        or (events[0]["timestamp"][:10] if events else None)
    )

    # Derive score before/after for quick display
    score_before = outcome["metrics"].get("score_before") if outcome else None
    score_after  = outcome["metrics"].get("score_after")  if outcome else None
    delta        = outcome["metrics"].get("delta")        if outcome else None

    # Attention weight for the focused term at time of learning
    focus_id = focus["entity_id"] if focus else None
    attn_weights = (learning or {}).get("metrics", {}).get("attention_weights", {})
    focus_attention = attn_weights.get(focus_id) if focus_id else None

    return {
        "investigation_id": inv_id,
        "date": date,
        "focus_term": focus["entity_name"] if focus else None,
        "focus_term_id": focus_id,
        "risk_score": (focus or {}).get("metrics", {}).get("risk_score", 0),
        "breach_count": len(breaches),
        "gap_count": len(gaps),
        "sql_model_count": len(sql_events),
        "recommendation_type": (rec or {}).get("context", {}).get("recommendation_type"),
        "recommendation_action": (rec or {}).get("context", {}).get("action"),
        "recommendation_rationale": (rec or {}).get("context", {}).get("rationale"),
        "score_before": score_before,
        "score_after": score_after,
        "score_delta": delta,
        "outcome_improved": bool((outcome or {}).get("metrics", {}).get("improved", False)),
        "focus_attention": focus_attention,
        "all_risks": [
            {
                "entity_id":   r["entity_id"],
                "entity_name": r["entity_name"],
                "risk_score":  r["metrics"].get("risk_score", 0),
                "breach_count":r["metrics"].get("breach_count", 0),
            }
            for r in risk_events
        ],
        "events": events,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
@_db_guard
def health():
    conn = _connect()
    count = conn.execute("SELECT COUNT(*) FROM EVENT_LOG").fetchone()[0]
    conn.close()
    return {"status": "ok", "event_count": count, "db": _db_path()}


@app.get("/events")
@_db_guard
def get_events(
    limit: int = Query(default=2000, le=10000),
    event_type: Optional[str] = Query(default=None),
):
    conn = _connect()
    if event_type:
        rows = conn.execute(
            "SELECT * FROM EVENT_LOG WHERE event_type=? ORDER BY event_id LIMIT ?",
            (event_type, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM EVENT_LOG ORDER BY event_id LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [_parse(r) for r in rows]


@app.get("/investigations")
@_db_guard
def get_investigations():
    conn = _connect()
    rows = conn.execute("SELECT * FROM EVENT_LOG ORDER BY event_id").fetchall()
    conn.close()
    events = [_parse(r) for r in rows]
    groups = _group_by_learning(events)
    return [_summarize(i + 1, g) for i, g in enumerate(groups)]


@app.get("/latest_state")
@_db_guard
def get_latest_state():
    """
    Walk the full event stream and derive the latest status for every
    entity that has been mentioned in `risk_assessed` or `focus_selected`.
    Status: investigating | breached | declining | stable
    """
    conn = _connect()
    rows = conn.execute("SELECT * FROM EVENT_LOG ORDER BY event_id").fetchall()
    conn.close()
    events = [_parse(r) for r in rows]

    state: dict[str, dict] = {}
    currently_investigating: Optional[str] = None

    for evt in events:
        eid   = evt["entity_id"]
        ename = evt["entity_name"]
        etype = evt["event_type"]
        ctx   = evt["context"]
        mets  = evt["metrics"]

        if etype == "risk_assessed":
            if eid not in state:
                state[eid] = {"entity_id": eid, "entity_name": ename}
            state[eid].update(
                {
                    "latest_risk_score": mets.get("risk_score", 0),
                    "breach_count": mets.get("breach_count", 0),
                    "criticality": mets.get("criticality"),
                    "attention": mets.get("attention_multiplier"),
                    "last_assessed": evt["timestamp"],
                }
            )

        elif etype == "focus_selected":
            currently_investigating = eid
            if eid not in state:
                state[eid] = {"entity_id": eid, "entity_name": ename}
            state[eid]["last_focused"] = evt["timestamp"]

        elif etype == "outcome_measured":
            if eid not in state:
                state[eid] = {"entity_id": eid, "entity_name": ename}
            state[eid].update(
                {
                    "latest_score": mets.get("score_after"),
                    "latest_delta": mets.get("delta", 0),
                    "improved": bool(mets.get("improved", False)),
                    "last_outcome": evt["timestamp"],
                    "score_before": mets.get("score_before"),
                }
            )

    # Assign status
    for eid, s in state.items():
        if eid == currently_investigating:
            s["status"] = "investigating"
        elif s.get("breach_count", 0) > 0:
            delta = s.get("latest_delta")
            if delta is not None and delta < -0.002:
                s["status"] = "declining"
            else:
                s["status"] = "breached"
        elif s.get("improved"):
            s["status"] = "improving"
        else:
            s["status"] = "stable"

    return sorted(state.values(), key=lambda x: x.get("latest_risk_score", 0), reverse=True)


@app.get("/learning_summary")
@_db_guard
def get_learning_summary():
    """
    Aggregate recommendation effectiveness and attention weight evolution
    entirely from outcome_measured and learning_updated events.
    """
    conn = _connect()
    o_rows = conn.execute(
        "SELECT * FROM EVENT_LOG WHERE event_type='outcome_measured' ORDER BY event_id"
    ).fetchall()
    l_rows = conn.execute(
        "SELECT * FROM EVENT_LOG WHERE event_type='learning_updated' ORDER BY event_id"
    ).fetchall()
    conn.close()

    outcomes  = [_parse(r) for r in o_rows]
    learnings = [_parse(r) for r in l_rows]

    # Recommendation type effectiveness
    rec_stats: dict[str, dict] = {}
    for o in outcomes:
        rtype = o["context"].get("recommendation_type", "unknown")
        delta = o["metrics"].get("delta", 0) or 0
        improved = bool(o["metrics"].get("improved", False))
        term = o["entity_name"]
        date = o["context"].get("date", o["timestamp"][:10])

        if rtype not in rec_stats:
            rec_stats[rtype] = {"total": 0, "improved_count": 0, "deltas": [], "timeline": []}
        rec_stats[rtype]["total"] += 1
        if improved:
            rec_stats[rtype]["improved_count"] += 1
        rec_stats[rtype]["deltas"].append(delta)
        rec_stats[rtype]["timeline"].append(
            {"date": date, "term": term, "delta": delta, "improved": improved}
        )

    recommendation_types = [
        {
            "type": rtype,
            "total_applied": s["total"],
            "improved_count": s["improved_count"],
            "avg_delta": round(sum(s["deltas"]) / len(s["deltas"]), 4) if s["deltas"] else 0,
            "effectiveness_pct": round(s["improved_count"] / s["total"] * 100) if s["total"] else 0,
            "timeline": s["timeline"],
        }
        for rtype, s in rec_stats.items()
    ]

    # Attention weight evolution
    attention_evolution = []
    for l in learnings:
        attention_evolution.append(
            {
                "date": l["context"].get("date", l["timestamp"][:10]),
                "day": l["context"].get("day_number"),
                "weights": l["metrics"].get("attention_weights", {}),
                "preferred_recommendation": l["context"].get("preferred_recommendation"),
                "outcomes_recorded": l["metrics"].get("outcomes_recorded", 0),
            }
        )

    total     = len(outcomes)
    improved  = sum(1 for o in outcomes if bool(o["metrics"].get("improved", False)))

    # Score trajectory per term from outcomes
    score_trajectory: dict[str, list] = {}
    for o in outcomes:
        term = o["entity_name"]
        date = o["context"].get("date", o["timestamp"][:10])
        after = o["metrics"].get("score_after")
        if after is not None:
            score_trajectory.setdefault(term, []).append({"date": date, "score": after})

    return {
        "recommendation_types": recommendation_types,
        "attention_evolution": attention_evolution,
        "score_trajectory": score_trajectory,
        "total_outcomes": total,
        "improved_outcomes": improved,
        "overall_improvement_rate": round(improved / total * 100) if total else 0,
    }
