#!/usr/bin/env python3
"""
run_simulation.py — Entry point for the 30-day Semantic Governance Agent demo.

Usage:
    python run_simulation.py [--reset]

    --reset   Wipe the event log before running (useful for re-running the demo)

Environment:
    ANTHROPIC_API_KEY must be set for LLM calls to work.
    If unset, LLM functions will raise; set a dummy key to use fallback text.

Output:
    - governance.db  (SQLite) — contains all tables including EVENT_LOG
    - Console summary of each daily cycle
"""

import argparse
import os
import sys
import json
import sqlite3
from datetime import date, timedelta

# Ensure the demo package is importable from the project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from governance_agent.config import (
    DB_PATH,
    SIMULATION_START_DATE,
    SIMULATION_DAYS,
)
from governance_agent.database import initialize_database, clear_event_log, get_connection
from governance_agent.mock_data import populate_all
from governance_agent.agent import GovernanceAgent


# ---------------------------------------------------------------------------
# Console formatting
# ---------------------------------------------------------------------------

RESET   = "\033[0m"
BOLD    = "\033[1m"
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
MAGENTA = "\033[95m"
GREY    = "\033[90m"


def _bar(label: str, value: float, width: int = 30) -> str:
    filled = int(round(value * width))
    bar = "█" * filled + "░" * (width - filled)
    return f"  {label:<28} [{bar}] {value:.4f}"


def _header(day: int, date_str: str) -> None:
    print()
    print(BOLD + CYAN + f"{'='*72}" + RESET)
    print(BOLD + CYAN + f"  DAY {day:02d}  |  {date_str}" + RESET)
    print(BOLD + CYAN + f"{'='*72}" + RESET)


def _summary(result: dict, conn: sqlite3.Connection) -> None:
    term_color = MAGENTA if result.get("focus_term") else GREY
    print(f"\n{BOLD}  Focus:{RESET} {term_color}{result.get('focus_term', 'n/a')}{RESET}")
    print(f"  Risk score     : {YELLOW}{result.get('risk_score', 0):.4f}{RESET}")
    print(f"  Primary score  : {_score_color(result.get('primary_score', 0))}{result.get('primary_score', 0):.4f}{RESET}")
    print(f"  Breaches today : {RED if result.get('breach_count', 0) > 0 else GREEN}{result.get('breach_count', 0)}{RESET}")
    print(f"  Policy gaps    : {RED if result.get('gap_count', 0) > 0 else GREEN}{result.get('gap_count', 0)}{RESET}")

    rec_type = result.get("recommendation", "none")
    rec_color = (
        RED    if rec_type == "add_validation"   else
        YELLOW if rec_type == "move_earlier"     else
        GREY
    )
    print(f"\n  {BOLD}Recommendation ({rec_color}{rec_type}{RESET}{BOLD}):{RESET}")
    action = result.get("recommendation_action", "n/a")
    # Wrap long action text
    for i in range(0, len(action), 80):
        print(f"    {action[i:i+80]}")

    # Show all-term scores from DB
    print(f"\n  {BOLD}All-term DQ scores [{result['date']}]:{RESET}")
    rows = conn.execute("""
        SELECT bt.name, tde.tde_id, ds.score, r.threshold
        FROM BUSINESS_TERMS bt
        JOIN TDE tde ON tde.business_term_id = bt.term_id
        JOIN DQ_SCORES ds ON ds.tde_id = tde.tde_id AND ds.date = ?
        JOIN RULES r ON r.business_term_id = bt.term_id
        GROUP BY bt.name, tde.tde_id
        ORDER BY bt.name, tde.tde_id
    """, (result["date"],)).fetchall()

    printed = set()
    for row in rows:
        key = (row[0], row[1])
        if key in printed:
            continue
        printed.add(key)
        sc = row[2]; thr = row[3]
        color = GREEN if sc >= thr else RED
        print(f"    {row[0]:<20} {row[1]:<30} {color}{sc:.4f}{RESET}  (thr {thr:.2f})")


def _score_color(score: float) -> str:
    if score >= 0.95:
        return GREEN
    if score >= 0.90:
        return YELLOW
    return RED


def _final_report(conn: sqlite3.Connection) -> None:
    print()
    print(BOLD + "=" * 72 + RESET)
    print(BOLD + "  SIMULATION COMPLETE — FINAL REPORT" + RESET)
    print(BOLD + "=" * 72 + RESET)

    # Event counts by type
    rows = conn.execute("""
        SELECT event_type, COUNT(*) as n
        FROM EVENT_LOG
        GROUP BY event_type
        ORDER BY n DESC
    """).fetchall()
    print(f"\n{BOLD}  Events emitted by type:{RESET}")
    for r in rows:
        print(f"    {r[0]:<30} {CYAN}{r[1]:>4}{RESET}")

    # Attention weight evolution (final state from last learning_updated)
    last = conn.execute("""
        SELECT metrics FROM EVENT_LOG
        WHERE event_type = 'learning_updated'
        ORDER BY event_id DESC LIMIT 1
    """).fetchone()
    if last:
        metrics = json.loads(last[0])
        weights = metrics.get("attention_weights", {})
        print(f"\n{BOLD}  Final attention weights:{RESET}")
        for term_id, w in sorted(weights.items(), key=lambda x: -x[1]):
            bar = "█" * int(w * 10)
            print(f"    {term_id:<8} {bar:<25} {w:.3f}")

    # Focus shift timeline
    focus_rows = conn.execute("""
        SELECT e.context, e.timestamp
        FROM EVENT_LOG e
        WHERE e.event_type = 'focus_selected'
        ORDER BY e.event_id
    """).fetchall()
    print(f"\n{BOLD}  Investigation focus timeline:{RESET}")
    prev_name = None
    for row in focus_rows:
        ctx = json.loads(row[0])
        day_ctx = ctx.get("date", "?")
        # entity_name embedded in entity column not context; get from outer query
        name_row = conn.execute("""
            SELECT entity_name FROM EVENT_LOG
            WHERE event_type='focus_selected' AND context=?
        """, (row[0],)).fetchone()
        name = name_row[0] if name_row else "?"
        shift = " ← SHIFT" if name != prev_name and prev_name else ""
        color = MAGENTA if shift else GREY
        print(f"    {day_ctx}  {color}{name}{RESET}{RED}{shift}{RESET}")
        prev_name = name

    # Recommendation summary
    rec_rows = conn.execute("""
        SELECT json_extract(context, '$.recommendation_type') as rtype, COUNT(*) as n
        FROM EVENT_LOG
        WHERE event_type = 'recommendation_created'
        GROUP BY rtype
    """).fetchall()
    print(f"\n{BOLD}  Recommendations by type:{RESET}")
    for r in rec_rows:
        print(f"    {r[0]:<25} {GREEN}{r[1]}{RESET}")

    # Outcome summary
    outcome_rows = conn.execute("""
        SELECT
            json_extract(metrics, '$.improved') as improved,
            COUNT(*) as n
        FROM EVENT_LOG
        WHERE event_type = 'outcome_measured'
        GROUP BY improved
    """).fetchall()
    print(f"\n{BOLD}  Outcomes measured:{RESET}")
    for r in outcome_rows:
        improved_label = "Improved" if r[0] == 1 else "No improvement"
        color = GREEN if r[0] == 1 else RED
        print(f"    {color}{improved_label:<20}{RESET} {r[1]}")

    total_events = conn.execute("SELECT COUNT(*) FROM EVENT_LOG").fetchone()[0]
    print(f"\n{BOLD}  Total events in EVENT_LOG: {CYAN}{total_events}{RESET}")
    print(f"{BOLD}  Database: {CYAN}{DB_PATH}{RESET}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run the 30-day Semantic Governance Agent simulation."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear the event log before running (idempotent re-run).",
    )
    args = parser.parse_args()

    # Verify API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            f"{RED}WARNING: ANTHROPIC_API_KEY is not set. "
            f"LLM calls will fail. Set the key or the simulation will use fallback text.{RESET}"
        )

    print(f"\n{BOLD}Semantic Governance Agent — 30-Day Simulation{RESET}")
    print(f"Database : {DB_PATH}")
    print(f"Start    : {SIMULATION_START_DATE}")
    print(f"Days     : {SIMULATION_DAYS}")
    print()

    # Initialise
    print("Initialising database...")
    initialize_database()

    if args.reset:
        print("Resetting event log...")
        clear_event_log()

    print("Loading mock data...")
    populate_all()

    conn = get_connection()
    agent = GovernanceAgent(conn)

    start = date.fromisoformat(SIMULATION_START_DATE)

    print(f"\n{BOLD}Starting simulation...{RESET}\n")

    all_results = []

    for day_num in range(1, SIMULATION_DAYS + 1):
        current_date = (start + timedelta(days=day_num - 1)).isoformat()
        _header(day_num, current_date)

        try:
            result = agent.run_daily_cycle(current_date, day_num)
            all_results.append(result)
            _summary(result, conn)
        except Exception as exc:
            print(f"{RED}ERROR on day {day_num}: {exc}{RESET}")
            import traceback
            traceback.print_exc()

    _final_report(conn)
    conn.close()


if __name__ == "__main__":
    main()
