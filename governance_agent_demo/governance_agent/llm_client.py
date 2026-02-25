"""
LLM Client — semantic interpretation layer.

The LLM is permitted ONLY to:
  1. Interpret a rule description → validation category
  2. Infer semantic types of SQL output columns
  3. Detect risky SQL transformations (cast, coalesce, join patterns)
  4. Generate natural-language explanation text for governance events

The LLM must NOT make governance decisions, assign severity, or override
deterministic Python logic.  All results are advisory inputs to the agent.

Includes an in-process cache keyed by (function, content_hash) to avoid
duplicate API calls during a single simulation run, and a graceful fallback
for every call in case the API is unavailable.
"""

import json
import hashlib
import re
from functools import lru_cache
from typing import Any

import anthropic

from governance_agent.config import (
    LLM_MODEL,
    LLM_MAX_TOKENS_SHORT,
    LLM_MAX_TOKENS_MEDIUM,
    LLM_MAX_TOKENS_LONG,
)

_client = anthropic.Anthropic()

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def _call(prompt: str, max_tokens: int) -> str:
    """Low-level API call with a single retry on transient error."""
    for attempt in range(2):
        try:
            response = _client.messages.create(
                model=LLM_MODEL,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as exc:
            if attempt == 0:
                continue
            raise RuntimeError(f"LLM call failed after 2 attempts: {exc}") from exc
    return ""


def _parse_json(text: str, fallback: Any) -> Any:
    """Extract JSON from LLM output, tolerating markdown fences."""
    # Strip markdown code fences if present
    clean = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).strip().strip("`").strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        return fallback


# ---------------------------------------------------------------------------
# Simple in-memory cache
# ---------------------------------------------------------------------------
_cache: dict[str, Any] = {}


def _cached(key: str, compute_fn):
    if key not in _cache:
        _cache[key] = compute_fn()
    return _cache[key]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

VALID_VALIDATION_CATEGORIES = {
    "not_null", "format", "numeric", "range", "uniqueness", "masking",
}

def interpret_rule(rule_description: str) -> str:
    """
    Classify a rule description into a single validation category.
    Returns one of: not_null | format | numeric | range | uniqueness | masking
    Falls back to 'format' if the LLM response is unrecognisable.
    """
    cache_key = f"rule:{_hash(rule_description)}"

    def _compute():
        prompt = (
            "You are a data quality rule classifier for a governance system.\n"
            "Given the rule description below, respond with EXACTLY ONE of these "
            "validation categories and nothing else:\n"
            "  not_null | format | numeric | range | uniqueness | masking\n\n"
            "Do not explain. Do not add punctuation. Output only the category name.\n\n"
            f"Rule: {rule_description}"
        )
        try:
            result = _call(prompt, LLM_MAX_TOKENS_SHORT).lower().strip()
            # Validate the returned category
            for cat in VALID_VALIDATION_CATEGORIES:
                if cat in result:
                    return cat
            return "format"  # safe fallback
        except Exception:
            return "format"

    return _cached(cache_key, _compute)


def infer_semantic_types(sql_text: str, columns: list[str]) -> dict[str, str]:
    """
    Infer the semantic type of each named output column from SQL context.
    Returns a dict: {column_name: semantic_type}
    Valid types: email | amount | id | pii | text | date | numeric
    Falls back to 'text' for all columns on error.
    """
    cache_key = f"semtype:{_hash(sql_text + '|'.join(sorted(columns)))}"

    def _compute():
        cols_str = ", ".join(columns)
        prompt = (
            "You are a data governance semantic classifier.\n"
            "Given the SQL model below, classify each output column's semantic type.\n"
            "Valid semantic types: email | amount | id | pii | text | date | numeric\n\n"
            "Rules:\n"
            "- email: columns storing email addresses\n"
            "- amount: monetary, metric, or measurement values\n"
            "- id: primary/foreign keys and identifiers\n"
            "- pii: names, birth dates, addresses, SSNs\n"
            "- date: temporal columns\n"
            "- numeric: any numeric that is not monetary\n"
            "- text: general string data\n\n"
            f"Columns to classify: {cols_str}\n\n"
            "SQL:\n"
            f"{sql_text}\n\n"
            "Respond with ONLY a valid JSON object mapping each column name to its "
            "semantic type. No explanation, no markdown fences.\n"
            f'Example: {{"{columns[0]}": "email"}}'
        )
        try:
            raw = _call(prompt, LLM_MAX_TOKENS_MEDIUM)
            result = _parse_json(raw, {})
            # Fill in any missing columns with 'text'
            return {col: result.get(col, "text") for col in columns}
        except Exception:
            return {col: "text" for col in columns}

    return _cached(cache_key, _compute)


def detect_risky_transformations(sql_text: str) -> list[dict]:
    """
    Identify risky SQL transformations that can compromise data quality.
    Returns a list of risk dicts:
      {transformation_type, column_affected, risk_description, severity}
    Falls back to [] on error.
    """
    cache_key = f"risks:{_hash(sql_text)}"

    def _compute():
        prompt = (
            "You are a SQL data governance risk analyst.\n"
            "Analyse the SQL below for transformations that could compromise data quality.\n"
            "Focus on:\n"
            "  - CAST operations that lose precision or change semantics\n"
            "  - COALESCE that masks nulls instead of fixing the root cause\n"
            "  - JOINs that can fan out and create duplicate rows\n"
            "  - String manipulation that could corrupt data formats\n"
            "  - Date truncation that loses temporal granularity\n\n"
            "SQL:\n"
            f"{sql_text}\n\n"
            "Respond with ONLY a valid JSON array. Each element must have:\n"
            '  "transformation_type": one of [cast, coalesce, join, string_manipulation, date_truncation]\n'
            '  "column_affected": the output column name (or "multiple")\n'
            '  "risk_description": one sentence describing the data quality risk\n'
            '  "severity": one of [low, medium, high]\n\n'
            "No explanation. No markdown. Only the JSON array."
        )
        try:
            raw = _call(prompt, LLM_MAX_TOKENS_MEDIUM)
            result = _parse_json(raw, [])
            if isinstance(result, list):
                return result
            return []
        except Exception:
            return []

    return _cached(cache_key, _compute)


def generate_explanation(event_type: str, context: dict) -> str:
    """
    Generate a 2-3 sentence governance narrative for a reasoning event.
    The LLM speaks from the perspective of a Data Steward Agent.
    Falls back to a template string on error.
    """
    cache_key = f"explain:{event_type}:{_hash(json.dumps(context, default=str, sort_keys=True))}"

    def _compute():
        prompt = (
            "You are an enterprise Data Steward Agent explaining your reasoning to "
            "a human data steward.\n\n"
            f"Event type: {event_type}\n"
            f"Context:\n{json.dumps(context, indent=2, default=str)}\n\n"
            "Write 2-3 sentences explaining this governance event. Requirements:\n"
            "- Use business language, not code or technical jargon\n"
            "- Be specific about which data asset is affected and why it matters\n"
            "- Describe the implication for data consumers\n"
            "- Do NOT start with 'I' or use first-person pronouns\n"
            "- Do NOT repeat the event_type verbatim\n"
            "Output only the explanation text."
        )
        try:
            return _call(prompt, LLM_MAX_TOKENS_LONG)
        except Exception:
            return (
                f"Governance event '{event_type}' recorded for "
                f"{context.get('entity_name', 'entity')}. "
                "Further investigation is required to assess impact on downstream consumers."
            )

    return _cached(cache_key, _compute)
