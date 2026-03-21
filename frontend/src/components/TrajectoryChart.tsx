import type { TrajectorySeries } from '../types/models'

const PALETTE = ['#bf5b39', '#0f5c6e', '#a84f62', '#5d7348', '#bc8c2f', '#7357a6', '#2d6a4f', '#8d4a4a']

interface TrajectoryChartProps {
  series: TrajectorySeries[]
  roundGoal: number
}

function xFor(round: number, width: number, roundGoal: number) {
  const usable = width - 72
  return 48 + (usable * round) / Math.max(roundGoal, 1)
}

function yFor(stance: number, height: number) {
  const usable = height - 52
  return 24 + ((1 - (stance + 1) / 2) * usable)
}

export function TrajectoryChart({ series, roundGoal }: TrajectoryChartProps) {
  const width = 640
  const height = 260

  return (
    <div className="chart-shell trajectory-shell">
      <svg viewBox={`0 0 ${width} ${height}`} className="trajectory-chart" role="img" aria-label="Opinion trajectory chart">
        <line x1="48" x2={width - 24} y1={height / 2} y2={height / 2} className="chart-axis" />
        <line x1="48" x2={width - 24} y1="24" y2="24" className="chart-grid" />
        <line x1="48" x2={width - 24} y1={height - 28} y2={height - 28} className="chart-grid" />

        {Array.from({ length: roundGoal + 1 }, (_, round) => {
          const x = xFor(round, width, roundGoal)
          return (
            <g key={round}>
              <line x1={x} x2={x} y1="24" y2={height - 28} className="chart-guide" />
              <text x={x} y={height - 8} className="chart-label">
                {round === 0 ? 'start' : `r${round}`}
              </text>
            </g>
          )
        })}

        <text x="10" y="28" className="chart-label">
          For
        </text>
        <text x="10" y={height / 2 + 4} className="chart-label">
          Mid
        </text>
        <text x="10" y={height - 30} className="chart-label">
          Against
        </text>

        {series.map((entry, index) => {
          const color = PALETTE[index % PALETTE.length]
          const path = entry.points
            .map((point, pointIndex) => {
              const x = xFor(point.round_index, width, roundGoal)
              const y = yFor(point.stance, height)
              return `${pointIndex === 0 ? 'M' : 'L'} ${x} ${y}`
            })
            .join(' ')
          return (
            <g key={entry.persona_id}>
              <path d={path} fill="none" stroke={color} strokeWidth="3" strokeLinecap="round" />
              {entry.points.map((point) => (
                <circle
                  key={`${entry.persona_id}-${point.round_index}`}
                  cx={xFor(point.round_index, width, roundGoal)}
                  cy={yFor(point.stance, height)}
                  r="4"
                  fill={color}
                />
              ))}
            </g>
          )
        })}
      </svg>

      <div className="chart-legend" aria-label="Trajectory legend">
        {series.map((entry, index) => {
          const color = PALETTE[index % PALETTE.length]
          const latest = entry.points[entry.points.length - 1]
          return (
            <div key={entry.persona_id} className="chart-legend-item">
              <span className="chart-swatch" style={{ backgroundColor: color }} />
              <span>
                {entry.avatar_emoji} {entry.persona_name} · {latest.stance > 0 ? '+' : ''}
                {latest.stance.toFixed(2)}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
