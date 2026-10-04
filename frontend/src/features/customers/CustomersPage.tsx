import { useEffect, useState } from 'react'
import { formatDateTime, formatPhone } from '../../lib/format'
import { getCustomers, type Customer } from '../../services/admin'

export function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    getCustomers().then(setCustomers).catch(() => setError('Não foi possível carregar os clientes.'))
  }, [])

  const term = search.trim().toLowerCase()
  const shown = customers.filter((c) => `${c.name} ${c.phone ?? ''}`.toLowerCase().includes(term))

  return (
    <section className="page narrow">
      <div className="page-head"><div><h1>Clientes</h1><p className="muted">Quem já pediu na sua casa.</p></div></div>
      {error && <div className="alert error">{error}</div>}
      <input className="input" placeholder="Buscar por nome ou telefone" value={search} onChange={(e) => setSearch(e.target.value)} />
      <div className="card list">
        {shown.map((c) => (
          <div className="list-row" key={c.id}>
            <div><strong>{c.name}</strong><span>{formatPhone(c.phone) || 'Sem telefone'}</span></div>
            <span className="muted">desde {formatDateTime(c.created_at)}</span>
          </div>
        ))}
        {shown.length === 0 && <div className="empty small">Nenhum cliente encontrado.</div>}
      </div>
    </section>
  )
}
