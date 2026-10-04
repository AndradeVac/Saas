import { api } from './api'
import type { BusinessType } from '../types'

export type SignupPayload = {
  business_name: string
  business_type: BusinessType
  slug: string
  phone?: string
  admin_name: string
  email: string
  password: string
}

export async function signup(payload: SignupPayload) {
  const { data } = await api.post<{ slug: string; name: string; url: string; login_url: string }>('/platform/signup', payload)
  return data
}

export async function checkSlug(slug: string) {
  const { data } = await api.get<{ slug: string; available: boolean; reason: string | null }>('/platform/slug-available', { params: { slug } })
  return data
}
