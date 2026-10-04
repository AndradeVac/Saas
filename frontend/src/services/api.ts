import axios from 'axios'
import { getTenantSlug } from '../lib/tenant'

const apiBaseUrl = import.meta.env.VITE_API_URL ?? '/api'
const TOKEN_KEY = 'mesa-digital-token'
export const SESSION_EXPIRED_EVENT = 'mesa-digital:session-expired'

export const api = axios.create({
  baseURL: apiBaseUrl,
  headers: { 'Content-Type': 'application/json' },
  timeout: 20_000,
})

// Tokens live in localStorage, which is per-origin, so every tenant subdomain has its own session.
export const tokenStorage = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

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
  (error) => {
    if (error.response?.status === 401 && tokenStorage.get()) {
      tokenStorage.clear()
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT))
    }
    return Promise.reject(error)
  },
)
