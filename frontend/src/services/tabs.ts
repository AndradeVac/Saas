import { api } from './api'
import type { PaymentMethod } from '../types'

export type TabStatus = 'PENDING' | 'OPEN' | 'CLOSING' | 'CLOSED' | 'CANCELLED'

export type TabOrder = {
  id: string
  order_number: number
  status: string
  customer_name: string | null
  total: string
  created_at: string
  items: Array<{ product_id: string; product_name: string; quantity: number; options: Array<{ group: string; name: string; price: string }>; notes: string | null }>
}

export type TabTotals = { subtotal: string; discount: string; service_fee: string; total: string; per_person: string | null }

export type PublicTab = {
  number: number
  public_token: string
  table_label: string
  status: TabStatus
  requested_payment_method: PaymentMethod | null
  split_count: number | null
  last_order_at: string | null
  totals: TabTotals
  orders: TabOrder[]
}

export type TabAlerts = {
  needs_approval: boolean
  wants_to_close: boolean
  idle: boolean
  late_orders: number
  minutes_open: number
  minutes_since_last_order: number | null
}

export type StaffTab = PublicTab & {
  id: string
  opened_by: string | null
  payment_method: PaymentMethod | null
  created_at: string
  close_requested_at: string | null
  alerts: TabAlerts
}

// Customer side (public, by token)
export const getPublicTab = async (token: string) => (await api.get<PublicTab>(`/public/tabs/${token}`)).data
export const findTableTab = async (table: string) => (await api.get<PublicTab>(`/public/tables/${encodeURIComponent(table)}/tab`)).data
export const requestTabClose = async (token: string, payment_method: PaymentMethod, split_count: number | null) =>
  (await api.post<PublicTab>(`/public/tabs/${token}/close-request`, { payment_method, split_count })).data

// Floor staff
export const getTabs = async () => (await api.get<StaffTab[]>('/tabs')).data
export const approveTab = async (id: string) => (await api.post<StaffTab>(`/tabs/${id}/approve`)).data
export const closeTab = async (id: string, payment_method: PaymentMethod) => (await api.post<StaffTab>(`/tabs/${id}/close`, { payment_method })).data
export const cancelTab = async (id: string, reason: string) => (await api.post<StaffTab>(`/tabs/${id}/cancel`, { reason })).data

export const tabStatusLabels: Record<TabStatus, string> = {
  PENDING: 'Aguardando o garçom',
  OPEN: 'Comanda aberta',
  CLOSING: 'Conta pedida',
  CLOSED: 'Conta fechada',
  CANCELLED: 'Comanda cancelada',
}
