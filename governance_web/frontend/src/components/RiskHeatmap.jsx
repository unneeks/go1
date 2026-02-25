import { statusMeta, scoreColor, deltaColor } from '../constants.js'

function ScoreBar({ value, max = 1 }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  return (
    <div className="risk-bar-track" style={{ height: 6 }}>
      <div
        className="risk-bar-fill"
        style={{
          width: `${pct}%`,
          background: value > 0.3 ? 'var(--accent-red)'
                    : value > 0.1 ? 'var(--accent-amber)' : 'var(--accent-teal)',
        }}
      />
    </div>
  )
}

function DeltaArrow({ delta }) {
  if (delta == null) return null
  const color = deltaColor(delta)
  const arrow = delta > 0.001 ? '▲' : delta < -0.001 ? '▼' : '—'
  return (
    <span style={{ color, fontWeight: 700, fontFamily: 'var(--font-mono)', fontSize: 13 }}>
      {arrow} {Math.abs(delta).toFixed(4)}
    </span>
  )
}

function HeatmapCard({ term, onClick }) {
  const sm = statusMeta(term.status || 'stable')

  const statusBarColor =
    term.status === 'investigating' ? 'var(--accent-purple)' :
    term.status === 'breached'      ? 'var(--accent-red)'    :
    term.status === 'declining'     ? 'var(--accent-orange)' :
    term.status === 'improving'     ? 'var(--accent-green)'  : 'var(--accent-teal)'

  return (
    <div
      className="heatmap-card"
      onClick={onClick}
      style={{ cursor: onClick ? 'pointer' : 'default' }}
    >
      {/* Top colour bar */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 3, background: statusBarColor }} />

      {/* Term name + status */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div className="term-name">{term.entity_name}</div>
        <span
          className="status-badge"
          style={{ background: sm.bg, color: sm.color }}
        >
          {sm.label}
        </span>
      </div>

      {/* ID */}
      <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginBottom: 12 }}>
        {term.entity_id}
      </div>

      {/* Metrics grid */}
      <div className="heatmap-metrics">
        <div>
          <div className="heatmap-metric-label">Risk Score</div>
          <div
            className="heatmap-metric-value"
            style={{
              color: (term.latest_risk_score ?? 0) > 0.3 ? 'var(--accent-red)'
                   : (term.latest_risk_score ?? 0) > 0.1 ? 'var(--accent-amber)' : 'var(--accent-teal)',
            }}
          >
            {(term.latest_risk_score ?? 0).toFixed(3)}
          </div>
        </div>

        <div>
          <div className="heatmap-metric-label">DQ Score</div>
          <div
            className="heatmap-metric-value"
            style={{ color: scoreColor(term.latest_score) }}
          >
            {term.latest_score != null ? term.latest_score.toFixed(4) : '—'}
          </div>
        </div>

        <div>
          <div className="heatmap-metric-label">Breach Count</div>
          <div
            className="heatmap-metric-value"
            style={{ color: (term.breach_count ?? 0) > 0 ? 'var(--accent-red)' : 'var(--text-muted)' }}
          >
            {term.breach_count ?? 0}
          </div>
        </div>

        <div>
          <div className="heatmap-metric-label">Score Δ</div>
          <div style={{ paddingTop: 4 }}>
            <DeltaArrow delta={term.latest_delta} />
          </div>
        </div>
      </div>

      {/* Risk bar */}
      <div style={{ marginTop: 14 }}>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>Risk level</div>
        <ScoreBar value={term.latest_risk_score ?? 0} max={1.5} />
      </div>

      {/* Attention weight */}
      {term.attention != null && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>
            Agent attention weight: {Number(term.attention).toFixed(3)}×
          </div>
          <div className="risk-bar-track" style={{ height: 4 }}>
            <div
              className="risk-bar-fill"
              style={{
                width: `${Math.min(100, (term.attention / 2.5) * 100)}%`,
                background: 'var(--accent-purple)',
              }}
            />
          </div>
        </div>
      )}

      {/* Click hint */}
      {onClick && (
        <div style={{ marginTop: 12, fontSize: 11, color: 'var(--text-muted)' }}>
          Click to view latest investigation →
        </div>
      )}
    </div>
  )
}

export default function RiskHeatmap({ state, onTermClick }) {
  if (!state || state.length === 0) {
    return (
      <div className="state-screen">
        <div className="state-icon">📭</div>
        <p>No business term state found. Run the simulation first.</p>
      </div>
    )
  }

  // Count statuses for summary
  const counts = state.reduce((acc, t) => {
    acc[t.status] = (acc[t.status] || 0) + 1
    return acc
  }, {})

  const summaryItems = [
    { status: 'investigating', icon: '🎯' },
    { status: 'breached',      icon: '🔴' },
    { status: 'declining',     icon: '🟠' },
    { status: 'improving',     icon: '🟢' },
    { status: 'stable',        icon: '🔵' },
  ].filter(x => counts[x.status])

  return (
    <div>
      <div className="section-header">
        <h2>Business Risk Heatmap</h2>
        <span className="count-badge">{state.length} terms</span>
      </div>

      {/* Status summary */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
        {summaryItems.map(({ status, icon }) => {
          const sm = statusMeta(status)
          return (
            <span
              key={status}
              className="status-badge"
              style={{ background: sm.bg, color: sm.color }}
            >
              {icon} {counts[status]} {sm.label}
            </span>
          )
        })}
      </div>

      <div className="heatmap-grid">
        {state.map(term => (
          <HeatmapCard
            key={term.entity_id}
            term={term}
            onClick={onTermClick ? () => onTermClick(term) : null}
          />
        ))}
      </div>
    </div>
  )
}
