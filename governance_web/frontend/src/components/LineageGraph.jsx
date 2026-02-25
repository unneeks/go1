import { useMemo } from 'react'

/**
 * SVG-based lineage graph rendered from a lineage_traced event's context.
 *
 * Draws: Business Term → TDE → Model → Column
 * Columns: 4 fixed lanes, nodes positioned by row index within each lane.
 */

const LANE_X   = [40, 180, 330, 480]
const NODE_W   = 130
const NODE_H   = 36
const ROW_GAP  = 48
const PAD_TOP  = 24
const PAD_BOT  = 24

const COLORS = {
  term:   { fill: 'rgba(168,85,247,0.12)', stroke: '#a855f7', text: '#c084fc' },
  tde:    { fill: 'rgba(6,182,212,0.12)',  stroke: '#06b6d4', text: '#22d3ee' },
  model:  { fill: 'rgba(99,102,241,0.12)', stroke: '#6366f1', text: '#818cf8' },
  column: { fill: 'rgba(34,197,94,0.12)',  stroke: '#22c55e', text: '#4ade80' },
}

const LANE_LABELS = ['Business Term', 'TDE', 'Model', 'Column']

function truncate(str, n = 16) {
  return str && str.length > n ? str.slice(0, n - 1) + '…' : str
}

function nodeCenter(laneIdx, rowIdx) {
  return {
    x: LANE_X[laneIdx] + NODE_W / 2,
    y: PAD_TOP + rowIdx * ROW_GAP + NODE_H / 2,
  }
}

function bezier(x1, y1, x2, y2) {
  const mx = (x1 + x2) / 2
  return `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`
}

export default function LineageGraph({ event }) {
  const { nodes, edges, svgH } = useMemo(() => {
    if (!event?.context?.lineage) return { nodes: [], edges: [], svgH: 120 }

    const { lineage } = event.context
    const termId   = event.entity_id
    const termName = event.entity_name

    const termNode   = { id: `term-${termId}`,  label: termName, type: 'term',   lane: 0, row: 0 }
    const tdeNodes   = []
    const modelNodes = []
    const colNodes   = []
    const edgeList   = []

    const modelMap = {}  // model_name → row index
    const colMap   = {}  // model_name+col → row index

    Object.entries(lineage).forEach(([tdeId, tdeData], ti) => {
      const tdeNode = { id: `tde-${tdeId}`, label: tdeData.tde_name, type: 'tde', lane: 1, row: ti }
      tdeNodes.push(tdeNode)
      edgeList.push({ from: termNode.id, to: tdeNode.id })

      ;(tdeData.models || []).forEach(({ model_name, column_name }) => {
        const mKey = `model-${model_name}`
        if (!(mKey in modelMap)) {
          modelMap[mKey] = modelNodes.length
          modelNodes.push({ id: mKey, label: model_name, type: 'model', lane: 2, row: modelNodes.length })
        }
        edgeList.push({ from: tdeNode.id, to: mKey })

        const cKey = `col-${model_name}-${column_name}`
        if (!(cKey in colMap)) {
          colMap[cKey] = colNodes.length
          colNodes.push({ id: cKey, label: column_name, type: 'column', lane: 3, row: colNodes.length })
        }
        edgeList.push({ from: mKey, to: cKey })
      })
    })

    const allNodes = [termNode, ...tdeNodes, ...modelNodes, ...colNodes]
    const maxRows  = Math.max(
      1, tdeNodes.length, modelNodes.length, colNodes.length
    )
    const svgH = PAD_TOP + maxRows * ROW_GAP + PAD_BOT

    // Node position lookup
    const posMap = {}
    allNodes.forEach(n => {
      posMap[n.id] = nodeCenter(n.lane, n.row)
    })

    return { nodes: allNodes, edges: edgeList, posMap, svgH }
  }, [event])

  if (!nodes.length) {
    return (
      <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: 12 }}>
        No lineage data available.
      </div>
    )
  }

  const svgW = LANE_X[3] + NODE_W + 20

  // Rebuild posMap inside render (safe since useMemo already ran)
  const posMap = {}
  nodes.forEach(n => { posMap[n.id] = nodeCenter(n.lane, n.row) })

  return (
    <div className="lineage-container">
      <svg
        className="lineage-svg"
        viewBox={`0 0 ${svgW} ${svgH}`}
        style={{ height: svgH, maxHeight: 320 }}
      >
        {/* Lane labels */}
        {LANE_LABELS.map((lbl, i) => (
          <text
            key={i}
            x={LANE_X[i] + NODE_W / 2}
            y={10}
            textAnchor="middle"
            className="lineage-col-label"
            fill="var(--text-muted)"
            fontSize={9}
            fontFamily="var(--font-sans)"
            fontWeight={600}
            textTransform="uppercase"
            letterSpacing="0.06em"
          >
            {lbl}
          </text>
        ))}

        {/* Edges (drawn first, under nodes) */}
        {edges.map((e, i) => {
          const from = posMap[e.from]
          const to   = posMap[e.to]
          if (!from || !to) return null
          return (
            <path
              key={i}
              d={bezier(from.x + NODE_W / 2, from.y, to.x - NODE_W / 2, to.y)}
              fill="none"
              stroke="var(--border-emphasis)"
              strokeWidth={1.5}
              strokeOpacity={0.7}
            />
          )
        })}

        {/* Nodes */}
        {nodes.map(n => {
          const c   = COLORS[n.type]
          const pos = posMap[n.id]
          const x   = LANE_X[n.lane]
          const y   = PAD_TOP + n.row * ROW_GAP
          return (
            <g key={n.id}>
              <rect
                x={x} y={y} width={NODE_W} height={NODE_H} rx={6}
                fill={c.fill} stroke={c.stroke} strokeWidth={1.5}
              />
              <text
                x={x + NODE_W / 2}
                y={y + NODE_H / 2 + 1}
                textAnchor="middle"
                dominantBaseline="middle"
                fill={c.text}
                fontSize={11}
                fontFamily="var(--font-mono)"
                fontWeight={500}
              >
                {truncate(n.label, 15)}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
