import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './AuthProvider'
import type { UserRole } from '../../types'

export function LoadingScreen() {
  return <div className="auth-loading">Carregando…</div>
}

export function ProtectedRoute() {
  const { user, isLoading } = useAuth()
  const location = useLocation()
  if (isLoading) return <LoadingScreen />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <Outlet />
}

export function RoleRoute({ roles }: { roles: UserRole[] }) {
  const { user } = useAuth()
  if (user && !roles.includes(user.role)) return <Navigate to="/painel/pedidos" replace />
  return <Outlet />
}
