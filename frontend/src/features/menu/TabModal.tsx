import { Copy, Minus, Plus, Receipt, Repeat2, ShoppingBag, Users } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { Modal } from '../../components/ui/Modal'
import { formatMoney, formatTime, orderStatusLabels, paymentMethodLabels } from '../../lib/format'
import { apiErrorMessage } from '../../services/api'
import { requestTabClose, tabStatusLabels, type PublicTab, type TabOrder } from '../../services/tabs'
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
  const [view, setView] = useState<'bill' | 'close'>('bill')
  const [payment, setPayment] = useState<PaymentMethod>(tab.requested_payment_method ?? tenant.accepted_payments[0])
  const [split, setSplit] = useState(tab.split_count ?? 1)
  const [sending, setSending] = useState(false)

  const live = tab.orders.filter((order) => order.status !== 'CANCELLED')
  const last = live[live.length - 1]
  const total = Number(tab.totals.total)
  const canOrder = tab.status === 'OPEN' || tab.status === 'CLOSING' || tab.status === 'PENDING'

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

  if (view === 'close') {
    return (
      <Modal
        title="Fechar a conta"
        onClose={() => setView('bill')}
        footer={
          <div className="stack" style={{ width: '100%' }}>
            <div className="total-row" style={{ padding: 0 }}>
              <span>{split > 1 ? `Cada um paga (${split})` : 'Total'}</span>
              <strong>{formatMoney(split > 1 ? total / split : total)}</strong>
            </div>
            <button className="btn primary large block" disabled={sending} onClick={() => void askForBill()}>
              <Receipt size={18} /> {sending ? 'Enviando…' : 'Pedir a conta'}
            </button>
          </div>
        }
      >
        <p className="muted">O garçom recebe o aviso na hora e vem até a sua mesa.</p>
        <h4>Como vocês vão pagar?</h4>
        <div className="pay-grid">
          {tenant.accepted_payments.map((method) => (
            <button key={method} className={`pay-option ${payment === method ? 'active' : ''}`} onClick={() => setPayment(method)}>{paymentMethodLabels[method]}</button>
          ))}
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
        <div className="card flat">
          <div className="total-row sub"><span>Total da mesa</span><span>{formatMoney(total)}</span></div>
          {split > 1 && <div className="total-row sub"><span>Por pessoa</span><strong>{formatMoney(total / split)}</strong></div>}
        </div>
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
        {Number(tab.totals.service_fee) > 0 && <div className="total-row sub"><span>Taxa de serviço</span><span>{formatMoney(tab.totals.service_fee)}</span></div>}
        <div className="total-row"><span>Total da mesa</span><strong>{formatMoney(tab.totals.total)}</strong></div>
      </div>
    </Modal>
  )
}
