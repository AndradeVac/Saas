import { ArrowLeft } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { formatMoney, formatPhone, formatTime, orderStatusLabels, paymentMethodLabels, serviceLabels } from '../../lib/format'
import { apiErrorMessage } from '../../services/api'
import { getOrder, updateOrderPayment, updateOrderStatus, type Order } from '../../services/admin'
import type { OrderStatus } from '../../types'

const FLOW: OrderStatus[] = ['RECEIVED', 'PREPARING', 'READY', 'FINISHED']

export function OrderDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [order, setOrder] = useState<Order | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (id) getOrder(id).then(setOrder).catch(() => setError('Pedido não encontrado.'))
  }, [id])

  async function run(action: () => Promise<Order>) {
    setBusy(true)
    setError('')
    try {
      setOrder(await action())
    } catch (err) {
      setError(apiErrorMessage(err, 'Não foi possível atualizar o pedido.'))
    } finally {
      setBusy(false)
    }
  }

  if (!order) return <section className="page">{error ? <div className="alert error">{error}</div> : <div className="empty">Carregando…</div>}</section>

  const next = FLOW[FLOW.indexOf(order.status) + 1]
  const closed = order.status === 'FINISHED' || order.status === 'CANCELLED'
  const cancellation = order.status_history.find((h) => h.status === 'CANCELLED')

  function cancel() {
    const reason = window.prompt('Motivo do cancelamento:')?.trim()
    if (reason) void run(() => updateOrderStatus(order!.id, 'CANCELLED', reason))
  }

  return (
    <section className="page narrow">
      <button className="btn ghost small" onClick={() => navigate('/painel/pedidos')}><ArrowLeft size={14} /> Voltar</button>
      <div className="page-head">
        <div>
          <h1>Pedido #{order.order_number} <span className={`badge status-${order.status.toLowerCase()}`}>{orderStatusLabels[order.status]}</span></h1>
          <p className="muted">
            {formatTime(order.created_at)} · {serviceLabels[order.service_type]}{order.table_label ? ` · Mesa ${order.table_label}` : ''}
          </p>
        </div>
      </div>
      {error && <div className="alert error">{error}</div>}

      <div className="card">
        <p><strong>{order.customer_name}</strong>{order.customer_phone && <span className="muted"> · {formatPhone(order.customer_phone)}</span>}</p>
        {order.items.map((item) => (
          <div className="detail-line" key={item.id}>
            <span>{item.quantity}× {item.product_name}{item.notes && <small> — {item.notes}</small>}</span>
            <b>{formatMoney(item.total_price)}</b>
          </div>
        ))}
        {order.notes && <p className="alert warn">Obs.: {order.notes}</p>}
        <div className="total-row"><span>Total</span><strong>{formatMoney(order.total)}</strong></div>
      </div>

      <div className="card">
        <div className="detail-line">
          <span>Pagamento ({paymentMethodLabels[order.payment_method]})</span>
          <span className={`badge ${order.payment_status === 'PAID' ? 'ok' : 'warn'}`}>
            {order.payment_status === 'PAID' ? `Pago às ${formatTime(order.paid_at)}` : 'Pendente'}
          </span>
        </div>
        {order.status !== 'CANCELLED' && (
          order.payment_status === 'PAID'
            ? <button className="btn small" disabled={busy} onClick={() => void run(() => updateOrderPayment(order.id, 'PENDING'))}>Desfazer pagamento</button>
            : <button className="btn primary small" disabled={busy} onClick={() => void run(() => updateOrderPayment(order.id, 'PAID'))}>Confirmar pagamento recebido</button>
        )}
      </div>

      {cancellation?.reason && <div className="alert error">Cancelado: {cancellation.reason}</div>}
      <div className="actions">
        {!closed && next && <button className="btn primary" disabled={busy} onClick={() => void run(() => updateOrderStatus(order.id, next))}>Avançar para “{orderStatusLabels[next]}”</button>}
        {!closed && <button className="btn danger" disabled={busy} onClick={cancel}>Cancelar pedido</button>}
      </div>

      <h3>Histórico</h3>
      <ul className="history">
        {order.status_history.map((h, i) => <li key={i}><span>{orderStatusLabels[h.status]}</span><span className="muted">{formatTime(h.created_at)}</span></li>)}
      </ul>
    </section>
  )
}
