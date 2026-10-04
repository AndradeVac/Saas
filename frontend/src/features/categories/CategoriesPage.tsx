import { ArrowDown, ArrowUp, Pencil, Plus, Tags } from 'lucide-react'
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { ImageUpload } from '../../components/ui/ImageUpload'
import { Modal } from '../../components/ui/Modal'
import { EmptyState, ErrorBanner, PageHeader, Skeleton } from '../../components/ui/parts'
import { Toggle } from '../../components/ui/Toggle'
import { apiErrorMessage } from '../../services/api'
import { createCategory, getCategories, getProducts, updateCategory, type Category } from '../../services/catalog'

type Draft = { id?: string; name: string; image_url: string | null; active: boolean }

export function CategoriesPage() {
  const [categories, setCategories] = useState<Category[]>([])
  const [counts, setCounts] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [draft, setDraft] = useState<Draft | null>(null)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(() => Promise.all([getCategories(), getProducts()])
    .then(([c, p]) => {
      setCategories(c)
      setCounts(p.reduce<Record<string, number>>((acc, item) => ({ ...acc, [item.category_id]: (acc[item.category_id] ?? 0) + (item.active ? 1 : 0) }), {}))
      setError('')
    })
    .catch(() => setError('Não foi possível carregar as categorias.'))
    .finally(() => setLoading(false)), [])
  useEffect(() => { void load() }, [load])

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!draft) return
    setSaving(true)
    setFormError('')
    try {
      if (draft.id) await updateCategory(draft.id, { name: draft.name.trim(), image_url: draft.image_url, active: draft.active })
      else await createCategory({ name: draft.name.trim(), image_url: draft.image_url, sort_order: categories.length })
      setDraft(null)
      toast.success('Categoria salva')
      await load()
    } catch (err) {
      setFormError(apiErrorMessage(err, 'Não foi possível salvar a categoria.'))
    } finally {
      setSaving(false)
    }
  }

  async function move(index: number, delta: number) {
    const target = categories[index + delta]
    if (!target) return
    const reordered = [...categories]
    ;[reordered[index], reordered[index + delta]] = [reordered[index + delta], reordered[index]]
    try {
      await Promise.all(reordered.map((c, i) => (c.sort_order === i ? null : updateCategory(c.id, { sort_order: i }))).filter(Boolean))
      await load()
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível reordenar.'))
    }
  }

  return (
    <section className="page narrow">
      <PageHeader
        title="Categorias"
        subtitle="As seções do cardápio, na ordem em que aparecem para o cliente."
        actions={<button className="btn primary" onClick={() => { setFormError(''); setDraft({ name: '', image_url: null, active: true }) }}><Plus size={16} /> Nova categoria</button>}
      />
      <ErrorBanner message={error} onRetry={() => void load()} />
      <div className="card" style={{ padding: '4px 20px' }}>
        {loading ? <Skeleton lines={4} height={40} /> : categories.length === 0 ? (
          <EmptyState icon={<Tags size={26} />} title="Nenhuma categoria" hint="Crie as seções do seu cardápio, como Pratos, Bebidas e Sobremesas." />
        ) : categories.map((c, i) => (
          <div className={`list-row ${c.active ? '' : 'off'}`} key={c.id}>
            <div>
              <strong>{c.name}</strong>
              <small>{counts[c.id] ?? 0} {(counts[c.id] ?? 0) === 1 ? 'produto' : 'produtos'}{!c.active && ' · oculta do cardápio'}</small>
            </div>
            <div className="row-actions">
              <button className="icon-btn" disabled={i === 0} onClick={() => void move(i, -1)} aria-label="Subir"><ArrowUp size={16} /></button>
              <button className="icon-btn" disabled={i === categories.length - 1} onClick={() => void move(i, 1)} aria-label="Descer"><ArrowDown size={16} /></button>
              <button className="btn small" onClick={() => { setFormError(''); setDraft({ id: c.id, name: c.name, image_url: c.image_url, active: c.active }) }}><Pencil size={14} /> Editar</button>
            </div>
          </div>
        ))}
      </div>

      {draft && (
        <Modal
          title={draft.id ? 'Editar categoria' : 'Nova categoria'}
          size="sm"
          onClose={() => setDraft(null)}
          footer={<><button type="button" className="btn" onClick={() => setDraft(null)}>Cancelar</button><button type="submit" form="category-form" className="btn primary" disabled={saving}>{saving ? 'Salvando…' : 'Salvar'}</button></>}
        >
          <form id="category-form" onSubmit={save}>
            {formError && <div className="alert error" role="alert">{formError}</div>}
            <label className="field"><span>Nome</span><input required autoFocus maxLength={80} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></label>
            <ImageUpload label="Imagem (opcional)" value={draft.image_url} onChange={(image_url) => setDraft({ ...draft, image_url })} />
            {draft.id && <Toggle label="Visível no cardápio" hint="Ocultar esconde a categoria e todos os produtos dela." checked={draft.active} onChange={(active) => setDraft({ ...draft, active })} />}
          </form>
        </Modal>
      )}
    </section>
  )
}
