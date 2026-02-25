import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line, Legend,
} from 'recharts'
import { recColor } from '../constants.js'

// ── Custom tooltip ────────────────────────────────────────────────────────────

function DarkTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--bg-panel)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)', padding: '10px 14px', fontSize: 12,
    }}>
      <div style={{ fontWeight: 600, marginBottom: 6 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color || 'var(--text-secondary)' }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(4) : p.value}
        </div>
      ))}
    </div>
  )
}

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, color }) {
  return (
    <div style={{
      background: 'var(--bg-card)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)', padding: '16px 20px', flex: 1,
    }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, fontFamily: 'var(--font-mono)', color: color || 'var(--text-primary)' }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{sub}</div>}
    </div>
  )
}

// ── Recommendation effectiveness bars ─────────────────────────────────────────

function EffectivenessChart({ types }) {
  const data = types.map(t => ({
    name: t.type,
    effectiveness: t.effectiveness_pct,
    applied: t.total_applied,
    avg_delta: t.avg_delta,
    color: recColor(t.type),
  }))

  return (
    <div className="chart-card" style={{ gridColumn: '1 / -1' }}>
      <div className="chart-title">Recommendation Effectiveness</div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis dataKey="name" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis
            domain={[0, 100]} unit="%" tickCount={5}
            tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
            axisLine={false} tickLine={false}
          />
          <Tooltip content={<DarkTooltip />} />
          <Bar dataKey="effectiveness" name="Effectiveness %" radius={[4, 4, 0, 0]} maxBarSize={60}>
            {data.map((d, i) => <Cell key={i} fill={d.color} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Summary table */}
      <div style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
        {types.map(t => (
          <div key={t.type} style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '6px 0', borderBottom: '1px solid var(--border)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 10, height: 10, borderRadius: 2, background: recColor(t.type), display: 'inline-block' }} />
              <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)' }}>{t.type}</span>
            </div>
            <div style={{ display: 'flex', gap: 16 }}>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>×{t.total_applied} applied</span>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>✓{t.improved_count} improved</span>
              <span style={{ fontSize: 12, fontWeight: 600, color: t.avg_delta > 0 ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                avg Δ {t.avg_delta >= 0 ? '+' : ''}{t.avg_delta.toFixed(4)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Attention weight evolution line chart ──────────────────────────────────────

function AttentionChart({ evolution }) {
  if (!evolution || evolution.length === 0) return null

  // Collect all term IDs
  const termIds = [...new Set(
    evolution.flatMap(e => Object.keys(e.weights || {}))
  )]

  const PALETTE = ['#a855f7', '#3b82f6', '#22c55e', '#f59e0b', '#ef4444']

  const data = evolution.map(e => ({
    day: `D${e.day || ''}`,
    ...Object.fromEntries(
      termIds.map(tid => [tid, Number((e.weights[tid] || 1).toFixed(3))])
    ),
  }))

  return (
    <div className="chart-card" style={{ gridColumn: '1 / -1' }}>
      <div className="chart-title">Agent Attention Weight Evolution</div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
        Weight &gt; 1.0 = agent is primed to focus here (persistent breach streaks)
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="day" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis
            domain={[0.5, 2.8]} tickCount={5}
            tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
            axisLine={false} tickLine={false}
          />
          <Tooltip content={<DarkTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: 11, color: 'var(--text-muted)', paddingTop: 8 }}
          />
          {/* Reference line at 1.0 */}
          {termIds.map((tid, i) => (
            <Line
              key={tid}
              type="monotone"
              dataKey={tid}
              stroke={PALETTE[i % PALETTE.length]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Score trajectory chart ─────────────────────────────────────────────────────

function ScoreTrajectoryChart({ trajectory }) {
  if (!trajectory || Object.keys(trajectory).length === 0) return null

  const terms = Object.keys(trajectory)
  const PALETTE = ['#22c55e', '#3b82f6', '#a855f7', '#f59e0b']

  // Align all series by index
  const maxLen = Math.max(...terms.map(t => trajectory[t].length))
  const data = Array.from({ length: maxLen }, (_, i) => {
    const row = { idx: i }
    terms.forEach(term => {
      const entry = trajectory[term][i]
      if (entry) {
        row[term] = entry.score
        row._date = entry.date
      }
    })
    return row
  })

  return (
    <div className="chart-card" style={{ gridColumn: '1 / -1' }}>
      <div className="chart-title">DQ Score Trajectory (from outcome_measured events)</div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="_date" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis
            domain={[0.75, 1.0]} tickCount={6}
            tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
            axisLine={false} tickLine={false}
            tickFormatter={v => v.toFixed(2)}
          />
          <Tooltip content={<DarkTooltip />} />
          <Legend wrapperStyle={{ fontSize: 11, color: 'var(--text-muted)', paddingTop: 8 }} />
          {terms.map((term, i) => (
            <Line
              key={term}
              type="monotone"
              dataKey={term}
              name={term}
              stroke={PALETTE[i % PALETTE.length]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function LearningView({ summary }) {
  if (!summary) {
    return (
      <div className="state-screen">
        <div className="spinner" />
        <p>Loading learning summary…</p>
      </div>
    )
  }

  const { recommendation_types, attention_evolution, score_trajectory,
          total_outcomes, improved_outcomes, overall_improvement_rate } = summary

  return (
    <div>
      <div className="section-header">
        <h2>Learning &amp; Adaptation</h2>
        <span className="count-badge">{total_outcomes} outcomes measured</span>
      </div>

      {/* Summary stats */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
        <StatCard
          label="Total Outcomes"
          value={total_outcomes}
          color="var(--text-primary)"
        />
        <StatCard
          label="Improvements"
          value={improved_outcomes}
          sub={`of ${total_outcomes} recommendations`}
          color="var(--accent-green)"
        />
        <StatCard
          label="Overall Success Rate"
          value={`${overall_improvement_rate}%`}
          sub="recommendations that improved scores"
          color={overall_improvement_rate >= 60 ? 'var(--accent-green)' : 'var(--accent-amber)'}
        />
      </div>

      <div className="learning-grid">
        {recommendation_types?.length > 0 && (
          <EffectivenessChart types={recommendation_types} />
        )}
        {attention_evolution?.length > 0 && (
          <AttentionChart evolution={attention_evolution} />
        )}
        {score_trajectory && Object.keys(score_trajectory).length > 0 && (
          <ScoreTrajectoryChart trajectory={score_trajectory} />
        )}
      </div>
    </div>
  )
}
