// The tenant is derived from the subdomain: <slug>.<root domain>. No subdomain = the platform site.
export const APP_NAME = import.meta.env.VITE_APP_NAME ?? 'Mesa Digital'
export const ROOT_DOMAIN = (import.meta.env.VITE_ROOT_DOMAIN ?? 'localhost').toLowerCase()

const DEV_KEY = 'mesa-dev-tenant'

export function getTenantSlug(): string | null {
  const host = window.location.hostname.toLowerCase()
  if (host.endsWith(`.${ROOT_DOMAIN}`)) {
    const sub = host.slice(0, -(ROOT_DOMAIN.length + 1))
    return sub && sub !== 'www' && !sub.includes('.') ? sub : null
  }
  // Dev helper for hosts without subdomains: open /?tenant=demo (and /?tenant= to clear).
  if (import.meta.env.DEV) {
    try {
      const params = new URLSearchParams(window.location.search)
      if (params.has('tenant')) {
        const value = params.get('tenant')
        if (value) sessionStorage.setItem(DEV_KEY, value)
        else sessionStorage.removeItem(DEV_KEY)
      }
      return sessionStorage.getItem(DEV_KEY)
    } catch {
      return null
    }
  }
  return null
}

function origin(host: string) {
  const { protocol, port } = window.location
  return `${protocol}//${host}${port ? `:${port}` : ''}`
}

export const tenantUrl = (slug: string, path = '/') => `${origin(`${slug}.${ROOT_DOMAIN}`)}${path}`
export const platformUrl = (path = '/') => `${origin(ROOT_DOMAIN)}${path}`
