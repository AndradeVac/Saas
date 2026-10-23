import { api } from './api'
import type { OptionGroup, PaymentMethod, PublicTenant, ServiceType } from '../types'

export type MenuCategory = { id: string; name: string; image_url: string | null; available_from: string | null; available_until: string | null }
export type MenuProduct = {
  id: string
  category_id: string
  name: string
  description: string | null
  image_url: string | null
  price: string
  featured: boolean
  available: boolean
  options: OptionGroup[]
}
export type Menu = { tenant: PublicTenant; categories: MenuCategory[]; products: MenuProduct[] }

export type TrackedItem = {
  product_id: string
  product_name: string
  quantity: number
  options: Array<{ group: string; name: string; price: string }>
  notes: string | null
}
export type Tracking = {
  order_number: number
  status: string
  total: string
  subtotal: string
  discount: string
  service_fee: string
  delivery_fee: string
  created_at: string
  payment_status: string
  payment_method: PaymentMethod
  service_type: ServiceType
  table_label: string | null
  delivery_address: string | null
  items: TrackedItem[]
  scheduled_for: string | null
  history: Array<{ status: string; at: string }>
  prep_minutes: number | null
  loyalty: { stamps: number; goal: number; reward: string; rewards_available: number } | null
  review_stars: number | null
  google_review_url: string | null
}

export const getMenu = async () => (await api.get<Menu>('/public/menu')).data

export type PublicOrderPayload = {
  customer_name: string
  customer_phone: string
  service_type: ServiceType
  table_label?: string
  table_code?: string
  delivery_address?: string
  payment_method: PaymentMethod
  notes?: string
  coupon_code?: string
  waive_service_fee?: boolean
  delivery_zone?: string
  scheduled_for?: string
  marketing_opt_in?: boolean
  notify_whatsapp?: boolean
  items: Array<{ product_id: string; quantity: number; notes?: string; options: Array<{ group_id: string; option_id: string }> }>
}

export async function createPublicOrder(payload: PublicOrderPayload) {
  const { data } = await api.post<{ order_number: number; status: string; total: string; public_token: string; tab_token: string | null }>('/public/orders', payload)
  return data
}

export const trackOrder = async (token: string) => (await api.get<Tracking>(`/public/orders/${token}`)).data
export const cancelPublicOrder = async (token: string) => { await api.post(`/public/orders/${token}/cancel`) }
export const reviewOrder = async (token: string, stars: number, comment?: string) =>
  (await api.post<{ google_review_url: string | null }>(`/public/orders/${token}/review`, { stars, comment })).data
export const getOrderPix = async (token: string) => (await api.get<{ code: string; amount: string }>(`/public/orders/${token}/pix`)).data

export async function checkCoupon(code: string, subtotal: number) {
  const { data } = await api.post<{ code: string; discount: string }>('/public/coupons/check', { code, subtotal: subtotal.toFixed(2) })
  return data
}
