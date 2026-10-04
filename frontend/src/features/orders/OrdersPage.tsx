import { ArrowRight, Bell, BellOff, Plus, Search, UtensilsCrossed } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { EmptyState, PageHeader, Skeleton } from '../../components/ui/parts'
import { formatMoney, formatTime, paymentMethodLabels, serviceShortLabels, timeAgo } from '../../lib/format'
import { apiErrorMessage } from '../../services/api'
import { updateOrderStatus, type Order } from '../../services/orders'
import type { OrderStatus } from '../../types'
import { useLiveOrders } from './LiveOrders'

const LATE_MINUTES = 20

const columns: Array<{ status: OrderStatus; title: string; color: string; next?: OrderStatus; action?: string }> = [
  { status: 'RECEIVED', title: 'Novos', color: 'var(--info)', next: 'PREPARING', action: 'Iniciar preparo' },
  { status: 'PREPARING', title: 'Em preparo', color: 'var(--warn)', next: 'READY', action: 'Marcar como pronto' },
  { status: 'READY', title: 'Prontos', color: 'var(--ok)', next: 'FINISHED', action: 'Entregar' },
  { status: 'FINISHED', title: 'Finalizados hoje', color: 'var(--muted)' },
]

export function OrdersPage() {
  const navigate = useNavigate()
  const { orders, loading, offline, freshIds, soundOn, setSoundOn, replace, refresh } = useLiveOrders()
  const [updating, setUpdating] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [now, setNow] = useState(Date.now())

  // Re-render every 30s so "há 12 min" and the late flag stay accurate between refreshes.
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])

  async function advance(order: Order, next: OrderStatus) {
    setUpdating(order.id)
    try {
      replace(await updateOrderStatus(order.id, next))
      void refresh()
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível atualizar o pedido.'))
    } finally {
      setUpdating(null)
    }
  }

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase().replace(/^#/, '')
    if (!term) return orders
    return orders.filter((o) =>
      `${o.order_number} ${o.customer_name ?? ''} ${o.table_label ?? ''} ${o.items.map((i) => i.product_name).join(' ')}`.toLowerCase().includes(term))
  }, [orders, search])

  const active = orders.filter((o) => o.status !== 'FINISHED' && o.status !== 'CANCELLED').length

  return (
    <section className="page">
      <PageHeader
        title="Pedidos"
        subtitle={`${active} ${active === 1 ? 'pedido em andamento' : 'pedidos em andamento'}`}
        actions={
          <div className="board-tools">
            <span className={`live-pill ${offline ? 'err' : ''}`}><i />{offline ? 'Sem conexão' : 'Ao vivo'}</span>
            <button className="btn" onClick={() => setSoundOn(!soundOn)} aria-pressed={soundOn} title="Som de novo pedido">
              {soundOn ? <Bell size={16} /> : <BellOff size={16} />} Som {soundOn ? 'ligado' : 'desligado'}
            </button>
            <button className="btn primary" onClick={() => navigate('/painel/pedidos/novo')}><Plus size={16} /> Novo pedido</button>
          </div>
        }
      />
      <label className="search">
        <Search size={16} />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar por número, cliente, mesa ou item" aria-label="Buscar pedidos" />
      </label>

      {loading ? (
        <div className="board">{columns.map((c) => <div className="board-col" key={c.status}><Skeleton lines={3} height={90} /></div>)}</div>
      ) : orders.length === 0 ? (
        <EmptyState
          icon={<UtensilsCrossed size={26} />}
          title="Nenhum pedido por enquanto"
          hint="Quando um cliente pedir pelo cardápio, o pedido aparece aqui na hora, com aviso sonoro."
          action={<button className="btn primary" onClick={() => navigate('/painel/pedidos/novo')}>Lançar pedido manual</button>}
        />
      ) : (
        <div className="board">
          {columns.map((column) => {
            const items = filtered.filter((o) => o.status === column.status)
            return (
              <div className="board-col" key={column.status} style={{ ['--col' as string]: column.color }}>
                <div className="board-col-head"><h3>{column.title}</h3><span>{items.length}</span></div>
                {items.length === 0 && <div className="empty small">Nenhum pedido</div>}
                {items.map((order) => {
                  const minutes = Math.round((now - new Date(order.created_at).getTime()) / 60_000)
                  const late = (order.status === 'RECEIVED' || order.status === 'PREPARING') && minutes >= LATE_MINUTES
                  return (
                    <article
                      key={order.id}
                      className={`order-card ${freshIds.has(order.id) ? 'fresh' : ''} ${late ? 'late' : ''}`}
                      onClick={() => navigate(`/painel/pedidos/${order.id}`)}
                      tabIndex={0}
                      onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/painel/pedidos/${order.id}`) }}
                    >
                      <div className="order-card-top">
                        <strong>#{order.order_number}</strong>
                        <span className={`order-age ${late ? 'late' : ''}`}>{formatTime(order.created_at)} · {timeAgo(order.created_at, now)}</span>
                      </div>
                      <div className="order-card-who">
                        <span>{order.customer_name ?? 'Cliente'}</span>
                        <span className="badge">{serviceShortLabels[order.service_type]}{order.table_label ? ` ${order.table_label}` : ''}</span>
                      </div>
                      <ul>
                        {order.items.map((item) => (
                          <li key={item.id}>
                            {item.quantity}× {item.product_name}
                            {item.options.length > 0 && <small>{item.options.map((o) => o.name).join(' · ')}</small>}
                            {item.notes && <small>“{item.notes}”</small>}
                          </li>
                        ))}
                      </ul>
                      {order.notes && <div className="alert warn" style={{ margin: 0 }}>Obs.: {order.notes}</div>}
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
                  )
                })}
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
