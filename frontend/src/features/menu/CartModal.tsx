import { Copy, Minus, Plus, Tag, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from 'react'
import { toast } from 'sonner'
import { Modal } from '../../components/ui/Modal'
import { formatMoney, maskPhone, paymentMethodLabels, serviceLabels } from '../../lib/format'
import { readJson, writeJson } from '../../lib/storage'
import { apiErrorMessage } from '../../services/api'
import { checkCoupon, createPublicOrder } from '../../services/publicMenu'
import type { PaymentMethod, PublicTenant, ServiceType } from '../../types'
import { cartSubtotal, type CartLine } from './cart'

type Props = {
  tenant: PublicTenant
  lines: CartLine[]
  setLines: Dispatch<SetStateAction<CartLine[]>>
  tableFromQr: string
  onClose: () => void
  onOrdered: (order: { token: string; tabToken: string | null; number: number }) => void
}

export function CartModal({ tenant, lines, setLines, tableFromQr, onClose, onOrdered }: Props) {
  const customerKey = `mesa:${tenant.slug}:customer`
  const saved = useMemo(() => readJson<{ name?: string; phone?: string }>(customerKey, {}), [customerKey])
  const services = tenant.enabled_services
  const payments = tenant.accepted_payments

  const [name, setName] = useState(saved.name ?? '')
  const [phone, setPhone] = useState(saved.phone ? maskPhone(saved.phone) : '')
  const [service, setService] = useState<ServiceType>(tableFromQr && services.includes('DINE_IN') ? 'DINE_IN' : services[0])
  const [table, setTable] = useState(tableFromQr)
  const [address, setAddress] = useState('')
  const [payment, setPayment] = useState<PaymentMethod>(payments[0])
  const [notes, setNotes] = useState('')
  const [couponInput, setCouponInput] = useState('')
  const [coupon, setCoupon] = useState<{ code: string; discount: number } | null>(null)
  const [couponError, setCouponError] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')

  const subtotal = cartSubtotal(lines)
  const discount = coupon ? Math.min(coupon.discount, subtotal) : 0
  const serviceFee = service === 'DINE_IN' ? ((subtotal - discount) * Number(tenant.service_fee_percent)) / 100 : 0
  const deliveryFee = service === 'DELIVERY' ? Number(tenant.delivery_fee) : 0
  const total = subtotal - discount + serviceFee + deliveryFee
  // Comanda: dine-in orders go to the table's bill; payment and the minimum order are settled at the end.
  const onTab = tenant.tabs_enabled && service === 'DINE_IN'
  const minOrder = onTab ? 0 : Number(tenant.min_order_value)
  const belowMinimum = subtotal < minOrder

  // The discount depends on the subtotal: re-check the applied coupon whenever the cart changes.
  useEffect(() => {
    if (!coupon) return
    let active = true
    checkCoupon(coupon.code, subtotal)
      .then((result) => { if (active) setCoupon({ code: result.code, discount: Number(result.discount) }) })
      .catch((err) => {
        if (!active) return
        setCoupon(null)
        setCouponError(apiErrorMessage(err, 'O cupom não vale mais para este pedido.'))
      })
    return () => { active = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subtotal])

  async function applyCoupon() {
    setCouponError('')
    try {
      const result = await checkCoupon(couponInput, subtotal)
      setCoupon({ code: result.code, discount: Number(result.discount) })
      setCouponInput('')
    } catch (err) {
      setCouponError(apiErrorMessage(err, 'Cupom inválido.'))
    }
  }

  function change(key: string, delta: number) {
    setLines((current) => current
      .map((line) => (line.key === key ? { ...line, quantity: Math.min(20, line.quantity + delta) } : line))
      .filter((line) => line.quantity > 0))
  }

  async function submit() {
    setError('')
    if (name.trim().length < 2) return setError('Informe seu nome.')
    if (phone.replace(/\D/g, '').length < 10) return setError('Informe um telefone com DDD.')
    if (service === 'DINE_IN' && !table.trim()) return setError('Informe o número da mesa.')
    if (service === 'DELIVERY' && address.trim().length < 6) return setError('Informe o endereço de entrega.')
    if (belowMinimum) return setError(`O pedido mínimo é de ${formatMoney(minOrder)}.`)
    setSending(true)
    try {
      const order = await createPublicOrder({
        customer_name: name,
        customer_phone: phone,
        service_type: service,
        table_label: service === 'DINE_IN' ? table : undefined,
        delivery_address: service === 'DELIVERY' ? address : undefined,
        payment_method: onTab ? 'TAB' : payment,
        notes: notes || undefined,
        coupon_code: coupon?.code,
        items: lines.map((line) => ({
          product_id: line.productId,
          quantity: line.quantity,
          notes: line.notes,
          options: line.options.map(({ group_id, option_id }) => ({ group_id, option_id })),
        })),
      })
      writeJson(customerKey, { name, phone })
      onOrdered({ token: order.public_token, tabToken: order.tab_token, number: order.order_number })
    } catch (err) {
      const message = apiErrorMessage(err, 'Não foi possível enviar o pedido. Tente novamente.')
      setError(message)
      toast.error(message)
    } finally {
      setSending(false)
    }
  }

  return (
    <Modal
      title="Seu pedido"
      onClose={onClose}
      footer={
        <div className="stack" style={{ width: '100%' }}>
          <div className="total-row" style={{ padding: 0 }}><span>Total</span><strong>{formatMoney(total)}</strong></div>
          <button className="btn primary large block" disabled={sending || lines.length === 0} onClick={() => void submit()}>
            {sending ? 'Enviando…' : onTab && table.trim() ? `Enviar para a mesa ${table.trim()}` : 'Enviar pedido'}
          </button>
        </div>
      }
    >
      {lines.length === 0 && <div className="empty">Seu pedido está vazio.</div>}
      {lines.map((line) => (
        <div className="cart-line" key={line.key}>
          <div className="cart-line-main">
            <strong>{line.name}</strong>
            {line.options.length > 0 && <span className="cart-line-opts">{line.options.map((o) => o.label).join(' · ')}</span>}
            {line.notes && <span className="cart-line-opts">“{line.notes}”</span>}
            <span>{formatMoney(line.unitPrice * line.quantity)}</span>
          </div>
          <div className="cart-line-end">
            <div className="stepper">
              <button onClick={() => change(line.key, -1)} aria-label="Diminuir">{line.quantity === 1 ? <Trash2 size={14} /> : <Minus size={14} />}</button>
              <span>{line.quantity}</span>
              <button onClick={() => change(line.key, 1)} aria-label="Aumentar" disabled={line.quantity >= 20}><Plus size={14} /></button>
            </div>
          </div>
        </div>
      ))}

      <h4>Como você quer receber?</h4>
      <div className="segmented choice" role="radiogroup" aria-label="Tipo de atendimento">
        {services.map((type) => (
          <button key={type} className={service === type ? 'active' : ''} onClick={() => setService(type)} role="radio" aria-checked={service === type}>
            {serviceLabels[type]}
          </button>
        ))}
      </div>
      {service === 'DINE_IN' && (
        <label className="field" style={{ marginTop: 12 }}>
          <span>Mesa</span>
          {/* The QR Code already says which table: on a tab, it cannot be changed to someone else's. */}
          <input value={table} onChange={(e) => setTable(e.target.value)} maxLength={30} readOnly={onTab && Boolean(tableFromQr)} />
        </label>
      )}
      {service === 'DELIVERY' && (
        <label className="field" style={{ marginTop: 12 }}>
          <span>Endereço de entrega</span>
          <textarea rows={2} maxLength={300} placeholder="Rua, número, bairro e complemento" value={address} onChange={(e) => setAddress(e.target.value)} />
        </label>
      )}

      <h4>Seus dados</h4>
      <div className="grid-2">
        <label className="field"><span>Nome</span><input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></label>
        <label className="field"><span>Telefone com DDD</span><input value={phone} onChange={(e) => setPhone(maskPhone(e.target.value))} autoComplete="tel" inputMode="tel" placeholder="(11) 99999-9999" /></label>
      </div>

      {onTab ? (
        <div className="alert info tab-hint">
          <span><strong>Comanda aberta:</strong> peça quantas vezes quiser. Você paga tudo de uma vez quando fechar a conta.</span>
        </div>
      ) : (<>
      <h4>Pagamento (no caixa)</h4>
      <div className="pay-grid">
        {payments.map((method) => (
          <button key={method} className={`pay-option ${payment === method ? 'active' : ''}`} onClick={() => setPayment(method)}>{paymentMethodLabels[method]}</button>
        ))}
      </div>
      {payment === 'PIX' && tenant.pix_key && (
        <div className="pix-box">
          <div><small className="muted">Chave PIX</small><br /><code>{tenant.pix_key}</code></div>
          <button className="btn small" onClick={() => { void navigator.clipboard?.writeText(tenant.pix_key ?? ''); toast.success('Chave PIX copiada') }}><Copy size={14} /> Copiar</button>
        </div>
      )}
      </>)}

      <h4>Cupom de desconto</h4>
      {coupon ? (
        <div className="alert ok"><span><Tag size={14} style={{ verticalAlign: -2 }} /> <strong>{coupon.code}</strong> aplicado: −{formatMoney(discount)}</span><button className="btn small" onClick={() => setCoupon(null)}>Remover</button></div>
      ) : (
        <>
          <div className="coupon-row">
            <input value={couponInput} onChange={(e) => setCouponInput(e.target.value)} placeholder="Código do cupom" aria-label="Código do cupom" />
            <button className="btn" disabled={!couponInput.trim()} onClick={() => void applyCoupon()}>Aplicar</button>
          </div>
          {couponError && <small className="field-error">{couponError}</small>}
        </>
      )}

      <label className="field" style={{ marginTop: 14 }}><span>Observações do pedido</span><textarea rows={2} maxLength={500} value={notes} onChange={(e) => setNotes(e.target.value)} /></label>

      <div className="card flat">
        <div className="total-row sub"><span>Subtotal</span><span>{formatMoney(subtotal)}</span></div>
        {discount > 0 && <div className="total-row sub discount"><span>Desconto</span><span>−{formatMoney(discount)}</span></div>}
        {serviceFee > 0 && <div className="total-row sub"><span>Taxa de serviço ({Number(tenant.service_fee_percent)}%)</span><span>{formatMoney(serviceFee)}</span></div>}
        {deliveryFee > 0 && <div className="total-row sub"><span>Entrega</span><span>{formatMoney(deliveryFee)}</span></div>}
      </div>
      {belowMinimum && minOrder > 0 && <div className="alert warn">Pedido mínimo de {formatMoney(minOrder)}. Faltam {formatMoney(minOrder - subtotal)}.</div>}
      {error && <div className="alert error" role="alert">{error}</div>}
    </Modal>
  )
}
