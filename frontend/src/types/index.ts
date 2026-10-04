export type OrderStatus = 'RECEIVED' | 'PREPARING' | 'READY' | 'FINISHED' | 'CANCELLED'
export type PaymentMethod = 'PIX' | 'CARD' | 'CASH'
export type PaymentStatus = 'PENDING' | 'PAID'
export type ServiceType = 'DINE_IN' | 'TAKEAWAY'
export type BusinessType = 'RESTAURANT' | 'BAKERY' | 'CAFE' | 'SNACK_BAR' | 'PIZZERIA' | 'OTHER'
export type UserRole = 'ADMIN' | 'OPERATOR'

export type PublicTenant = {
  slug: string
  name: string
  business_type: BusinessType
  phone: string | null
  logo_url: string | null
  primary_color: string
  accepting_orders: boolean
}

export type TenantSettings = PublicTenant & {
  id: string
  timezone: string
  status: 'TRIAL' | 'ACTIVE' | 'SUSPENDED'
  plan: string
  trial_ends_at: string | null
  created_at: string
}
