import { api } from './api'
import type { Page, UserRole } from '../types'

export type Customer = {
  id: string
  name: string
  phone: string | null
  notes: string | null
  active: boolean
  created_at: string
  orders_count: number
  total_spent: string
  last_order_at: string | null
}

export type CustomerQuery = { q?: string; active?: boolean; sort?: 'name' | 'recent' | 'spent'; page?: number; page_size?: number }

export const getCustomers = async (query: CustomerQuery = {}) =>
  (await api.get<Page<Customer>>('/customers', { params: query })).data
export const createCustomer = async (payload: { name: string; phone?: string | null; notes?: string | null }) =>
  (await api.post<Customer>('/customers', payload)).data
export const updateCustomer = async (id: string, payload: Partial<Pick<Customer, 'name' | 'phone' | 'notes' | 'active'>>) =>
  (await api.patch<Customer>(`/customers/${id}`, payload)).data

export type TeamUser = { id: string; name: string; email: string; role: UserRole; active: boolean }
export const getUsers = async () => (await api.get<TeamUser[]>('/users')).data
export const createUser = async (payload: { name: string; email: string; password: string; role: UserRole }) =>
  (await api.post<TeamUser>('/users', payload)).data
export const updateUser = async (id: string, payload: { name?: string; role?: UserRole }) =>
  (await api.patch<TeamUser>(`/users/${id}`, payload)).data
export const setUserActive = async (id: string, active: boolean) =>
  (await api.patch<TeamUser>(`/users/${id}/status`, { active })).data
export const resetUserPassword = async (id: string, new_password: string) => {
  await api.post(`/users/${id}/password`, { new_password })
}

export type AuditEntry = {
  id: string
  actor_name: string | null
  action: string
  entity_type: string
  details: string | null
  created_at: string
}
export const getAudit = async (params: { entity_type?: string; page?: number; page_size?: number }) =>
  (await api.get<Page<AuditEntry>>('/audit', { params })).data
