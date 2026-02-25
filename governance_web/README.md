# Governance Agent — Cognition UI

A **cognition playback UI** for the Semantic Governance Agent.
This app reads the agent's `EVENT_LOG` and renders its reasoning as a visual investigation replay.

This is **not** a dashboard. It is a reconstruction of agent thinking.

---

## Stack

| Layer    | Technology                      |
|----------|---------------------------------|
| Backend  | FastAPI (Python) — read-only SQLite |
| Frontend | React + Vite                    |
| Charts   | Recharts                        |
| Lineage  | Custom SVG                      |

---

## Prerequisites

1. Run the governance agent simulation first:
   ```bash
   cd governance_agent_demo
   pip install -r requirements.txt
   export ANTHROPIC_API_KEY=sk-ant-...
   python run_simulation.py
   ```
   This creates `governance_agent_demo/governance.db`.

2. Install Node.js ≥ 18 and Python ≥ 3.11.

---

## Running Locally

### 1. Start the backend

```bash
cd governance_web/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

The backend defaults to reading `../../governance_agent_demo/governance.db`.
Override with:
```bash
GOVERNANCE_DB_PATH=/path/to/governance.db uvicorn main:app --reload
```

Check it's alive:
```
http://localhost:8000/health
http://localhost:8000/docs
```

### 2. Start the frontend

```bash
cd governance_web/frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## Views

### Timeline (primary)
Chronological playback of all 30 investigation cycles.

- Events grouped into daily investigation cycles (one per agent run)
- **Focus shift badges** highlight when the agent changes which Business Term it investigates
- Each card shows: breach count · policy gaps · event dot chain · recommendation · score delta
- Click any card to open the Investigation Detail panel

### Investigation Detail Panel
Slides in from the right when you click a Timeline card.

| Tab | Content |
|-----|---------|
| **Problem** | Rule breaches, risk scores per term, why this term was selected |
| **Reasoning** | Lineage graph (Business Term → TDE → Model → Column), SQL analysis flags, policy gaps |
| **Decision** | Recommendation type, action, rationale |
| **Result** | Score before/after, delta, learning memory update |

### Risk Heatmap
Color-coded grid of Business Terms showing current status:
- 🟣 **Investigating** — agent currently focused here
- 🔴 **Breached** — DQ score below threshold
- 🟠 **Declining** — score falling
- 🟢 **Improving** — recommendation taking effect
- 🔵 **Stable** — within acceptable range

Click a card to jump to the latest investigation for that term.

### Learning
Charts showing how the agent adapted over 30 days:
- Recommendation type effectiveness (% that improved scores)
- Attention weight evolution per term (line chart)
- DQ score trajectory per term (from outcome_measured events)

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | DB connectivity + event count |
| `GET /events` | All events ordered by timestamp |
| `GET /investigations` | Events grouped into daily cycles |
| `GET /latest_state` | Latest status per Business Term |
| `GET /learning_summary` | Recommendation effectiveness aggregation |

All endpoints are read-only. No business logic is implemented in the UI layer.

---

## Architecture Constraints

- The UI derives **all state** from `EVENT_LOG` only
- No hardcoded domain knowledge — event types and payloads drive all display
- The API performs only grouping and aggregation — no governance decisions
- Future agent versions with different payloads will not break the UI structure
