import { api } from './api'
import type { BusinessType, OpeningHours, PaymentMethod, PublicTenant, ServiceType, TenantSettings } from '../types'

export const getTenant = async () => (await api.get<PublicTenant>('/tenant')).data
export const getTenantSettings = async () => (await api.get<TenantSettings>('/tenant/settings')).data

export type SettingsUpdate = Partial<{
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
  hours_mode: 'MANUAL' | 'SCHEDULE'
  opening_hours: OpeningHours
  enabled_services: ServiceType[]
  accepted_payments: PaymentMethod[]
  delivery_fee: string
  min_order_value: string
  service_fee_percent: string
}>

export const updateTenantSettings = async (payload: SettingsUpdate) =>
  (await api.patch<TenantSettings>('/tenant/settings', payload)).data

export type UploadResult = { url: string; size: number; used_bytes: number; quota_bytes: number }

export async function uploadImage(file: File) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<UploadResult>('/media', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60_000,
  })
  return data
}

export const getMediaUsage = async () => (await api.get<UploadResult>('/media-usage')).data
