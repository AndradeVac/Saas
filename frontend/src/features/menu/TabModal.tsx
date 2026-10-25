import { Check, Copy, Minus, Plus, QrCode, Receipt, Repeat2, ShoppingBag, Users } from 'lucide-react'
import QRCode from 'qrcode'
import { useState } from 'react'
import { toast } from 'sonner'
import { Modal } from '../../components/ui/Modal'
import { formatMoney, formatTime, orderStatusLabels, paymentMethodLabels } from '../../lib/format'
import { apiErrorMessage } from '../../services/api'
import { readJson } from '../../lib/storage'
import { callWaiter, getTabPix, reportTabPix, requestTabClose, setTabServiceFee, tabStatusLabels, WAITER_REASONS, type PublicTab, type TabOrder } from '../../services/tabs'
import type { OrderStatus, PaymentMethod, PublicTenant } from '../../types'

type Props = {
  tab: PublicTab
  tenant: PublicTenant
  /** Order just placed, highlighted at the top. */
  highlight?: number
  onClose: () => void
  onOrderMore: () => void
  onRepeat: (order: TabOrder) => void
  onUpdated: (tab: PublicTab) => void
}

export function TabModal({ tab, tenant, highlight, onClose, onOrderMore, onRepeat, onUpdated }: Props) {
  const [view, setView] = useState<'bill' | 'close' | 'pix'>('bill')
  const [pix, setPix] = useState<{ code: string; amount: string } | null>(null)
  const [qr, setQr] = useState('')
  const [reported, setReported] = useState(false)
  const [payment, setPayment] = useState<PaymentMethod>(tab.requested_payment_method ?? tenant.accepted_payments[0])
  const [split, setSplit] = useState(tab.split_count ?? 1)
  const [mine, setMine] = useState<Set<string>>(new Set())
  const [calling, setCalling] = useState(false)
  async function call(reason: string) {
    try {
      onUpdated(await callWaiter(tab.public_token, reason))
      setCalling(false)
      toast.success('Pronto! A equipe já foi avisada.')
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível chamar o garçom.'))
    }
  }
  const [sending, setSending] = useState(false)

  const live = tab.orders.filter((order) => order.status !== 'CANCELLED')
  const last = live[live.length - 1]
  const total = Number(tab.totals.total)
  const canOrder = tab.status === 'OPEN' || tab.status === 'CLOSING' || tab.status === 'PENDING'
  const pixAvailable = Boolean(tenant.pix_key) && tenant.accepted_payments.includes('PIX')

  const feeRate = Number(tenant.service_fee_percent)
  async function toggleFee() {
    try {
      onUpdated(await setTabServiceFee(tab.public_token, !tab.service_fee_waived))
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível alterar a taxa de serviço.'))
    }
  }
  // The service fee is optional by law (a tip): the table decides.
  const feeLine = feeRate > 0 && live.length > 0 && (
    <div className="total-row sub fee-toggle">
      <span>
        Taxa de serviço ({feeRate}%, opcional){' '}
        {(tab.status === 'OPEN' || tab.status === 'CLOSING' || tab.status === 'PENDING') && (
          <button className="link-btn" onClick={() => void toggleFee()}>{tab.service_fee_waived ? 'incluir' : 'retirar'}</button>
        )}
      </span>
      <span>{tab.service_fee_waived ? 'Sem taxa' : formatMoney(tab.totals.service_fee)}</span>
    </div>
  )

  async function startPix(amount: number) {
    setSending(true)
    try {
      const code = await getTabPix(tab.public_token, amount.toFixed(2))
      setPix(code)
      setQr(await QRCode.toDataURL(code.code, { margin: 1, width: 280 }))
      setReported(false)
      setView('pix')
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível gerar o PIX.'))
    } finally {
      setSending(false)
    }
  }

  async function sayPaid() {
    if (!pix) return
    setSending(true)
    try {
      const payer = readJson<{ name?: string }>(`mesa:${tenant.slug}:customer`, {}).name
      onUpdated(await reportTabPix(tab.public_token, pix.amount, payer))
      setReported(true)
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível avisar o garçom.'))
    } finally {
      setSending(false)
    }
  }

  async function askForBill() {
    setSending(true)
    try {
      const updated = await requestTabClose(tab.public_token, payment, split > 1 ? split : null)
      onUpdated(updated)
      setView('bill')
      toast.success('Conta pedida! O garçom já foi avisado.')
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível pedir a conta.'))
    } finally {
      setSending(false)
    }
  }

  if (view === 'pix' && pix) {
    return (
      <Modal
        title="Pagar com PIX"
        onClose={() => setView('close')}
        footer={
          reported ? (
            <button className="btn primary large block" onClick={() => { setView('bill'); setPix(null); setReported(false) }}>Voltar para a conta</button>
          ) : (
            <button className="btn primary large block" disabled={sending} onClick={() => void sayPaid()}>
              <Check size={18} /> {sending ? 'Avisando…' : 'Já paguei'}
            </button>
          )
        }
      >
        {reported ? (
          <div className="success-hero">
            <div className="tick"><Check size={28} /></div>
            <h2>Pagamento enviado!</h2>
            <p className="muted">Avisamos o garçom. Ele confere o PIX de <strong>{formatMoney(pix.amount)}</strong> e confirma em instantes.</p>
          </div>
        ) : (
          <>
            <p className="muted">Pague <strong>{formatMoney(pix.amount)}</strong> direto para <strong>{tenant.name}</strong>: abra o app do seu banco e use o QR Code ou o PIX copia e cola.</p>
            {qr && <img className="pix-qr" src={qr} alt="QR Code PIX" />}
            <div className="pix-box">
              <code className="pix-code">{pix.code}</code>
              <button className="btn small" onClick={() => { void navigator.clipboard?.writeText(pix.code); toast.success('PIX copiado. Cole no app do seu banco.') }}><Copy size={14} /> Copiar</button>
            </div>
            <p className="muted"><small>Depois de pagar, toque em “Já paguei” para avisar o garçom.</small></p>
          </>
        )}
      </Modal>
    )
  }

  if (view === 'close') {
    const remaining = Number(tab.totals.remaining)
    const share = split > 1 ? Math.ceil((remaining / split) * 100) / 100 : remaining
    return (
      <Modal title="Fechar a conta" onClose={() => setView('bill')} footer={<button className="btn large block" onClick={() => setView('bill')}>Voltar</button>}>
        <div className="card flat">
          {feeLine}
          <div className="total-row sub"><span>Total da mesa</span><span>{formatMoney(total)}</span></div>
          {Number(tab.totals.paid) > 0 && <div className="total-row sub"><span>Já pago</span><span>−{formatMoney(tab.totals.paid)}</span></div>}
          <div className="total-row"><span>Falta pagar</span><strong>{formatMoney(remaining)}</strong></div>
        </div>

        <h4>Dividir a conta</h4>
        <div className="split-row">
          <span><Users size={16} /> Pessoas</span>
          <div className="stepper">
            <button onClick={() => setSplit((n) => Math.max(1, n - 1))} aria-label="Menos pessoas" disabled={split <= 1}><Minus size={14} /></button>
            <span>{split}</span>
            <button onClick={() => setSplit((n) => Math.min(20, n + 1))} aria-label="Mais pessoas" disabled={split >= 20}><Plus size={14} /></button>
          </div>
        </div>

        {pixAvailable && remaining > 0 && live.length > 0 && (() => {
          // "Pagar só o que eu consumi": the chosen items plus their share of fee and discounts.
          const items = live.flatMap((order) => order.items.map((item, index) => ({ key: `${order.id}:${index}`, item })))
          const chosen = items.filter((x) => mine.has(x.key)).reduce((sum, x) => sum + Number(x.item.total_price), 0)
          const subtotal = Number(tab.totals.subtotal) || 1
          const myShare = Math.min(remaining, Math.round((chosen / subtotal) * total * 100) / 100)
          return (
            <details className="by-item">
              <summary>Pagar só o que eu consumi</summary>
              <ul>
                {items.map(({ key, item }) => (
                  <li key={key}>
                    <label className="check-line">
                      <input type="checkbox" checked={mine.has(key)} onChange={(e) => setMine((current) => { const next = new Set(current); if (e.target.checked) next.add(key); else next.delete(key); return next })} />
                      <span>{item.quantity}× {item.product_name}</span>
                      <strong>{formatMoney(item.total_price)}</strong>
                    </label>
                  </li>
                ))}
              </ul>
              <button className="btn primary block" disabled={sending || myShare <= 0} onClick={() => void startPix(myShare)}>
                {myShare > 0 ? `Pagar minha parte · ${formatMoney(myShare)}` : 'Marque o que você consumiu'}
              </button>
              {myShare > 0 && Number(tab.totals.service_fee) > 0 && <small className="muted">Inclui a taxa de serviço proporcional.</small>}
            </details>
          )
        })()}

        {pixAvailable && remaining > 0 && (
          <div className="pay-now">
            <strong><QrCode size={18} /> Pagar agora pelo PIX</strong>
            <span className="muted">Na hora, sem esperar o garçom. O dinheiro vai direto para {tenant.name}.</span>
            <div className="pay-now-actions">
              {split > 1 && <button className="btn primary" disabled={sending} onClick={() => void startPix(share)}>Minha parte · {formatMoney(share)}</button>}
              <button className={`btn ${split > 1 ? '' : 'primary'}`} disabled={sending} onClick={() => void startPix(remaining)}>Conta inteira · {formatMoney(remaining)}</button>
            </div>
          </div>
        )}

        <h4>{pixAvailable ? 'Ou chame o garçom' : 'Chamar o garçom'}</h4>
        <div className="pay-grid">
          {tenant.accepted_payments.map((method) => (
            <button key={method} className={`pay-option ${payment === method ? 'active' : ''}`} onClick={() => setPayment(method)}>{paymentMethodLabels[method]}</button>
          ))}
        </div>
        <button className="btn large block" disabled={sending} onClick={() => void askForBill()}>
          <Receipt size={18} /> {sending ? 'Enviando…' : `Pedir a conta (${paymentMethodLabels[payment]})`}
        </button>
      </Modal>
    )
  }

  return (
    <Modal
      title={`Mesa ${tab.table_label}`}
      onClose={onClose}
      footer={
        <div className="tab-actions">
          {canOrder && <button className="btn primary large" onClick={onOrderMore}><ShoppingBag size={18} /> Pedir mais</button>}
          {canOrder && last && <button className="btn large" onClick={() => onRepeat(last)}><Repeat2 size={18} /> Repetir a última rodada</button>}
          {(tab.status === 'OPEN' || tab.status === 'CLOSING') && live.length > 0 && (
            <button className="btn large ghost" onClick={() => setView('close')}><Receipt size={18} /> {tab.status === 'CLOSING' ? 'Alterar pagamento' : 'Fechar a conta'}</button>
          )}
        </div>
      }
    >
      <div className="tab-head">
        <span className={`badge tab-${tab.status.toLowerCase()}`}>{tabStatusLabels[tab.status]}</span>
        <span className="muted">Comanda #{tab.number}</span>
      </div>

      {(tab.status === 'OPEN' || tab.status === 'CLOSING' || tab.status === 'PENDING') && (
        tab.waiter_call
          ? <div className="alert ok waiter-called"><span>🙋 Chamado enviado: <strong>{WAITER_REASONS[tab.waiter_call]}</strong>. Já estamos indo!</span></div>
          : calling
            ? (
              <div className="waiter-options">
                {Object.entries(WAITER_REASONS).map(([key, text]) => <button key={key} className="btn" onClick={() => void call(key)}>{text}</button>)}
                <button className="btn ghost" onClick={() => setCalling(false)}>Cancelar</button>
              </div>
            )
            : <button className="btn block waiter-btn" onClick={() => setCalling(true)}>🙋 Chamar o garçom</button>
      )}

      {tab.status === 'PENDING' && (
        <div className="alert info">O garçom vai confirmar a sua mesa em instantes. Depois disso o pedido segue para a cozinha.</div>
      )}
      {tab.status === 'CLOSING' && (
        <div className="alert ok">
          <span>
            Conta pedida: <strong>{tab.requested_payment_method ? paymentMethodLabels[tab.requested_payment_method] : ''}</strong>
            {tab.split_count && tab.split_count > 1 && tab.totals.per_person && <> · {tab.split_count} pessoas, {formatMoney(tab.totals.per_person)} cada</>}
            . O garçom está a caminho.
          </span>
        </div>
      )}
      {tab.status === 'CLOSING' && tab.requested_payment_method === 'PIX' && tenant.pix_key && (
        <div className="pix-box">
          <div><small className="muted">Chave PIX</small><br /><code>{tenant.pix_key}</code></div>
          <button className="btn small" onClick={() => { void navigator.clipboard?.writeText(tenant.pix_key ?? ''); toast.success('Chave PIX copiada') }}><Copy size={14} /> Copiar</button>
        </div>
      )}
      {tab.status === 'CLOSED' && <div className="alert ok">Conta fechada. Obrigado pela visita! 💛</div>}

      <div className="tab-orders">
        {[...tab.orders].reverse().map((order) => (
          <div key={order.id} className={`tab-order ${order.order_number === highlight ? 'new' : ''} ${order.status === 'CANCELLED' ? 'off' : ''}`}>
            <div className="tab-order-head">
              <strong>Pedido #{order.order_number}</strong>
              <span className={`badge status-${order.status.toLowerCase()}`}>{orderStatusLabels[order.status as OrderStatus]}</span>
            </div>
            <small className="muted">{formatTime(order.created_at)}{order.customer_name ? ` · ${order.customer_name}` : ''}</small>
            <ul>
              {order.items.map((item, i) => (
                <li key={i}>
                  {item.quantity}× {item.product_name}
                  {item.options.length > 0 && <small className="muted"> · {item.options.map((o) => o.name).join(', ')}</small>}
                </li>
              ))}
            </ul>
            <span className="tab-order-total">{formatMoney(order.total)}</span>
          </div>
        ))}
      </div>

      <div className="card flat">
        <div className="total-row sub"><span>Consumo</span><span>{formatMoney(tab.totals.subtotal)}</span></div>
        {Number(tab.totals.discount) > 0 && <div className="total-row sub discount"><span>Descontos</span><span>−{formatMoney(tab.totals.discount)}</span></div>}
        {feeLine}
        <div className="total-row"><span>Total da mesa</span><strong>{formatMoney(tab.totals.total)}</strong></div>
        {Number(tab.totals.paid) > 0 && <div className="total-row sub"><span>Já pago</span><span>{formatMoney(tab.totals.paid)}</span></div>}
        {Number(tab.totals.reported) > 0 && <div className="total-row sub"><span>PIX aguardando o garçom confirmar</span><span>{formatMoney(tab.totals.reported)}</span></div>}
        {Number(tab.totals.paid) > 0 && <div className="total-row"><span>Falta pagar</span><strong>{formatMoney(tab.totals.remaining)}</strong></div>}
      </div>
    </Modal>
  )
}
