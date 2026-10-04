import { ArrowRight, Plus, Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { formatMoney, formatTime, paymentMethodLabels, serviceLabels } from '../../lib/format'
import { apiErrorMessage } from '../../services/api'
import { getOrders, updateOrderStatus, type Order } from '../../services/admin'
import type { OrderStatus } from '../../types'

const REFRESH_MS = 10_000

const columns: Array<{ status: OrderStatus; title: string; next?: OrderStatus; action?: string }> = [
  { status: 'RECEIVED', title: 'Novos', next: 'PREPARING', action: 'Iniciar preparo' },
  { status: 'PREPARING', title: 'Em preparo', next: 'READY', action: 'Marcar como pronto' },
  { status: 'READY', title: 'Prontos', next: 'FINISHED', action: 'Entregar' },
  { status: 'FINISHED', title: 'Finalizados' },
]

export function OrdersPage() {
  const navigate = useNavigate()
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [updating, setUpdating] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')

  useEffect(() => {
    let active = true
    const load = () => getOrders()
      .then((data) => { if (active) { setOrders(data); setError('') } })
      .catch(() => { if (active) setError('Não foi possível carregar os pedidos.') })
      .finally(() => { if (active) setLoading(false) })
    void load()
    const timer = window.setInterval(() => void load(), REFRESH_MS)
    return () => { active = false; window.clearInterval(timer) }
  }, [])

  async function advance(order: Order, next: OrderStatus) {
    setUpdating(order.id)
    try {
      const updated = await updateOrderStatus(order.id, next)
      setOrders((current) => current.map((o) => (o.id === order.id ? updated : o)))
    } catch (err) {
      setError(apiErrorMessage(err, 'Não foi possível atualizar o pedido.'))
    } finally {
      setUpdating(null)
    }
  }

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase()
    if (!term) return orders
    return orders.filter((o) =>
      `${o.order_number} ${o.customer_name ?? ''} ${o.table_label ?? ''} ${o.items.map((i) => i.product_name).join(' ')}`.toLowerCase().includes(term))
  }, [orders, search])

  const today = new Date().toDateString()

  return (
    <section className="page">
      <div className="page-head">
        <div><h1>Pedidos</h1><p className="muted">Atualiza sozinho a cada 10 segundos.</p></div>
        <button className="btn primary" onClick={() => navigate('/painel/pedidos/novo')}><Plus size={16} /> Novo pedido</button>
      </div>
      {error && <div className="alert error">{error}</div>}
      <label className="search"><Search size={16} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar por número, cliente, mesa ou item" /></label>
      {loading ? <div className="empty">Carregando…</div> : (
        <div className="board">
          {columns.map((column) => {
            const items = filtered
              .filter((o) => o.status === column.status)
              .filter((o) => column.status !== 'FINISHED' || new Date(o.created_at).toDateString() === today)
            return (
              <div className="board-col" key={column.status}>
                <div className="board-col-head"><h3>{column.title}</h3><span>{items.length}</span></div>
                {items.length === 0 && <div className="empty small">Nenhum pedido</div>}
                {items.map((order) => (
                  <article className="order-card" key={order.id} onClick={() => navigate(`/painel/pedidos/${order.id}`)}>
                    <div className="order-card-top">
                      <strong>#{order.order_number}</strong>
                      <span>{formatTime(order.created_at)}</span>
                    </div>
                    <div className="order-card-who">
                      {order.customer_name ?? 'Cliente'} · {serviceLabels[order.service_type]}{order.table_label ? ` · Mesa ${order.table_label}` : ''}
                    </div>
                    <ul>{order.items.map((item) => <li key={item.id}>{item.quantity}× {item.product_name}</li>)}</ul>
                    <div className="order-card-foot">
                      <strong>{formatMoney(order.total)}</strong>
                      <span className={`badge ${order.payment_status === 'PAID' ? 'ok' : 'warn'}`}>
                        {order.payment_status === 'PAID' ? 'Pago' : paymentMethodLabels[order.payment_method]}
                      </span>
                    </div>
                    {column.next && (
                      <button
                        className="btn primary small block"
                        disabled={updating === order.id}
                        onClick={(e) => { e.stopPropagation(); void advance(order, column.next!) }}
                      >
                        <ArrowRight size={14} /> {updating === order.id ? 'Atualizando…' : column.action}
                      </button>
                    )}
                  </article>
                ))}
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
