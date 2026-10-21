import { Download, Pencil, Plus, UsersRound } from 'lucide-react'
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { Modal } from '../../components/ui/Modal'
import { Pagination } from '../../components/ui/Pagination'
import { EmptyState, ErrorBanner, PageHeader, Skeleton } from '../../components/ui/parts'
import { useDebounced } from '../../hooks/useDebounced'
import { formatDate, formatMoney, formatPhone, maskPhone } from '../../lib/format'
import { apiErrorMessage, isPlanLimitError } from '../../services/api'
import { downloadCsv } from '../../services/orders'
import { createCustomer, getCustomers, updateCustomer, type Customer } from '../../services/people'
import { usePlan } from '../plans/PlanProvider'

const PAGE_SIZE = 25
type Draft = { id?: string; name: string; phone: string; notes: string; active: boolean }

export function CustomersPage() {
  const { guard } = usePlan()
  const [data, setData] = useState<{ items: Customer[]; total: number } | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [sort, setSort] = useState<'name' | 'recent' | 'spent'>('recent')
  const [showInactive, setShowInactive] = useState(false)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const search = useDebounced(q)

  useEffect(() => { setPage(1) }, [search, sort, showInactive])

  const load = useCallback(() => {
    setLoading(true)
    getCustomers({ q: search || undefined, sort, active: showInactive ? undefined : true, page, page_size: PAGE_SIZE })
      .then((r) => { setData({ items: r.items, total: r.total }); setError('') })
      .catch(() => setError('Não foi possível carregar os clientes.'))
      .finally(() => setLoading(false))
  }, [search, sort, showInactive, page])
  useEffect(load, [load])

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!draft) return
    setSaving(true)
    setFormError('')
    try {
      const payload = { name: draft.name.trim(), phone: draft.phone.trim() || null, notes: draft.notes.trim() || null }
      if (draft.id) await updateCustomer(draft.id, { ...payload, active: draft.active })
      else await createCustomer(payload)
      setDraft(null)
      toast.success('Cliente salvo')
      load()
    } catch (err) {
      setFormError(apiErrorMessage(err, 'Não foi possível salvar o cliente.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="page">
      <PageHeader
        title="Clientes"
        subtitle="Quem já pediu na sua casa, quanto gastou e quando voltou."
        actions={<>
          <button className="btn" onClick={() => guard('exports', () => { downloadCsv('/customers/export', undefined, 'clientes.csv').catch((err) => { if (!isPlanLimitError(err)) toast.error('Não foi possível exportar.') }) })}><Download size={16} /> Exportar</button>
          <button className="btn primary" onClick={() => { setFormError(''); setDraft({ name: '', phone: '', notes: '', active: true }) }}><Plus size={16} /> Novo cliente</button>
        </>}
      />
      <ErrorBanner message={error} onRetry={load} />
      <div className="toolbar">
        <label className="search"><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por nome ou telefone" aria-label="Buscar cliente" /></label>
        <select value={sort} onChange={(e) => setSort(e.target.value as typeof sort)} aria-label="Ordenar">
          <option value="recent">Mais recentes</option>
          <option value="spent">Que mais gastaram</option>
          <option value="name">Nome (A–Z)</option>
        </select>
        <label className="check" style={{ margin: 0 }}><input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} /> Mostrar inativos</label>
      </div>

      <div className="card pad0">
        {loading && !data ? <div style={{ padding: 20 }}><Skeleton lines={5} height={30} /></div> : data && data.items.length === 0 ? (
          <EmptyState icon={<UsersRound size={26} />} title="Nenhum cliente encontrado" hint={q ? 'Tente outra busca.' : 'Os clientes aparecem aqui quando fazem o primeiro pedido.'} />
        ) : data && (
          <>
            <div className="table-wrap" style={{ opacity: loading ? 0.6 : 1 }}>
              <table className="table keep-cols">
                <thead><tr><th>Cliente</th><th>Telefone</th><th className="num">Pedidos</th><th className="num">Total gasto</th><th>Último pedido</th><th /></tr></thead>
                <tbody>
                  {data.items.map((c) => (
                    <tr key={c.id} style={{ opacity: c.active ? 1 : 0.5 }}>
                      <td><strong>{c.name}</strong>{c.notes && <span className="sub">{c.notes}</span>}</td>
                      <td>{c.phone ? <a href={`https://wa.me/55${c.phone.replace(/\D/g, '')}`} target="_blank" rel="noreferrer">{formatPhone(c.phone)}</a> : '—'}</td>
                      <td className="num">{c.orders_count}</td>
                      <td className="num">{formatMoney(c.total_spent)}</td>
                      <td>{formatDate(c.last_order_at)}</td>
                      <td className="num"><button className="icon-btn" onClick={() => { setFormError(''); setDraft({ id: c.id, name: c.name, phone: c.phone ? maskPhone(c.phone) : '', notes: c.notes ?? '', active: c.active }) }} aria-label={`Editar ${c.name}`}><Pencil size={16} /></button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onChange={setPage} />
          </>
        )}
      </div>

      {draft && (
        <Modal
          title={draft.id ? 'Editar cliente' : 'Novo cliente'}
          size="sm"
          onClose={() => setDraft(null)}
          footer={<><button type="button" className="btn" onClick={() => setDraft(null)}>Cancelar</button><button type="submit" form="customer-form" className="btn primary" disabled={saving}>{saving ? 'Salvando…' : 'Salvar'}</button></>}
        >
          <form id="customer-form" onSubmit={save}>
            {formError && <div className="alert error" role="alert">{formError}</div>}
            <label className="field"><span>Nome</span><input required autoFocus maxLength={120} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></label>
            <label className="field"><span>Telefone com DDD</span><input inputMode="tel" placeholder="(11) 99999-9999" value={draft.phone} onChange={(e) => setDraft({ ...draft, phone: maskPhone(e.target.value) })} /></label>
            <label className="field"><span>Observações</span><textarea rows={3} maxLength={1000} placeholder="Preferências, alergias…" value={draft.notes} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} /></label>
            {draft.id && <label className="check"><input type="checkbox" checked={draft.active} onChange={(e) => setDraft({ ...draft, active: e.target.checked })} /> Cliente ativo</label>}
          </form>
        </Modal>
      )}
    </section>
  )
}
