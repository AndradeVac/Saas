import { formatMoney } from '../../lib/format'

type Point = { label: string; value: number }

const W = 600
const H = 190
const PAD = { top: 12, right: 12, bottom: 24, left: 8 }

const niceMax = (max: number) => {
  if (max <= 0) return 1
  const power = 10 ** Math.floor(Math.log10(max))
  return Math.ceil(max / power) * power
}

/** Revenue over time. Falls back to a single dot for one data point. */
export function LineChart({ points, money = true }: { points: Point[]; money?: boolean }) {
  if (points.length === 0) return <div className="empty small">Sem vendas no período.</div>
  const max = niceMax(Math.max(...points.map((p) => p.value)))
  const innerW = W - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  const x = (i: number) => PAD.left + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW)
  const y = (v: number) => PAD.top + innerH - (v / max) * innerH
  const line = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(' ')
  const area = `${line} L${x(points.length - 1).toFixed(1)},${PAD.top + innerH} L${x(0).toFixed(1)},${PAD.top + innerH} Z`
  const every = Math.ceil(points.length / 7)

  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Gráfico de faturamento por dia" preserveAspectRatio="none">
      {[0, 0.5, 1].map((t) => <line key={t} className="grid" x1={PAD.left} x2={W - PAD.right} y1={PAD.top + innerH * (1 - t)} y2={PAD.top + innerH * (1 - t)} />)}
      {points.length > 1 && <path className="area" d={area} />}
      <path className="line" d={line} />
      {points.map((p, i) => (
        <g key={p.label}>
          <circle className="dot" cx={x(i)} cy={y(p.value)} r={3.5}><title>{`${p.label}: ${money ? formatMoney(p.value) : p.value}`}</title></circle>
          {i % every === 0 && <text className="axis" x={x(i)} y={H - 6} textAnchor="middle">{p.label}</text>}
        </g>
      ))}
    </svg>
  )
}

/** Orders per hour of the day. */
export function ColumnChart({ points }: { points: Point[] }) {
  if (points.length === 0) return <div className="empty small">Sem vendas no período.</div>
  const byHour = new Map(points.map((p) => [Number(p.label), p.value]))
  const hours = Array.from({ length: 24 }, (_, h) => ({ h, v: byHour.get(h) ?? 0 }))
  const max = Math.max(...hours.map((d) => d.v), 1)
  const innerW = W - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  const slot = innerW / 24

  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Pedidos por hora do dia" preserveAspectRatio="none">
      {[0, 0.5, 1].map((t) => <line key={t} className="grid" x1={PAD.left} x2={W - PAD.right} y1={PAD.top + innerH * (1 - t)} y2={PAD.top + innerH * (1 - t)} />)}
      {hours.map(({ h, v }) => {
        const height = (v / max) * innerH
        return (
          <g key={h}>
            <rect className="col" x={PAD.left + h * slot + 2} y={PAD.top + innerH - height} width={slot - 4} height={Math.max(height, v > 0 ? 2 : 0)} rx={3}>
              <title>{`${h}h: ${v} ${v === 1 ? 'pedido' : 'pedidos'}`}</title>
            </rect>
            {h % 3 === 0 && <text className="axis" x={PAD.left + h * slot + slot / 2} y={H - 6} textAnchor="middle">{h}h</text>}
          </g>
        )
      })}
    </svg>
  )
}

export function Bars({ rows }: { rows: Array<{ label: string; value: number; text?: string }> }) {
  const max = Math.max(...rows.map((r) => r.value), 1)
  if (rows.length === 0) return <div className="empty small">Sem dados no período.</div>
  return (
    <div className="bars">
      {rows.map((r) => (
        <div className="bar-row" key={r.label}>
          <div><span title={r.label}>{r.label}</span><strong>{r.text ?? r.value}</strong></div>
          <i><b style={{ width: `${Math.max(3, (r.value / max) * 100)}%` }} /></i>
        </div>
      ))}
    </div>
  )
}
