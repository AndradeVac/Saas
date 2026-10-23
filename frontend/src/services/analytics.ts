import { api } from './api'
import { downloadCsv } from './orders'

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
  previous_revenue: string
  revenue_change_percent: string
}
export type Period = 'month' | 'quarter' | 'all'

export async function getDashboard(period: Period, start?: string, end?: string) {
  const { data } = await api.get<Dashboard>('/analytics/dashboard', { params: { period, start: start || undefined, end: end || undefined } })
  return data
}

export function downloadDashboard(period: Period, format: 'xlsx' | 'pdf', start?: string, end?: string) {
  const params = new URLSearchParams({ period, format })
  if (start && end) { params.set('start', start); params.set('end', end) }
  return downloadCsv('/analytics/dashboard/export', params, `relatorio-de-vendas.${format}`)
}

export type CustomerRow = { customer_id: string; name: string; phone: string | null; orders: number; total_spent: string; last_order_at: string; days_since: number }
export type Insights = {
  period_start: string
  period_end: string
  kpis: {
    customers: number; new_customers: number; returning_customers: number; returning_rate: number
    items_per_order: number; cancellation_rate: number; cancelled_orders: number
    avg_prep_minutes: number | null; avg_delivery_minutes: number | null
    coupon_orders: number; coupon_revenue: string; discount_total: string
    projected_revenue: string | null; revenue_so_far: string
  }
  heatmap: { weekday: number; hour: number; orders: number; revenue: string }[]
  comparison: { day: number; current: string | null; previous: string | null }[]
  abc: { product_name: string; quantity: number; revenue: string; share: number; cumulative: number; grade: 'A' | 'B' | 'C' }[]
  tickets_by_service: { service_type: string; orders: number; average_ticket: string; revenue: string }[]
  top_customers: CustomerRow[]
  at_risk: CustomerRow[]
  cancellation_reasons: { reason: string; count: number }[]
}

export async function getInsights(period: Period, start?: string, end?: string) {
  const { data } = await api.get<Insights>('/analytics/insights', { params: { period, start: start || undefined, end: end || undefined } })
  return data
}
