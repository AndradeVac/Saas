import { Check, Minus, Sparkles } from 'lucide-react'
import { useEffect } from 'react'
import { PageHeader, Skeleton } from '../../components/ui/parts'
import { formatDate, formatMoney } from '../../lib/format'
import { paidPlans, type FeatureKey, type PlanInfo } from '../../services/plans'
import { planHighlights, SubscribeButton, usePlan } from './PlanProvider'

function Meter({ label, used, max }: { label: string; used: number; max: number | null }) {
  const percent = max ? Math.min(100, Math.round((used / max) * 100)) : 0
  const tone = max && used > max ? 'danger' : percent >= 80 ? 'warn' : ''
  return (
    <div className="meter">
      <div className="meter-head">
        <span>{label}</span>
        <strong>{used}{max !== null ? ` de ${max}` : ''}</strong>
      </div>
      {max !== null ? <div className={`meter-track ${tone}`}><span style={{ width: `${percent}%` }} /></div> : <small className="muted">Ilimitado</small>}
    </div>
  )
}

const limitRows: Array<{ label: string; value: (plan: PlanInfo) => string }> = [
  { label: 'Produtos no cardápio', value: (plan) => (plan.max_products === null ? 'Ilimitados' : `Até ${plan.max_products}`) },
  { label: 'Pessoas na equipe', value: (plan) => (plan.max_users === null ? 'Ilimitadas' : `Até ${plan.max_users}`) },
  { label: 'Pedidos', value: (plan) => (plan.max_orders === null ? 'Ilimitados' : `${plan.max_orders} no teste`) },
]
const coreRows = ['Cardápio digital com fotos', 'QR Code por mesa', 'Pedidos em tempo real', 'Tamanhos e adicionais', 'Relatórios no painel']

export function PlanPage() {
  const { status, catalog, refresh } = usePlan()
  useEffect(() => { void refresh() }, [refresh])

  if (!status || !catalog) {
    return <section className="page narrow"><PageHeader title="Meu plano" /><Skeleton lines={6} /></section>
  }

  const plans = catalog.plans
  const trial = status.status === 'TRIAL'
  const features = Object.keys(catalog.feature_names) as FeatureKey[]

  return (
    <section className="page">
      <PageHeader title="Meu plano" subtitle="Acompanhe o seu uso e libere mais recursos quando quiser." />

      <div className={`card plan-current ${trial ? 'trial' : ''}`}>
        <div>
          <span className="badge brand">{trial ? 'Período de teste' : 'Plano ativo'}</span>
          <h2>{status.plan.name}</h2>
          {trial && (status.trial_expired
            ? <p><strong>Seu período de teste terminou.</strong> O cardápio continua no ar, mas não recebe novos pedidos.</p>
            : <p>Faltam <strong>{status.trial_days_left} {status.trial_days_left === 1 ? 'dia' : 'dias'}</strong> de teste (até {formatDate(status.trial_ends_at)}).</p>)}
          {!trial && <p className="muted">{formatMoney(status.plan.price)}/mês</p>}
          {!status.can_take_orders && !status.trial_expired && <p className="field-error">Você usou todos os pedidos do teste. Assine para voltar a receber pedidos.</p>}
        </div>
        <div className="meters">
          <Meter label="Produtos ativos" used={status.usage.products} max={status.plan.max_products} />
          <Meter label="Equipe" used={status.usage.users} max={status.plan.max_users} />
          <Meter label="Pedidos" used={status.usage.orders} max={status.plan.max_orders} />
        </div>
      </div>

      <h2 id="assinar" className="section-heading">Escolha o seu plano</h2>
      <div className="plan-grid">
        {paidPlans(catalog).map((plan) => {
          const current = !trial && plan.key === status.plan.key
          return (
            <div key={plan.key} className={`plan-card ${plan.highlight ? 'highlight' : ''}`}>
              {plan.highlight && <span className="plan-ribbon"><Sparkles size={13} /> Mais escolhido</span>}
              <h3>{plan.name}</h3>
              <div className="plan-price"><strong>{formatMoney(plan.price)}</strong><span>/mês</span></div>
              <p className="muted plan-tagline">{plan.tagline}</p>
              <ul className="plan-list">
                {planHighlights(plan, catalog).map((line) => <li key={line}><Check size={15} /> {line}</li>)}
              </ul>
              {current
                ? <button className="btn block" disabled>Seu plano atual</button>
                : <SubscribeButton plan={plan} className={`btn ${plan.highlight ? 'primary' : ''} block`} />}
            </div>
          )
        })}
      </div>
      {!catalog.sales_whatsapp && (
        <p className="muted center-link">Para assinar, fale com o suporte da plataforma e informe o endereço <strong>{window.location.hostname.split('.')[0]}</strong>.</p>
      )}

      <div className="card table-wrap compare">
        <table className="table">
          <thead>
            <tr><th>Recurso</th>{plans.map((plan) => <th key={plan.key}>{plan.name}</th>)}</tr>
          </thead>
          <tbody>
            {limitRows.map((row) => (
              <tr key={row.label}><td>{row.label}</td>{plans.map((plan) => <td key={plan.key}>{row.value(plan)}</td>)}</tr>
            ))}
            {coreRows.map((label) => (
              <tr key={label}><td>{label}</td>{plans.map((plan) => <td key={plan.key}><Check size={16} className="yes" /></td>)}</tr>
            ))}
            {features.map((feature) => (
              <tr key={feature}>
                <td>{catalog.feature_names[feature]}</td>
                {plans.map((plan) => <td key={plan.key}>{plan.features.includes(feature) ? <Check size={16} className="yes" /> : <Minus size={16} className="no" />}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
