import { ArrowLeft, Plus, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { formatMoney, paymentMethodLabels, serviceLabels } from '../../lib/format'
import { apiErrorMessage } from '../../services/api'
import {
  createCustomer, createOrder, getCategories, getCustomers, getProducts,
  type Category, type Customer, type Product,
} from '../../services/admin'
import type { PaymentMethod, ServiceType } from '../../types'

export function NewOrderPage() {
  const navigate = useNavigate()
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [customers, setCustomers] = useState<Customer[]>([])
  const [customerId, setCustomerId] = useState('')
  const [newName, setNewName] = useState('')
  const [service, setService] = useState<ServiceType>('DINE_IN')
  const [table, setTable] = useState('')
  const [payment, setPayment] = useState<PaymentMethod>('CASH')
  const [notes, setNotes] = useState('')
  const [cart, setCart] = useState<Record<string, number>>({})
  const [filter, setFilter] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([getProducts(), getCategories(), getCustomers()])
      .then(([p, c, cu]) => {
        setProducts(p.filter((x) => x.active))
        setCategories(c.filter((x) => x.active))
        setCustomers(cu.filter((x) => x.active))
      })
      .catch(() => setError('Não foi possível carregar os dados.'))
  }, [])

  const byId = useMemo(() => new Map(products.map((p) => [p.id, p])), [products])
  const lines = Object.entries(cart).filter(([, q]) => q > 0)
  const total = lines.reduce((sum, [id, q]) => sum + Number(byId.get(id)?.price ?? 0) * q, 0)
  const shown = products.filter((p) => p.name.toLowerCase().includes(filter.toLowerCase()))

  async function submit() {
    setError('')
    setSaving(true)
    try {
      let id = customerId
      if (!id) {
        if (newName.trim().length < 2) throw new Error('Selecione um cliente ou informe um nome.')
        id = (await createCustomer({ name: newName.trim() })).id
      }
      const order = await createOrder({
        customer_id: id,
        payment_method: payment,
        service_type: service,
        table_label: service === 'DINE_IN' && table ? table : undefined,
        notes: notes || undefined,
        items: lines.map(([product_id, quantity]) => ({ product_id, quantity })),
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
      <button className="btn ghost small" onClick={() => navigate('/painel/pedidos')}><ArrowLeft size={14} /> Voltar</button>
      <div className="page-head"><h1>Novo pedido</h1></div>
      {error && <div className="alert error">{error}</div>}
      <div className="two-col">
        <div className="card">
          <h3>Itens</h3>
          <input className="input" placeholder="Filtrar produtos" value={filter} onChange={(e) => setFilter(e.target.value)} />
          <div className="pick-list">
            {categories.map((c) => {
              const items = shown.filter((p) => p.category_id === c.id)
              if (!items.length) return null
              return (
                <div key={c.id}>
                  <h4>{c.name}</h4>
                  {items.map((p) => (
                    <button className="pick-row" key={p.id} onClick={() => setCart((cur) => ({ ...cur, [p.id]: (cur[p.id] ?? 0) + 1 }))}>
                      <span>{p.name}</span><span>{formatMoney(p.price)} <Plus size={14} /></span>
                    </button>
                  ))}
                </div>
              )
            })}
          </div>
        </div>
        <div className="card">
          <h3>Pedido</h3>
          {lines.length === 0 && <div className="empty small">Toque nos produtos para adicionar.</div>}
          {lines.map(([id, q]) => (
            <div className="detail-line" key={id}>
              <span>{q}× {byId.get(id)?.name}</span>
              <span>
                <b>{formatMoney(Number(byId.get(id)?.price) * q)}</b>
                <button className="icon-btn" aria-label="Remover" onClick={() => setCart((cur) => ({ ...cur, [id]: 0 }))}><Trash2 size={15} /></button>
              </span>
            </div>
          ))}
          <label className="field"><span>Cliente</span>
            <select value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
              <option value="">Novo cliente…</option>
              {customers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          {!customerId && <label className="field"><span>Nome do cliente</span><input value={newName} onChange={(e) => setNewName(e.target.value)} /></label>}
          <div className="grid-2">
            <label className="field"><span>Atendimento</span>
              <select value={service} onChange={(e) => setService(e.target.value as ServiceType)}>
                {(Object.keys(serviceLabels) as ServiceType[]).map((s) => <option key={s} value={s}>{serviceLabels[s]}</option>)}
              </select>
            </label>
            {service === 'DINE_IN' && <label className="field"><span>Mesa</span><input value={table} onChange={(e) => setTable(e.target.value)} /></label>}
          </div>
          <label className="field"><span>Pagamento</span>
            <select value={payment} onChange={(e) => setPayment(e.target.value as PaymentMethod)}>
              {(Object.keys(paymentMethodLabels) as PaymentMethod[]).map((m) => <option key={m} value={m}>{paymentMethodLabels[m]}</option>)}
            </select>
          </label>
          <label className="field"><span>Observações</span><textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
          <div className="total-row"><span>Total</span><strong>{formatMoney(total)}</strong></div>
          <button className="btn primary block" disabled={saving || lines.length === 0} onClick={() => void submit()}>{saving ? 'Enviando…' : 'Criar pedido'}</button>
        </div>
      </div>
    </section>
  )
}
