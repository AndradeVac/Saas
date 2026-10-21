import { Download, History } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { Pagination } from '../../components/ui/Pagination'
import { EmptyState, ErrorBanner, PageHeader, Skeleton } from '../../components/ui/parts'
import { useDebounced } from '../../hooks/useDebounced'
import { formatDateTime, formatMoney, orderStatusLabels, paymentMethodLabels, serviceShortLabels } from '../../lib/format'
import { apiErrorMessage, isPlanLimitError } from '../../services/api'
import { exportOrders, getOrders, type Order, type OrderFilters } from '../../services/orders'
import type { OrderStatus, PaymentStatus, ServiceType } from '../../types'
import { usePlan } from '../plans/PlanProvider'

const PAGE_SIZE = 25
const today = () => new Date().toISOString().slice(0, 10)

export function HistoryPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<{ items: Order[]; total: number } | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [status, setStatus] = useState<OrderStatus | ''>('')
  const [payment, setPayment] = useState<PaymentStatus | ''>('')
  const [service, setService] = useState<ServiceType | ''>('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const search = useDebounced(q)

  const filters: OrderFilters = {
    q: search || undefined,
    status: status ? [status] : undefined,
    payment_status: payment || undefined,
    service_type: service || undefined,
    date_from: from || undefined,
    date_to: to || undefined,
  }
  const key = JSON.stringify(filters)

  // Any filter change goes back to the first page.
  useEffect(() => { setPage(1) }, [key])

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    getOrders({ ...JSON.parse(key), page, page_size: PAGE_SIZE })
      .then((result) => setData({ items: result.items, total: result.total }))
      .catch((err) => setError(apiErrorMessage(err, 'Não foi possível carregar os pedidos.')))
      .finally(() => setLoading(false))
  }, [key, page])
  useEffect(load, [load])

  const { guard } = usePlan()
  const download = () => guard('exports', () => {
    exportOrders(JSON.parse(key)).catch((err) => { if (!isPlanLimitError(err)) toast.error(apiErrorMessage(err, 'Não foi possível exportar.')) })
  })

  const clear = () => { setQ(''); setStatus(''); setPayment(''); setService(''); setFrom(''); setTo('') }
  const hasFilters = Boolean(q || status || payment || service || from || to)

  return (
    <section className="page">
      <PageHeader
        title="Histórico de pedidos"
        subtitle="Busque qualquer pedido, filtre por período e exporte para o Excel."
        actions={<button className="btn" onClick={download}><Download size={16} /> Exportar CSV</button>}
      />

      <div className="toolbar">
        <label className="search"><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nº do pedido, cliente, telefone ou mesa" aria-label="Buscar" /></label>
        <select value={status} onChange={(e) => setStatus(e.target.value as OrderStatus | '')} aria-label="Status">
          <option value="">Todos os status</option>
          {(Object.keys(orderStatusLabels) as OrderStatus[]).map((s) => <option key={s} value={s}>{orderStatusLabels[s]}</option>)}
        </select>
        <select value={payment} onChange={(e) => setPayment(e.target.value as PaymentStatus | '')} aria-label="Pagamento">
          <option value="">Pago e pendente</option>
          <option value="PAID">Pagos</option>
          <option value="PENDING">Pendentes</option>
        </select>
        <select value={service} onChange={(e) => setService(e.target.value as ServiceType | '')} aria-label="Atendimento">
          <option value="">Todos os atendimentos</option>
          {(Object.keys(serviceShortLabels) as ServiceType[]).map((s) => <option key={s} value={s}>{serviceShortLabels[s]}</option>)}
        </select>
        <input type="date" value={from} max={to || today()} onChange={(e) => setFrom(e.target.value)} aria-label="De" />
        <input type="date" value={to} min={from} max={today()} onChange={(e) => setTo(e.target.value)} aria-label="Até" />
        {hasFilters && <button className="btn ghost" onClick={clear}>Limpar</button>}
      </div>

      <ErrorBanner message={error} onRetry={load} />
      <div className="card pad0">
        {loading && !data ? <div style={{ padding: 20 }}><Skeleton lines={6} height={30} /></div> : data && data.items.length === 0 ? (
          <EmptyState icon={<History size={26} />} title="Nenhum pedido encontrado" hint={hasFilters ? 'Tente remover algum filtro.' : 'Os pedidos aparecerão aqui.'} />
        ) : data && (
          <>
            <div className="table-wrap" style={{ opacity: loading ? 0.6 : 1 }}>
              <table className="table keep-cols">
                <thead><tr><th>Pedido</th><th>Cliente</th><th>Atendimento</th><th>Status</th><th>Pagamento</th><th className="num">Total</th></tr></thead>
                <tbody>
                  {data.items.map((order) => (
                    <tr key={order.id} className="clickable" onClick={() => navigate(`/painel/pedidos/${order.id}`)}>
                      <td><strong>#{order.order_number}</strong><span className="sub">{formatDateTime(order.created_at)}</span></td>
                      <td>{order.customer_name}</td>
                      <td>{serviceShortLabels[order.service_type]}{order.table_label ? ` ${order.table_label}` : ''}</td>
                      <td><span className={`badge status-${order.status.toLowerCase()}`}>{orderStatusLabels[order.status]}</span></td>
                      <td><span className={`badge ${order.payment_status === 'PAID' ? 'ok' : 'warn'}`}>{order.payment_status === 'PAID' ? 'Pago' : 'Pendente'}</span><span className="sub">{paymentMethodLabels[order.payment_method]}</span></td>
                      <td className="num"><strong>{formatMoney(order.total)}</strong></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onChange={setPage} />
          </>
        )}
      </div>
    </section>
  )
}
