import { api } from './api'
import type { OptionGroup } from '../types'

export type Category = { id: string; name: string; image_url: string | null; sort_order: number; active: boolean }
export type Product = {
  id: string
  category_id: string
  name: string
  description: string | null
  image_url: string | null
  price: string
  featured: boolean
  available: boolean
  active: boolean
  sort_order: number
  options: OptionGroup[]
}
export type ProductPayload = Partial<Omit<Product, 'id'>> & { category_id: string; name: string; price: string }

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

export type Coupon = {
  id: string
  code: string
  kind: 'PERCENT' | 'FIXED'
  value: string
  min_order: string
  max_uses: number | null
  used_count: number
  expires_at: string | null
  active: boolean
}
export type CouponPayload = {
  code: string
  kind: 'PERCENT' | 'FIXED'
  value: string
  min_order?: string
  max_uses?: number | null
  expires_at?: string | null
}
export const getCoupons = async () => (await api.get<Coupon[]>('/coupons')).data
export const createCoupon = async (payload: CouponPayload) => (await api.post<Coupon>('/coupons', payload)).data
export const updateCoupon = async (id: string, payload: Partial<Pick<Coupon, 'active' | 'value' | 'min_order' | 'max_uses' | 'expires_at'>>) =>
  (await api.patch<Coupon>(`/coupons/${id}`, payload)).data
export const deleteCoupon = async (id: string) => { await api.delete(`/coupons/${id}`) }
