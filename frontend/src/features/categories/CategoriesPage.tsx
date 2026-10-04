import { useEffect, useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { apiErrorMessage } from '../../services/api'
import { createCategory, getCategories, updateCategory, type Category } from '../../services/admin'

export function CategoriesPage() {
  const [categories, setCategories] = useState<Category[]>([])
  const [name, setName] = useState('')
  const [error, setError] = useState('')

  const load = () => getCategories().then(setCategories).catch(() => setError('Não foi possível carregar as categorias.'))
  useEffect(() => { void load() }, [])

  async function add(event: FormEvent) {
    event.preventDefault()
    setError('')
    try {
      await createCategory({ name: name.trim(), sort_order: categories.length })
      setName('')
      await load()
    } catch (err) {
      setError(apiErrorMessage(err, 'Não foi possível criar a categoria.'))
    }
  }

  async function patch(category: Category, data: Partial<Category>) {
    try {
      await updateCategory(category.id, data)
      await load()
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível atualizar.'))
    }
  }

  function rename(category: Category) {
    const value = window.prompt('Novo nome da categoria:', category.name)?.trim()
    if (value && value !== category.name) void patch(category, { name: value })
  }

  function move(index: number, delta: number) {
    const b = categories[index + delta]
    if (!b) return
    // Swap positions, normalizing so equal sort orders never block a move.
    void Promise.all(categories.map((c, i) => {
      const position = i === index ? index + delta : i === index + delta ? index : i
      return c.sort_order === position ? null : updateCategory(c.id, { sort_order: position })
    }).filter(Boolean)).then(load)
  }

  return (
    <section className="page narrow">
      <div className="page-head"><div><h1>Categorias</h1><p className="muted">Seções do cardápio, na ordem em que aparecem.</p></div></div>
      {error && <div className="alert error">{error}</div>}
      <form className="inline-form" onSubmit={add}>
        <input className="input" placeholder="Nova categoria (ex.: Sucos)" value={name} onChange={(e) => setName(e.target.value)} required />
        <button className="btn primary">Adicionar</button>
      </form>
      <div className="card list">
        {categories.map((c, i) => (
          <div className={`list-row ${c.active ? '' : 'muted-row'}`} key={c.id}>
            <div><strong>{c.name}</strong>{!c.active && <span>Oculta</span>}</div>
            <div className="row-actions">
              <button className="btn small" disabled={i === 0} onClick={() => move(i, -1)} aria-label="Subir">↑</button>
              <button className="btn small" disabled={i === categories.length - 1} onClick={() => move(i, 1)} aria-label="Descer">↓</button>
              <button className="btn small" onClick={() => rename(c)}>Renomear</button>
              <button className="btn small" onClick={() => void patch(c, { active: !c.active })}>{c.active ? 'Ocultar' : 'Mostrar'}</button>
            </div>
          </div>
        ))}
        {categories.length === 0 && <div className="empty small">Nenhuma categoria.</div>}
      </div>
    </section>
  )
}
