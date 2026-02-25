import { useMemo } from 'react'
import { eventMeta, recColor, deltaColor, scoreColor } from '../constants.js'

// ── Event dot chain ──────────────────────────────────────────────────────────

function DotChain({ events }) {
  return (
    <div className="dot-chain">
      {events.map((evt, i) => {
        const m = eventMeta(evt.event_type)
        return (
          <div
            key={i}
            className="dot-chain-dot"
            title={`${m.label}\n${evt.entity_name}\n${evt.explanation?.slice(0, 120) ?? ''}`}
            style={{
              background: m.bg,
              color: m.color,
              border: `1px solid ${m.color}33`,
            }}
          >
            {m.short}
          </div>
        )
      })}
    </div>
  )
}

// ── Stat chip ────────────────────────────────────────────────────────────────

function Chip({ color, label, value }) {
  return (
    <span
      className="metric-pill"
      style={{ color, borderColor: color + '44' }}
    >
      {label}: <strong>{value}</strong>
    </span>
  )
}

// ── Single investigation card ────────────────────────────────────────────────

function InvCard({ inv, prevFocusTerm, isSelected, onClick }) {
  const isFocusShift = prevFocusTerm && prevFocusTerm !== inv.focus_term
  const rColor = recColor(inv.recommendation_type)
  const dColor = deltaColor(inv.score_delta)

  return (
    <div
      className={`inv-card${isSelected ? ' selected' : ''}`}
      onClick={onClick}
    >
      <div className="inv-card-header">
        <div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span className="inv-day">DAY {String(inv.investigation_id).padStart(2, '0')}</span>
            <span className="inv-date">{inv.date}</span>
            {isFocusShift && (
              <span className="inv-shift-badge">↻ FOCUS SHIFT</span>
            )}
          </div>
          <div className="inv-focus-term">{inv.focus_term ?? '—'}</div>
        </div>
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Risk score</div>
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 18,
              fontWeight: 700,
              color: inv.risk_score > 0.3 ? 'var(--accent-red)' :
                     inv.risk_score > 0.1 ? 'var(--accent-amber)' : 'var(--accent-teal)',
            }}
          >
            {inv.risk_score?.toFixed(4) ?? '—'}
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div className="inv-stats">
        {inv.breach_count > 0 && (
          <Chip color="var(--accent-red)"    label="breaches" value={inv.breach_count} />
        )}
        {inv.gap_count > 0 && (
          <Chip color="var(--accent-orange)" label="gaps"     value={inv.gap_count} />
        )}
        {inv.sql_model_count > 0 && (
          <Chip color="var(--accent-indigo)" label="models"   value={inv.sql_model_count} />
        )}
        {inv.recommendation_type && (
          <span
            className="metric-pill"
            style={{ color: rColor, borderColor: rColor + '44' }}
          >
            {inv.recommendation_type}
          </span>
        )}
      </div>

      {/* Event dot chain */}
      <DotChain events={inv.events ?? []} />

      {/* Recommendation action */}
      {inv.recommendation_action && (
        <div className="inv-action">
          <span style={{ color: rColor, fontWeight: 600 }}>💡 </span>
          {inv.recommendation_action}
        </div>
      )}

      {/* Outcome */}
      {inv.score_delta != null && (
        <div className="inv-outcome">
          <span>Outcome:</span>
          {inv.score_before != null && (
            <span
              style={{ fontFamily: 'var(--font-mono)', color: scoreColor(inv.score_before) }}
            >
              {inv.score_before.toFixed(4)}
            </span>
          )}
          <span style={{ color: 'var(--text-muted)' }}>→</span>
          {inv.score_after != null && (
            <span
              style={{ fontFamily: 'var(--font-mono)', color: scoreColor(inv.score_after) }}
            >
              {inv.score_after.toFixed(4)}
            </span>
          )}
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: dColor }}>
            ({inv.score_delta >= 0 ? '+' : ''}{inv.score_delta.toFixed(4)})
          </span>
        </div>
      )}
    </div>
  )
}

// ── Focus group header ───────────────────────────────────────────────────────

function FocusGroupHeader({ term, count, riskRange }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      margin: '20px 0 8px',
      padding: '8px 12px',
      background: 'rgba(168,85,247,0.07)',
      border: '1px solid rgba(168,85,247,0.2)',
      borderRadius: 'var(--radius-md)',
    }}>
      <span style={{ fontSize: 15 }}>🎯</span>
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
          {term}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {count} investigation{count !== 1 ? 's' : ''}
          {riskRange && ` · risk ${riskRange}`}
        </div>
      </div>
    </div>
  )
}

// ── Main Timeline component ──────────────────────────────────────────────────

export default function Timeline({ investigations, selected, onSelect }) {
  // Group consecutive same-term investigations for visual grouping
  const groups = useMemo(() => {
    const result = []
    let currentGroup = null

    investigations.forEach((inv, i) => {
      if (!currentGroup || inv.focus_term !== currentGroup.term) {
        if (currentGroup) result.push(currentGroup)
        currentGroup = { term: inv.focus_term, items: [] }
      }
      currentGroup.items.push({ inv, prev: i > 0 ? investigations[i - 1] : null })
    })
    if (currentGroup) result.push(currentGroup)
    return result
  }, [investigations])

  if (!investigations.length) {
    return (
      <div className="state-screen">
        <div className="state-icon">📭</div>
        <p>No investigation cycles found.</p>
      </div>
    )
  }

  return (
    <div>
      <div className="section-header">
        <h2>Investigation Timeline</h2>
        <span className="count-badge">{investigations.length} cycles</span>
      </div>

      {groups.map((group, gi) => {
        const risks = group.items.map(x => x.inv.risk_score).filter(Boolean)
        const riskRange = risks.length
          ? `${Math.min(...risks).toFixed(3)} – ${Math.max(...risks).toFixed(3)}`
          : null

        return (
          <div key={gi}>
            <FocusGroupHeader
              term={group.term}
              count={group.items.length}
              riskRange={riskRange}
            />
            {group.items.map(({ inv, prev }) => (
              <InvCard
                key={inv.investigation_id}
                inv={inv}
                prevFocusTerm={prev?.focus_term}
                isSelected={selected?.investigation_id === inv.investigation_id}
                onClick={() => onSelect(inv)}
              />
            ))}
          </div>
        )
      })}
    </div>
  )
}
