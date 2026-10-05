import { ArrowDown, ArrowUp, Pencil, Plus, Search, Star } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { MoneyInput } from '../../components/ui/MoneyInput'
import { ImageUpload } from '../../components/ui/ImageUpload'
import { Modal } from '../../components/ui/Modal'
import { EmptyState, ErrorBanner, PageHeader, Skeleton } from '../../components/ui/parts'
import { Toggle } from '../../components/ui/Toggle'
import { formatMoney } from '../../lib/format'
import { mediaUrl } from '../../lib/media'
import { apiErrorMessage } from '../../services/api'
import {
  createProduct, getCategories, getProducts, updateProduct,
  type Category, type Product,
} from '../../services/catalog'
import type { OptionGroup } from '../../types'
import { OptionsEditor } from './OptionsEditor'
import { usePlan } from '../plans/PlanProvider'

type Draft = {
  id?: string
  category_id: string
  name: string
  description: string
  image_url: string | null
  price: string
  featured: boolean
  available: boolean
  active: boolean
  options: OptionGroup[]
}

const blank = (category_id: string): Draft => ({
  category_id, name: '', description: '', image_url: null, price: '', featured: false, available: true, active: true, options: [],
})

export function ProductsPage() {
  const navigate = useNavigate()
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [draft, setDraft] = useState<Draft | null>(null)
  const [tab, setTab] = useState<'details' | 'options'>('details')
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'hidden' | 'soldout'>('all')

  const plan = usePlan()
  const { refresh: refreshPlan } = plan
  const load = useCallback(() => Promise.all([getProducts(), getCategories()])
    .then(([p, c]) => { setProducts(p); setCategories(c); setError(''); void refreshPlan() })
    .catch(() => setError('Não foi possível carregar o cardápio.'))
    .finally(() => setLoading(false)), [refreshPlan])
  useEffect(() => { void load() }, [load])

  const activeCategories = categories.filter((c) => c.active)

  const matches = useCallback((p: Product) => {
    const term = search.trim().toLowerCase()
    if (term && !`${p.name} ${p.description ?? ''}`.toLowerCase().includes(term)) return false
    if (categoryFilter && p.category_id !== categoryFilter) return false
    if (statusFilter === 'active') return p.active && p.available
    if (statusFilter === 'hidden') return !p.active
    if (statusFilter === 'soldout') return p.active && !p.available
    return true
  }, [search, categoryFilter, statusFilter])

  const grouped = useMemo(
    () => categories.map((category) => ({
      category,
      items: products.filter((p) => p.category_id === category.id).sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name)),
    })),
    [categories, products],
  )

  function openNew() {
    if (plan.atLimit('products')) {
      return plan.openUpgrade(`Seu plano permite até ${plan.status?.plan.max_products} produtos ativos. Oculte um produto ou assine para cadastrar mais.`)
    }
    setTab('details'); setFormError('')
    setDraft(blank(activeCategories[0]?.id ?? ''))
  }

  function openEdit(p: Product) {
    setTab('details'); setFormError('')
    setDraft({
      id: p.id, category_id: p.category_id, name: p.name, description: p.description ?? '', image_url: p.image_url,
      price: p.price, featured: p.featured, available: p.available, active: p.active, options: p.options,
    })
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!draft) return
    setFormError('')
    if (draft.price === '') return setFormError('Informe o preço no formato 12,50.')
    if (draft.options.some((g) => !g.name.trim() || g.options.some((o) => !o.name.trim()))) {
      setTab('options')
      return setFormError('Preencha o nome de todos os grupos e opções (ou remova os vazios).')
    }
    setSaving(true)
    const payload = {
      category_id: draft.category_id,
      name: draft.name.trim(),
      description: draft.description.trim() || null,
      image_url: draft.image_url,
      price: draft.price,
      featured: draft.featured,
      available: draft.available,
      active: draft.active,
      options: draft.options.map((g) => ({
        ...g,
        name: g.name.trim(),
        min: g.required ? Math.max(1, g.min) : g.min,
        options: g.options.map((o) => ({ ...o, name: o.name.trim() })),
      })),
    }
    try {
      if (draft.id) await updateProduct(draft.id, payload)
      else await createProduct(payload)
      setDraft(null)
      toast.success('Produto salvo')
      await load()
    } catch (err) {
      setFormError(apiErrorMessage(err, 'Não foi possível salvar o produto.'))
    } finally {
      setSaving(false)
    }
  }

  async function patch(product: Product, data: Partial<Product>, message?: string) {
    try {
      await updateProduct(product.id, data)
      if (message) toast.success(message)
      await load()
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível alterar o produto.'))
    }
  }

  async function move(items: Product[], index: number, delta: number) {
    const target = index + delta
    if (target < 0 || target >= items.length) return
    const reordered = [...items]
    ;[reordered[index], reordered[target]] = [reordered[target], reordered[index]]
    try {
      await Promise.all(reordered.map((p, i) => (p.sort_order === i ? null : updateProduct(p.id, { sort_order: i }))).filter(Boolean))
      await load()
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível reordenar.'))
    }
  }

  return (
    <section className="page">
      <PageHeader
        title="Produtos"
        subtitle={plan.status?.plan.max_products != null
          ? `${plan.status.usage.products} de ${plan.status.plan.max_products} produtos ativos no plano ${plan.status.plan.name}.`
          : 'Tudo o que aparece no cardápio dos seus clientes.'}
        actions={<button className="btn primary" disabled={activeCategories.length === 0} onClick={openNew}><Plus size={16} /> Novo produto</button>}
      />
      <ErrorBanner message={error} onRetry={() => void load()} />
      {!loading && activeCategories.length === 0 && (
        <div className="alert warn"><span>Crie uma categoria antes de cadastrar produtos.</span><button className="btn small" onClick={() => navigate('/painel/categorias')}>Ir para categorias</button></div>
      )}

      <div className="toolbar">
        <label className="search"><Search size={16} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar produto" aria-label="Buscar produto" /></label>
        <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} aria-label="Categoria">
          <option value="">Todas as categorias</option>
          {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)} aria-label="Situação">
          <option value="all">Todos</option>
          <option value="active">Disponíveis</option>
          <option value="soldout">Esgotados</option>
          <option value="hidden">Ocultos</option>
        </select>
      </div>

      {loading ? <Skeleton lines={5} height={70} /> : products.length === 0 ? (
        <EmptyState icon={<Plus size={26} />} title="Nenhum produto ainda" hint="Cadastre o primeiro produto para ele aparecer no cardápio." action={<button className="btn primary" onClick={openNew} disabled={activeCategories.length === 0}>Cadastrar produto</button>} />
      ) : grouped.map(({ category, items }) => {
        const shown = items.filter(matches)
        if (shown.length === 0) return null
        return (
          <div key={category.id}>
            <div className="cat-section-head"><h2>{category.name} {!category.active && <span className="badge">categoria oculta</span>}</h2><span className="muted">{shown.length} {shown.length === 1 ? 'item' : 'itens'}</span></div>
            <div className="grid-cards">
              {shown.map((p) => {
                const index = items.findIndex((x) => x.id === p.id)
                return (
                  <article className={`admin-product ${p.active ? '' : 'off'}`} key={p.id}>
                    {p.image_url ? <img src={mediaUrl(p.image_url)} alt="" loading="lazy" /> : <div className="product-placeholder">{p.name.charAt(0)}</div>}
                    <div className="admin-product-body">
                      <strong title={p.name}>{p.name}</strong>
                      <span>{formatMoney(p.price)}</span>
                      <div className="row" style={{ gap: 4 }}>
                        {p.featured && <span className="badge warn"><Star size={11} /> Destaque</span>}
                        {!p.available && <span className="badge danger">Esgotado</span>}
                        {!p.active && <span className="badge">Oculto</span>}
                        {p.options.length > 0 && <span className="badge info">{p.options.length} {p.options.length === 1 ? 'grupo' : 'grupos'}</span>}
                      </div>
                    </div>
                    <div className="admin-product-actions">
                      <div className="row" style={{ gap: 2 }}>
                        <button className="icon-btn" disabled={index === 0} onClick={() => void move(items, index, -1)} aria-label="Subir"><ArrowUp size={15} /></button>
                        <button className="icon-btn" disabled={index === items.length - 1} onClick={() => void move(items, index, 1)} aria-label="Descer"><ArrowDown size={15} /></button>
                      </div>
                      <div className="row" style={{ gap: 6 }}>
                        <button className="btn small" onClick={() => void patch(p, { available: !p.available }, p.available ? 'Marcado como esgotado' : 'Produto disponível')}>{p.available ? 'Esgotar' : 'Disponibilizar'}</button>
                        <button className="icon-btn bordered" onClick={() => openEdit(p)} aria-label={`Editar ${p.name}`}><Pencil size={15} /></button>
                      </div>
                    </div>
                  </article>
                )
              })}
            </div>
          </div>
        )
      })}
      {!loading && products.length > 0 && products.filter(matches).length === 0 && <EmptyState icon={<Search size={24} />} title="Nenhum produto encontrado" hint="Ajuste a busca ou os filtros." />}

      {draft && (
        <Modal
          title={draft.id ? 'Editar produto' : 'Novo produto'}
          size="lg"
          onClose={() => setDraft(null)}
          footer={
            <>
              <button type="button" className="btn" onClick={() => setDraft(null)}>Cancelar</button>
              <button type="submit" form="product-form" className="btn primary" disabled={saving}>{saving ? 'Salvando…' : 'Salvar produto'}</button>
            </>
          }
        >
          <form id="product-form" onSubmit={save}>
            <div className="tabs">
              <button type="button" className={tab === 'details' ? 'active' : ''} onClick={() => setTab('details')}>Detalhes</button>
              <button type="button" className={tab === 'options' ? 'active' : ''} onClick={() => setTab('options')}>Opções e adicionais {draft.options.length > 0 && `(${draft.options.length})`}</button>
            </div>
            {formError && <div className="alert error" role="alert">{formError}</div>}
            {tab === 'details' ? (
              <>
                <div className="grid-2">
                  <label className="field"><span>Nome</span><input required autoFocus maxLength={160} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></label>
                  <MoneyInput label="Preço" required value={draft.price} onChange={(price) => setDraft({ ...draft, price })} hint="Se tiver opções, este é o preço base." />
                </div>
                <label className="field"><span>Categoria</span>
                  <select value={draft.category_id} onChange={(e) => setDraft({ ...draft, category_id: e.target.value })}>
                    {activeCategories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </label>
                <label className="field"><span>Descrição</span><textarea rows={3} maxLength={1000} placeholder="Ingredientes, tamanho da porção…" value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} /></label>
                <ImageUpload label="Foto" value={draft.image_url} onChange={(image_url) => setDraft({ ...draft, image_url })} hint="JPG, PNG ou WebP. A imagem é redimensionada automaticamente." />
                <Toggle label="Disponível" hint="Desligue quando acabar. O produto continua no cardápio como “Esgotado”." checked={draft.available} onChange={(available) => setDraft({ ...draft, available })} />
                <Toggle label="Destaque" hint="Aparece em “Destaques”, no topo do cardápio." checked={draft.featured} onChange={(featured) => setDraft({ ...draft, featured })} />
                <Toggle label="Visível no cardápio" hint="Desligue para ocultar sem apagar." checked={draft.active} onChange={(active) => setDraft({ ...draft, active })} />
              </>
            ) : (
              <OptionsEditor value={draft.options} onChange={(options) => setDraft({ ...draft, options })} />
            )}
          </form>
        </Modal>
      )}
    </section>
  )
}
