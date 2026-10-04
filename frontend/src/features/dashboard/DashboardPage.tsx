import { useEffect, useState } from 'react'
import { formatMoney, orderStatusLabels, paymentMethodLabels, serviceLabels } from '../../lib/format'
import { downloadExport, getDashboard, type Dashboard, type Period } from '../../services/admin'

const labels: Record<string, string> = { ...orderStatusLabels, ...paymentMethodLabels, ...serviceLabels }

function Bars({ rows }: { rows: Array<{ label: string; value: number; text?: string }> }) {
  const max = Math.max(...rows.map((r) => r.value), 1)
  if (rows.length === 0) return <div className="empty small">Sem dados no período.</div>
  return (
    <div className="bars">
      {rows.map((r) => (
        <div className="bar-row" key={r.label}>
          <div><span>{r.label}</span><strong>{r.text ?? r.value}</strong></div>
          <i><b style={{ width: `${(r.value / max) * 100}%` }} /></i>
        </div>
      ))}
    </div>
  )
}

export function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null)
  const [period, setPeriod] = useState<Period>('month')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    setError('')
    const custom = start && end
    getDashboard(period, custom ? start : undefined, custom ? end : undefined)
      .then(setData)
      .catch(() => setError('Não foi possível carregar os indicadores.'))
  }, [period, start, end])

  const change = Number(data?.revenue_change_percent ?? 0)
  const kpis = data ? [
    { label: 'Faturamento', value: formatMoney(data.revenue), hint: `${change >= 0 ? '+' : ''}${change.toFixed(1)}% vs período anterior` },
    { label: 'Pedidos', value: String(data.order_count), hint: 'Sem os cancelados' },
    { label: 'Ticket médio', value: formatMoney(data.average_ticket), hint: 'Por pedido' },
    { label: 'Mais vendido', value: data.top_product?.product_name ?? '—', hint: data.top_product ? `${data.top_product.quantity} un.` : 'Aguardando pedidos' },
  ] : []

  return (
    <section className="page">
      <div className="page-head">
        <div><h1>Visão geral</h1><p className="muted">Resumo de vendas do seu negócio.</p></div>
        <div className="toolbar">
          <select value={period} onChange={(e) => setPeriod(e.target.value as Period)} aria-label="Período">
            <option value="month">Este mês</option>
            <option value="quarter">Este trimestre</option>
            <option value="all">Todo o período</option>
          </select>
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} aria-label="Data inicial" />
          <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} aria-label="Data final" />
          <button className="btn small" onClick={() => void downloadExport(period, 'xlsx')}>Excel</button>
          <button className="btn small" onClick={() => void downloadExport(period, 'pdf')}>PDF</button>
        </div>
      </div>
      {error && <div className="alert error">{error}</div>}
      {!data ? <div className="empty">Carregando…</div> : <>
        <div className="kpis">{kpis.map((k) => <article className="card kpi" key={k.label}><span>{k.label}</span><strong>{k.value}</strong><small>{k.hint}</small></article>)}</div>
        <div className="grid-2 top">
          <article className="card"><h3>Vendas por horário</h3><Bars rows={data.sales_by_hour.map((h) => ({ label: `${h.hour}h`, value: h.orders, text: `${h.orders} · ${formatMoney(h.revenue)}` }))} /></article>
          <article className="card"><h3>Mais vendidos</h3><Bars rows={data.products.slice(0, 8).map((p) => ({ label: p.product_name, value: p.quantity, text: `${p.quantity} un.` }))} /></article>
          <article className="card"><h3>Faturamento por categoria</h3><Bars rows={data.categories.map((c) => ({ label: c.category_name, value: Number(c.revenue), text: formatMoney(c.revenue) }))} /></article>
          <article className="card"><h3>Faturamento por dia</h3><Bars rows={data.sales_by_day.slice(-10).map((d) => ({ label: d.day.slice(8) + '/' + d.day.slice(5, 7), value: Number(d.revenue), text: formatMoney(d.revenue) }))} /></article>
          <article className="card"><h3>Status dos pedidos</h3><Bars rows={data.orders_by_status.map((s) => ({ label: labels[s.label] ?? s.label, value: s.count }))} /></article>
          <article className="card"><h3>Pagamento e atendimento</h3><Bars rows={[...data.orders_by_payment, ...data.orders_by_service].map((s) => ({ label: labels[s.label] ?? s.label, value: s.count }))} /></article>
        </div>
      </>}
    </section>
  )
}
