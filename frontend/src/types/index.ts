export type OrderStatus = 'RECEIVED' | 'PREPARING' | 'READY' | 'FINISHED' | 'CANCELLED'
export type PaymentMethod = 'PIX' | 'CARD' | 'CASH' | 'TAB'
export type PaymentStatus = 'PENDING' | 'PAID'
export type ServiceType = 'DINE_IN' | 'TAKEAWAY' | 'DELIVERY'
export type BusinessType = 'RESTAURANT' | 'BAKERY' | 'CAFE' | 'SNACK_BAR' | 'PIZZERIA' | 'OTHER'
export type UserRole = 'ADMIN' | 'OPERATOR'
export type DayKey = 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun'
export type OpeningHours = Partial<Record<DayKey, string[][]>>

export type OptionItem = { id: string; name: string; price: string; active: boolean }
export type OptionGroup = {
  id: string
  name: string
  required: boolean
  min: number
  max: number
  options: OptionItem[]
}

export type PublicTenant = {
  slug: string
  name: string
  business_type: BusinessType
  description: string | null
  phone: string | null
  address: string | null
  instagram: string | null
  logo_url: string | null
  cover_url: string | null
  primary_color: string
  pix_key: string | null
  accepting_orders: boolean
  is_open: boolean
  hours_mode: 'MANUAL' | 'SCHEDULE'
  opening_hours: OpeningHours
  enabled_services: ServiceType[]
  accepted_payments: PaymentMethod[]
  delivery_fee: string
  min_order_value: string
  service_fee_percent: string
  show_platform_badge: boolean
  /** Comanda por mesa: dine-in orders go to the table's open bill, paid at the end. */
  tabs_enabled: boolean
  tab_idle_minutes: number
}

export type TenantSettings = PublicTenant & {
  id: string
  tabs_auto_approve: boolean
  timezone: string
  status: 'TRIAL' | 'ACTIVE' | 'SUSPENDED'
  plan: string
  trial_ends_at: string | null
  created_at: string
}

export type Page<T> = { items: T[]; total: number; page: number; page_size: number }
