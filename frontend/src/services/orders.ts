import { api } from './api'
import type { OrderStatus, Page, PaymentMethod, PaymentStatus, ServiceType } from '../types'

export type OrderItem = {
  id: string
  product_id: string
  product_name: string
  quantity: number
  unit_price: string
  total_price: string
  options: Array<{ group: string; name: string; price: string }>
  notes: string | null
}

export type Order = {
  id: string
  order_number: number
  customer_id: string
  customer_name: string | null
  customer_phone: string | null
  status: OrderStatus
  service_type: ServiceType
  table_label: string | null
  delivery_address: string | null
  payment_method: PaymentMethod
  payment_status: PaymentStatus
  paid_at: string | null
  notes: string | null
  coupon_code: string | null
  subtotal: string
  discount: string
  service_fee: string
  delivery_fee: string
  total: string
  created_at: string
  updated_at: string
  items: OrderItem[]
  status_history: Array<{ status: OrderStatus; created_at: string; reason: string | null }>
}

export type NewOrderPayload = {
  customer_id: string
  payment_method: PaymentMethod
  service_type: ServiceType
  table_label?: string
  delivery_address?: string
  notes?: string
  coupon_code?: string
  items: Array<{ product_id: string; quantity: number; notes?: string; options?: Array<{ group_id: string; option_id: string }> }>
}

export type OrderFilters = {
  status?: OrderStatus[]
  payment_status?: PaymentStatus
  service_type?: ServiceType
  date_from?: string
  date_to?: string
  q?: string
  page?: number
  page_size?: number
}

// Repeated `status=A&status=B` keys, the format the API expects.
const serialize = (filters: OrderFilters) => {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value === undefined || value === '') return
    if (Array.isArray(value)) value.forEach((v) => params.append(key, v))
    else params.append(key, String(value))
  })
  return params
}

export const getBoard = async () => (await api.get<Order[]>('/orders/board')).data
export const getOrders = async (filters: OrderFilters) => (await api.get<Page<Order>>('/orders', { params: serialize(filters) })).data
export const getOrder = async (id: string) => (await api.get<Order>(`/orders/${id}`)).data
export const createOrder = async (payload: NewOrderPayload) => (await api.post<Order>('/orders', payload)).data
export const editOrder = async (id: string, payload: { table_label?: string | null; notes?: string | null; delivery_address?: string | null }) =>
  (await api.patch<Order>(`/orders/${id}`, payload)).data
export const updateOrderStatus = async (id: string, status: OrderStatus, reason?: string) =>
  (await api.patch<Order>(`/orders/${id}/status`, { status, reason })).data
export const updateOrderPayment = async (id: string, payment_status: PaymentStatus, payment_method?: PaymentMethod) =>
  (await api.patch<Order>(`/orders/${id}/payment`, { payment_status, payment_method })).data

export async function downloadCsv(path: string, params: URLSearchParams | undefined, filename: string) {
  const response = await api.get<Blob>(path, { params, responseType: 'blob' })
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export const exportOrders = (filters: OrderFilters) =>
  downloadCsv('/orders/export', serialize({ ...filters, page: undefined, page_size: undefined }), 'pedidos.csv')
