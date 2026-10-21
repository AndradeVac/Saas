import { Check, Lock, MessageCircle, Sparkles } from 'lucide-react'
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type PropsWithChildren, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Modal } from '../../components/ui/Modal'
import { Skeleton } from '../../components/ui/parts'
import { formatMoney } from '../../lib/format'
import { PLAN_LIMIT_EVENT, type PlanLimitDetail } from '../../services/api'
import { getPlanCatalog, getPlanStatus, paidPlans, salesLink, type FeatureKey, type PlanCatalog, type PlanInfo, type PlanStatus } from '../../services/plans'
import { useTenant } from '../tenant/TenantProvider'

type Limit = 'products' | 'users'

type PlanContextValue = {
  status: PlanStatus | null
  catalog: PlanCatalog | null
  refresh: () => Promise<void>
  has: (feature: FeatureKey) => boolean
  /** True when adding one more would exceed the plan (the API enforces it too). */
  atLimit: (limit: Limit) => boolean
  openUpgrade: (reason?: string) => void
  /** Runs `action` when the plan allows `feature`, otherwise opens the upgrade prompt. */
  guard: (feature: FeatureKey, action: () => void) => void
}

const PlanContext = createContext<PlanContextValue | undefined>(undefined)

export const FEATURE_PITCH: Record<FeatureKey, string> = {
  coupons: 'Crie cupons como BEMVINDO10 para trazer o cliente de volta, com validade, pedido mínimo e limite de usos.',
  exports: 'Leve suas vendas, pedidos e clientes para o Excel, PDF ou para o seu contador com um clique.',
  audit: 'Saiba quem mudou um preço, cancelou um pedido ou alterou as configurações, com data e hora.',
  white_label: 'Seu cardápio só com a sua marca, sem o selo da plataforma.',
}

export function planHighlights(plan: PlanInfo, catalog: PlanCatalog): string[] {
  const lines = [
    plan.max_products === null ? 'Produtos ilimitados' : `Até ${plan.max_products} produtos`,
    plan.max_users === null ? 'Equipe ilimitada' : plan.max_users === 1 ? 'Só o dono acessa o painel' : `Até ${plan.max_users} pessoas na equipe`,
    plan.max_orders === null ? 'Pedidos ilimitados' : `${plan.max_orders} pedidos para testar`,
  ]
  return [...lines, ...plan.features.map((feature) => catalog.feature_names[feature])]
}

export function PlanProvider({ children }: PropsWithChildren) {
  const [status, setStatus] = useState<PlanStatus | null>(null)
  const [catalog, setCatalog] = useState<PlanCatalog | null>(null)
  const [upgrade, setUpgrade] = useState<{ reason?: string } | null>(null)

  const refresh = useCallback(async () => {
    try {
      setStatus(await getPlanStatus())
    } catch {
      // Without plan info the panel still works; the API keeps enforcing the limits.
    }
  }, [])

  useEffect(() => {
    void refresh()
    getPlanCatalog().then(setCatalog).catch(() => setCatalog(null))
  }, [refresh])

  useEffect(() => {
    const onLimit = (event: Event) => {
      setUpgrade({ reason: (event as CustomEvent<PlanLimitDetail>).detail.message })
      void refresh()
    }
    window.addEventListener(PLAN_LIMIT_EVENT, onLimit)
    return () => window.removeEventListener(PLAN_LIMIT_EVENT, onLimit)
  }, [refresh])

  const value = useMemo<PlanContextValue>(() => {
    // Until the status loads, assume unlocked: the API is the real gate and this avoids flashing locks.
    const has = (feature: FeatureKey) => !status || status.plan.features.includes(feature)
    const openUpgrade = (reason?: string) => setUpgrade({ reason })
    return {
      status,
      catalog,
      refresh,
      has,
      openUpgrade,
      atLimit: (limit) => {
        if (!status) return false
        const max = limit === 'products' ? status.plan.max_products : status.plan.max_users
        return max !== null && status.usage[limit] >= max
      },
      guard: (feature, action) => (has(feature) ? action() : openUpgrade(`“${catalog?.feature_names[feature] ?? 'Este recurso'}” não está incluído no seu plano.`)),
    }
  }, [status, catalog, refresh])

  return (
    <PlanContext.Provider value={value}>
      {children}
      {upgrade && <UpgradeModal reason={upgrade.reason} onClose={() => setUpgrade(null)} />}
    </PlanContext.Provider>
  )
}

export function usePlan() {
  const context = useContext(PlanContext)
  if (!context) throw new Error('usePlan precisa estar dentro de PlanProvider')
  return context
}

/** "Quero este plano" button: opens WhatsApp with a ready message, or explains how to subscribe. */
export function SubscribeButton({ plan, className = 'btn primary block', children }: { plan: PlanInfo; className?: string; children?: ReactNode }) {
  const { catalog } = usePlan()
  const { tenant } = useTenant()
  const link = salesLink(catalog, `Olá! Quero assinar o plano ${plan.name} para ${tenant.name} (${tenant.slug}).`)
  const label = children ?? `Quero o ${plan.name}`
  if (link) {
    return <a className={className} href={link} target="_blank" rel="noreferrer"><MessageCircle size={16} /> {label}</a>
  }
  return <Link className={className} to="/painel/plano#assinar">{label}</Link>
}

function UpgradeModal({ reason, onClose }: { reason?: string; onClose: () => void }) {
  const { catalog } = usePlan()
  const plans = catalog ? paidPlans(catalog) : []
  return (
    <Modal title="Libere o Mesa Digital completo" onClose={onClose} size="lg">
      {reason && <div className="alert warn"><span><Lock size={15} /> {reason}</span></div>}
      <p className="muted">Você está usando a degustação. Escolha um plano para vender sem limites e usar todas as ferramentas.</p>
      <div className="plan-grid compact">
        {catalog && plans.map((plan) => (
          <div key={plan.key} className={`plan-card ${plan.highlight ? 'highlight' : ''}`}>
            {plan.highlight && <span className="plan-ribbon"><Sparkles size={13} /> Mais escolhido</span>}
            <h3>{plan.name}</h3>
            <div className="plan-price"><strong>{formatMoney(plan.price)}</strong><span>/mês</span></div>
            <p className="muted plan-tagline">{plan.tagline}</p>
            <ul className="plan-list">
              {planHighlights(plan, catalog).map((line) => <li key={line}><Check size={15} /> {line}</li>)}
            </ul>
            <SubscribeButton plan={plan} className={`btn ${plan.highlight ? 'primary' : ''} block`} />
          </div>
        ))}
      </div>
      <p className="center-link"><Link to="/painel/plano" onClick={onClose}>Comparar todos os recursos</Link></p>
    </Modal>
  )
}

/** Wraps a premium page: renders it when the plan allows, or a pitch with the upgrade buttons. */
export function FeatureGate({ feature, title, children }: { feature: FeatureKey; title: string; children: ReactNode }) {
  const { has, catalog, status } = usePlan()
  // Wait for the plan before mounting the page, so a locked page never fires its (402) requests.
  if (!status) return <div className="page"><Skeleton lines={4} /></div>
  if (has(feature)) return <>{children}</>
  const plans = catalog ? paidPlans(catalog).filter((plan) => plan.features.includes(feature)) : []
  return (
    <div className="page">
      <div className="locked-hero card">
        <div className="locked-icon"><Lock size={26} /></div>
        <span className="badge brand">Recurso dos planos pagos</span>
        <h1>{title}</h1>
        <p className="muted">{FEATURE_PITCH[feature]}</p>
        <div className="row" style={{ justifyContent: 'center' }}>
          {plans[0] && <SubscribeButton plan={plans[0]} className="btn primary large">Liberar a partir de {formatMoney(plans[0].price)}/mês</SubscribeButton>}
          <Link className="btn large" to="/painel/plano">Ver planos</Link>
        </div>
      </div>
    </div>
  )
}
