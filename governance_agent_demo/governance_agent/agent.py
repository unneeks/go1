"""
Governance Agent — closed-loop, event-driven Data Steward.

Implements the 10-step daily behavior loop:
  1.  Detect breached rules
  2.  Assess risk (criticality × gap × trend)
  3.  Select focus (highest adjusted risk)
  4.  Start investigation
  5.  Trace lineage (BusinessTerm → TDE → dbt model → column)
  6.  LLM SQL analysis (semantic types + risky transformations)
  7.  Deterministic policy gap detection
  8.  Create recommendation
  9.  Measure outcome (previous day's recommendation)
  10. Update learning memory

All governance decisions are deterministic Python.
LLM is called only for semantic interpretation and explanation generation.
"""

import sqlite3
from datetime import date, timedelta
from typing import Optional

from governance_agent import llm_client, sql_scanner, policy_checker
from governance_agent.event_emitter import emit_event
from governance_agent.learning_memory import LearningMemory
from governance_agent.config import TREND_WINDOW_DAYS, MIN_TREND_FACTOR, MAX_TREND_FACTOR


# ---------------------------------------------------------------------------
# DB query helpers
# ---------------------------------------------------------------------------

def _q(conn, sql, *args):
    return conn.execute(sql, args).fetchall()


def _q1(conn, sql, *args):
    row = conn.execute(sql, args).fetchone()
    return dict(row) if row else None


def _all_terms(conn) -> list[dict]:
    return [dict(r) for r in _q(conn, "SELECT * FROM BUSINESS_TERMS")]


def _rules_for_term(conn, term_id: str) -> list[dict]:
    return [
        dict(r)
        for r in _q(conn, "SELECT * FROM RULES WHERE business_term_id = ?", term_id)
    ]


def _tdes_for_term(conn, term_id: str) -> list[dict]:
    return [
        dict(r)
        for r in _q(conn, "SELECT * FROM TDE WHERE business_term_id = ?", term_id)
    ]


def _score(conn, tde_id: str, date_str: str) -> Optional[float]:
    row = _q1(conn, "SELECT score FROM DQ_SCORES WHERE tde_id=? AND date=?", tde_id, date_str)
    return row["score"] if row else None


def _recent_scores(conn, tde_id: str, date_str: str, window: int) -> list[float]:
    rows = _q(
        conn,
        """
        SELECT score FROM DQ_SCORES
        WHERE tde_id = ? AND date <= ?
        ORDER BY date DESC
        LIMIT ?
        """,
        tde_id, date_str, window,
    )
    return [r["score"] for r in rows]


def _models_for_tde(conn, tde_id: str) -> list[dict]:
    return [
        dict(r)
        for r in _q(
            conn,
            "SELECT model_name, column_name FROM DBT_COLUMN_MAPPING WHERE tde_id = ?",
            tde_id,
        )
    ]


def _sql_for_model(conn, model_name: str) -> Optional[str]:
    row = _q1(conn, "SELECT sql_text FROM DBT_SQL_MODELS WHERE model_name = ?", model_name)
    return row["sql_text"] if row else None


# ---------------------------------------------------------------------------
# Risk calculation
# ---------------------------------------------------------------------------

def _trend_decline_factor(scores: list[float]) -> float:
    """
    > 1.0 when scores are declining (bad trend amplifies risk).
    < 1.0 when scores are improving (good trend dampens risk).
    Uses linear regression slope over the window.
    """
    if len(scores) < 2:
        return 1.0
    n = len(scores)
    # scores[0] = most recent, scores[-1] = oldest
    # reverse so index 0 = oldest
    s = list(reversed(scores))
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_s = sum(s) / n
    num = sum((x - mean_x) * (sv - mean_s) for x, sv in zip(xs, s))
    den = sum((x - mean_x) ** 2 for x in xs) or 1e-9
    slope = num / den   # positive = improving, negative = declining
    # Map slope to factor: decline → factor > 1, improve → factor < 1
    factor = 1.0 - slope * 20   # scale: 0.05/day slope → ±1.0
    return max(MIN_TREND_FACTOR, min(MAX_TREND_FACTOR, factor))


def _term_risk(
    conn,
    term: dict,
    rules: list[dict],
    date_str: str,
    memory: LearningMemory,
) -> tuple[float, list[dict]]:
    """
    Compute the aggregated risk score for a business term on a given date.
    Returns (risk_score, [breach_info, ...]).
    """
    breaches = []
    total_risk = 0.0

    for rule in rules:
        threshold = rule["threshold"]
        tdes = _tdes_for_term(conn, term["term_id"])
        for tde in tdes:
            sc = _score(conn, tde["tde_id"], date_str)
            if sc is None:
                continue
            if sc < threshold:
                recent = _recent_scores(conn, tde["tde_id"], date_str, TREND_WINDOW_DAYS)
                tdf = _trend_decline_factor(recent)
                gap = threshold - sc
                risk = term["criticality"] * gap * tdf
                total_risk += risk
                breaches.append({
                    "rule_id": rule["rule_id"],
                    "tde_id": tde["tde_id"],
                    "tde_name": tde["name"],
                    "score": sc,
                    "threshold": threshold,
                    "gap": round(gap, 4),
                    "trend_factor": round(tdf, 4),
                    "risk_contribution": round(risk, 4),
                })

    # Apply learning memory attention weight
    attention = memory.get_attention_weight(term["term_id"])
    adjusted_risk = round(total_risk * attention, 4)
    return adjusted_risk, breaches


# ---------------------------------------------------------------------------
# Recommendation logic (deterministic)
# ---------------------------------------------------------------------------

def _choose_recommendation(
    gaps: list[dict],
    scan: dict,
    memory: LearningMemory,
) -> dict:
    """
    Deterministically choose a recommendation type and action.
    Priority: policy gap → SQL risk → threshold adjustment.
    Memory biases the type selection when multiple options are equal.
    """
    preferred = memory.preferred_recommendation_type()

    if gaps:
        # Critical PII masking gap → must add masking validation
        for g in gaps:
            if g["severity"] == "critical" and g["missing_validation"] == "masking":
                return {
                    "type": "add_validation",
                    "action": f"Add masking validation for PII column '{g['column_name']}'",
                    "target_column": g["column_name"],
                    "validation": "masking",
                    "rationale": (
                        f"Column '{g['column_name']}' exposes PII in plain text. "
                        "A masking or tokenisation step must be added upstream."
                    ),
                }
        # Other gaps → add or move validation
        top = gaps[0]
        if preferred == "move_earlier":
            return {
                "type": "move_earlier",
                "action": (
                    f"Move '{top['missing_validation']}' validation for "
                    f"'{top['column_name']}' to the staging model"
                ),
                "target_column": top["column_name"],
                "validation": top["missing_validation"],
                "rationale": (
                    f"The '{top['missing_validation']}' check is applied too late in "
                    f"the pipeline. Moving it to staging prevents corrupt "
                    f"'{top['column_name']}' values from propagating downstream."
                ),
            }
        return {
            "type": "add_validation",
            "action": (
                f"Add '{top['missing_validation']}' validation for "
                f"column '{top['column_name']}' ({top['semantic_type']})"
            ),
            "target_column": top["column_name"],
            "validation": top["missing_validation"],
            "rationale": (
                f"Policy requires '{top['missing_validation']}' for "
                f"semantic type '{top['semantic_type']}', but this check is absent. "
                f"Forbidden transform '{top['forbidden_found']}' was detected."
            ),
        }

    if scan.get("summary_flags"):
        flag = scan["summary_flags"][0]
        return {
            "type": "add_validation",
            "action": f"Add data quality test to address: {flag}",
            "target_column": "multiple",
            "validation": "format",
            "rationale": (
                f"Static SQL scan identified a risk pattern: {flag}. "
                "Adding an explicit DQ test will surface violations before downstream impact."
            ),
        }

    # Fallback: threshold adjustment
    return {
        "type": "adjust_threshold",
        "action": "Review and adjust DQ rule threshold based on current score trajectory",
        "target_column": "n/a",
        "validation": "n/a",
        "rationale": (
            "No specific SQL pattern gap detected. The threshold may not reflect "
            "achievable data quality given current pipeline constraints."
        ),
    }


# ---------------------------------------------------------------------------
# The Agent
# ---------------------------------------------------------------------------

class GovernanceAgent:

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.memory = LearningMemory()
        # Track last day's focus and recommendation for outcome measurement
        self._prev: dict = {}   # term_id → {score, recommendation_type}

    # ------------------------------------------------------------------
    # Step 1 — Detect breaches
    # ------------------------------------------------------------------

    def _step_detect_breaches(self, date_str: str) -> list[dict]:
        """Emit rule_breached events for every score below threshold."""
        all_breaches = []
        for term in _all_terms(self.conn):
            for rule in _rules_for_term(self.conn, term["term_id"]):
                tdes = _tdes_for_term(self.conn, term["term_id"])
                for tde in tdes:
                    sc = _score(self.conn, tde["tde_id"], date_str)
                    if sc is not None and sc < rule["threshold"]:
                        breach = {
                            "term_id": term["term_id"],
                            "term_name": term["name"],
                            "rule_id": rule["rule_id"],
                            "tde_id": tde["tde_id"],
                            "tde_name": tde["name"],
                            "score": sc,
                            "threshold": rule["threshold"],
                            "gap": round(rule["threshold"] - sc, 4),
                        }
                        all_breaches.append(breach)

                        emit_event(
                            self.conn,
                            event_type="rule_breached",
                            entity_type="rule",
                            entity_id=rule["rule_id"],
                            entity_name=f"{rule['rule_id']} → {tde['name']}",
                            context_dict={
                                "date": date_str,
                                "business_term": term["name"],
                                "tde": tde["name"],
                                "rule_description": rule["description"],
                            },
                            metrics_dict={
                                "score": sc,
                                "threshold": rule["threshold"],
                                "gap": round(rule["threshold"] - sc, 4),
                            },
                            explanation_text=(
                                f"Rule {rule['rule_id']} breached on {date_str}: "
                                f"'{tde['name']}' scored {sc:.4f} against threshold "
                                f"{rule['threshold']:.2f} "
                                f"(gap={rule['threshold']-sc:.4f}). "
                                f"Business term '{term['name']}' is at risk."
                            ),
                        )
                        self.memory.record_breach(term["term_id"])

        return all_breaches

    # ------------------------------------------------------------------
    # Step 2 — Assess risk
    # ------------------------------------------------------------------

    def _step_assess_risk(self, date_str: str) -> list[tuple[dict, float]]:
        """Compute risk score per business term and emit risk_assessed events."""
        term_risks = []
        for term in _all_terms(self.conn):
            rules = _rules_for_term(self.conn, term["term_id"])
            risk, breaches = _term_risk(self.conn, term, rules, date_str, self.memory)

            if not breaches:
                self.memory.record_no_breach(term["term_id"])

            attention = self.memory.get_attention_weight(term["term_id"])
            emit_event(
                self.conn,
                event_type="risk_assessed",
                entity_type="business_term",
                entity_id=term["term_id"],
                entity_name=term["name"],
                context_dict={
                    "date": date_str,
                    "breaches_detected": len(breaches),
                    "attention_weight": round(attention, 4),
                    "breach_details": breaches[:3],   # top-3 for readability
                },
                metrics_dict={
                    "risk_score": risk,
                    "criticality": term["criticality"],
                    "breach_count": len(breaches),
                    "attention_multiplier": round(attention, 4),
                },
                explanation_text=(
                    f"Business term '{term['name']}' carries a composite risk score of "
                    f"{risk:.4f} on {date_str}, derived from "
                    f"{len(breaches)} active rule breach(es) weighted by "
                    f"criticality {term['criticality']} and "
                    f"attention multiplier {attention:.2f}."
                ),
            )
            term_risks.append((term, risk))

        return sorted(term_risks, key=lambda x: x[1], reverse=True)

    # ------------------------------------------------------------------
    # Step 3 — Select focus
    # ------------------------------------------------------------------

    def _step_select_focus(self, term_risks: list, date_str: str, day_num: int) -> dict:
        """Choose the highest-risk business term as today's investigation focus."""
        focus_term, focus_risk = term_risks[0]
        self.memory.record_focus(day_num, focus_term["term_id"])

        runner_up = term_risks[1] if len(term_risks) > 1 else None
        explanation = llm_client.generate_explanation(
            "focus_selected",
            {
                "entity_name": focus_term["name"],
                "risk_score": focus_risk,
                "date": date_str,
                "runner_up": runner_up[0]["name"] if runner_up else "none",
                "runner_up_risk": round(runner_up[1], 4) if runner_up else 0,
                "attention_weight": self.memory.get_attention_weight(focus_term["term_id"]),
            },
        )

        emit_event(
            self.conn,
            event_type="focus_selected",
            entity_type="business_term",
            entity_id=focus_term["term_id"],
            entity_name=focus_term["name"],
            context_dict={
                "date": date_str,
                "selection_reason": "highest_adjusted_risk",
                "all_risks": [
                    {"term": t["name"], "risk": round(r, 4)} for t, r in term_risks
                ],
            },
            metrics_dict={
                "risk_score": focus_risk,
                "margin_over_runner_up": (
                    round(focus_risk - term_risks[1][1], 4)
                    if len(term_risks) > 1 else focus_risk
                ),
            },
            explanation_text=explanation,
        )
        return focus_term

    # ------------------------------------------------------------------
    # Step 4 — Start investigation
    # ------------------------------------------------------------------

    def _step_start_investigation(self, term: dict, date_str: str) -> None:
        explanation = llm_client.generate_explanation(
            "investigation_started",
            {
                "entity_name": term["name"],
                "date": date_str,
                "criticality": term["criticality"],
            },
        )
        emit_event(
            self.conn,
            event_type="investigation_started",
            entity_type="business_term",
            entity_id=term["term_id"],
            entity_name=term["name"],
            context_dict={
                "date": date_str,
                "investigation_scope": [
                    "tde_lineage", "dbt_model_scan", "policy_gap_check"
                ],
            },
            metrics_dict={"criticality": term["criticality"]},
            explanation_text=explanation,
        )

    # ------------------------------------------------------------------
    # Step 5 — Trace lineage
    # ------------------------------------------------------------------

    def _step_trace_lineage(self, term: dict, date_str: str) -> dict:
        """
        BusinessTerm → TDE → dbt model → column mapping.
        Returns the lineage dict for use in subsequent steps.
        """
        tdes = _tdes_for_term(self.conn, term["term_id"])
        lineage = {}  # tde_id → {tde_name, models: [{model_name, column_name}]}
        all_models = set()

        for tde in tdes:
            mappings = _models_for_tde(self.conn, tde["tde_id"])
            lineage[tde["tde_id"]] = {
                "tde_name": tde["name"],
                "models": mappings,
            }
            for m in mappings:
                all_models.add(m["model_name"])

        emit_event(
            self.conn,
            event_type="lineage_traced",
            entity_type="business_term",
            entity_id=term["term_id"],
            entity_name=term["name"],
            context_dict={
                "date": date_str,
                "tde_count": len(tdes),
                "model_count": len(all_models),
                "lineage": lineage,
            },
            metrics_dict={
                "tde_count": len(tdes),
                "model_count": len(all_models),
            },
            explanation_text=(
                f"Lineage traced for '{term['name']}': "
                f"{len(tdes)} Technical Data Element(s) materialised across "
                f"{len(all_models)} dbt model(s): {sorted(all_models)}. "
                "Each TDE-to-model link is a potential governance injection point."
            ),
        )
        return {"lineage": lineage, "models": sorted(all_models)}

    # ------------------------------------------------------------------
    # Step 6 — LLM SQL Analysis
    # ------------------------------------------------------------------

    def _step_analyze_sql(
        self, term: dict, lineage_info: dict, date_str: str
    ) -> dict:
        """
        For each dbt model in the lineage: static scan + LLM semantic enrichment.
        Returns analysis results keyed by model_name.
        """
        analysis_results = {}
        for model_name in lineage_info["models"]:
            sql_text = _sql_for_model(self.conn, model_name)
            if not sql_text:
                continue

            # Static scan (deterministic)
            scan = sql_scanner.scan_to_dict(model_name, sql_text)

            # Collect columns relevant to this business term
            relevant_cols = []
            for tde_data in lineage_info["lineage"].values():
                for m in tde_data["models"]:
                    if m["model_name"] == model_name:
                        relevant_cols.append(m["column_name"])
            # Also include all detected columns for semantic context
            all_cols = list(set(relevant_cols + scan["columns_detected"]))

            # LLM: infer semantic types (cached)
            sem_types = llm_client.infer_semantic_types(sql_text, all_cols)

            # LLM: detect risky transformations (cached)
            llm_risks = llm_client.detect_risky_transformations(sql_text)

            analysis_results[model_name] = {
                "scan": scan,
                "semantic_types": sem_types,
                "llm_risks": llm_risks,
                "relevant_columns": relevant_cols,
            }

            explanation = llm_client.generate_explanation(
                "sql_analysis_completed",
                {
                    "entity_name": model_name,
                    "business_term": term["name"],
                    "summary_flags": scan["summary_flags"],
                    "llm_risks_count": len(llm_risks),
                    "semantic_types": sem_types,
                },
            )

            emit_event(
                self.conn,
                event_type="sql_analysis_completed",
                entity_type="dbt_model",
                entity_id=model_name,
                entity_name=model_name,
                context_dict={
                    "date": date_str,
                    "business_term": term["name"],
                    "summary_flags": scan["summary_flags"],
                    "semantic_types": sem_types,
                    "llm_risk_count": len(llm_risks),
                    "llm_risks": llm_risks[:5],   # top-5
                    "pii_exposed": scan["pii_columns_exposed"],
                },
                metrics_dict={
                    "transformation_count": len(scan["transformations"]),
                    "join_count": scan["join_count"],
                    "has_non_equi_join": scan["has_non_equi_join"],
                    "flag_count": len(scan["summary_flags"]),
                    "llm_risk_count": len(llm_risks),
                },
                explanation_text=explanation,
            )

        return analysis_results

    # ------------------------------------------------------------------
    # Step 7 — Deterministic Policy Gap Detection
    # ------------------------------------------------------------------

    def _step_check_policies(
        self, term: dict, analysis_results: dict, date_str: str
    ) -> list[dict]:
        """
        Compare required validations (from ontology) against what SQL provides.
        All logic is deterministic Python — no LLM.
        """
        all_gaps: list[dict] = []
        for model_name, analysis in analysis_results.items():
            scan = analysis["scan"]
            sem_types = analysis["semantic_types"]
            gaps = policy_checker.detect_gaps(
                column_semantic_map=sem_types,
                scan_transformations=scan["transformations"],
                scan_flags=scan["summary_flags"],
                pii_exposed=scan["pii_columns_exposed"],
            )
            gap_dicts = policy_checker.gaps_to_dicts(gaps)
            all_gaps.extend(gap_dicts)

            for gap in gap_dicts:
                explanation = llm_client.generate_explanation(
                    "policy_gap_detected",
                    {
                        "entity_name": model_name,
                        "business_term": term["name"],
                        "column": gap["column_name"],
                        "semantic_type": gap["semantic_type"],
                        "missing_validation": gap["missing_validation"],
                        "forbidden_transform": gap["forbidden_found"],
                        "severity": gap["severity"],
                    },
                )
                emit_event(
                    self.conn,
                    event_type="policy_gap_detected",
                    entity_type="dbt_model",
                    entity_id=model_name,
                    entity_name=model_name,
                    context_dict={
                        "date": date_str,
                        "business_term": term["name"],
                        "column": gap["column_name"],
                        "semantic_type": gap["semantic_type"],
                        "missing_validation": gap["missing_validation"],
                        "forbidden_transform": gap["forbidden_found"],
                        "gap_description": gap["description"],
                    },
                    metrics_dict={
                        "severity_level": gap["severity"],
                        "severity_code": (
                            3 if gap["severity"] == "critical" else
                            2 if gap["severity"] == "high" else 1
                        ),
                    },
                    explanation_text=explanation,
                )

        return all_gaps

    # ------------------------------------------------------------------
    # Step 8 — Create Recommendation
    # ------------------------------------------------------------------

    def _step_create_recommendation(
        self,
        term: dict,
        gaps: list[dict],
        analysis_results: dict,
        date_str: str,
        current_score: float,
    ) -> dict:
        # Pick the first model's scan for SQL context
        first_scan = next(iter(analysis_results.values()), {}).get("scan", {})
        rec = _choose_recommendation(gaps, first_scan, self.memory)

        # Store for outcome measurement next day
        self.memory.record_recommendation(
            day=0,   # day_num will be recorded via the caller
            term_id=term["term_id"],
            recommendation_type=rec["type"],
            score_at_recommendation=current_score,
        )
        self._prev[term["term_id"]] = {
            "score": current_score,
            "recommendation_type": rec["type"],
        }

        explanation = llm_client.generate_explanation(
            "recommendation_created",
            {
                "entity_name": term["name"],
                "recommendation_type": rec["type"],
                "action": rec["action"],
                "rationale": rec["rationale"],
                "gaps_count": len(gaps),
            },
        )

        emit_event(
            self.conn,
            event_type="recommendation_created",
            entity_type="business_term",
            entity_id=term["term_id"],
            entity_name=term["name"],
            context_dict={
                "date": date_str,
                "recommendation_type": rec["type"],
                "action": rec["action"],
                "rationale": rec["rationale"],
                "target_column": rec.get("target_column", "n/a"),
                "validation_required": rec.get("validation", "n/a"),
                "gaps_addressed": len(gaps),
            },
            metrics_dict={
                "gap_count": len(gaps),
                "current_score": round(current_score, 4),
            },
            explanation_text=explanation,
        )
        return rec

    # ------------------------------------------------------------------
    # Step 9 — Measure Outcome
    # ------------------------------------------------------------------

    def _step_measure_outcome(self, term: dict, date_str: str) -> None:
        """Compare today's score to yesterday's; emit outcome_measured."""
        prev_info = self._prev.get(term["term_id"])
        if not prev_info:
            return

        tdes = _tdes_for_term(self.conn, term["term_id"])
        if not tdes:
            return
        tde = tdes[0]   # primary TDE for this term

        today_score = _score(self.conn, tde["tde_id"], date_str)
        if today_score is None:
            return

        prev_score = prev_info["score"]
        delta = round(today_score - prev_score, 4)
        improved = delta > 0.001

        # Record outcome in learning memory
        self.memory.record_outcome(
            day=0,
            term_id=term["term_id"],
            recommendation_type=prev_info["recommendation_type"],
            score_after=today_score,
        )

        emit_event(
            self.conn,
            event_type="outcome_measured",
            entity_type="business_term",
            entity_id=term["term_id"],
            entity_name=term["name"],
            context_dict={
                "date": date_str,
                "tde_measured": tde["name"],
                "recommendation_type": prev_info["recommendation_type"],
                "improvement_observed": improved,
            },
            metrics_dict={
                "score_before": round(prev_score, 4),
                "score_after": round(today_score, 4),
                "delta": delta,
                "improved": improved,
            },
            explanation_text=(
                f"Outcome measured for '{term['name']}' on {date_str}: "
                f"score moved from {prev_score:.4f} to {today_score:.4f} "
                f"(Δ={delta:+.4f}). "
                + (
                    "The previous recommendation appears effective — score improved."
                    if improved
                    else "Score did not improve; the recommendation may need reinforcement or escalation."
                )
            ),
        )

    # ------------------------------------------------------------------
    # Step 10 — Update Learning
    # ------------------------------------------------------------------

    def _step_update_learning(self, day_num: int, date_str: str) -> None:
        """Emit a learning_updated event summarising memory state."""
        summary = self.memory.summary()
        explanation = llm_client.generate_explanation(
            "learning_updated",
            {
                "day": day_num,
                "date": date_str,
                "preferred_recommendation": summary["preferred_recommendation"],
                "outcomes_recorded": summary["outcomes_recorded"],
                "attention_weights": summary["attention_weights"],
            },
        )
        emit_event(
            self.conn,
            event_type="learning_updated",
            entity_type="system",
            entity_id="agent",
            entity_name="GovernanceAgent",
            context_dict={
                "date": date_str,
                "day_number": day_num,
                "focus_history_last5": summary["focus_history_last5"],
                "preferred_recommendation": summary["preferred_recommendation"],
            },
            metrics_dict={
                "outcomes_recorded": summary["outcomes_recorded"],
                "attention_weights": summary["attention_weights"],
                "effectiveness": summary["effectiveness"],
            },
            explanation_text=explanation,
        )

    # ------------------------------------------------------------------
    # Main daily loop
    # ------------------------------------------------------------------

    def run_daily_cycle(self, date_str: str, day_num: int) -> dict:
        """
        Execute the full 10-step governance cycle for one day.
        Returns a summary dict for console reporting.
        """
        conn = self.conn

        # Step 1: Detect breaches
        breaches = self._step_detect_breaches(date_str)

        # Step 2: Assess risk per term
        term_risks = self._step_assess_risk(date_str)

        if not term_risks:
            return {"day": day_num, "date": date_str, "status": "no_terms"}

        # Step 3: Select focus
        focus_term = self._step_select_focus(term_risks, date_str, day_num)

        # Step 9 (prior focus): Measure outcome before starting new investigation
        self._step_measure_outcome(focus_term, date_str)

        # Step 4: Start investigation
        self._step_start_investigation(focus_term, date_str)

        # Step 5: Trace lineage
        lineage_info = self._step_trace_lineage(focus_term, date_str)

        # Step 6: SQL Analysis (LLM-assisted)
        analysis_results = self._step_analyze_sql(focus_term, lineage_info, date_str)

        # Step 7: Policy gap check (deterministic)
        gaps = self._step_check_policies(focus_term, analysis_results, date_str)

        # Compute current score for the primary TDE
        tdes = _tdes_for_term(conn, focus_term["term_id"])
        primary_score = (
            _score(conn, tdes[0]["tde_id"], date_str)
            if tdes else 0.0
        ) or 0.0

        # Step 8: Create recommendation
        rec = self._step_create_recommendation(
            focus_term, gaps, analysis_results, date_str, primary_score
        )

        # Step 10: Update learning
        self._step_update_learning(day_num, date_str)

        return {
            "day": day_num,
            "date": date_str,
            "focus_term": focus_term["name"],
            "risk_score": term_risks[0][1],
            "breach_count": len(breaches),
            "gap_count": len(gaps),
            "recommendation": rec["type"],
            "recommendation_action": rec["action"],
            "primary_score": round(primary_score, 4),
        }
