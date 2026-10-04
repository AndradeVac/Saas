import { Check, Download, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { ErrorBanner, PageHeader, Skeleton } from '../../components/ui/parts'
import { formatMoney, orderStatusLabels, paymentMethodLabels, serviceLabels } from '../../lib/format'
import { readJson, writeJson } from '../../lib/storage'
import { apiErrorMessage } from '../../services/api'
import { downloadDashboard, getDashboard, type Dashboard, type Period } from '../../services/analytics'
import { getProducts } from '../../services/catalog'
import { getTenantSettings } from '../../services/tenant'
import { Bars, ColumnChart, LineChart } from './Charts'

const labels: Record<string, string> = { ...orderStatusLabels, ...paymentMethodLabels, ...serviceLabels, DINE_IN: 'Na mesa', TAKEAWAY: 'Retirada', DELIVERY: 'Entrega' }

type Step = { done: boolean; text: string; to: string; cta: string }

function Onboarding({ steps, onDismiss }: { steps: Step[]; onDismiss: () => void }) {
  const done = steps.filter((s) => s.done).length
  return (
    <div className="card">
      <div className="row between">
        <div><h3>Primeiros passos</h3><p className="card-sub" style={{ margin: 0 }}>{done} de {steps.length} concluídos. Deixe seu cardápio pronto para receber pedidos.</p></div>
        <button className="icon-btn" onClick={onDismiss} aria-label="Dispensar"><X size={18} /></button>
      </div>
      <div className="progress"><b style={{ width: `${(done / steps.length) * 100}%` }} /></div>
      <ul className="checklist">
        {steps.map((s) => (
          <li key={s.text} className={s.done ? 'done' : ''}>
            <span className="tick">{s.done && <Check size={14} />}</span>
            <span className="check-text">{s.text}</span>
            {!s.done && <Link className="btn small" to={s.to}>{s.cta}</Link>}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null)
  const [period, setPeriod] = useState<Period>('month')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [error, setError] = useState('')
  const [steps, setSteps] = useState<Step[] | null>(null)
  const [dismissed, setDismissed] = useState(() => readJson<boolean>('mesa-onboarding-dismissed', false))

  useEffect(() => {
    setError('')
    const custom = start && end
    getDashboard(period, custom ? start : undefined, custom ? end : undefined)
      .then(setData)
      .catch((err) => setError(apiErrorMessage(err, 'Não foi possível carregar os indicadores.')))
  }, [period, start, end])

  useEffect(() => {
    Promise.all([getTenantSettings(), getProducts(), getDashboard('all')]).then(([settings, products, all]) => {
      setSteps([
        { done: Boolean(settings.logo_url), text: 'Envie a logo e escolha a cor da sua marca', to: '/painel/configuracoes', cta: 'Personalizar' },
        { done: products.filter((p) => p.active).length >= 3, text: 'Cadastre seus primeiros produtos (pelo menos 3)', to: '/painel/produtos', cta: 'Cadastrar' },
        { done: Boolean(settings.phone && settings.address), text: 'Informe telefone e endereço do negócio', to: '/painel/configuracoes', cta: 'Preencher' },
        { done: settings.hours_mode === 'SCHEDULE', text: 'Defina os horários de funcionamento', to: '/painel/configuracoes', cta: 'Definir' },
        { done: all.order_count > 0, text: 'Receba o primeiro pedido (faça um teste pelo seu cardápio)', to: '/painel/pedidos/novo', cta: 'Lançar pedido' },
      ])
    }).catch(() => setSteps(null))
  }, [])

  const exportFile = (format: 'xlsx' | 'pdf') => downloadDashboard(period, format).catch(() => toast.error('Não foi possível exportar.'))

  const change = Number(data?.revenue_change_percent ?? 0)
  const showOnboarding = steps && !dismissed && steps.some((s) => !s.done)

  return (
    <section className="page">
      <PageHeader
        title="Visão geral"
        subtitle="Como está o seu negócio."
        actions={
          <div className="toolbar" style={{ margin: 0 }}>
            <select value={period} onChange={(e) => { setPeriod(e.target.value as Period); setStart(''); setEnd('') }} aria-label="Período">
              <option value="month">Este mês</option>
              <option value="quarter">Este trimestre</option>
              <option value="all">Todo o período</option>
            </select>
            <input type="date" value={start} max={end || undefined} onChange={(e) => setStart(e.target.value)} aria-label="Data inicial" />
            <input type="date" value={end} min={start || undefined} onChange={(e) => setEnd(e.target.value)} aria-label="Data final" />
            <button className="btn" onClick={() => void exportFile('xlsx')}><Download size={15} /> Excel</button>
            <button className="btn" onClick={() => void exportFile('pdf')}><Download size={15} /> PDF</button>
          </div>
        }
      />
      <ErrorBanner message={error} />
      {showOnboarding && <Onboarding steps={steps} onDismiss={() => { setDismissed(true); writeJson('mesa-onboarding-dismissed', true) }} />}

      {!data ? <Skeleton lines={6} height={40} /> : (
        <>
          <div className="kpis">
            <article className="card kpi"><span>Faturamento</span><strong>{formatMoney(data.revenue)}</strong><small className={change >= 0 ? 'delta-up' : 'delta-down'}>{Number(data.previous_revenue) > 0 ? `${change >= 0 ? '▲' : '▼'} ${Math.abs(change).toFixed(1)}% vs período anterior` : 'Sem período anterior'}</small></article>
            <article className="card kpi"><span>Pedidos</span><strong>{data.order_count}</strong><small>Sem os cancelados</small></article>
            <article className="card kpi"><span>Ticket médio</span><strong>{formatMoney(data.average_ticket)}</strong><small>Por pedido</small></article>
            <article className="card kpi"><span>Mais vendido</span><strong title={data.top_product?.product_name}>{data.top_product?.product_name ?? '—'}</strong><small>{data.top_product ? `${data.top_product.quantity} unidades` : 'Aguardando pedidos'}</small></article>
          </div>
          <div className="grid-2 top">
            <article className="card"><h3>Faturamento por dia</h3><LineChart points={data.sales_by_day.map((d) => ({ label: `${d.day.slice(8)}/${d.day.slice(5, 7)}`, value: Number(d.revenue) }))} /></article>
            <article className="card"><h3>Pedidos por horário</h3><ColumnChart points={data.sales_by_hour.map((h) => ({ label: String(h.hour), value: h.orders }))} /></article>
            <article className="card"><h3>Mais vendidos</h3><Bars rows={data.products.slice(0, 8).map((p) => ({ label: p.product_name, value: p.quantity, text: `${p.quantity} un.` }))} /></article>
            <article className="card"><h3>Faturamento por categoria</h3><Bars rows={data.categories.map((c) => ({ label: c.category_name, value: Number(c.revenue), text: formatMoney(c.revenue) }))} /></article>
            <article className="card"><h3>Status dos pedidos</h3><Bars rows={data.orders_by_status.map((s) => ({ label: labels[s.label] ?? s.label, value: s.count }))} /></article>
            <article className="card"><h3>Pagamento e atendimento</h3><Bars rows={[...data.orders_by_payment, ...data.orders_by_service].map((s) => ({ label: labels[s.label] ?? s.label, value: s.count }))} /></article>
          </div>
        </>
      )}
    </section>
  )
}
