import { createContext, useCallback, useContext, useEffect, useMemo, useState, type PropsWithChildren } from 'react'
import { toast } from 'sonner'
import { api, SESSION_EXPIRED_EVENT, tokenStorage } from '../../services/api'
import { login as loginRequest, logout as clearSession, type LoginPayload } from '../../services/auth'
import type { UserRole } from '../../types'

export type AuthUser = { id: string; name: string; email: string; role: UserRole; active: boolean }

type AuthContextValue = {
  user: AuthUser | null
  isLoading: boolean
  login: (payload: LoginPayload) => Promise<AuthUser>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!tokenStorage.get()) {
      setIsLoading(false)
      return
    }
    api.get<AuthUser>('/auth/me')
      .then(({ data }) => setUser(data))
      .catch(() => clearSession())
      .finally(() => setIsLoading(false))
  }, [])

  useEffect(() => {
    function handleExpired() {
      toast.warning('Sua sessão expirou. Entre novamente.')
      setUser(null)
    }
    window.addEventListener(SESSION_EXPIRED_EVENT, handleExpired)
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, handleExpired)
  }, [])

  const login = useCallback(async (payload: LoginPayload) => {
    await loginRequest(payload)
    const { data } = await api.get<AuthUser>('/auth/me')
    setUser(data)
    return data
  }, [])

  const logout = useCallback(() => {
    clearSession()
    setUser(null)
  }, [])

  const value = useMemo(() => ({ user, isLoading, login, logout }), [user, isLoading, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth precisa estar dentro de AuthProvider')
  return context
}
