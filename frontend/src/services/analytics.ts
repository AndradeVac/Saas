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

export const downloadDashboard = (period: Period, format: 'xlsx' | 'pdf') =>
  downloadCsv('/analytics/dashboard/export', new URLSearchParams({ period, format }), `dashboard-${period}.${format}`)
