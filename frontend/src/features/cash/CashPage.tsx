import { Printer } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ErrorBanner, PageHeader, Skeleton } from '../../components/ui/parts'
import { formatMoney } from '../../lib/format'
import { api, apiErrorMessage } from '../../services/api'

type CashReport = {
  day: string
  received: Array<{ method: string; label: string; count: number; amount: string }>
  received_total: string
  orders: number
  cancelled: number
  cancelled_amount: string
  discounts: string
  service_fees: string
  delivery_fees: string
  pending_orders: number
  pending_amount: string
  open_tabs: number
  pix_to_confirm: number
}

const today = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60_000).toISOString().slice(0, 10)

/** Fechamento de caixa: what came in today by payment method, and what is still open. Printable. */
export function CashPage() {
  const [day, setDay] = useState(today())
  const [data, setData] = useState<CashReport | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    setData(null)
    api.get<CashReport>('/analytics/cash', { params: { day } }).then((r) => setData(r.data)).catch((err) => setError(apiErrorMessage(err, 'Não foi possível carregar o caixa.')))
  }, [day])

  return (
    <section className="page narrow cash">
      <PageHeader
        title="Fechamento de caixa"
        subtitle="Quanto entrou no dia, por forma de pagamento."
        actions={<div className="toolbar" style={{ margin: 0 }}>
          <input type="date" value={day} max={today()} onChange={(e) => setDay(e.target.value || today())} aria-label="Dia" />
          <button className="btn no-print" onClick={() => window.print()}><Printer size={16} /> Imprimir</button>
        </div>}
      />
      <ErrorBanner message={error} />
      {!data ? <Skeleton lines={5} height={36} /> : (
        <>
          {(data.open_tabs > 0 || data.pending_orders > 0 || data.pix_to_confirm > 0) && (
            <div className="alert warn">
              <span>
                Antes de fechar: {[
                  data.open_tabs > 0 && `${data.open_tabs} ${data.open_tabs === 1 ? 'mesa aberta' : 'mesas abertas'}`,
                  data.pending_orders > 0 && `${data.pending_orders} ${data.pending_orders === 1 ? 'pedido sem pagamento' : 'pedidos sem pagamento'} (${formatMoney(data.pending_amount)})`,
                  data.pix_to_confirm > 0 && `${data.pix_to_confirm} PIX para conferir`,
                ].filter(Boolean).join(' · ')}.
              </span>
            </div>
          )}
          <div className="card">
            <div className="cash-total"><span>Total recebido</span><strong>{formatMoney(data.received_total)}</strong></div>
            <table className="table">
              <thead><tr><th>Forma de pagamento</th><th className="num">Pagamentos</th><th className="num">Valor</th></tr></thead>
              <tbody>
                {data.received.length === 0 && <tr><td colSpan={3} className="muted">Nenhum pagamento recebido neste dia.</td></tr>}
                {data.received.map((r) => <tr key={r.method}><td>{r.label}</td><td className="num">{r.count}</td><td className="num"><strong>{formatMoney(r.amount)}</strong></td></tr>)}
              </tbody>
            </table>
          </div>
          <div className="kpis">
            <article className="card kpi"><span>Pedidos do dia</span><strong>{data.orders}</strong><small>sem os cancelados</small></article>
            <article className="card kpi"><span>Cancelados</span><strong>{data.cancelled}</strong><small>{formatMoney(data.cancelled_amount)}</small></article>
            <article className="card kpi"><span>Descontos</span><strong>{formatMoney(data.discounts)}</strong><small>cupons</small></article>
            <article className="card kpi"><span>Taxas</span><strong>{formatMoney(Number(data.service_fees) + Number(data.delivery_fees))}</strong><small>serviço {formatMoney(data.service_fees)} · entrega {formatMoney(data.delivery_fees)}</small></article>
          </div>
        </>
      )}
    </section>
  )
}
