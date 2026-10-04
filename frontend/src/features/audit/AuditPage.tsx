import { ScrollText } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Pagination } from '../../components/ui/Pagination'
import { EmptyState, ErrorBanner, PageHeader, Skeleton } from '../../components/ui/parts'
import { formatDateTime } from '../../lib/format'
import { getAudit, type AuditEntry } from '../../services/people'

const PAGE_SIZE = 50

const entityLabels: Record<string, string> = {
  ORDER: 'Pedidos', PRODUCT: 'Produtos', CATEGORY: 'Categorias', USER: 'Equipe', COUPON: 'Cupons', TENANT: 'Configurações',
}
const actionLabels: Record<string, string> = {
  ORDER_STATUS_CHANGED: 'Status do pedido alterado',
  ORDER_PAYMENT_CHANGED: 'Pagamento alterado',
  ORDER_EDITED: 'Pedido editado',
  PRODUCT_CREATED: 'Produto criado',
  PRODUCT_UPDATED: 'Produto alterado',
  PRODUCT_REMOVED: 'Produto removido',
  CATEGORY_CREATED: 'Categoria criada',
  CATEGORY_UPDATED: 'Categoria alterada',
  CATEGORY_REMOVED: 'Categoria removida',
  COUPON_CREATED: 'Cupom criado',
  COUPON_UPDATED: 'Cupom alterado',
  COUPON_DELETED: 'Cupom excluído',
  USER_CREATED: 'Usuário criado',
  USER_UPDATED: 'Usuário alterado',
  USER_STATUS_CHANGED: 'Acesso de usuário alterado',
  PASSWORD_CHANGED: 'Senha alterada',
  PASSWORD_RESET: 'Senha redefinida',
  TENANT_CREATED: 'Conta criada',
  TENANT_SETTINGS_UPDATED: 'Configurações alteradas',
}

export function AuditPage() {
  const [data, setData] = useState<{ items: AuditEntry[]; total: number } | null>(null)
  const [error, setError] = useState('')
  const [page, setPage] = useState(1)
  const [entity, setEntity] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => { setPage(1) }, [entity])

  const load = useCallback(() => {
    setLoading(true)
    getAudit({ entity_type: entity || undefined, page, page_size: PAGE_SIZE })
      .then((r) => { setData({ items: r.items, total: r.total }); setError('') })
      .catch(() => setError('Não foi possível carregar a auditoria.'))
      .finally(() => setLoading(false))
  }, [entity, page])
  useEffect(load, [load])

  return (
    <section className="page narrow">
      <PageHeader title="Auditoria" subtitle="Registro de quem fez o quê no painel." />
      <ErrorBanner message={error} onRetry={load} />
      <div className="toolbar">
        <select value={entity} onChange={(e) => setEntity(e.target.value)} aria-label="Filtrar por área">
          <option value="">Todas as áreas</option>
          {Object.entries(entityLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
      </div>
      <div className="card pad0">
        {loading && !data ? <div style={{ padding: 20 }}><Skeleton lines={6} height={26} /></div> : data && data.items.length === 0 ? (
          <EmptyState icon={<ScrollText size={26} />} title="Nenhum registro" />
        ) : data && (
          <>
            <div className="table-wrap" style={{ opacity: loading ? 0.6 : 1 }}>
              <table className="table keep-cols">
                <thead><tr><th>Quando</th><th>Quem</th><th>Ação</th><th>Detalhe</th></tr></thead>
                <tbody>
                  {data.items.map((e) => (
                    <tr key={e.id}>
                      <td style={{ whiteSpace: 'nowrap' }}>{formatDateTime(e.created_at)}</td>
                      <td>{e.actor_name ?? 'Sistema'}</td>
                      <td>{actionLabels[e.action] ?? e.action}</td>
                      <td className="muted">{e.details ?? ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onChange={setPage} />
          </>
        )}
      </div>
    </section>
  )
}
