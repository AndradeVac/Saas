import { Check, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { formatDateTime, formatMoney, orderStatusLabels, serviceLabels } from '../../lib/format'
import { trackOrder, type Tracking } from '../../services/publicMenu'
import type { OrderStatus } from '../../types'

const STEPS: OrderStatus[] = ['RECEIVED', 'PREPARING', 'READY', 'FINISHED']
const POLL_MS = 5000

function Sheet({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <section className="sheet" onClick={(e) => e.stopPropagation()} role="dialog" aria-label={title}>
        <header className="sheet-head">
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Fechar"><X size={20} /></button>
        </header>
        <div className="sheet-body">{children}</div>
      </section>
    </div>
  )
}

export function TrackSheet({ token, onClose }: { token: string; onClose: () => void }) {
  const [order, setOrder] = useState<Tracking | null>(null)
  const [missing, setMissing] = useState(false)

  useEffect(() => {
    let active = true
    let timer = 0
    const load = () => trackOrder(token)
      .then((data) => {
        if (!active) return
        setOrder(data)
        if (data.status !== 'FINISHED' && data.status !== 'CANCELLED') timer = window.setTimeout(load, POLL_MS)
      })
      .catch(() => { if (active) setMissing(true) })
    void load()
    return () => { active = false; window.clearTimeout(timer) }
  }, [token])

  if (missing) return <Sheet title="Pedido" onClose={onClose}><div className="empty">Pedido não encontrado.</div></Sheet>
  if (!order) return <Sheet title="Pedido" onClose={onClose}><div className="empty">Carregando…</div></Sheet>

  const status = order.status as OrderStatus
  const index = STEPS.indexOf(status)
  return (
    <Sheet title={`Pedido #${order.order_number}`} onClose={onClose}>
      <p className="muted">
        {serviceLabels[order.service_type]}{order.table_label ? ` · Mesa ${order.table_label}` : ''} · {formatDateTime(order.created_at)}
      </p>
      {status === 'CANCELLED' ? (
        <div className="alert error">Este pedido foi cancelado. Fale com a equipe se tiver dúvidas.</div>
      ) : (
        <ol className="track">
          {STEPS.map((step, i) => (
            <li key={step} className={i < index ? 'done' : i === index ? 'current' : ''}>
              <span className="dot">{i < index || status === 'FINISHED' ? <Check size={12} /> : null}</span>
              {orderStatusLabels[step]}
            </li>
          ))}
        </ol>
      )}
      <div className="card flat">
        {order.items.map((item, i) => (
          <div className="detail-line" key={i}>
            <span>{item.quantity}× {item.product_name}{item.notes ? <small> — {item.notes}</small> : null}</span>
          </div>
        ))}
        <div className="total-row"><span>Total</span><strong>{formatMoney(order.total)}</strong></div>
      </div>
      <p className="muted">O pagamento é feito no caixa. {order.payment_status === 'PAID' && '✔ Pagamento confirmado.'}</p>
    </Sheet>
  )
}

export function OrdersSheet({ tokens, onClose, onOpen }: { slug: string; tokens: string[]; onClose: () => void; onOpen: (token: string) => void }) {
  const [orders, setOrders] = useState<Array<{ token: string; data: Tracking }>>([])
  const [loading, setLoading] = useState(tokens.length > 0)

  useEffect(() => {
    Promise.all(tokens.map((token) => trackOrder(token).then((data) => ({ token, data })).catch(() => null)))
      .then((results) => setOrders(results.filter((r): r is { token: string; data: Tracking } => r !== null)))
      .finally(() => setLoading(false))
  }, [tokens])

  return (
    <Sheet title="Meus pedidos" onClose={onClose}>
      {loading && <div className="empty">Carregando…</div>}
      {!loading && orders.length === 0 && <div className="empty">Você ainda não fez pedidos neste aparelho.</div>}
      {orders.map(({ token, data }) => (
        <button className="order-row" key={token} onClick={() => onOpen(token)}>
          <div>
            <strong>Pedido #{data.order_number}</strong>
            <span>{formatDateTime(data.created_at)} · {data.items.length} {data.items.length === 1 ? 'item' : 'itens'}</span>
          </div>
          <div className="order-row-end">
            <span className={`badge status-${data.status.toLowerCase()}`}>{orderStatusLabels[data.status as OrderStatus]}</span>
            <strong>{formatMoney(data.total)}</strong>
          </div>
        </button>
      ))}
    </Sheet>
  )
}
