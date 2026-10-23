import { RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { formatDate, formatDateTime, formatMoney, formatPhone } from '../../lib/format'
import { tenantUrl } from '../../lib/tenant'
import { api, apiErrorMessage } from '../../services/api'

type Store = {
  slug: string; name: string; status: string; plan: string; billing_status: string; billing_cycle: string
  paid_until: string | null; trial_ends_at: string | null; created_at: string; phone: string | null
  owner_name: string | null; owner_email: string | null; orders_7d: number; orders_total: number
  last_order_at: string | null; monthly_value: string; referred_by: string | null
}
type Overview = { mrr: string; stores: number; paying: number; trials: number; trials_ending_3d: number; no_orders_7d: number; overdue: number; list: Store[] }

const TOKEN_KEY = 'mesa-platform-admin'

/** Platform panel for the owner of Mesa Digital (token-protected): MRR, trials ending and who needs a call. */
export function AdminPage() {
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY) ?? '')
  const [input, setInput] = useState('')
  const [data, setData] = useState<Overview | null>(null)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState<'all' | 'trial' | 'paying' | 'idle'>('all')

  const load = useCallback(async (value: string) => {
    setError('')
    try {
      const response = await api.get<Overview>('/platform/admin/overview', { headers: { 'X-Admin-Token': value } })
      setData(response.data)
      sessionStorage.setItem(TOKEN_KEY, value)
    } catch (err) {
      sessionStorage.removeItem(TOKEN_KEY)
      setToken('')
      setError(apiErrorMessage(err, 'Token inválido.'))
    }
  }, [])
  useEffect(() => { if (token) void load(token) }, [token, load])

  if (!data) {
    return (
      <section className="page narrow" style={{ paddingTop: 60 }}>
        <form className="card" onSubmit={(e: FormEvent) => { e.preventDefault(); setToken(input.trim()) }}>
          <h2>Painel da plataforma</h2>
          <label className="field"><span>Token de acesso</span><input type="password" value={input} onChange={(e) => setInput(e.target.value)} autoFocus /></label>
          {error && <div className="alert error">{error}</div>}
          <button className="btn primary">Entrar</button>
        </form>
      </section>
    )
  }

  const now = Date.now()
  const rows = data.list.filter((s) => filter === 'all' || (filter === 'trial' && s.status === 'TRIAL') || (filter === 'paying' && Number(s.monthly_value) > 0) || (filter === 'idle' && s.orders_7d === 0 && s.status !== 'SUSPENDED'))
  return (
    <section className="page admin-page">
      <div className="row between"><h1>Mesa Digital · Plataforma</h1><button className="btn" onClick={() => void load(token)}><RefreshCw size={16} /> Atualizar</button></div>
      <div className="kpis">
        <article className="card kpi"><span>Receita mensal (MRR)</span><strong>{formatMoney(data.mrr)}</strong><small>{data.paying} pagantes</small></article>
        <article className="card kpi"><span>Lojas</span><strong>{data.stores}</strong><small>{data.trials} em teste</small></article>
        <article className="card kpi"><span>Testes acabando em 3 dias</span><strong>{data.trials_ending_3d}</strong><small>ligue para eles</small></article>
        <article className="card kpi"><span>Sem pedido há 7 dias</span><strong>{data.no_orders_7d}</strong><small>{data.overdue} com pagamento atrasado</small></article>
      </div>
      <div className="toolbar">
        <select value={filter} onChange={(e) => setFilter(e.target.value as typeof filter)} aria-label="Filtro">
          <option value="all">Todas</option><option value="trial">Em teste</option><option value="paying">Pagantes</option><option value="idle">Sem pedidos em 7 dias</option>
        </select>
      </div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Loja</th><th>Dono</th><th>Plano</th><th className="num">Pedidos 7d</th><th>Último pedido</th><th className="num">R$/mês</th></tr></thead>
          <tbody>
            {rows.map((s) => {
              const trialDays = s.trial_ends_at ? Math.ceil((new Date(s.trial_ends_at).getTime() - now) / 86_400_000) : null
              const phone = s.phone?.replace(/\D/g, '')
              return (
                <tr key={s.slug}>
                  <td><a href={tenantUrl(s.slug, '/')} target="_blank" rel="noreferrer"><strong>{s.name}</strong></a><span className="sub">{s.slug} · desde {formatDate(s.created_at)}{s.referred_by ? ` · indicado por ${s.referred_by}` : ''}</span></td>
                  <td>{s.owner_name}<span className="sub">{s.owner_email}{phone ? <> · <a href={`https://wa.me/55${phone}`} target="_blank" rel="noreferrer">{formatPhone(s.phone)}</a></> : null}</span></td>
                  <td><span className={`badge ${s.status === 'TRIAL' ? 'info' : s.billing_status === 'OVERDUE' ? 'danger' : 'ok'}`}>{s.status === 'TRIAL' ? `Teste${trialDays !== null ? ` · ${trialDays}d` : ''}` : s.plan}</span>{s.billing_status !== 'NONE' && <span className="sub">{s.billing_status}{s.billing_cycle === 'YEARLY' ? ' · anual' : ''}</span>}</td>
                  <td className="num">{s.orders_7d}<span className="sub">{s.orders_total} no total</span></td>
                  <td>{s.last_order_at ? formatDateTime(s.last_order_at) : <span className="muted">nenhum</span>}</td>
                  <td className="num">{formatMoney(s.monthly_value)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
