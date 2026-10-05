import axios from 'axios'
import { getTenantSlug } from '../lib/tenant'

const apiBaseUrl = import.meta.env.VITE_API_URL ?? '/api'
// One session per tenant: in development without subdomains every tenant shares the localhost origin,
// so a single key would let logging into one account knock out another open tab.
const tokenKey = () => `mesa-digital-token:${getTenantSlug() ?? ''}`
export const SESSION_EXPIRED_EVENT = 'mesa-digital:session-expired'
/** Fired with `{ detail: { message, feature } }` when the API answers 402 (plan limit); the panel opens the upgrade prompt. */
export const PLAN_LIMIT_EVENT = 'mesa-digital:plan-limit'
export type PlanLimitDetail = { message: string; feature: string }

export const api = axios.create({
  baseURL: apiBaseUrl,
  headers: { 'Content-Type': 'application/json' },
  timeout: 20_000,
})

export const tokenStorage = {
  get: () => localStorage.getItem(tokenKey()),
  set: (token: string) => localStorage.setItem(tokenKey(), token),
  clear: () => localStorage.removeItem(tokenKey()),
}

export const isPlanLimitError = (error: unknown) => axios.isAxiosError(error) && error.response?.status === 402

/** Extracts the API's `detail` message, falling back to a generic text. */
export function apiErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && typeof detail[0]?.msg === 'string') return detail[0].msg.replace(/^Value error, /, '')
  }
  return fallback
}

api.interceptors.request.use((config) => {
  const slug = getTenantSlug()
  if (slug) config.headers['X-Tenant'] = slug
  const token = tokenStorage.get()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 402) {
      // Downloads ask for a Blob, so the JSON body may need decoding first.
      let body = error.response.data
      if (body instanceof Blob) body = await body.text().then((text) => JSON.parse(text)).catch(() => ({}))
      const detail: PlanLimitDetail = { message: body?.detail ?? 'Recurso indisponível no seu plano.', feature: body?.feature ?? '' }
      window.dispatchEvent(new CustomEvent(PLAN_LIMIT_EVENT, { detail }))
    }
    if (error.response?.status === 401 && tokenStorage.get()) {
      tokenStorage.clear()
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT))
    }
    return Promise.reject(error)
  },
)
