import QRCode from 'qrcode'
import { Check, Copy, MessageCircle } from 'lucide-react'
import { toast } from 'sonner'
import { useEffect, useState } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Skeleton } from '../../components/ui/parts'
import { formatDateTime, formatMoney, orderStatusLabels, paymentMethodLabels, serviceLabels } from '../../lib/format'
import { getOrderPix, trackOrder, type Tracking } from '../../services/publicMenu'
import type { OrderStatus, PublicTenant } from '../../types'

const STEPS: OrderStatus[] = ['RECEIVED', 'PREPARING', 'READY', 'FINISHED']
const POLL_MS = 5000

/** QR Code + copia e cola with the exact total, while a PIX order is waiting for payment. */
function OrderPix({ token, tenantName }: { token: string; tenantName: string }) {
  const [pix, setPix] = useState<{ code: string; amount: string; qr: string } | null>(null)
  useEffect(() => {
    let active = true
    getOrderPix(token)
      .then(async (data) => { const qr = await QRCode.toDataURL(data.code, { margin: 1, width: 280 }); if (active) setPix({ ...data, qr }) })
      .catch(() => { if (active) setPix(null) })
    return () => { active = false }
  }, [token])
  if (!pix) return null
  return (
    <div className="card flat pix-pay">
      <h3>Pague {formatMoney(pix.amount)} com PIX</h3>
      <p className="muted">Direto para <strong>{tenantName}</strong>: abra o app do seu banco e leia o QR Code ou use o PIX copia e cola. O valor já vem preenchido.</p>
      <img className="pix-qr" src={pix.qr} alt="QR Code PIX" />
      <div className="pix-box">
        <code className="pix-code">{pix.code}</code>
        <button className="btn small" onClick={() => { void navigator.clipboard?.writeText(pix.code); toast.success('PIX copiado. Cole no app do seu banco.') }}><Copy size={14} /> Copiar</button>
      </div>
      <p className="muted"><small>O estabelecimento confere o pagamento e confirma. Esta tela atualiza sozinha.</small></p>
    </div>
  )
}

const stepHints: Record<string, string> = {
  RECEIVED: 'Recebemos seu pedido. Em instantes ele entra em preparo.',
  PREPARING: 'Estamos preparando seu pedido.',
  READY: 'Seu pedido está pronto!',
  FINISHED: 'Pedido entregue. Bom apetite!',
}

export function TrackModal({ token, tenant, isNew, onClose }: { token: string; tenant: PublicTenant; isNew: boolean; onClose: () => void }) {
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

  if (missing) return <Modal title="Pedido" onClose={onClose}><div className="empty">Pedido não encontrado.</div></Modal>
  if (!order) return <Modal title="Pedido" onClose={onClose}><Skeleton lines={5} height={20} /></Modal>

  const status = order.status as OrderStatus
  const index = STEPS.indexOf(status)
  const whatsapp = tenant.phone ? `https://wa.me/55${tenant.phone.replace(/\D/g, '')}?text=${encodeURIComponent(`Olá! Sobre o meu pedido #${order.order_number}`)}` : null

  return (
    <Modal title={`Pedido #${order.order_number}`} onClose={onClose} footer={<button className="btn block" onClick={onClose}>{isNew ? 'Voltar ao cardápio' : 'Fechar'}</button>}>
      {isNew && (
        <div className="success-hero">
          <div className="tick"><Check size={28} /></div>
          <h2>Pedido enviado!</h2>
          <p className="muted">Guarde o número <strong>#{order.order_number}</strong>. Você pode acompanhar por aqui.</p>
        </div>
      )}
      <p className="muted">
        {serviceLabels[order.service_type]}{order.table_label ? ` · Mesa ${order.table_label}` : ''} · {formatDateTime(order.created_at)}
      </p>
      {order.delivery_address && <p className="muted">Entrega em: {order.delivery_address}</p>}

      {status === 'CANCELLED' ? (
        <div className="alert error">Este pedido foi cancelado. Fale com a equipe se tiver dúvidas.</div>
      ) : (
        <>
          <ol className="track">
            {STEPS.map((step, i) => (
              <li key={step} className={i < index || status === 'FINISHED' ? 'done' : i === index ? 'current' : ''}>
                <span className="dot">{i < index || status === 'FINISHED' ? <Check size={13} /> : null}</span>
                {orderStatusLabels[step]}
              </li>
            ))}
          </ol>
          <p className="alert info">{stepHints[status]}</p>
        </>
      )}

      <div className="card flat">
        {order.items.map((item, i) => (
          <div className="detail-line" key={i}>
            <span>
              {item.quantity}× {item.product_name}
              {item.options.length > 0 && <small>{item.options.map((o) => o.name).join(' · ')}</small>}
              {item.notes && <small>“{item.notes}”</small>}
            </span>
          </div>
        ))}
        {Number(order.discount) > 0 && <div className="total-row sub discount"><span>Desconto</span><span>−{formatMoney(order.discount)}</span></div>}
        {Number(order.service_fee) > 0 && <div className="total-row sub"><span>Taxa de serviço</span><span>{formatMoney(order.service_fee)}</span></div>}
        {Number(order.delivery_fee) > 0 && <div className="total-row sub"><span>Entrega</span><span>{formatMoney(order.delivery_fee)}</span></div>}
        <div className="total-row"><span>Total</span><strong>{formatMoney(order.total)}</strong></div>
      </div>
      {order.payment_method === 'PIX' && order.payment_status !== 'PAID' && status !== 'CANCELLED' && tenant.pix_key && !order.table_label
        ? <OrderPix token={token} tenantName={tenant.name.trim()} />
        : <p className="muted">
            {order.payment_status === 'PAID' ? `✔ Pagamento confirmado (${paymentMethodLabels[order.payment_method]}).` : `Pagamento no caixa (${paymentMethodLabels[order.payment_method]}).`}
          </p>}
      {whatsapp && <a className="btn block" href={whatsapp} target="_blank" rel="noreferrer"><MessageCircle size={16} /> Falar com o estabelecimento</a>}
    </Modal>
  )
}

export function OrdersModal({ tokens, onClose, onOpen }: { tokens: string[]; onClose: () => void; onOpen: (token: string) => void }) {
  const [orders, setOrders] = useState<Array<{ token: string; data: Tracking }>>([])
  const [loading, setLoading] = useState(tokens.length > 0)

  useEffect(() => {
    Promise.all(tokens.map((token) => trackOrder(token).then((data) => ({ token, data })).catch(() => null)))
      .then((results) => setOrders(results.filter((r): r is { token: string; data: Tracking } => r !== null)))
      .finally(() => setLoading(false))
  }, [tokens])

  return (
    <Modal title="Meus pedidos" onClose={onClose}>
      {loading && <Skeleton lines={3} height={52} />}
      {!loading && orders.length === 0 && <div className="empty">Você ainda não fez pedidos neste aparelho.</div>}
      {orders.map(({ token, data }) => (
        <button className="order-row" key={token} onClick={() => onOpen(token)}>
          <div>
            <strong>Pedido #{data.order_number}</strong>
            <small>{formatDateTime(data.created_at)} · {data.items.length} {data.items.length === 1 ? 'item' : 'itens'}</small>
          </div>
          <div className="order-row-end">
            <span className={`badge status-${data.status.toLowerCase()}`}>{orderStatusLabels[data.status as OrderStatus]}</span>
            <strong>{formatMoney(data.total)}</strong>
          </div>
        </button>
      ))}
    </Modal>
  )
}
