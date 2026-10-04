import { Pencil, Plus, Star } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { formatMoney } from '../../lib/format'
import { apiErrorMessage } from '../../services/api'
import {
  createProduct, getCategories, getProducts, updateProduct,
  type Category, type Product, type ProductPayload,
} from '../../services/admin'

type Draft = { id?: string; category_id: string; name: string; description: string; image_url: string; price: string; featured: boolean }
const empty = (category_id: string): Draft => ({ category_id, name: '', description: '', image_url: '', price: '', featured: false })

export function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [draft, setDraft] = useState<Draft | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = () => Promise.all([getProducts(), getCategories()])
    .then(([p, c]) => { setProducts(p); setCategories(c) })
    .catch(() => setError('Não foi possível carregar o cardápio.'))
    .finally(() => setLoading(false))
  useEffect(() => { void load() }, [])

  const activeCategories = categories.filter((c) => c.active)

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!draft) return
    setSaving(true)
    setError('')
    const payload: ProductPayload = {
      category_id: draft.category_id,
      name: draft.name.trim(),
      description: draft.description.trim() || null,
      image_url: draft.image_url.trim() || null,
      price: draft.price.replace(',', '.'),
      featured: draft.featured,
    }
    try {
      if (draft.id) await updateProduct(draft.id, payload)
      else await createProduct(payload)
      setDraft(null)
      toast.success('Produto salvo.')
      await load()
    } catch (err) {
      setError(apiErrorMessage(err, 'Não foi possível salvar o produto.'))
    } finally {
      setSaving(false)
    }
  }

  async function toggle(product: Product) {
    try {
      await updateProduct(product.id, { active: !product.active })
      await load()
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível alterar o produto.'))
    }
  }

  return (
    <section className="page">
      <div className="page-head">
        <div><h1>Produtos</h1><p className="muted">O que aparece no cardápio dos seus clientes.</p></div>
        <button className="btn primary" disabled={!activeCategories.length} onClick={() => setDraft(empty(activeCategories[0]?.id ?? ''))}><Plus size={16} /> Novo produto</button>
      </div>
      {error && <div className="alert error">{error}</div>}
      {!loading && activeCategories.length === 0 && <div className="alert warn">Crie uma categoria antes de cadastrar produtos.</div>}

      {draft && (
        <form className="card" onSubmit={save}>
          <h3>{draft.id ? 'Editar produto' : 'Novo produto'}</h3>
          <div className="grid-2">
            <label className="field"><span>Nome</span><input required value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></label>
            <label className="field"><span>Preço (R$)</span><input required inputMode="decimal" value={draft.price} onChange={(e) => setDraft({ ...draft, price: e.target.value })} /></label>
            <label className="field"><span>Categoria</span>
              <select value={draft.category_id} onChange={(e) => setDraft({ ...draft, category_id: e.target.value })}>
                {activeCategories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <label className="field"><span>Link da foto (opcional)</span><input type="url" placeholder="https://…" value={draft.image_url} onChange={(e) => setDraft({ ...draft, image_url: e.target.value })} /></label>
          </div>
          <label className="field"><span>Descrição</span><textarea rows={2} maxLength={1000} value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} /></label>
          <label className="check"><input type="checkbox" checked={draft.featured} onChange={(e) => setDraft({ ...draft, featured: e.target.checked })} /> Destacar no topo do cardápio</label>
          <div className="actions">
            <button className="btn primary" disabled={saving}>{saving ? 'Salvando…' : 'Salvar'}</button>
            <button type="button" className="btn" onClick={() => setDraft(null)}>Cancelar</button>
          </div>
        </form>
      )}

      {categories.map((category) => {
        const items = products.filter((p) => p.category_id === category.id)
        if (!items.length) return null
        return (
          <div className="card list" key={category.id}>
            <h3>{category.name}{!category.active && <span className="badge"> inativa</span>}</h3>
            {items.map((p) => (
              <div className={`list-row ${p.active ? '' : 'muted-row'}`} key={p.id}>
                <div>
                  <strong>{p.name} {p.featured && <Star size={13} className="star" />}</strong>
                  <span>{formatMoney(p.price)}{!p.active && ' · oculto do cardápio'}</span>
                </div>
                <div className="row-actions">
                  <button className="icon-btn" aria-label="Editar" onClick={() => setDraft({
                    id: p.id, category_id: p.category_id, name: p.name, description: p.description ?? '',
                    image_url: p.image_url ?? '', price: p.price, featured: p.featured,
                  })}><Pencil size={16} /></button>
                  <button className="btn small" onClick={() => void toggle(p)}>{p.active ? 'Ocultar' : 'Mostrar'}</button>
                </div>
              </div>
            ))}
          </div>
        )
      })}
      {!loading && products.length === 0 && <div className="empty">Nenhum produto ainda. Cadastre o primeiro!</div>}
    </section>
  )
}
