"""
Learning Memory — adaptive prioritisation and pattern reinforcement.

The agent accumulates evidence about which recommendation types lead to
score improvements and biases future focus selection accordingly.

This is purely deterministic Python — no LLM.
Data is not persisted across simulation runs (in-memory only).
"""

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class OutcomeRecord:
    day: int
    term_id: str
    recommendation_type: str   # e.g. "add_validation", "move_earlier", "adjust_threshold"
    score_before: float
    score_after: float

    @property
    def delta(self) -> float:
        return self.score_after - self.score_before

    @property
    def improved(self) -> bool:
        return self.delta > 0.001


class LearningMemory:
    """
    Tracks recommendation effectiveness and adjusts attention weights.

    attention_weights: per-term modifier applied on top of raw risk scores.
      > 1.0 → agent is primed to focus here (seen persistent issues)
      < 1.0 → agent deprioritises (term consistently improving)

    effectiveness: per-recommendation-type running average of score delta.
      Used to bias which recommendation type the agent prefers.
    """

    def __init__(self):
        # term_id → attention weight (float, starts at 1.0)
        self.attention_weights: dict[str, float] = defaultdict(lambda: 1.0)

        # recommendation_type → list of observed score deltas
        self._rec_deltas: dict[str, list[float]] = defaultdict(list)

        # History of all outcome records
        self.outcomes: list[OutcomeRecord] = []

        # term_id → list of consecutive days with breach (for streak detection)
        self._breach_streaks: dict[str, int] = defaultdict(int)

        # Focus history: list of (day, term_id) — for shift detection
        self.focus_history: list[tuple[int, str]] = []

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_focus(self, day: int, term_id: str) -> None:
        self.focus_history.append((day, term_id))

    def record_breach(self, term_id: str) -> None:
        """Increment breach streak; boosts attention weight."""
        self._breach_streaks[term_id] += 1
        streak = self._breach_streaks[term_id]
        # Each consecutive breach day raises attention by 5%, capped at 2.5×
        self.attention_weights[term_id] = min(
            2.5,
            self.attention_weights[term_id] * (1 + 0.05 * min(streak, 5))
        )

    def record_no_breach(self, term_id: str) -> None:
        """Reset streak; gently decay attention weight toward 1.0."""
        self._breach_streaks[term_id] = 0
        w = self.attention_weights[term_id]
        self.attention_weights[term_id] = max(1.0, w * 0.90)

    def record_recommendation(
        self,
        day: int,
        term_id: str,
        recommendation_type: str,
        score_at_recommendation: float,
    ) -> None:
        """Store a pending recommendation for outcome tracking."""
        # Outcome will be recorded next day via record_outcome
        self._pending: dict = getattr(self, "_pending", {})
        self._pending[(term_id, recommendation_type)] = (day, score_at_recommendation)

    def record_outcome(
        self,
        day: int,
        term_id: str,
        recommendation_type: str,
        score_after: float,
    ) -> OutcomeRecord | None:
        """
        Record the outcome of a previous recommendation.
        Updates effectiveness and attention weights.
        """
        pending = getattr(self, "_pending", {})
        key = (term_id, recommendation_type)
        if key not in pending:
            return None

        prev_day, score_before = pending.pop(key)
        record = OutcomeRecord(
            day=day,
            term_id=term_id,
            recommendation_type=recommendation_type,
            score_before=score_before,
            score_after=score_after,
        )
        self.outcomes.append(record)
        self._rec_deltas[recommendation_type].append(record.delta)

        # Update attention weight based on improvement
        if record.improved:
            # Score is getting better → relax attention weight
            self.attention_weights[term_id] = max(
                0.6, self.attention_weights[term_id] * 0.85
            )
        else:
            # No improvement → slightly increase attention (still a problem)
            self.attention_weights[term_id] = min(
                2.5, self.attention_weights[term_id] * 1.10
            )

        return record

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_attention_weight(self, term_id: str) -> float:
        return self.attention_weights[term_id]

    def get_effectiveness(self, recommendation_type: str) -> float:
        """
        Returns the average score delta for a recommendation type.
        Positive = effective; negative = counter-productive; 0 = neutral/unknown.
        """
        deltas = self._rec_deltas[recommendation_type]
        if not deltas:
            return 0.0
        return sum(deltas) / len(deltas)

    def preferred_recommendation_type(self) -> str:
        """
        Return the recommendation type with the best average effectiveness.
        Defaults to 'add_validation' if no evidence yet.
        """
        types = ["add_validation", "move_earlier", "adjust_threshold"]
        best = max(types, key=self.get_effectiveness)
        return best

    def summary(self) -> dict:
        """Serialisable summary for event context."""
        return {
            "attention_weights": dict(self.attention_weights),
            "effectiveness": {
                k: round(sum(v) / len(v), 4)
                for k, v in self._rec_deltas.items()
                if v
            },
            "outcomes_recorded": len(self.outcomes),
            "focus_history_last5": self.focus_history[-5:],
            "preferred_recommendation": self.preferred_recommendation_type(),
        }
