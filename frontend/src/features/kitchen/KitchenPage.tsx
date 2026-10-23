import { ArrowLeft, Maximize2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { apiErrorMessage } from '../../services/api'
import { awaitingPix, updateOrderPayment, updateOrderStatus, type Order } from '../../services/orders'
import type { OrderStatus } from '../../types'
import { useLiveOrders } from '../orders/LiveOrders'
import { useTenant } from '../tenant/TenantProvider'
import { usePlan } from '../plans/PlanProvider'
import { offerReadyWhatsapp } from '../../lib/notify'

const COLUMNS: Array<{ status: OrderStatus; title: string; next: OrderStatus; action: string }> = [
  { status: 'RECEIVED', title: 'A fazer', next: 'PREPARING', action: 'Começar' },
  { status: 'PREPARING', title: 'Preparando', next: 'READY', action: 'Pronto' },
  { status: 'READY', title: 'Prontos', next: 'FINISHED', action: 'Entregue' },
]
const WHERE: Record<string, string> = { DINE_IN: 'Mesa', TAKEAWAY: 'Retirada', DELIVERY: 'Entrega' }

/** Kitchen display (KDS): big cards, minutes since the order, one tap to move forward. Works on a TV or tablet. */
export function KitchenPage() {
  const { orders, replace, refresh, offline } = useLiveOrders()
  const { tenant } = useTenant()
  const { catalog } = usePlan()
  const [now, setNow] = useState(Date.now())
  const [busy, setBusy] = useState<string | null>(null)
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 15_000); return () => window.clearInterval(timer) }, [])

  async function advance(order: Order, next: OrderStatus) {
    setBusy(order.id)
    try {
      const updated = awaitingPix(order, Boolean(tenant.pix_key)) ? await updateOrderPayment(order.id, 'PAID') : await updateOrderStatus(order.id, next)
      replace(updated)
      if (updated.status === 'READY' && !catalog?.whatsapp_auto) offerReadyWhatsapp(updated, tenant.name.trim())
      void refresh()
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível atualizar.'))
    } finally {
      setBusy(null)
    }
  }

  const late = tenant.prep_minutes || 20
  return (
    <section className="kitchen">
      <header className="kitchen-head">
        <Link className="btn ghost" to="/painel/pedidos"><ArrowLeft size={16} /> Painel</Link>
        <h1>Cozinha {offline && <span className="badge danger">Sem conexão</span>}</h1>
        <button className="btn ghost" onClick={() => void document.documentElement.requestFullscreen?.()}><Maximize2 size={16} /> Tela cheia</button>
      </header>
      <div className="kitchen-board">
        {COLUMNS.map((column) => {
          const list = orders.filter((o) => o.status === column.status).sort((a, b) => a.created_at.localeCompare(b.created_at))
          return (
            <div className="kitchen-col" key={column.status}>
              <h2>{column.title} <span>{list.length}</span></h2>
              {list.map((order) => {
                const minutes = Math.floor((now - new Date(order.created_at).getTime()) / 60_000)
                const tone = column.status === 'READY' ? '' : minutes >= late ? 'late' : minutes >= late * 0.7 ? 'warn' : ''
                const waiting = awaitingPix(order, Boolean(tenant.pix_key))
                return (
                  <article key={order.id} className={`kitchen-card ${tone}`}>
                    <div className="kitchen-card-head">
                      <strong>#{order.order_number}</strong>
                      <span>{WHERE[order.service_type]}{order.table_label ? ` ${order.table_label}` : ''}</span>
                      <span className="kitchen-time">{minutes} min</span>
                    </div>
                    <ul>
                      {order.items.map((item) => (
                        <li key={item.id}><b>{item.quantity}×</b> {item.product_name}
                          {item.options.length > 0 && <small>{item.options.map((o) => o.name).join(' · ')}</small>}
                          {item.notes && <small className="note">» {item.notes}</small>}
                        </li>
                      ))}
                    </ul>
                    {order.notes && <p className="note">Obs.: {order.notes}</p>}
                    <button className="btn primary block" disabled={busy === order.id} onClick={() => void advance(order, column.next)}>
                      {waiting ? 'PIX recebido · começar' : column.action}
                    </button>
                  </article>
                )
              })}
            </div>
          )
        })}
      </div>
    </section>
  )
}
