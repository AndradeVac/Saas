import { ArrowLeft, Pencil, Printer } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { useConfirm } from '../../components/ui/Confirm'
import { Modal } from '../../components/ui/Modal'
import { ErrorBanner, Skeleton } from '../../components/ui/parts'
import {
  formatDateTime, formatMoney, formatPhone, formatTime, orderStatusLabels, paymentMethodLabels, serviceLabels,
} from '../../lib/format'
import { apiErrorMessage } from '../../services/api'
import { editOrder, getOrder, updateOrderPayment, updateOrderStatus, type Order } from '../../services/orders'
import type { OrderStatus } from '../../types'
import { useTenant } from '../tenant/TenantProvider'
import { useLiveOrders } from './LiveOrders'

const FLOW: OrderStatus[] = ['RECEIVED', 'PREPARING', 'READY', 'FINISHED']

export function OrderDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const confirm = useConfirm()
  const { tenant } = useTenant()
  const { refresh } = useLiveOrders()
  const [order, setOrder] = useState<Order | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState({ table_label: '', notes: '', delivery_address: '' })

  useEffect(() => {
    if (id) getOrder(id).then(setOrder).catch(() => setError('Pedido não encontrado.'))
  }, [id])

  async function run(action: () => Promise<Order>, success?: string) {
    setBusy(true)
    setError('')
    try {
      setOrder(await action())
      if (success) toast.success(success)
      void refresh()
    } catch (err) {
      setError(apiErrorMessage(err, 'Não foi possível atualizar o pedido.'))
    } finally {
      setBusy(false)
    }
  }

  if (!order) {
    return (
      <section className="page narrow">
        <button className="btn ghost small back-link" onClick={() => navigate('/painel/pedidos')}><ArrowLeft size={14} /> Voltar</button>
        {error ? <ErrorBanner message={error} /> : <Skeleton lines={6} height={22} />}
      </section>
    )
  }

  const next = FLOW[FLOW.indexOf(order.status) + 1]
  const closed = order.status === 'FINISHED' || order.status === 'CANCELLED'
  const cancellation = order.status_history.find((h) => h.status === 'CANCELLED')

  async function cancel() {
    const result = await confirm({
      title: `Cancelar pedido #${order!.order_number}?`,
      message: 'O cliente verá o pedido como cancelado. Essa ação não pode ser desfeita.',
      confirmLabel: 'Cancelar pedido',
      danger: true,
      reason: { label: 'Motivo do cancelamento', required: true },
    })
    if (result.ok) await run(() => updateOrderStatus(order!.id, 'CANCELLED', result.reason), 'Pedido cancelado')
  }

  function openEdit() {
    setDraft({ table_label: order!.table_label ?? '', notes: order!.notes ?? '', delivery_address: order!.delivery_address ?? '' })
    setEditing(true)
  }

  async function saveEdit() {
    setEditing(false)
    await run(() => editOrder(order!.id, {
      table_label: order!.service_type === 'DINE_IN' ? draft.table_label || null : undefined,
      delivery_address: order!.service_type === 'DELIVERY' ? draft.delivery_address || null : undefined,
      notes: draft.notes || null,
    }), 'Pedido atualizado')
  }

  return (
    <section className="page narrow">
      <button className="btn ghost small back-link no-print" onClick={() => navigate('/painel/pedidos')}><ArrowLeft size={14} /> Voltar</button>
      <div className="page-head">
        <div>
          <h1>Pedido #{order.order_number} <span className={`badge status-${order.status.toLowerCase()}`}>{orderStatusLabels[order.status]}</span></h1>
          <p className="muted">
            {formatDateTime(order.created_at)} · {serviceLabels[order.service_type]}{order.table_label ? ` · Mesa ${order.table_label}` : ''}
          </p>
        </div>
        <div className="page-actions no-print">
          {!closed && <button className="btn" onClick={openEdit}><Pencil size={15} /> Editar</button>}
          <button className="btn" onClick={() => window.print()}><Printer size={15} /> Imprimir</button>
        </div>
      </div>
      <ErrorBanner message={error} />

      <div className="card">
        <h3>{order.customer_name}</h3>
        {order.customer_phone && <p className="muted"><a href={`https://wa.me/55${order.customer_phone.replace(/\D/g, '')}`} target="_blank" rel="noreferrer">{formatPhone(order.customer_phone)}</a></p>}
        {order.delivery_address && <p><strong>Entrega:</strong> {order.delivery_address}</p>}
        {order.items.map((item) => (
          <div className="detail-line" key={item.id}>
            <span>
              {item.quantity}× {item.product_name}
              {item.options.length > 0 && <small>{item.options.map((o) => o.name).join(' · ')}</small>}
              {item.notes && <small>“{item.notes}”</small>}
            </span>
            <b>{formatMoney(item.total_price)}</b>
          </div>
        ))}
        {order.notes && <p className="alert warn">Obs.: {order.notes}</p>}
        <div className="total-row sub"><span>Subtotal</span><span>{formatMoney(order.subtotal)}</span></div>
        {Number(order.discount) > 0 && <div className="total-row sub discount"><span>Desconto {order.coupon_code && `(${order.coupon_code})`}</span><span>−{formatMoney(order.discount)}</span></div>}
        {Number(order.service_fee) > 0 && <div className="total-row sub"><span>Taxa de serviço</span><span>{formatMoney(order.service_fee)}</span></div>}
        {Number(order.delivery_fee) > 0 && <div className="total-row sub"><span>Entrega</span><span>{formatMoney(order.delivery_fee)}</span></div>}
        <div className="total-row"><span>Total</span><strong>{formatMoney(order.total)}</strong></div>
      </div>

      <div className="card no-print">
        <div className="row between">
          <div>
            <h3>Pagamento</h3>
            <p className="muted" style={{ margin: 0 }}>
              {paymentMethodLabels[order.payment_method]} ·{' '}
              <span className={`badge ${order.payment_status === 'PAID' ? 'ok' : 'warn'}`}>{order.payment_status === 'PAID' ? `Pago às ${formatTime(order.paid_at)}` : 'Pendente'}</span>
            </p>
          </div>
          {order.status !== 'CANCELLED' && (
            order.payment_status === 'PAID'
              ? <button className="btn" disabled={busy} onClick={() => void run(() => updateOrderPayment(order.id, 'PENDING'))}>Desfazer pagamento</button>
              : <button className="btn primary" disabled={busy} onClick={() => void run(() => updateOrderPayment(order.id, 'PAID'), 'Pagamento confirmado')}>Confirmar pagamento recebido</button>
          )}
        </div>
      </div>

      {cancellation?.reason && <div className="alert error">Cancelado: {cancellation.reason}</div>}
      {!closed && (
        <div className="actions no-print">
          {next && <button className="btn primary large" disabled={busy} onClick={() => void run(() => updateOrderStatus(order.id, next))}>Avançar para “{orderStatusLabels[next]}”</button>}
          <button className="btn danger" disabled={busy} onClick={() => void cancel()}>Cancelar pedido</button>
        </div>
      )}

      <div className="card no-print">
        <h3>Histórico</h3>
        <ul className="history-list">
          {order.status_history.map((h, i) => (
            <li key={i}><span>{orderStatusLabels[h.status]}{h.reason ? ` — ${h.reason}` : ''}</span><span className="muted">{formatTime(h.created_at)}</span></li>
          ))}
        </ul>
      </div>

      <div className="print-only ticket">
        <h2>{tenant.name}</h2>
        <hr />
        <div className="t-row"><strong>Pedido #{order.order_number}</strong><span>{formatDateTime(order.created_at)}</span></div>
        <div>{serviceLabels[order.service_type]}{order.table_label ? ` — Mesa ${order.table_label}` : ''}</div>
        <div>{order.customer_name} {order.customer_phone ? formatPhone(order.customer_phone) : ''}</div>
        {order.delivery_address && <div>Entrega: {order.delivery_address}</div>}
        <hr />
        {order.items.map((item) => (
          <div key={item.id}>
            <div className="t-row"><span>{item.quantity}x {item.product_name}</span><span>{formatMoney(item.total_price)}</span></div>
            {item.options.length > 0 && <div>  + {item.options.map((o) => o.name).join(', ')}</div>}
            {item.notes && <div>  Obs: {item.notes}</div>}
          </div>
        ))}
        <hr />
        {order.notes && <div>Obs: {order.notes}</div>}
        <div className="t-row"><strong>TOTAL</strong><strong>{formatMoney(order.total)}</strong></div>
        <div>Pagamento: {paymentMethodLabels[order.payment_method]} ({order.payment_status === 'PAID' ? 'pago' : 'pendente'})</div>
      </div>

      {editing && (
        <Modal
          title="Editar pedido"
          size="sm"
          onClose={() => setEditing(false)}
          footer={<><button className="btn" onClick={() => setEditing(false)}>Cancelar</button><button className="btn primary" onClick={() => void saveEdit()}>Salvar</button></>}
        >
          {order.service_type === 'DINE_IN' && <label className="field"><span>Mesa</span><input value={draft.table_label} onChange={(e) => setDraft({ ...draft, table_label: e.target.value })} maxLength={30} /></label>}
          {order.service_type === 'DELIVERY' && <label className="field"><span>Endereço de entrega</span><textarea rows={2} value={draft.delivery_address} onChange={(e) => setDraft({ ...draft, delivery_address: e.target.value })} /></label>}
          <label className="field"><span>Observações</span><textarea rows={3} maxLength={500} value={draft.notes} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} /></label>
        </Modal>
      )}
    </section>
  )
}
