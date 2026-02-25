"""
Policy Checker — deterministic governance gap detector.

Loads the policy ontology YAML and compares required validations against:
  1. SQL transformation patterns found by the static scanner
  2. Semantic types inferred by the LLM

All gap detection logic is pure Python — no LLM involvement.
"""

import yaml
from dataclasses import dataclass, field
from governance_agent.config import POLICY_ONTOLOGY_PATH


# ---------------------------------------------------------------------------
# Load ontology (cached after first load)
# ---------------------------------------------------------------------------
_ONTOLOGY: dict | None = None


def load_ontology() -> dict:
    global _ONTOLOGY
    if _ONTOLOGY is None:
        with open(POLICY_ONTOLOGY_PATH, "r") as fh:
            _ONTOLOGY = yaml.safe_load(fh)
    return _ONTOLOGY


# ---------------------------------------------------------------------------
# Gap structure
# ---------------------------------------------------------------------------

@dataclass
class PolicyGap:
    column_name: str
    semantic_type: str
    missing_validation: str   # e.g. "not_null", "format", "masking"
    forbidden_found: str      # e.g. "coalesce" if a forbidden transform is present
    severity: str             # "critical" | "high" | "medium"
    description: str


# ---------------------------------------------------------------------------
# Core gap detection
# ---------------------------------------------------------------------------

# Map SQL scanner pattern_type → ontology forbidden_transformation key
_SCANNER_TO_ONTOLOGY = {
    "cast_integer":  "cast_integer",
    "cast":          "cast_integer",   # general cast also triggers amount check
    "coalesce":      "coalesce",
    "lower":         "lower",
    "concat_pii":    "concat_pii",
    "lpad":          "concat_fallback",
    "replace":       "concat_fallback",
}

# Validations that are inferred from SQL patterns found by the scanner
_PATTERN_IMPLIES_MISSING = {
    # If COALESCE is on an email column, not_null and format are at risk
    ("email",   "coalesce"): ["not_null", "format"],
    # If CAST_INTEGER is on an amount column, range and numeric are at risk
    ("amount",  "cast_integer"): ["numeric", "range"],
    ("amount",  "coalesce"):     ["range"],
    # If COALESCE is on an id column, uniqueness is at risk
    ("id",      "coalesce"):     ["uniqueness"],
    ("id",      "lpad"):         ["format"],
    # PII in plain text → masking missing
    ("pii",     "concat_pii"):   ["masking"],
    ("pii",     "lower"):        ["masking"],
}

# Severity mapping
def _severity_for(validation: str, semantic_type: str) -> str:
    if validation == "masking" or semantic_type == "pii":
        return "critical"
    if validation in ("uniqueness", "not_null") or semantic_type == "id":
        return "high"
    return "medium"


def detect_gaps(
    column_semantic_map: dict[str, str],   # {column_name: semantic_type}
    scan_transformations: list[dict],       # from sql_scanner.scan_to_dict()
    scan_flags: list[str],                  # summary_flags from scanner
    pii_exposed: list[str],                 # pii_columns_exposed from scanner
) -> list[PolicyGap]:
    """
    Deterministically detect policy gaps by comparing:
      - what the policy ontology requires for each semantic type
      - what the SQL scanner found (transformation patterns)
      - which PII columns are exposed without masking

    Returns a list of PolicyGap objects.
    """
    ontology = load_ontology()
    gaps: list[PolicyGap] = []

    # Collect observed forbidden transformations from scanner
    observed_patterns = {t["pattern_type"] for t in scan_transformations}

    for col, sem_type in column_semantic_map.items():
        sem_type_lower = sem_type.lower()
        if sem_type_lower not in ontology:
            continue  # No policy defined for this type

        policy = ontology[sem_type_lower]
        required_validations = set(policy.get("required_validations", []))
        forbidden_transforms = set(policy.get("forbidden_transformations", []))

        # 1. Check for forbidden transformations present in SQL
        for obs_pattern in observed_patterns:
            ontology_key = _SCANNER_TO_ONTOLOGY.get(obs_pattern)
            if ontology_key and ontology_key in forbidden_transforms:
                # Determine which validations this compromises
                implied_missing = _PATTERN_IMPLIES_MISSING.get(
                    (sem_type_lower, obs_pattern), []
                )
                for missing_val in implied_missing:
                    if missing_val in required_validations:
                        gaps.append(PolicyGap(
                            column_name=col,
                            semantic_type=sem_type_lower,
                            missing_validation=missing_val,
                            forbidden_found=obs_pattern,
                            severity=_severity_for(missing_val, sem_type_lower),
                            description=(
                                f"Column '{col}' ({sem_type_lower}) uses "
                                f"'{obs_pattern}' transformation which violates the "
                                f"'{missing_val}' policy requirement. "
                                f"The ontology forbids '{ontology_key}' for "
                                f"semantic type '{sem_type_lower}'."
                            ),
                        ))

        # 2. PII exposure gap — column is PII type but not in masking context
        if sem_type_lower == "pii" and col in pii_exposed:
            gaps.append(PolicyGap(
                column_name=col,
                semantic_type="pii",
                missing_validation="masking",
                forbidden_found="plain_select",
                severity="critical",
                description=(
                    f"Column '{col}' contains PII data and is materialised "
                    f"in plain text without masking, tokenisation, or encryption. "
                    f"This violates the PII masking policy for analytical data products."
                ),
            ))

    # Deduplicate by (column, missing_validation)
    seen = set()
    deduped = []
    for gap in gaps:
        key = (gap.column_name, gap.missing_validation)
        if key not in seen:
            seen.add(key)
            deduped.append(gap)

    # Sort by severity (critical first)
    severity_order = {"critical": 0, "high": 1, "medium": 2}
    deduped.sort(key=lambda g: severity_order.get(g.severity, 3))
    return deduped


def gaps_to_dicts(gaps: list[PolicyGap]) -> list[dict]:
    return [
        {
            "column_name": g.column_name,
            "semantic_type": g.semantic_type,
            "missing_validation": g.missing_validation,
            "forbidden_found": g.forbidden_found,
            "severity": g.severity,
            "description": g.description,
        }
        for g in gaps
    ]
