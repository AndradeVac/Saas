import { api } from './api'

export type FeatureKey = 'coupons' | 'exports' | 'audit' | 'white_label' | 'insights' | 'loyalty'

export type PlanInfo = {
  key: string
  name: string
  price: string
  tagline: string
  max_products: number | null
  max_users: number | null
  max_orders: number | null
  features: FeatureKey[]
  highlight: boolean
}

export type PlanCatalog = {
  plans: PlanInfo[]
  feature_names: Record<FeatureKey, string>
  trial_days: number
  /** Subscriptions paid online (Asaas checkout); otherwise "Assinar" opens the sales WhatsApp. */
  online_billing: boolean
  annual_billing: boolean
  annual_months_charged: number
  whatsapp_auto: boolean
  menu_import: boolean
  sales_whatsapp: string
}

export type BillingStatus = 'NONE' | 'COURTESY' | 'PENDING' | 'ACTIVE' | 'OVERDUE' | 'CANCELED'

export type PlanStatus = {
  billing_status: BillingStatus
  billing_plan: string | null
  paid_until: string | null
  grace_until: string | null
  billing_blocked: boolean
  plan: PlanInfo
  status: 'TRIAL' | 'ACTIVE' | 'SUSPENDED'
  trial_ends_at: string | null
  trial_days_left: number | null
  trial_expired: boolean
  can_take_orders: boolean
  usage: { products: number; users: number; orders: number }
}

export const getPlanCatalog = async () => (await api.get<PlanCatalog>('/platform/plans')).data
export const getPlanStatus = async () => (await api.get<PlanStatus>('/tenant/plan')).data

/** Paid plans, cheapest first (the trial is not sold). */
export const paidPlans = (catalog: PlanCatalog) => catalog.plans.filter((plan) => plan.key !== 'trial')

export function salesLink(catalog: PlanCatalog | null, message: string) {
  if (!catalog?.sales_whatsapp) return null
  return `https://wa.me/${catalog.sales_whatsapp}?text=${encodeURIComponent(message)}`
}

// Online subscription (Asaas): every call returns the Asaas payment page to open.
export type Cycle = 'MONTHLY' | 'YEARLY'
export const subscribe = async (plan: string, document: string, email: string, cycle: Cycle = 'MONTHLY') =>
  (await api.post<{ checkout_url: string | null }>('/billing/subscribe', { plan, document, email, cycle })).data
export const payNow = async () => (await api.post<{ checkout_url: string | null }>('/billing/pay')).data
export const cancelSubscription = async () => { await api.post('/billing/cancel') }
