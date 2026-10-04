import { useEffect, useState } from 'react'
import { formatDateTime } from '../../lib/format'
import { getAudit, type AuditEntry } from '../../services/admin'

export function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    getAudit().then(setEntries).catch(() => setError('Não foi possível carregar a auditoria.'))
  }, [])

  return (
    <section className="page narrow">
      <div className="page-head"><div><h1>Auditoria</h1><p className="muted">Últimas ações feitas no painel.</p></div></div>
      {error && <div className="alert error">{error}</div>}
      <div className="card list">
        {entries.map((e) => (
          <div className="list-row" key={e.id}>
            <div><strong>{e.action}</strong><span>{e.actor_name ?? 'Sistema'} · {e.entity_type}{e.details ? ` · ${e.details}` : ''}</span></div>
            <span className="muted">{formatDateTime(e.created_at)}</span>
          </div>
        ))}
        {entries.length === 0 && <div className="empty small">Sem registros.</div>}
      </div>
    </section>
  )
}
