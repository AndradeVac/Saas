import { api } from './api'

export type FeatureKey = 'coupons' | 'exports' | 'audit' | 'white_label'

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
  sales_whatsapp: string
}

export type PlanStatus = {
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
