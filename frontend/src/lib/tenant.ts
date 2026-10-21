// The tenant is derived from the subdomain: <slug>.<root domain>. No subdomain = the platform site.
export const APP_NAME = import.meta.env.VITE_APP_NAME ?? 'Mesa Digital'
export const ROOT_DOMAIN = (import.meta.env.VITE_ROOT_DOMAIN ?? 'localhost').toLowerCase()

const DEV_KEY = 'mesa-dev-tenant'

// The landing page shows a tenant menu inside an iframe; it must not change the parent tab's remembered tenant.
const embedded = (() => {
  try {
    return window.self !== window.top
  } catch {
    return true
  }
})()

const onTenantSubdomain = () => window.location.hostname.toLowerCase().endsWith(`.${ROOT_DOMAIN}`)

/** Dev without subdomains (Safari does not resolve *.localhost): the tenant travels as ?tenant=<slug>. */
const usesQueryTenant = () => import.meta.env.DEV && !onTenantSubdomain()

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
        if (!embedded) {
          if (value) sessionStorage.setItem(DEV_KEY, value)
          else sessionStorage.removeItem(DEV_KEY)
        }
        return value || null
      }
      return embedded ? null : sessionStorage.getItem(DEV_KEY)
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

function withTenantParam(path: string, slug: string) {
  const url = new URL(path, window.location.origin)
  url.searchParams.set('tenant', slug)
  return url.toString()
}

/** Address of a tenant page: its subdomain, or ?tenant=<slug> when developing without subdomains. */
export const tenantUrl = (slug: string, path = '/') =>
  usesQueryTenant() ? withTenantParam(path, slug) : `${origin(`${slug}.${ROOT_DOMAIN}`)}${path}`
/** The platform site (landing, sign-up); `?tenant=` clears the remembered dev tenant. */
export const platformUrl = (path = '/') => (usesQueryTenant() ? withTenantParam(path, '') : `${origin(ROOT_DOMAIN)}${path}`)
