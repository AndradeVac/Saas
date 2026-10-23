import { CheckCheck, MessageCircle } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { EmptyState, ErrorBanner, PageHeader, Skeleton } from '../../components/ui/parts'
import { formatDate, formatMoney, formatPhone } from '../../lib/format'
import { readJson, writeJson } from '../../lib/storage'
import { apiErrorMessage } from '../../services/api'
import { getInsights, type CustomerRow, type Insights, type Period } from '../../services/analytics'
import { Bars, CompareChart, Heatmap } from '../dashboard/Charts'
import { useTenant } from '../tenant/TenantProvider'

const SERVICE: Record<string, string> = { DINE_IN: 'Na mesa', TAKEAWAY: 'Retirada', DELIVERY: 'Entrega' }
const percent = (value: number) => `${(value * 100).toFixed(value < 0.1 && value > 0 ? 1 : 0).replace('.', ',')}%`
const minutes = (value: number | null) => (value === null ? '—' : `${Math.round(value)} min`)

const DEFAULT_MESSAGE = 'Oi, {nome}! Aqui é da {loja}. Faz um tempinho que você não aparece e sentimos sua falta! Que tal matar a saudade hoje? Peça por aqui: {link}'

function whatsappLink(phone: string | null, text: string) {
  const digits = (phone ?? '').replace(/\D/g, '')
  if (digits.length < 10) return null
  return `https://wa.me/${digits.length <= 11 ? `55${digits}` : digits}?text=${encodeURIComponent(text)}`
}

/** "Clientes para reconquistar": regulars who stopped coming, with a ready WhatsApp message. */
function WinBack({ customers, storeName, slug }: { customers: CustomerRow[]; storeName: string; slug: string }) {
  const messageKey = `mesa:${slug}:winback-message`
  const sentKey = `mesa:${slug}:winback-sent`
  const [message, setMessage] = useState(() => readJson(messageKey, DEFAULT_MESSAGE))
  const [sent, setSent] = useState<Record<string, string>>(() => readJson(sentKey, {}))
  const link = `${window.location.origin}/`
  const lostRevenue = customers.reduce((sum, c) => sum + Number(c.total_spent) / Math.max(c.orders, 1), 0)

  function markSent(id: string) {
    const next = { ...sent, [id]: new Date().toISOString() }
    setSent(next)
    writeJson(sentKey, next)
  }

  return (
    <article className="card">
      <div className="row between">
        <div>
          <h3>Clientes para reconquistar</h3>
          <p className="card-sub" style={{ margin: 0 }}>Clientes que compraram 2 vezes ou mais e não voltam há mais de 3 semanas.</p>
        </div>
        {customers.length > 0 && <span className="badge brand" title="Soma do ticket médio de cada um: o que entra se todos voltarem uma vez">{customers.length} clientes · {formatMoney(lostRevenue)} se cada um voltar 1 vez</span>}
      </div>
      {customers.length === 0 ? (
        <EmptyState icon={<CheckCheck size={24} />} title="Ninguém sumido por enquanto" hint="Quando um cliente frequente parar de pedir, ele aparece aqui para você chamar de volta." />
      ) : (
        <>
          <label className="field" style={{ marginTop: 12 }}>
            <span>Mensagem (use {'{nome}'}, {'{loja}'} e {'{link}'})</span>
            <textarea className="winback-message" value={message} onChange={(e) => { setMessage(e.target.value); writeJson(messageKey, e.target.value) }} />
            <small className="muted">Dica: ofereça um cupom só para quem volta (crie em Cupons, ex.: VOLTEI10).</small>
          </label>
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Cliente</th><th className="num">Última visita</th><th className="num">Pedidos</th><th className="num">Já gastou</th><th /></tr></thead>
              <tbody>
                {customers.map((c) => {
                  const text = message.replaceAll('{nome}', c.name.split(' ')[0]).replaceAll('{loja}', storeName).replaceAll('{link}', link)
                  const href = whatsappLink(c.phone, text)
                  const when = sent[c.customer_id]
                  return (
                    <tr key={c.customer_id}>
                      <td>{c.name}<span className="sub">{formatPhone(c.phone)}</span></td>
                      <td className="num">há {c.days_since} dias<span className="sub">{formatDate(c.last_order_at)}</span></td>
                      <td className="num">{c.orders}</td>
                      <td className="num">{formatMoney(c.total_spent)}</td>
                      <td className="num">
                        {href
                          ? <a className={`btn small ${when ? '' : 'primary'}`} href={href} target="_blank" rel="noreferrer" onClick={() => markSent(c.customer_id)}>
                              <MessageCircle size={14} /> {when ? `Chamado em ${formatDate(when)}` : 'Chamar no WhatsApp'}
                            </a>
                          : <span className="muted">Sem telefone</span>}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </article>
  )
}

export function InsightsPage() {
  const { tenant } = useTenant()
  const [period, setPeriod] = useState<Period>('month')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [data, setData] = useState<Insights | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setError('')
    const custom = start && end
    getInsights(period, custom ? start : undefined, custom ? end : undefined)
      .then(setData)
      .catch((err) => setError(apiErrorMessage(err, 'Não foi possível carregar as análises.')))
  }, [period, start, end])

  const abc = useMemo(() => {
    if (!data) return null
    const a = data.abc.filter((p) => p.grade === 'A')
    return { a, total: data.abc.length, c: data.abc.filter((p) => p.grade === 'C') }
  }, [data])

  const k = data?.kpis
  const startDate = data?.period_start ? new Date(data.period_start) : null

  return (
    <section className="page">
      <PageHeader
        title="Análises"
        subtitle="Quem volta, quem sumiu, quando a casa enche e o que realmente dá dinheiro."
        actions={
          <div className="toolbar" style={{ margin: 0 }}>
            <select value={period} onChange={(e) => { setPeriod(e.target.value as Period); setStart(''); setEnd('') }} aria-label="Período">
              <option value="month">Este mês</option>
              <option value="quarter">Este trimestre</option>
              <option value="all">Todo o período</option>
            </select>
            <input type="date" value={start} max={end || undefined} onChange={(e) => setStart(e.target.value)} aria-label="Data inicial" />
            <input type="date" value={end} min={start || undefined} onChange={(e) => setEnd(e.target.value)} aria-label="Data final" />
          </div>
        }
      />
      <ErrorBanner message={error} />
      {!data || !k || !abc ? <Skeleton lines={6} height={40} /> : (
        <>
          <div className="kpis">
            <article className="card kpi"><span>Clientes que voltam</span><strong>{percent(k.returning_rate)}</strong><small>{k.returning_customers} de {k.customers} clientes · {k.new_customers} novos</small></article>
            {k.projected_revenue !== null
              ? <article className="card kpi"><span>Previsão do mês</span><strong>{formatMoney(k.projected_revenue)}</strong><small>No ritmo atual · até agora {formatMoney(k.revenue_so_far)}</small></article>
              : <article className="card kpi"><span>Faturamento</span><strong>{formatMoney(k.revenue_so_far)}</strong><small>No período</small></article>}
            <article className="card kpi"><span>Tempo de preparo</span><strong>{minutes(k.avg_prep_minutes)}</strong><small>{k.avg_delivery_minutes !== null ? `Entrega completa: ${minutes(k.avg_delivery_minutes)}` : 'Do pedido até ficar pronto'}</small></article>
            <article className="card kpi"><span>Itens por pedido</span><strong>{k.items_per_order.toFixed(1).replace('.', ',')}</strong><small>Média de itens em cada pedido</small></article>
            <article className="card kpi"><span>Cancelamentos</span><strong>{percent(k.cancellation_rate)}</strong><small>{k.cancelled_orders} pedidos cancelados</small></article>
            <article className="card kpi"><span>Vendas com cupom</span><strong>{formatMoney(k.coupon_revenue)}</strong><small>{k.coupon_orders} pedidos · {formatMoney(k.discount_total)} em descontos</small></article>
          </div>

          <WinBack customers={data.at_risk} storeName={tenant.name.trim()} slug={tenant.slug} />

          <div className="grid-2 top">
            <article className="card">
              <h3>Faturamento acumulado</h3>
              <CompareChart points={data.comparison.map((p) => {
                const day = startDate ? new Date(startDate.getTime() + (p.day - 1) * 86400000) : null
                return { label: day ? `${String(day.getDate()).padStart(2, '0')}/${String(day.getMonth() + 1).padStart(2, '0')}` : String(p.day), current: p.current === null ? null : Number(p.current), previous: p.previous === null ? null : Number(p.previous) }
              })} />
              {data.comparison.length > 0 && <div className="chart-legend"><span><i />Este período</span><span><i className="previous" />Período anterior</span></div>}
            </article>
            <article className="card">
              <h3>Quando a casa enche</h3>
              <Heatmap cells={data.heatmap} />
            </article>
            <article className="card">
              <h3>Curva ABC dos produtos</h3>
              {abc.total > 0 && (
                <p className="insight-note"><strong>{abc.a.length} de {abc.total} produtos</strong> fazem 80% do seu faturamento. Nunca deixe faltar: {abc.a.slice(0, 3).map((p) => p.product_name).join(', ')}.</p>
              )}
              <div className="table-wrap">
                <table className="table">
                  <thead><tr><th /><th>Produto</th><th className="num">Faturamento</th><th className="num">% </th></tr></thead>
                  <tbody>
                    {data.abc.slice(0, 12).map((p) => (
                      <tr key={p.product_name}><td><span className={`grade grade-${p.grade}`}>{p.grade}</span></td><td>{p.product_name}<span className="sub">{p.quantity} vendidos</span></td><td className="num">{formatMoney(p.revenue)}</td><td className="num">{percent(p.share)}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {abc.c.length > 0 && <p className="card-sub">Classe C ({abc.c.length}): vendem pouco. Vale rever preço, foto ou tirar do cardápio.</p>}
            </article>
            <article className="card">
              <h3>Melhores clientes</h3>
              <div className="table-wrap">
                <table className="table">
                  <thead><tr><th>Cliente</th><th className="num">Pedidos</th><th className="num">Gastou</th></tr></thead>
                  <tbody>
                    {data.top_customers.map((c, i) => (
                      <tr key={c.customer_id}><td>{i + 1}. {c.name}<span className="sub">última visita há {c.days_since} dias</span></td><td className="num">{c.orders}</td><td className="num">{formatMoney(c.total_spent)}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
            <article className="card">
              <h3>Ticket médio por atendimento</h3>
              <Bars rows={data.tickets_by_service.map((t) => ({ label: `${SERVICE[t.service_type] ?? t.service_type} (${t.orders})`, value: Number(t.average_ticket), text: formatMoney(t.average_ticket) }))} />
            </article>
            <article className="card">
              <h3>Por que os pedidos são cancelados</h3>
              <Bars rows={data.cancellation_reasons.map((r) => ({ label: r.reason, value: r.count }))} />
            </article>
          </div>
        </>
      )}
    </section>
  )
}
