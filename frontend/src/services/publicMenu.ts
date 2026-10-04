import { api } from './api'
import type { PaymentMethod, PublicTenant, ServiceType } from '../types'

export type MenuCategory = { id: string; name: string; image_url: string | null }
export type MenuProduct = {
  id: string
  category_id: string
  name: string
  description: string | null
  image_url: string | null
  price: string
  featured: boolean
}
export type Menu = { tenant: PublicTenant; categories: MenuCategory[]; products: MenuProduct[] }

export type TrackedItem = { product_id: string; product_name: string; quantity: number; notes: string | null }
export type Tracking = {
  order_number: number
  status: string
  total: string
  created_at: string
  payment_status: string
  service_type: ServiceType
  table_label: string | null
  items: TrackedItem[]
}
export type HistoryOrder = {
  order_number: number
  public_token: string
  status: string
  total: string
  created_at: string
  items: TrackedItem[]
}

export const getMenu = async () => (await api.get<Menu>('/public/menu')).data

export async function createPublicOrder(payload: {
  customer_name: string
  customer_phone: string
  service_type: ServiceType
  table_label?: string
  payment_method: PaymentMethod
  notes?: string
  items: Array<{ product_id: string; quantity: number; notes?: string }>
}) {
  const { data } = await api.post<{ order_number: number; status: string; total: string; public_token: string }>('/public/orders', payload)
  return data
}

export const trackOrder = async (token: string) => (await api.get<Tracking>(`/public/orders/${token}`)).data
export const getHistory = async (phone: string) => (await api.get<HistoryOrder[]>('/public/history', { params: { phone } })).data
