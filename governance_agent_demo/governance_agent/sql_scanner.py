"""
SQL Scanner — static analysis of dbt SQL models.

Performs deterministic, regex-based detection of transformation patterns
that are governance-relevant.  Results feed the policy checker and provide
the raw material for LLM semantic enrichment.

No dbt runtime is invoked.  All analysis is purely lexical/structural.
"""

import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

_PATTERNS = {
    # CAST(expr AS type)
    "cast": re.compile(
        r"\bCAST\s*\([^)]+\bAS\s+(\w+)", re.IGNORECASE
    ),
    # CAST to integer specifically
    "cast_integer": re.compile(
        r"\bCAST\s*\([^)]+\bAS\s+(?:INTEGER|INT|BIGINT|SMALLINT|TINYINT)\b",
        re.IGNORECASE,
    ),
    # COALESCE(...)
    "coalesce": re.compile(r"\bCOALESCE\s*\(", re.IGNORECASE),
    # Any JOIN
    "join": re.compile(r"\b(?:INNER|LEFT|RIGHT|FULL|CROSS)?\s*JOIN\b", re.IGNORECASE),
    # Non-equi join condition (<=, >=, <, >) — can cause fan-out
    "non_equi_join": re.compile(r"\bJOIN\b.*?ON\b.*?(?:<=|>=|<(?!=)|>(?!=))", re.IGNORECASE | re.DOTALL),
    # LOWER() / UPPER() on what could be email or ID
    "lower": re.compile(r"\bLOWER\s*\(", re.IGNORECASE),
    "upper": re.compile(r"\bUPPER\s*\(", re.IGNORECASE),
    # CONCAT on multiple columns — potential PII assembly
    "concat_pii": re.compile(r"\bCONCAT\s*\([^)]+,[^)]+\)", re.IGNORECASE),
    # LPAD/RPAD without null guard
    "lpad": re.compile(r"\bLPAD\s*\(", re.IGNORECASE),
    # Date/timestamp truncation
    "date_truncation": re.compile(r"\bDATE_TRUNC\s*\(|\bTRUNC\s*\(", re.IGNORECASE),
    # String replace that could mangle IDs
    "replace": re.compile(r"\bREPLACE\s*\(", re.IGNORECASE),
}

# Columns that suggest PII content by name
_PII_COLUMN_HINTS = re.compile(
    r"\b(full_name|date_of_birth|dob|ssn|national_id|passport|phone|address|"
    r"first_name|last_name|surname|forename|email)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Result structures
# ---------------------------------------------------------------------------

@dataclass
class TransformationFinding:
    pattern_type: str          # e.g. "coalesce", "cast_integer"
    matched_text: str          # the snippet that triggered the match
    line_number: int           # approximate 1-indexed line


@dataclass
class ScanResult:
    model_name: str
    columns_detected: list[str] = field(default_factory=list)
    transformations: list[TransformationFinding] = field(default_factory=list)
    pii_columns_exposed: list[str] = field(default_factory=list)
    join_count: int = 0
    has_non_equi_join: bool = False
    summary_flags: list[str] = field(default_factory=list)   # human-readable flags


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

def _extract_select_columns(sql_text: str) -> list[str]:
    """
    Heuristically extract output column aliases from the final SELECT.
    Looks for patterns like:  <expr> AS <alias>  or  <table>.<column>
    """
    # Find the last SELECT block
    select_match = list(re.finditer(r"\bSELECT\b", sql_text, re.IGNORECASE))
    if not select_match:
        return []

    start = select_match[-1].end()
    # Up to first FROM after that SELECT
    from_match = re.search(r"\bFROM\b", sql_text[start:], re.IGNORECASE)
    select_clause = sql_text[start: start + from_match.start()] if from_match else sql_text[start:]

    # Extract AS aliases
    aliases = re.findall(r"\bAS\s+(\w+)", select_clause, re.IGNORECASE)

    # Extract bare column references (table.column) not already aliased
    bare = re.findall(r"\b\w+\.(\w+)\b", select_clause)

    # Wildcard expansion placeholder
    if re.search(r"\bSELECT\s+\*", sql_text, re.IGNORECASE):
        aliases.append("*")

    seen = set()
    result = []
    for col in aliases + bare:
        if col.lower() not in seen:
            seen.add(col.lower())
            result.append(col)

    return result


def scan_model(model_name: str, sql_text: str) -> ScanResult:
    """
    Statically analyse a dbt SQL model for governance-relevant patterns.
    Returns a ScanResult with all findings.
    """
    result = ScanResult(model_name=model_name)
    result.columns_detected = _extract_select_columns(sql_text)
    lines = sql_text.splitlines()

    # Scan each pattern
    for pattern_name, pattern in _PATTERNS.items():
        for match in pattern.finditer(sql_text):
            # Compute approximate line number
            line_num = sql_text[: match.start()].count("\n") + 1
            snippet = match.group(0)[:120]  # truncate for readability
            result.transformations.append(
                TransformationFinding(
                    pattern_type=pattern_name,
                    matched_text=snippet,
                    line_number=line_num,
                )
            )

    # Count JOINs
    result.join_count = len([
        t for t in result.transformations if t.pattern_type == "join"
    ])
    result.has_non_equi_join = any(
        t.pattern_type == "non_equi_join" for t in result.transformations
    )

    # PII exposure scan — look for unmasked PII column names in SELECT
    for col in result.columns_detected:
        if _PII_COLUMN_HINTS.search(col):
            result.pii_columns_exposed.append(col)

    # Build human-readable summary flags
    flags = []
    transformation_types = {t.pattern_type for t in result.transformations}

    if "cast_integer" in transformation_types:
        flags.append("INTEGER_CAST: decimal precision at risk")
    elif "cast" in transformation_types:
        flags.append("CAST: type conversion may alter semantics")
    if "coalesce" in transformation_types:
        flags.append("COALESCE: null masking detected — root cause obscured")
    if result.has_non_equi_join:
        flags.append("NON_EQUI_JOIN: potential row fan-out on join condition")
    elif result.join_count > 0:
        flags.append(f"JOIN_PRESENT: {result.join_count} join(s) detected")
    if "lower" in transformation_types or "upper" in transformation_types:
        flags.append("CASE_TRANSFORM: LOWER/UPPER applied — format risk")
    if "concat_pii" in transformation_types:
        flags.append("CONCAT_PII: PII fields concatenated in plain text")
    if result.pii_columns_exposed:
        flags.append(f"PII_EXPOSED: {result.pii_columns_exposed} present unmasked")
    if "lpad" in transformation_types:
        flags.append("LPAD: ID formatting without null guard")
    if "date_truncation" in transformation_types:
        flags.append("DATE_TRUNCATION: temporal granularity may be lost")

    result.summary_flags = flags
    return result


def scan_to_dict(model_name: str, sql_text: str) -> dict:
    """Convenience wrapper — returns ScanResult as a plain dict."""
    sr = scan_model(model_name, sql_text)
    return {
        "model_name": sr.model_name,
        "columns_detected": sr.columns_detected,
        "transformations": [
            {
                "pattern_type": t.pattern_type,
                "matched_text": t.matched_text,
                "line_number": t.line_number,
            }
            for t in sr.transformations
        ],
        "pii_columns_exposed": sr.pii_columns_exposed,
        "join_count": sr.join_count,
        "has_non_equi_join": sr.has_non_equi_join,
        "summary_flags": sr.summary_flags,
    }
