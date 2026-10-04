import { createContext, useCallback, useContext, useEffect, useMemo, useState, type PropsWithChildren } from 'react'
import { applyBrand } from '../../lib/theme'
import { getTenantSlug, platformUrl } from '../../lib/tenant'
import { getTenant } from '../../services/admin'
import type { PublicTenant } from '../../types'

type TenantContextValue = {
  tenant: PublicTenant
  refresh: () => Promise<void>
  setTenant: (tenant: PublicTenant) => void
}

const TenantContext = createContext<TenantContextValue | undefined>(undefined)

/** Loads the business behind the current subdomain and applies its branding. */
export function TenantProvider({ children }: PropsWithChildren) {
  const [tenant, setTenantState] = useState<PublicTenant | null>(null)
  const [state, setState] = useState<'loading' | 'missing' | 'error' | 'ready'>('loading')

  const setTenant = useCallback((value: PublicTenant) => {
    setTenantState(value)
    applyBrand(value.primary_color)
    document.title = value.name
  }, [])

  const refresh = useCallback(async () => setTenant(await getTenant()), [setTenant])

  useEffect(() => {
    if (!getTenantSlug()) {
      setState('missing')
      return
    }
    getTenant()
      .then((value) => { setTenant(value); setState('ready') })
      .catch((error) => setState(error?.response?.status === 404 ? 'missing' : 'error'))
  }, [setTenant])

  const value = useMemo(() => (tenant ? { tenant, refresh, setTenant } : undefined), [tenant, refresh, setTenant])

  if (state === 'loading') return <div className="auth-loading">Carregando…</div>
  if (state === 'missing') {
    return (
      <div className="auth-loading column">
        <h1>Estabelecimento não encontrado</h1>
        <p>Confira o endereço digitado.</p>
        <a className="btn" href={platformUrl('/')}>Ir para a página inicial</a>
      </div>
    )
  }
  if (state === 'error' || !value) {
    return (
      <div className="auth-loading column">
        <h1>Não foi possível carregar</h1>
        <p>Verifique sua conexão e tente novamente.</p>
        <button className="btn" onClick={() => window.location.reload()}>Tentar de novo</button>
      </div>
    )
  }
  return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>
}

export function useTenant() {
  const context = useContext(TenantContext)
  if (!context) throw new Error('useTenant precisa estar dentro de TenantProvider')
  return context
}
