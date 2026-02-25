// ─── Event type display metadata ────────────────────────────────────────────

export const EVENT_META = {
  rule_breached: {
    color:  '#ef4444',
    bg:     'rgba(239,68,68,0.12)',
    label:  'Rule Breached',
    icon:   '⚠',
    short:  'BR',
  },
  risk_assessed: {
    color:  '#f59e0b',
    bg:     'rgba(245,158,11,0.12)',
    label:  'Risk Assessed',
    icon:   '⚡',
    short:  'RA',
  },
  focus_selected: {
    color:  '#a855f7',
    bg:     'rgba(168,85,247,0.12)',
    label:  'Focus Selected',
    icon:   '🎯',
    short:  'FS',
  },
  investigation_started: {
    color:  '#3b82f6',
    bg:     'rgba(59,130,246,0.12)',
    label:  'Investigation Started',
    icon:   '🔍',
    short:  'IS',
  },
  lineage_traced: {
    color:  '#06b6d4',
    bg:     'rgba(6,182,212,0.12)',
    label:  'Lineage Traced',
    icon:   '🔗',
    short:  'LT',
  },
  sql_analysis_completed: {
    color:  '#6366f1',
    bg:     'rgba(99,102,241,0.12)',
    label:  'SQL Analysis',
    icon:   '📊',
    short:  'SA',
  },
  policy_gap_detected: {
    color:  '#f97316',
    bg:     'rgba(249,115,22,0.12)',
    label:  'Policy Gap',
    icon:   '🚨',
    short:  'PG',
  },
  recommendation_created: {
    color:  '#22c55e',
    bg:     'rgba(34,197,94,0.12)',
    label:  'Recommendation',
    icon:   '💡',
    short:  'RC',
  },
  outcome_measured: {
    color:  '#14b8a6',
    bg:     'rgba(20,184,166,0.12)',
    label:  'Outcome Measured',
    icon:   '📈',
    short:  'OM',
  },
  learning_updated: {
    color:  '#ec4899',
    bg:     'rgba(236,72,153,0.12)',
    label:  'Learning Updated',
    icon:   '🧠',
    short:  'LU',
  },
}

export const DEFAULT_EVENT = {
  color: '#64748b',
  bg:    'rgba(100,116,139,0.12)',
  label: 'Event',
  icon:  '●',
  short: '??',
}

export function eventMeta(type) {
  return EVENT_META[type] || DEFAULT_EVENT
}

// ─── Status colours ──────────────────────────────────────────────────────────

export const STATUS_META = {
  investigating: { color: '#a855f7', bg: 'rgba(168,85,247,0.15)', label: 'Investigating' },
  breached:      { color: '#ef4444', bg: 'rgba(239,68,68,0.15)',  label: 'Breached'      },
  declining:     { color: '#f97316', bg: 'rgba(249,115,22,0.15)', label: 'Declining'     },
  improving:     { color: '#22c55e', bg: 'rgba(34,197,94,0.15)',  label: 'Improving'     },
  stable:        { color: '#14b8a6', bg: 'rgba(20,184,166,0.15)', label: 'Stable'        },
}

export function statusMeta(status) {
  return STATUS_META[status] || STATUS_META.stable
}

// ─── Recommendation colours ───────────────────────────────────────────────────

export const REC_COLORS = {
  add_validation:    '#22c55e',
  move_earlier:      '#3b82f6',
  adjust_threshold:  '#f59e0b',
  unknown:           '#64748b',
}

export function recColor(type) {
  return REC_COLORS[type] || REC_COLORS.unknown
}

// ─── Score colour (green / amber / red) ──────────────────────────────────────

export function scoreColor(score) {
  if (score == null) return '#64748b'
  if (score >= 0.95) return '#22c55e'
  if (score >= 0.90) return '#f59e0b'
  return '#ef4444'
}

export function deltaColor(delta) {
  if (delta == null) return '#64748b'
  if (delta > 0.001)  return '#22c55e'
  if (delta < -0.001) return '#ef4444'
  return '#94a3b8'
}
