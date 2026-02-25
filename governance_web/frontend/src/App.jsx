import { useState, useEffect, useCallback } from 'react'
import { fetchHealth, fetchInvestigations, fetchLatestState, fetchLearningSummary } from './api.js'
import Timeline from './components/Timeline.jsx'
import RiskHeatmap from './components/RiskHeatmap.jsx'
import LearningView from './components/LearningView.jsx'
import InvestigationDetail from './components/InvestigationDetail.jsx'

const VIEWS = [
  { id: 'timeline', icon: '⏱', label: 'Timeline',     desc: 'Investigation replay' },
  { id: 'heatmap',  icon: '🗺', label: 'Risk Heatmap', desc: 'Business term status' },
  { id: 'learning', icon: '🧠', label: 'Learning',     desc: 'Recommendation effectiveness' },
]

export default function App() {
  const [view, setView]                   = useState('timeline')
  const [investigations, setInvestigations] = useState([])
  const [latestState, setLatestState]     = useState([])
  const [learningSummary, setLearning]    = useState(null)
  const [selected, setSelected]           = useState(null)
  const [loading, setLoading]             = useState(true)
  const [error, setError]                 = useState(null)
  const [eventCount, setEventCount]       = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [h, invs, state, learn] = await Promise.all([
        fetchHealth(),
        fetchInvestigations(),
        fetchLatestState(),
        fetchLearningSummary(),
      ])
      setEventCount(h.event_count)
      setInvestigations(invs)
      setLatestState(state)
      setLearning(learn)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div className="app-shell">
      {/* ── Header ── */}
      <header className="app-header">
        <div className="logo">
          Governance<span>Agent</span>
        </div>
        <span className="header-badge">Cognition UI</span>
        <div className="header-right">
          {eventCount != null && (
            <span className="header-status">
              <span className="dot-live anim" />
              {eventCount.toLocaleString()} events
            </span>
          )}
          <button className="refresh-btn" onClick={load} title="Refresh data">
            ↻ Refresh
          </button>
        </div>
      </header>

      {/* ── Sidebar ── */}
      <aside className="app-sidebar">
        <div className="sidebar-section-label">Views</div>
        {VIEWS.map(v => (
          <button
            key={v.id}
            className={`nav-btn${view === v.id ? ' active' : ''}`}
            onClick={() => { setView(v.id); setSelected(null) }}
          >
            <span className="nav-icon">{v.icon}</span>
            {v.label}
          </button>
        ))}

        {investigations.length > 0 && (
          <>
            <hr className="sidebar-divider" />
            <div className="sidebar-section-label">Quick nav</div>
            {/* Focus shift markers */}
            {investigations
              .filter((inv, i) =>
                i === 0 || inv.focus_term_id !== investigations[i - 1].focus_term_id
              )
              .slice(0, 6)
              .map(inv => (
                <button
                  key={inv.investigation_id}
                  className="nav-btn"
                  onClick={() => { setView('timeline'); setSelected(inv) }}
                  style={{ fontSize: 12 }}
                >
                  <span className="nav-icon">🎯</span>
                  Day {inv.investigation_id} — {inv.focus_term || '…'}
                </button>
              ))}
          </>
        )}
      </aside>

      {/* ── Main ── */}
      <main className="app-main">
        {loading ? (
          <div className="state-screen">
            <div className="spinner" />
            <p>Loading agent cognition data…</p>
          </div>
        ) : error ? (
          <div className="state-screen">
            <div className="state-icon">⚠️</div>
            <h3>Cannot connect to backend</h3>
            <p>{error}</p>
            <p>Make sure the FastAPI server is running and the database exists.</p>
            <code>uvicorn main:app --reload</code>
          </div>
        ) : investigations.length === 0 ? (
          <div className="state-screen">
            <div className="state-icon">📭</div>
            <h3>No events found</h3>
            <p>Run the 30-day simulation first to populate the event log.</p>
            <code>python run_simulation.py</code>
          </div>
        ) : (
          <>
            <div className="view-scroll">
              {view === 'timeline' && (
                <Timeline
                  investigations={investigations}
                  selected={selected}
                  onSelect={setSelected}
                />
              )}
              {view === 'heatmap' && (
                <RiskHeatmap state={latestState} onTermClick={term => {
                  // Find latest investigation for this term
                  const inv = [...investigations].reverse()
                    .find(i => i.focus_term_id === term.entity_id)
                  if (inv) { setView('timeline'); setSelected(inv) }
                }} />
              )}
              {view === 'learning' && (
                <LearningView summary={learningSummary} />
              )}
            </div>

            {/* Detail panel */}
            {selected && (
              <div className="detail-overlay" onClick={() => setSelected(null)}>
                <div onClick={e => e.stopPropagation()}>
                  <InvestigationDetail
                    investigation={selected}
                    onClose={() => setSelected(null)}
                  />
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}
