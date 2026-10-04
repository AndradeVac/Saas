import { Minus, Plus, X } from 'lucide-react'
import { useState, type Dispatch, type SetStateAction } from 'react'
import { toast } from 'sonner'
import { formatMoney, paymentMethodLabels, serviceLabels } from '../../lib/format'
import { readJson, writeJson } from '../../lib/storage'
import { apiErrorMessage } from '../../services/api'
import { createPublicOrder, type MenuProduct } from '../../services/publicMenu'
import type { PaymentMethod, PublicTenant, ServiceType } from '../../types'

export type Cart = Record<string, { quantity: number; notes?: string }>

type Props = {
  tenant: PublicTenant
  products: Map<string, MenuProduct>
  cart: Cart
  setCart: Dispatch<SetStateAction<Cart>>
  tableFromQr: string
  onClose: () => void
  onOrdered: (token: string) => void
}

export function CartSheet({ tenant, products, cart, setCart, tableFromQr, onClose, onOrdered }: Props) {
  const customerKey = `mesa:${tenant.slug}:customer`
  const saved = readJson<{ name?: string; phone?: string }>(customerKey, {})
  const [name, setName] = useState(saved.name ?? '')
  const [phone, setPhone] = useState(saved.phone ?? '')
  const [service, setService] = useState<ServiceType>('DINE_IN')
  const [table, setTable] = useState(tableFromQr)
  const [payment, setPayment] = useState<PaymentMethod>('CASH')
  const [notes, setNotes] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')

  const lines = Object.entries(cart).filter(([id, line]) => line.quantity > 0 && products.has(id))
  const total = lines.reduce((sum, [id, line]) => sum + Number(products.get(id)!.price) * line.quantity, 0)

  function change(id: string, delta: number) {
    setCart((current) => ({ ...current, [id]: { ...current[id], quantity: Math.max(0, current[id].quantity + delta) } }))
  }

  async function submit() {
    setError('')
    if (name.trim().length < 2) return setError('Informe seu nome.')
    if (phone.replace(/\D/g, '').length < 10) return setError('Informe um telefone com DDD.')
    if (service === 'DINE_IN' && !table.trim()) return setError('Informe o número da mesa.')
    setSending(true)
    try {
      const order = await createPublicOrder({
        customer_name: name,
        customer_phone: phone,
        service_type: service,
        table_label: service === 'DINE_IN' ? table : undefined,
        payment_method: payment,
        notes: notes || undefined,
        items: lines.map(([id, line]) => ({ product_id: id, quantity: line.quantity, notes: line.notes || undefined })),
      })
      writeJson(customerKey, { name, phone })
      onOrdered(order.public_token)
    } catch (err) {
      const message = apiErrorMessage(err, 'Não foi possível enviar o pedido. Tente novamente.')
      setError(message)
      toast.error(message)
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <section className="sheet" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Seu pedido">
        <header className="sheet-head">
          <h2>Seu pedido</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Fechar"><X size={20} /></button>
        </header>

        <div className="sheet-body">
          {lines.length === 0 && <div className="empty">Seu pedido está vazio.</div>}
          {lines.map(([id, line]) => {
            const product = products.get(id)!
            return (
              <div className="cart-line" key={id}>
                <div>
                  <strong>{product.name}</strong>
                  <span>{formatMoney(Number(product.price) * line.quantity)}</span>
                  <input
                    className="line-note"
                    placeholder="Observação (ex.: sem cebola)"
                    maxLength={300}
                    value={line.notes ?? ''}
                    onChange={(e) => setCart((c) => ({ ...c, [id]: { ...c[id], notes: e.target.value } }))}
                  />
                </div>
                <div className="stepper">
                  <button onClick={() => change(id, -1)} aria-label="Diminuir"><Minus size={14} /></button>
                  <span>{line.quantity}</span>
                  <button onClick={() => change(id, 1)} aria-label="Aumentar" disabled={line.quantity >= 20}><Plus size={14} /></button>
                </div>
              </div>
            )
          })}

          <div className="segmented" role="radiogroup" aria-label="Tipo de atendimento">
            {(Object.keys(serviceLabels) as ServiceType[]).map((type) => (
              <button key={type} className={service === type ? 'active' : ''} onClick={() => setService(type)} role="radio" aria-checked={service === type}>
                {serviceLabels[type]}
              </button>
            ))}
          </div>

          {service === 'DINE_IN' && (
            <label className="field"><span>Mesa</span><input value={table} onChange={(e) => setTable(e.target.value)} maxLength={30} inputMode="text" /></label>
          )}
          <div className="grid-2">
            <label className="field"><span>Seu nome</span><input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></label>
            <label className="field"><span>Telefone (DDD)</span><input value={phone} onChange={(e) => setPhone(e.target.value)} autoComplete="tel" inputMode="tel" /></label>
          </div>
          <label className="field">
            <span>Como vai pagar? (no caixa)</span>
            <select value={payment} onChange={(e) => setPayment(e.target.value as PaymentMethod)}>
              {(Object.keys(paymentMethodLabels) as PaymentMethod[]).map((m) => <option key={m} value={m}>{paymentMethodLabels[m]}</option>)}
            </select>
          </label>
          <label className="field"><span>Observações do pedido</span><textarea rows={2} maxLength={500} value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
          {error && <div className="alert error">{error}</div>}
        </div>

        <footer className="sheet-foot">
          <div className="total-row"><span>Total</span><strong>{formatMoney(total)}</strong></div>
          <button className="btn primary block" disabled={sending || lines.length === 0} onClick={() => void submit()}>
            {sending ? 'Enviando…' : 'Enviar pedido'}
          </button>
        </footer>
      </section>
    </div>
  )
}
