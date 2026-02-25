import { useState } from 'react'
import { eventMeta, scoreColor, deltaColor, recColor } from '../constants.js'
import LineageGraph from './LineageGraph.jsx'

// ── Helpers ──────────────────────────────────────────────────────────────────

function EventBadge({ type }) {
  const m = eventMeta(type)
  return (
    <span
      className="event-badge"
      style={{ background: m.bg, color: m.color, border: `1px solid ${m.color}33` }}
    >
      {m.icon} {m.label}
    </span>
  )
}

function MetricPill({ label, value, color }) {
  return (
    <span className="metric-pill" style={{ color: color || 'var(--text-secondary)' }}>
      {label}: <strong>{value}</strong>
    </span>
  )
}

function SectionTitle({ children }) {
  return <div className="tab-section-title">{children}</div>
}

function EventBlock({ event }) {
  const [open, setOpen] = useState(false)
  const m = eventMeta(event.event_type)

  return (
    <div className="event-row" style={{ borderLeft: `3px solid ${m.color}` }}>
      <div className="event-row-header">
        <EventBadge type={event.event_type} />
        <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 'auto' }}>
          {event.entity_name}
        </span>
      </div>

      {event.explanation && (
        <p className="explanation" style={{ fontSize: 12, borderLeftColor: m.color + '44' }}>
          {event.explanation}
        </p>
      )}

      {/* Expandable metrics/context */}
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          marginTop: 6,
          background: 'none',
          border: 'none',
          color: 'var(--text-muted)',
          fontSize: 11,
          cursor: 'pointer',
          padding: 0,
        }}
      >
        {open ? '▲ hide details' : '▼ show metrics'}
      </button>

      {open && (
        <div style={{ marginTop: 8 }}>
          <div className="event-row-meta">
            {Object.entries(event.metrics || {}).map(([k, v]) => (
              typeof v !== 'object' && (
                <MetricPill key={k} label={k} value={String(v)} />
              )
            ))}
          </div>
          {Object.keys(event.context || {}).length > 0 && (
            <pre style={{
              fontSize: 10,
              color: 'var(--text-muted)',
              background: 'var(--bg-input)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              padding: '8px',
              overflow: 'auto',
              maxHeight: 160,
              marginTop: 6,
              fontFamily: 'var(--font-mono)',
              lineHeight: 1.6,
            }}>
              {JSON.stringify(event.context, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}

// ── Tab: Problem ─────────────────────────────────────────────────────────────

function ProblemTab({ inv }) {
  const breaches   = (inv.events || []).filter(e => e.event_type === 'rule_breached')
  const riskEvents = (inv.events || []).filter(e => e.event_type === 'risk_assessed')
  const focus      = (inv.events || []).find(e => e.event_type === 'focus_selected')

  return (
    <div>
      {/* Focus context */}
      {focus && (
        <div className="tab-section">
          <SectionTitle>Why this term was selected</SectionTitle>
          <p className="explanation">{focus.explanation}</p>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
            <MetricPill label="risk score"  value={(focus.metrics?.risk_score ?? 0).toFixed(4)} color="var(--accent-red)" />
            <MetricPill label="margin over runner-up" value={(focus.metrics?.margin_over_runner_up ?? 0).toFixed(4)} />
          </div>
        </div>
      )}

      {/* Rule breaches */}
      {breaches.length > 0 && (
        <div className="tab-section">
          <SectionTitle>Rule Breaches ({breaches.length})</SectionTitle>
          {breaches.map((e, i) => (
            <div key={i} className="event-row" style={{ borderLeft: '3px solid var(--accent-red)' }}>
              <div className="event-row-header">
                <EventBadge type="rule_breached" />
                <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 'auto' }}>
                  {e.context?.tde || e.entity_name}
                </span>
              </div>
              <div className="event-row-meta">
                <MetricPill label="score"     value={(e.metrics?.score ?? 0).toFixed(4)}     color={scoreColor(e.metrics?.score)} />
                <MetricPill label="threshold" value={(e.metrics?.threshold ?? 0).toFixed(2)} />
                <MetricPill label="gap"       value={(e.metrics?.gap ?? 0).toFixed(4)}       color="var(--accent-red)" />
              </div>
              {e.explanation && <p className="explanation" style={{ fontSize: 12 }}>{e.explanation}</p>}
            </div>
          ))}
        </div>
      )}

      {/* Risk assessment per term */}
      {riskEvents.length > 0 && (
        <div className="tab-section">
          <SectionTitle>Risk Assessment — all business terms</SectionTitle>
          {riskEvents.map((e, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '8px 12px',
              background: 'var(--bg-input)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              marginBottom: 6,
            }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{e.entity_name}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  {e.metrics?.breach_count ?? 0} breach(es) · criticality {e.metrics?.criticality ?? '—'}
                </div>
              </div>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 18,
                fontWeight: 700,
                color: (e.metrics?.risk_score ?? 0) > 0.1 ? 'var(--accent-amber)' : 'var(--accent-teal)',
              }}>
                {(e.metrics?.risk_score ?? 0).toFixed(4)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Tab: Reasoning ───────────────────────────────────────────────────────────

function ReasoningTab({ inv }) {
  const lineageEvt = (inv.events || []).find(e => e.event_type === 'lineage_traced')
  const sqlEvts    = (inv.events || []).filter(e => e.event_type === 'sql_analysis_completed')
  const gapEvts    = (inv.events || []).filter(e => e.event_type === 'policy_gap_detected')

  return (
    <div>
      {/* Lineage */}
      {lineageEvt && (
        <div className="tab-section">
          <SectionTitle>Lineage Traced</SectionTitle>
          <p className="explanation">{lineageEvt.explanation}</p>
          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
            <MetricPill label="TDEs"   value={lineageEvt.metrics?.tde_count ?? 0}   color="var(--accent-cyan)" />
            <MetricPill label="models" value={lineageEvt.metrics?.model_count ?? 0} color="var(--accent-indigo)" />
          </div>
          {/* Lineage graph */}
          <div style={{ marginTop: 12 }}>
            <LineageGraph event={lineageEvt} />
          </div>
        </div>
      )}

      {/* SQL analysis */}
      {sqlEvts.length > 0 && (
        <div className="tab-section">
          <SectionTitle>SQL Analysis ({sqlEvts.length} model{sqlEvts.length !== 1 ? 's' : ''})</SectionTitle>
          {sqlEvts.map((e, i) => (
            <div key={i} className="event-row" style={{ borderLeft: '3px solid var(--accent-indigo)' }}>
              <div className="event-row-header">
                <EventBadge type="sql_analysis_completed" />
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, marginLeft: 8 }}>
                  {e.entity_name}
                </span>
              </div>
              {(e.context?.summary_flags || []).length > 0 && (
                <div style={{ marginTop: 6 }}>
                  {(e.context.summary_flags).map((f, fi) => (
                    <div key={fi} style={{
                      fontSize: 12, color: 'var(--accent-orange)',
                      fontFamily: 'var(--font-mono)',
                      marginBottom: 3,
                    }}>
                      ⚑ {f}
                    </div>
                  ))}
                </div>
              )}
              {e.explanation && <p className="explanation" style={{ fontSize: 12, marginTop: 6 }}>{e.explanation}</p>}
              <div className="event-row-meta" style={{ marginTop: 6 }}>
                <MetricPill label="transformations" value={e.metrics?.transformation_count ?? 0} />
                <MetricPill label="joins"           value={e.metrics?.join_count ?? 0} />
                {e.metrics?.has_non_equi_join && (
                  <MetricPill label="non-equi join" value="YES" color="var(--accent-red)" />
                )}
                <MetricPill label="LLM risks" value={e.metrics?.llm_risk_count ?? 0} color="var(--accent-amber)" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Policy gaps */}
      {gapEvts.length > 0 && (
        <div className="tab-section">
          <SectionTitle>Policy Gaps ({gapEvts.length})</SectionTitle>
          {gapEvts.map((e, i) => {
            const sev = e.metrics?.severity_level || 'medium'
            const sevColor = sev === 'critical' ? 'var(--accent-red)'
                           : sev === 'high'     ? 'var(--accent-orange)'
                           : 'var(--accent-amber)'
            return (
              <div key={i} className="event-row" style={{ borderLeft: `3px solid ${sevColor}` }}>
                <div className="event-row-header">
                  <EventBadge type="policy_gap_detected" />
                  <span
                    style={{
                      marginLeft: 'auto', fontSize: 11, fontWeight: 700,
                      textTransform: 'uppercase', letterSpacing: '0.05em', color: sevColor,
                    }}
                  >
                    {sev}
                  </span>
                </div>
                <div className="event-row-meta">
                  <MetricPill label="column"       value={e.context?.column ?? '—'}              color="var(--accent-cyan)" />
                  <MetricPill label="type"         value={e.context?.semantic_type ?? '—'}        />
                  <MetricPill label="missing"      value={e.context?.missing_validation ?? '—'}   color={sevColor} />
                  <MetricPill label="forbidden"    value={e.context?.forbidden_transform ?? '—'}  color="var(--accent-red)" />
                </div>
                {e.explanation && <p className="explanation" style={{ fontSize: 12, marginTop: 6 }}>{e.explanation}</p>}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Tab: Decision ────────────────────────────────────────────────────────────

function DecisionTab({ inv }) {
  const rec = (inv.events || []).find(e => e.event_type === 'recommendation_created')
  if (!rec) return <p style={{ color: 'var(--text-muted)' }}>No recommendation recorded.</p>

  const rtype  = rec.context?.recommendation_type || 'unknown'
  const rColor = recColor(rtype)

  return (
    <div>
      <div className="tab-section">
        <SectionTitle>Recommendation</SectionTitle>
        <div style={{
          padding: '14px 16px',
          background: `${rColor}0f`,
          border: `1px solid ${rColor}44`,
          borderRadius: 'var(--radius-md)',
          marginBottom: 12,
        }}>
          <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase',
            letterSpacing: '0.06em', color: rColor, marginBottom: 8 }}>
            {rtype}
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
            {rec.context?.action}
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            {rec.context?.rationale}
          </p>
        </div>
        <div className="event-row-meta">
          <MetricPill label="target"     value={rec.context?.target_column ?? '—'}       color="var(--accent-cyan)" />
          <MetricPill label="validation" value={rec.context?.validation_required ?? '—'} />
          <MetricPill label="gaps addressed" value={rec.context?.gaps_addressed ?? 0}    color="var(--accent-orange)" />
          <MetricPill label="score at decision" value={(rec.metrics?.current_score ?? 0).toFixed(4)} />
        </div>
      </div>

      {rec.explanation && (
        <div className="tab-section">
          <SectionTitle>Agent Reasoning</SectionTitle>
          <p className="explanation">{rec.explanation}</p>
        </div>
      )}
    </div>
  )
}

// ── Tab: Result ──────────────────────────────────────────────────────────────

function ResultTab({ inv }) {
  const outcome  = (inv.events || []).find(e => e.event_type === 'outcome_measured')
  const learning = (inv.events || []).find(e => e.event_type === 'learning_updated')

  return (
    <div>
      {outcome ? (
        <div className="tab-section">
          <SectionTitle>Outcome Measurement</SectionTitle>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 16,
            padding: 16, background: 'var(--bg-card)',
            border: '1px solid var(--border)', borderRadius: 'var(--radius-md)',
            marginBottom: 12,
          }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>BEFORE</div>
              <div className="score-display" style={{ color: scoreColor(outcome.metrics?.score_before) }}>
                {(outcome.metrics?.score_before ?? 0).toFixed(4)}
              </div>
            </div>
            <div style={{ fontSize: 22, color: 'var(--text-muted)' }}>→</div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>AFTER</div>
              <div className="score-display" style={{ color: scoreColor(outcome.metrics?.score_after) }}>
                {(outcome.metrics?.score_after ?? 0).toFixed(4)}
              </div>
            </div>
            <div style={{ textAlign: 'center', marginLeft: 'auto' }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>DELTA</div>
              <div className="score-delta" style={{ color: deltaColor(outcome.metrics?.delta) }}>
                {outcome.metrics?.delta >= 0 ? '+' : ''}
                {(outcome.metrics?.delta ?? 0).toFixed(4)}
              </div>
              <div style={{
                fontSize: 11, fontWeight: 700,
                color: outcome.metrics?.improved ? 'var(--accent-green)' : 'var(--accent-red)',
                marginTop: 4,
              }}>
                {outcome.metrics?.improved ? '✓ Improved' : '✗ No change'}
              </div>
            </div>
          </div>
          {outcome.explanation && (
            <p className="explanation">{outcome.explanation}</p>
          )}
        </div>
      ) : (
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
          No outcome measured for this cycle (first day, or no prior recommendation).
        </p>
      )}

      {learning && (
        <div className="tab-section">
          <SectionTitle>Learning Updated</SectionTitle>
          {learning.explanation && (
            <p className="explanation" style={{ marginBottom: 10 }}>{learning.explanation}</p>
          )}
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>
            Preferred recommendation after this cycle:
          </div>
          <span
            className="metric-pill"
            style={{ color: recColor(learning.context?.preferred_recommendation) }}
          >
            {learning.context?.preferred_recommendation || '—'}
          </span>

          {/* Attention weights */}
          {learning.metrics?.attention_weights && (
            <div style={{ marginTop: 14 }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
                Attention weights (after learning):
              </div>
              {Object.entries(learning.metrics.attention_weights).map(([k, w]) => (
                <div key={k} style={{ marginBottom: 6 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                    <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{k}</span>
                    <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent-purple)' }}>
                      {Number(w).toFixed(3)}×
                    </span>
                  </div>
                  <div className="risk-bar-track">
                    <div
                      className="risk-bar-fill"
                      style={{
                        width: `${Math.min(100, (w / 2.5) * 100)}%`,
                        background: w > 1.5 ? 'var(--accent-red)' :
                                    w > 1.1 ? 'var(--accent-amber)' : 'var(--accent-teal)',
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main component ───────────────────────────────────────────────────────────

const TABS = [
  { id: 'problem',   label: '⚠ Problem'  },
  { id: 'reasoning', label: '🔍 Reasoning' },
  { id: 'decision',  label: '💡 Decision'  },
  { id: 'result',    label: '📈 Result'    },
]

export default function InvestigationDetail({ investigation: inv, onClose }) {
  const [tab, setTab] = useState('problem')

  return (
    <div className="detail-panel">
      <div className="detail-header">
        <button className="close-btn" onClick={onClose}>✕</button>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          DAY {String(inv.investigation_id).padStart(2, '0')} · {inv.date}
        </div>
        <div style={{ fontSize: 17, fontWeight: 700, margin: '4px 0 8px', color: 'var(--text-primary)' }}>
          {inv.focus_term}
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <span className="metric-pill" style={{ color: 'var(--accent-red)' }}>
            {inv.breach_count} breach{inv.breach_count !== 1 ? 'es' : ''}
          </span>
          <span className="metric-pill" style={{ color: 'var(--accent-orange)' }}>
            {inv.gap_count} gap{inv.gap_count !== 1 ? 's' : ''}
          </span>
          <span className="metric-pill">
            risk {(inv.risk_score ?? 0).toFixed(4)}
          </span>
        </div>
      </div>

      <div className="detail-tabs">
        {TABS.map(t => (
          <button
            key={t.id}
            className={`detail-tab${tab === t.id ? ' active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="detail-body">
        {tab === 'problem'   && <ProblemTab   inv={inv} />}
        {tab === 'reasoning' && <ReasoningTab inv={inv} />}
        {tab === 'decision'  && <DecisionTab  inv={inv} />}
        {tab === 'result'    && <ResultTab    inv={inv} />}
      </div>
    </div>
  )
}
