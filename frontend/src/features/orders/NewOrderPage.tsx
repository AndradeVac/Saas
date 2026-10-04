import { ArrowLeft, Minus, Plus, Search, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ErrorBanner, PageHeader, Skeleton } from '../../components/ui/parts'
import { useDebounced } from '../../hooks/useDebounced'
import { formatMoney, formatPhone, maskPhone, paymentMethodLabels, serviceLabels } from '../../lib/format'
import { mediaUrl } from '../../lib/media'
import { apiErrorMessage } from '../../services/api'
import { getCategories, getProducts, type Category, type Product } from '../../services/catalog'
import { createOrder } from '../../services/orders'
import { createCustomer, getCustomers, type Customer } from '../../services/people'
import type { MenuProduct } from '../../services/publicMenu'
import type { PaymentMethod, ServiceType } from '../../types'
import { cartSubtotal, type CartLine } from '../menu/cart'
import { ProductModal } from '../menu/ProductModal'
import { useTenant } from '../tenant/TenantProvider'

// The staff screen reuses the customer's product dialog (options, notes, quantity).
const toMenuProduct = (p: Product): MenuProduct => ({
  ...p,
  options: p.options
    .map((g) => ({ ...g, options: g.options.filter((o) => o.active) }))
    .filter((g) => g.options.length > 0),
})

export function NewOrderPage() {
  const navigate = useNavigate()
  const { tenant } = useTenant()
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)
  const [category, setCategory] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  const [picking, setPicking] = useState<MenuProduct | null>(null)
  const [lines, setLines] = useState<CartLine[]>([])

  const [customerQuery, setCustomerQuery] = useState('')
  const debouncedQuery = useDebounced(customerQuery, 250)
  const [matches, setMatches] = useState<Customer[]>([])
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [newName, setNewName] = useState('')
  const [newPhone, setNewPhone] = useState('')

  const [service, setService] = useState<ServiceType>('DINE_IN')
  const [table, setTable] = useState('')
  const [address, setAddress] = useState('')
  const [payment, setPayment] = useState<PaymentMethod>('CASH')
  const [coupon, setCoupon] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([getProducts(), getCategories()])
      .then(([p, c]) => { setProducts(p.filter((x) => x.active)); setCategories(c.filter((x) => x.active)) })
      .catch(() => setError('Não foi possível carregar o cardápio.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (customer || debouncedQuery.trim().length < 2) { setMatches([]); return }
    getCustomers({ q: debouncedQuery, active: true, page_size: 6 }).then((r) => setMatches(r.items)).catch(() => setMatches([]))
  }, [debouncedQuery, customer])

  const visible = useMemo(() => {
    const term = filter.trim().toLowerCase()
    return products.filter((p) => (!category || p.category_id === category) && (!term || p.name.toLowerCase().includes(term)))
  }, [products, category, filter])

  const subtotal = cartSubtotal(lines)
  const serviceFee = service === 'DINE_IN' ? (subtotal * Number(tenant.service_fee_percent)) / 100 : 0
  const deliveryFee = service === 'DELIVERY' ? Number(tenant.delivery_fee) : 0

  function addLine(line: CartLine) {
    setLines((current) => {
      const existing = current.find((l) => l.key === line.key)
      return existing ? current.map((l) => (l.key === line.key ? { ...l, quantity: l.quantity + line.quantity } : l)) : [...current, line]
    })
    setPicking(null)
  }

  const change = (key: string, delta: number) =>
    setLines((current) => current.map((l) => (l.key === key ? { ...l, quantity: l.quantity + delta } : l)).filter((l) => l.quantity > 0))

  async function submit() {
    setError('')
    setSaving(true)
    try {
      let customerId = customer?.id
      if (!customerId) {
        if (newName.trim().length < 2) throw new Error('Selecione um cliente ou informe o nome do cliente.')
        customerId = (await createCustomer({ name: newName.trim(), phone: newPhone.trim() || null })).id
      }
      const order = await createOrder({
        customer_id: customerId,
        payment_method: payment,
        service_type: service,
        table_label: service === 'DINE_IN' && table ? table : undefined,
        delivery_address: service === 'DELIVERY' ? address : undefined,
        notes: notes || undefined,
        coupon_code: coupon.trim() || undefined,
        items: lines.map((l) => ({
          product_id: l.productId,
          quantity: l.quantity,
          notes: l.notes,
          options: l.options.map(({ group_id, option_id }) => ({ group_id, option_id })),
        })),
      })
      navigate(`/painel/pedidos/${order.id}`)
    } catch (err) {
      setError(err instanceof Error && !('response' in err) ? err.message : apiErrorMessage(err, 'Não foi possível criar o pedido.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="page">
      <button className="btn ghost small back-link" onClick={() => navigate('/painel/pedidos')}><ArrowLeft size={14} /> Voltar</button>
      <PageHeader title="Novo pedido" subtitle="Lance um pedido de balcão, telefone ou WhatsApp." />
      <ErrorBanner message={error} />
      <div className="two-col">
        <div className="card">
          <label className="search"><Search size={16} /><input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Buscar produto" aria-label="Buscar produto" /></label>
          <div className="segmented" style={{ overflowX: 'auto', marginBottom: 12 }}>
            <button className={!category ? 'active' : ''} onClick={() => setCategory(null)}>Tudo</button>
            {categories.map((c) => <button key={c.id} className={category === c.id ? 'active' : ''} onClick={() => setCategory(c.id)}>{c.name}</button>)}
          </div>
          {loading ? <Skeleton lines={6} height={44} /> : (
            <div className="pick-list">
              {visible.map((p) => (
                <button className={`pick-row ${p.available ? '' : 'off'}`} key={p.id} disabled={!p.available} onClick={() => setPicking(toMenuProduct(p))}>
                  <span style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                    {p.image_url ? <img src={mediaUrl(p.image_url)} alt="" width={36} height={36} style={{ borderRadius: 8, objectFit: 'cover' }} /> : null}
                    {p.name}{!p.available && ' (esgotado)'}
                  </span>
                  <span>{formatMoney(p.price)} <Plus size={14} style={{ verticalAlign: -2 }} /></span>
                </button>
              ))}
              {visible.length === 0 && <div className="empty small">Nenhum produto.</div>}
            </div>
          )}
        </div>

        <div className="card">
          <h3>Pedido</h3>
          {lines.length === 0 && <div className="empty small">Toque nos produtos para adicionar.</div>}
          {lines.map((l) => (
            <div className="cart-line" key={l.key}>
              <div className="cart-line-main">
                <strong>{l.name}</strong>
                {l.options.length > 0 && <span className="cart-line-opts">{l.options.map((o) => o.label).join(' · ')}</span>}
                {l.notes && <span className="cart-line-opts">“{l.notes}”</span>}
                <span>{formatMoney(l.unitPrice * l.quantity)}</span>
              </div>
              <div className="stepper">
                <button onClick={() => change(l.key, -1)} aria-label="Diminuir">{l.quantity === 1 ? <Trash2 size={14} /> : <Minus size={14} />}</button>
                <span>{l.quantity}</span>
                <button onClick={() => change(l.key, 1)} aria-label="Aumentar"><Plus size={14} /></button>
              </div>
            </div>
          ))}

          <h4>Cliente</h4>
          {customer ? (
            <div className="alert info"><span><strong>{customer.name}</strong> {customer.phone && `· ${formatPhone(customer.phone)}`}</span><button className="btn small" onClick={() => { setCustomer(null); setCustomerQuery('') }}>Trocar</button></div>
          ) : (
            <>
              <label className="field">
                <span>Buscar cliente existente</span>
                <input value={customerQuery} onChange={(e) => setCustomerQuery(e.target.value)} placeholder="Nome ou telefone" />
              </label>
              {matches.map((c) => (
                <button className="pick-row" key={c.id} onClick={() => setCustomer(c)}><span>{c.name}</span><span className="muted">{formatPhone(c.phone)}</span></button>
              ))}
              <div className="grid-2" style={{ marginTop: 8 }}>
                <label className="field"><span>Ou novo cliente</span><input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Nome" /></label>
                <label className="field"><span>Telefone (opcional)</span><input value={newPhone} onChange={(e) => setNewPhone(maskPhone(e.target.value))} placeholder="(11) 99999-9999" inputMode="tel" /></label>
              </div>
            </>
          )}

          <div className="grid-2">
            <label className="field"><span>Atendimento</span>
              <select value={service} onChange={(e) => setService(e.target.value as ServiceType)}>
                {(Object.keys(serviceLabels) as ServiceType[]).map((s) => <option key={s} value={s}>{serviceLabels[s]}</option>)}
              </select>
            </label>
            <label className="field"><span>Pagamento</span>
              <select value={payment} onChange={(e) => setPayment(e.target.value as PaymentMethod)}>
                {(Object.keys(paymentMethodLabels) as PaymentMethod[]).map((m) => <option key={m} value={m}>{paymentMethodLabels[m]}</option>)}
              </select>
            </label>
          </div>
          {service === 'DINE_IN' && <label className="field"><span>Mesa / comanda</span><input value={table} onChange={(e) => setTable(e.target.value)} maxLength={30} /></label>}
          {service === 'DELIVERY' && <label className="field"><span>Endereço de entrega</span><textarea rows={2} value={address} onChange={(e) => setAddress(e.target.value)} /></label>}
          <div className="grid-2">
            <label className="field"><span>Cupom (opcional)</span><input value={coupon} onChange={(e) => setCoupon(e.target.value)} style={{ textTransform: 'uppercase' }} /></label>
            <label className="field"><span>Observações</span><input value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={500} /></label>
          </div>

          <div className="card flat">
            <div className="total-row sub"><span>Subtotal</span><span>{formatMoney(subtotal)}</span></div>
            {serviceFee > 0 && <div className="total-row sub"><span>Taxa de serviço</span><span>{formatMoney(serviceFee)}</span></div>}
            {deliveryFee > 0 && <div className="total-row sub"><span>Entrega</span><span>{formatMoney(deliveryFee)}</span></div>}
            <div className="total-row"><span>Total estimado</span><strong>{formatMoney(subtotal + serviceFee + deliveryFee)}</strong></div>
            {coupon && <small className="muted">O desconto do cupom é calculado ao criar o pedido.</small>}
          </div>
          <button className="btn primary large block" disabled={saving || lines.length === 0} onClick={() => void submit()}>{saving ? 'Criando…' : 'Criar pedido'}</button>
        </div>
      </div>

      {picking && <ProductModal product={picking} canOrder onClose={() => setPicking(null)} onAdd={addLine} />}
    </section>
  )
}
