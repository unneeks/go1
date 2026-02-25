const BASE = '/api'

async function _get(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const fetchHealth          = ()       => _get('/health')
export const fetchEvents          = (type)   => _get(type ? `/events?event_type=${type}` : '/events')
export const fetchInvestigations  = ()       => _get('/investigations')
export const fetchLatestState     = ()       => _get('/latest_state')
export const fetchLearningSummary = ()       => _get('/learning_summary')
