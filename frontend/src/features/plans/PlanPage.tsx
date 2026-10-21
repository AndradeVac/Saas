import { Check, CreditCard, Minus, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { useConfirm } from '../../components/ui/Confirm'
import { apiErrorMessage } from '../../services/api'
import { PageHeader, Skeleton } from '../../components/ui/parts'
import { formatDate, formatMoney } from '../../lib/format'
import { cancelSubscription, paidPlans, payNow, type FeatureKey, type PlanInfo } from '../../services/plans'
import { useTenant } from '../tenant/TenantProvider'
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
  { label: 'Pedidos', value: (plan) => (plan.max_orders === null ? 'Ilimitados' : `${plan.max_orders} no teste (comanda conta 1)`) },
]
const coreRows = ['Cardápio digital com fotos', 'QR Code por mesa', 'Pedidos em tempo real', 'Tamanhos e adicionais', 'Relatórios no painel']

export function PlanPage() {
  const { status, catalog, refresh } = usePlan()
  const { tenant } = useTenant()
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

      {status.billing_status !== 'NONE' && <BillingCard />}

      <h2 id="assinar" className="section-heading">{status.billing_status === 'ACTIVE' ? 'Trocar de plano' : 'Escolha o seu plano'}</h2>
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
        <p className="muted center-link">Para assinar, fale com o suporte da plataforma e informe o endereço <strong>{tenant.slug}</strong>.</p>
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


/** Online subscription state with the one action that matters in each case. */
function BillingCard() {
  const { status, refresh, catalog } = usePlan()
  const confirm = useConfirm()
  const [busy, setBusy] = useState(false)
  if (!status) return null
  const billingPlan = catalog?.plans.find((p) => p.key === status.billing_plan)

  async function pay() {
    setBusy(true)
    try {
      const { checkout_url } = await payNow()
      if (checkout_url) window.location.href = checkout_url
      else toast.info('Não há cobrança em aberto no momento.')
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível abrir o pagamento.'))
    } finally {
      setBusy(false)
    }
  }

  async function cancel() {
    const ok = await confirm({
      title: 'Cancelar a assinatura?',
      message: status?.paid_until
        ? `Você continua com todos os recursos até ${formatDate(status.paid_until)}. Depois disso o cardápio para de receber pedidos.`
        : 'O plano volta para a degustação.',
      confirmLabel: 'Cancelar assinatura',
      danger: true,
    })
    if (!ok) return
    setBusy(true)
    try {
      await cancelSubscription()
      toast.success('Assinatura cancelada.')
      await refresh()
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível cancelar.'))
    } finally {
      setBusy(false)
    }
  }

  const s = status.billing_status
  return (
    <div className={`card billing-card billing-${s.toLowerCase()}`}>
      <div>
        <h3>
          {s === 'PENDING' && 'Aguardando o primeiro pagamento'}
          {s === 'ACTIVE' && `Assinatura ativa · ${billingPlan?.name ?? ''}`}
          {s === 'OVERDUE' && (status.billing_blocked ? 'Pedidos bloqueados por falta de pagamento' : 'Pagamento em atraso')}
          {s === 'CANCELED' && 'Assinatura cancelada'}
        </h3>
        <p className="muted" style={{ margin: 0 }}>
          {s === 'PENDING' && `Plano ${billingPlan?.name ?? ''}: assim que o pagamento for confirmado, os recursos são liberados automaticamente.`}
          {s === 'ACTIVE' && status.paid_until && `Pago até ${formatDate(status.paid_until)}. A próxima cobrança chega por e-mail.`}
          {s === 'OVERDUE' && (status.billing_blocked
            ? 'O cardápio está no ar, mas não recebe pedidos. Pague agora e tudo volta na hora.'
            : `Pague até ${formatDate(status.grace_until)} para o cardápio continuar recebendo pedidos.`)}
          {s === 'CANCELED' && (status.paid_until && !status.billing_blocked
            ? `Você continua com acesso até ${formatDate(status.paid_until)}.`
            : 'Assine de novo quando quiser: seus dados continuam salvos.')}
        </p>
      </div>
      <div className="row">
        {(s === 'PENDING' || s === 'OVERDUE') && <button className="btn primary" disabled={busy} onClick={() => void pay()}><CreditCard size={16} /> Pagar agora</button>}
        {(s === 'ACTIVE' || s === 'OVERDUE' || s === 'PENDING') && <button className="btn ghost" disabled={busy} onClick={() => void cancel()}>Cancelar assinatura</button>}
      </div>
    </div>
  )
}
