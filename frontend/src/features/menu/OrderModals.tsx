import QRCode from 'qrcode'
import { Check, Copy, MessageCircle, Star } from 'lucide-react'
import { toast } from 'sonner'
import { useEffect, useState } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Skeleton } from '../../components/ui/parts'
import { formatDateTime, formatMoney, orderStatusLabels, paymentMethodLabels, serviceLabels } from '../../lib/format'
import { cancelPublicOrder, getOrderPix, reviewOrder, trackOrder, type Tracking } from '../../services/publicMenu'
import { pushSupported, subscribeOrderPush } from '../../lib/push'
import { orderProgress, type Progress } from './orderProgress'
import { beep } from '../orders/LiveOrders'
import { apiErrorMessage } from '../../services/api'
import type { OrderStatus, PublicTenant } from '../../types'

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

/** Loyalty card: stamps toward the reward ("a cada 10 pedidos, 1 grátis"). */
function LoyaltyCard({ card }: { card: NonNullable<Tracking['loyalty']> }) {
  return (
    <div className="card flat loyalty">
      <strong>{card.rewards_available > 0 ? '🎉 Você ganhou: ' + card.reward : 'Cartão fidelidade'}</strong>
      <div className="stamps">{Array.from({ length: card.goal }, (_, i) => <span key={i} className={i < card.stamps ? 'on' : ''}>{i < card.stamps ? '★' : ''}</span>)}</div>
      <small className="muted">{card.rewards_available > 0 ? 'Mostre esta tela no balcão para resgatar.' : `Faltam ${card.goal - card.stamps} pedidos para ganhar ${card.reward}.`}</small>
    </div>
  )
}

/** 1-5 stars after delivery; 5 stars invites the customer to review the store on Google. */
function ReviewBox({ token, given, googleUrl }: { token: string; given: number | null; googleUrl: string | null }) {
  const [stars, setStars] = useState(given ?? 0)
  const [comment, setComment] = useState('')
  const [sent, setSent] = useState(given !== null)
  const [google, setGoogle] = useState<string | null>(given === 5 ? googleUrl : null)
  async function send() {
    try {
      const result = await reviewOrder(token, stars, comment || undefined)
      setSent(true)
      setGoogle(result.google_review_url)
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível enviar a avaliação.'))
    }
  }
  if (sent) {
    return (
      <div className="card flat review">
        <strong>Obrigado pela avaliação!</strong>
        {google && <a className="btn primary block" href={google} target="_blank" rel="noreferrer"><Star size={16} /> Avaliar também no Google</a>}
      </div>
    )
  }
  return (
    <div className="card flat review">
      <strong>Como foi o seu pedido?</strong>
      <div className="stars" role="radiogroup" aria-label="Nota">
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} role="radio" aria-checked={stars === n} aria-label={`${n} estrela${n > 1 ? 's' : ''}`} className={n <= stars ? 'on' : ''} onClick={() => setStars(n)}>★</button>
        ))}
      </div>
      {stars > 0 && stars < 5 && <textarea rows={2} maxLength={500} placeholder="O que podemos melhorar? (opcional)" value={comment} onChange={(e) => setComment(e.target.value)} />}
      {stars > 0 && <button className="btn primary block" onClick={() => void send()}>Enviar avaliação</button>}
    </div>
  )
}

/** The moment the customer waits for: sound + vibration when the order turns ready. */
export function celebrate() {
  try { navigator.vibrate?.([250, 120, 250, 120, 400]) } catch { /* not supported */ }
  beep()
}

/** Big, glanceable status: animated icon, headline, forecast, progress bar and the time of each step. */
function StatusHero({ progress }: { progress: Progress }) {
  const icon = { wait: '🧾', cook: '👨‍🍳', ready: '🎉', done: '✅', off: '✖️' }[progress.tone]
  return (
    <div className={`status-hero tone-${progress.tone}`} role="status" aria-live="polite">
      <div className="status-hero-top">
        <span className="status-icon" aria-hidden="true">{icon}</span>
        <div>
          <h2>{progress.title}</h2>
          <p>{progress.detail}</p>
        </div>
      </div>
      {progress.tone !== 'off' && (
        <>
          <div className="status-bar"><b style={{ width: `${progress.percent}%` }} /></div>
          <ol className="status-steps">
            {progress.steps.map((step) => (
              <li key={step.label} className={step.state}>
                <span>{step.label}</span>
                <small>{step.at ? new Date(step.at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : '—'}</small>
              </li>
            ))}
          </ol>
          {(progress.tone === 'wait' || progress.tone === 'cook') && <small className="status-live"><i /> Atualiza sozinho</small>}
        </>
      )}
    </div>
  )
}


export function TrackModal({ token, tenant, isNew, onClose }: { token: string; tenant: PublicTenant; isNew: boolean; onClose: () => void }) {
  const [order, setOrder] = useState<Tracking | null>(null)
  const [missing, setMissing] = useState(false)
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 30_000); return () => window.clearInterval(timer) }, [])
  const [alerting, setAlerting] = useState(false)
  async function alertMe() {
    try {
      const state = await subscribeOrderPush(token)
      if (state === 'on') { setAlerting(true); toast.success('Pronto! Avisamos neste celular quando o pedido estiver pronto.') }
      else if (state === 'blocked') toast.error('As notificações estão bloqueadas neste navegador.')
      else toast.error('Este celular não aceita avisos pelo navegador. No iPhone, adicione o cardápio à tela de início.')
    } catch {
      toast.error('Não foi possível ativar o aviso.')
    }
  }

  useEffect(() => {
    let active = true
    let timer = 0
    const load = () => trackOrder(token)
      .then((data) => {
        if (!active) return
        setOrder((previous) => {
          if (previous && previous.status !== 'READY' && data.status === 'READY') celebrate()
          return data
        })
        if (data.status !== 'FINISHED' && data.status !== 'CANCELLED') timer = window.setTimeout(load, POLL_MS)
      })
      .catch(() => { if (active) setMissing(true) })
    void load()
    return () => { active = false; window.clearTimeout(timer) }
  }, [token])

  if (missing) return <Modal title="Pedido" onClose={onClose}><div className="empty">Pedido não encontrado.</div></Modal>
  if (!order) return <Modal title="Pedido" onClose={onClose}><Skeleton lines={5} height={20} /></Modal>

  async function cancel() {
    if (!confirmCancel) return setConfirmCancel(true)
    try {
      await cancelPublicOrder(token)
      setOrder((current) => (current ? { ...current, status: 'CANCELLED' } : current))
      toast.success('Pedido cancelado.')
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível cancelar.'))
    }
  }

  const status = order.status as OrderStatus
  const waitingPix = Boolean(tenant.pix_key) && order.payment_method === 'PIX' && order.payment_status !== 'PAID' && status === 'RECEIVED' && !order.table_label
    && ((order.service_type === 'TAKEAWAY' && tenant.require_pix_takeaway) || (order.service_type === 'DELIVERY' && tenant.require_pix_delivery))
  const progress = orderProgress(order, waitingPix, now)
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
      {order.scheduled_for && <p className="alert info">📅 Encomenda para <strong>{formatDateTime(order.scheduled_for)}</strong></p>}

      <StatusHero progress={progress} />
      {(status === 'RECEIVED' || status === 'PREPARING') && !order.table_label && (
        tenant.whatsapp_notifications
          ? <p className="muted eta">📲 Vamos avisar pelo WhatsApp quando estiver pronto.</p>
          : !alerting && pushSupported() && <button className="btn block" onClick={() => void alertMe()}>🔔 Avisar neste celular quando ficar pronto</button>
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
      {status === 'FINISHED' && <ReviewBox token={token} given={order.review_stars} googleUrl={order.google_review_url} />}
      {order.loyalty && status !== 'CANCELLED' && <LoyaltyCard card={order.loyalty} />}
      {status === 'RECEIVED' && order.payment_status !== 'PAID' && !order.table_label && (
        <button className={`btn block ${confirmCancel ? 'danger' : 'ghost'}`} onClick={() => void cancel()}>{confirmCancel ? 'Toque de novo para confirmar o cancelamento' : 'Cancelar pedido'}</button>
      )}
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
