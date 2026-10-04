import { api } from './api'
import type { BusinessType, OrderStatus, PaymentMethod, PaymentStatus, PublicTenant, ServiceType, TenantSettings, UserRole } from '../types'

// ---- tenant -------------------------------------------------------------------------------
export const getTenant = async () => (await api.get<PublicTenant>('/tenant')).data
export const getTenantSettings = async () => (await api.get<TenantSettings>('/tenant/settings')).data
export type SettingsUpdate = Partial<{
  name: string
  business_type: BusinessType
  phone: string | null
  logo_url: string | null
  primary_color: string
  accepting_orders: boolean
}>
export const updateTenantSettings = async (payload: SettingsUpdate) => (await api.patch<TenantSettings>('/tenant/settings', payload)).data

// ---- catalog ------------------------------------------------------------------------------
export type Category = { id: string; name: string; image_url: string | null; sort_order: number; active: boolean }
export type Product = {
  id: string
  category_id: string
  name: string
  description: string | null
  image_url: string | null
  price: string
  featured: boolean
  active: boolean
}
export type ProductPayload = {
  category_id: string
  name: string
  description?: string | null
  image_url?: string | null
  price: string
  featured?: boolean
  active?: boolean
}

export const getCategories = async () => (await api.get<Category[]>('/categories')).data
export const createCategory = async (payload: { name: string; image_url?: string | null; sort_order?: number }) =>
  (await api.post<Category>('/categories', payload)).data
export const updateCategory = async (id: string, payload: Partial<Omit<Category, 'id'>>) =>
  (await api.patch<Category>(`/categories/${id}`, payload)).data
export const deleteCategory = async (id: string) => (await api.delete<Category>(`/categories/${id}`)).data

export const getProducts = async () => (await api.get<Product[]>('/products')).data
export const createProduct = async (payload: ProductPayload) => (await api.post<Product>('/products', payload)).data
export const updateProduct = async (id: string, payload: Partial<ProductPayload>) =>
  (await api.patch<Product>(`/products/${id}`, payload)).data
export const deleteProduct = async (id: string) => (await api.delete<Product>(`/products/${id}`)).data

// ---- customers ----------------------------------------------------------------------------
export type Customer = { id: string; name: string; phone: string | null; active: boolean; created_at: string }
export const getCustomers = async () => (await api.get<Customer[]>('/customers')).data
export const createCustomer = async (payload: { name: string; phone?: string | null }) =>
  (await api.post<Customer>('/customers', payload)).data
export const updateCustomer = async (id: string, payload: Partial<Pick<Customer, 'name' | 'phone' | 'active'>>) =>
  (await api.patch<Customer>(`/customers/${id}`, payload)).data

// ---- orders -------------------------------------------------------------------------------
export type OrderItem = {
  id: string
  product_id: string
  product_name: string
  quantity: number
  unit_price: string
  total_price: string
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
  payment_method: PaymentMethod
  payment_status: PaymentStatus
  paid_at: string | null
  notes: string | null
  subtotal: string
  total: string
  created_at: string
  items: OrderItem[]
  status_history: Array<{ status: OrderStatus; created_at: string; reason: string | null }>
}
export type NewOrderPayload = {
  customer_id: string
  payment_method: PaymentMethod
  service_type: ServiceType
  table_label?: string
  notes?: string
  items: Array<{ product_id: string; quantity: number; notes?: string }>
}

export const getOrders = async () => (await api.get<Order[]>('/orders')).data
export const getOrder = async (id: string) => (await api.get<Order>(`/orders/${id}`)).data
export const createOrder = async (payload: NewOrderPayload) => (await api.post<Order>('/orders', payload)).data
export const updateOrderStatus = async (id: string, status: OrderStatus, reason?: string) =>
  (await api.patch<Order>(`/orders/${id}/status`, { status, reason })).data
export const updateOrderPayment = async (id: string, payment_status: PaymentStatus, payment_method?: PaymentMethod) =>
  (await api.patch<Order>(`/orders/${id}/payment`, { payment_status, payment_method })).data

// ---- users / audit ------------------------------------------------------------------------
export type TeamUser = { id: string; name: string; email: string; role: UserRole; active: boolean }
export const getUsers = async () => (await api.get<TeamUser[]>('/users')).data
export const createUser = async (payload: { name: string; email: string; password: string; role: UserRole }) =>
  (await api.post<TeamUser>('/users', payload)).data
export const setUserActive = async (id: string, active: boolean) =>
  (await api.patch<TeamUser>(`/users/${id}/status`, { active })).data

export type AuditEntry = {
  id: string
  actor_name: string | null
  action: string
  entity_type: string
  details: string | null
  created_at: string
}
export const getAudit = async () => (await api.get<AuditEntry[]>('/audit')).data

// ---- analytics ----------------------------------------------------------------------------
export type Dashboard = {
  revenue: string
  order_count: number
  average_ticket: string
  top_product: { product_name: string; quantity: number; revenue: string } | null
  products: Array<{ product_name: string; quantity: number; revenue: string }>
  categories: Array<{ category_name: string; quantity: number; revenue: string }>
  sales_by_hour: Array<{ hour: number; orders: number; revenue: string }>
  sales_by_day: Array<{ day: string; orders: number; revenue: string }>
  orders_by_status: Array<{ label: string; count: number }>
  orders_by_payment: Array<{ label: string; count: number }>
  orders_by_service: Array<{ label: string; count: number }>
  revenue_change_percent: string
}
export type Period = 'month' | 'quarter' | 'all'

export async function getDashboard(period: Period, start?: string, end?: string) {
  const { data } = await api.get<Dashboard>('/analytics/dashboard', { params: { period, start: start || undefined, end: end || undefined } })
  return data
}

export async function downloadExport(period: Period, format: 'xlsx' | 'pdf') {
  const response = await api.get<Blob>('/analytics/dashboard/export', { params: { period, format }, responseType: 'blob' })
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = `dashboard-${period}.${format}`
  link.click()
  URL.revokeObjectURL(url)
}
