# Semantic Governance Agent — Demo

A self-contained, closed-loop, event-driven Data Steward Agent runnable locally in VS Code.

## What This Is

This system simulates an enterprise Data Steward Agent operating over:

- **Business Terms** — Customer Email, Revenue Amount, Transaction ID
- **DQ Rules** — exported from Neo4j (simulated as SQLite)
- **Technical Data Elements (TDE)** — linked to Business Terms
- **Daily DQ Scores** — 30 days of simulated quality measurements
- **dbt SQL models** — statically analysed for governance flaws

This is **not** a dashboard. It is a **closed-loop, event-driven, agentic governance system** that:
1. Detects breached DQ rules daily
2. Assesses risk using a deterministic scoring formula
3. Shifts investigative focus between Business Terms as risk evolves
4. Statically analyses dbt SQL for governance flaws
5. Detects policy gaps using a semantic type ontology
6. Creates actionable recommendations
7. Measures the outcome of prior recommendations
8. Learns from outcomes to bias future prioritisation

## Architecture

```
governance_agent_demo/
├── governance_agent/
│   ├── config.py            # Paths and constants
│   ├── database.py          # SQLite schema (all 7 tables)
│   ├── mock_data.py         # 3 business terms, 6 rules, 6 TDEs, 30-day DQ scores
│   ├── event_emitter.py     # Canonical emit_event() function
│   ├── llm_client.py        # Claude Haiku — semantic interpretation only
│   ├── sql_scanner.py       # Deterministic regex-based SQL static analysis
│   ├── policy_checker.py    # Ontology-driven gap detection (pure Python)
│   ├── learning_memory.py   # Adaptive attention weights and effectiveness tracking
│   └── agent.py             # 10-step daily governance loop
├── dbt_models/
│   ├── dim_customer.sql     # FLAW: COALESCE on email, PII plain text
│   ├── fct_revenue.sql      # FLAW: INTEGER CAST on amount, non-equi join fan-out
│   └── fct_transactions.sql # FLAW: synthetic IDs, LPAD without null guard
├── policy_ontology.yaml     # email | amount | id | pii → required validations
├── run_simulation.py        # Entry point — 30-day simulation
└── requirements.txt
```

## Setup

```bash
cd governance_agent_demo
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here
```

## Run

```bash
python run_simulation.py
```

Re-run (clears event log first):
```bash
python run_simulation.py --reset
```

## Database

After simulation, `governance.db` contains all data including the full `EVENT_LOG`.

Query the event stream:
```sql
SELECT event_type, entity_name, explanation, metrics
FROM EVENT_LOG
ORDER BY event_id;
```

## Event Types (Stable)

| Event Type | Trigger |
|---|---|
| `rule_breached` | DQ score < threshold |
| `risk_assessed` | Daily risk score computed per Business Term |
| `focus_selected` | Highest-risk term chosen for investigation |
| `investigation_started` | Deep-dive begins on the focus term |
| `lineage_traced` | BusinessTerm → TDE → dbt model → column mapped |
| `sql_analysis_completed` | Static scan + LLM semantic enrichment done |
| `policy_gap_detected` | Ontology requires a validation not present in SQL |
| `recommendation_created` | Actionable recommendation generated |
| `outcome_measured` | Score change from prior recommendation measured |
| `learning_updated` | Memory updated; attention weights revised |

## LLM Usage

Claude Haiku (`claude-haiku-4-5-20251001`) is called **only** for:
- Interpreting rule descriptions into validation categories
- Inferring semantic types of SQL output columns
- Detecting risky SQL transformations
- Generating explanation text for events

**All governance decisions are deterministic Python logic.**
The LLM has no authority to assign severity, choose focus, or override policy checks.

## Demonstrated Behaviors

| Days | Primary Focus | Driver |
|---|---|---|
| 1–13 | Revenue Amount | Score 0.82–0.89 vs threshold 0.90 |
| 7–22 | Customer Email | Score drops to 0.88 vs threshold 0.95 |
| 19–26 | Transaction ID | Score drops to 0.95 vs threshold 0.98 |
| 27–30 | All recovering | Recommendations taking effect |

## Success Criteria

The `EVENT_LOG` table alone is sufficient for a web application to:
- Replay agent cognition day by day
- Visualise investigation focus shifts
- Display policy gaps by model and column
- Plot DQ score improvement over time
- Show which recommendation types were most effective
