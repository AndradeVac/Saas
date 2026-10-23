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

export type TabTotals = {
  subtotal: string; discount: string; service_fee: string; total: string; per_person: string | null
  /** Confirmed payments, PIX reported by customers (to be checked) and what is still due. */
  paid: string; reported: string; remaining: string
}

export type TabPayment = { id: string; amount: string; method: PaymentMethod; status: 'REPORTED' | 'CONFIRMED' | 'REJECTED'; payer_name: string | null; created_at: string }

export type PublicTab = {
  number: number
  public_token: string
  table_label: string
  status: TabStatus
  requested_payment_method: PaymentMethod | null
  split_count: number | null
  service_fee_waived: boolean
  last_order_at: string | null
  totals: TabTotals
  orders: TabOrder[]
  payments: TabPayment[]
}

export type TabAlerts = {
  needs_approval: boolean
  wants_to_close: boolean
  idle: boolean
  late_orders: number
  payments_to_confirm: number
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
/** `code` is the secret printed in the table's QR Code (`?k=`); without it the table's bill is not revealed. */
export const findTableTab = async (table: string, code: string) =>
  (await api.get<PublicTab>(`/public/tables/${encodeURIComponent(table)}/tab`, { params: { k: code } })).data
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

export type TableQr = { label: string; code: string; url: string }
/** Menu links (with each table's code) for printing the QR Codes. */
export const getTableQrCodes = async (labels: string[]) =>
  (await api.get<TableQr[]>('/tabs/qr-codes', { params: { labels }, paramsSerializer: { indexes: null } })).data

// PIX straight to the restaurant's key (whole bill or one person's share)
export const setTabServiceFee = async (token: string, waived: boolean) =>
  (await api.post<PublicTab>(`/public/tabs/${token}/service-fee`, { waived })).data
export const setStaffTabServiceFee = async (tabId: string, waived: boolean) =>
  (await api.post<unknown>(`/tabs/${tabId}/service-fee`, { waived })).data
export const getTabPix = async (token: string, amount?: string) =>
  (await api.get<{ code: string; amount: string }>(`/public/tabs/${token}/pix`, { params: amount ? { amount } : {} })).data
export const reportTabPix = async (token: string, amount: string, payer_name?: string) =>
  (await api.post<PublicTab>(`/public/tabs/${token}/pix-report`, { amount, payer_name })).data
export const addTabPayment = async (id: string, amount: string, payment_method: PaymentMethod) =>
  (await api.post<StaffTab>(`/tabs/${id}/payments`, { amount, payment_method })).data
export const resolveTabPayment = async (id: string, paymentId: string, confirm: boolean) =>
  (await api.post<StaffTab>(`/tabs/${id}/payments/${paymentId}/${confirm ? 'confirm' : 'reject'}`)).data
