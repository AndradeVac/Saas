import { lazy, Suspense, type ComponentType } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '../components/layout/AppShell'
import { AuthProvider } from '../features/auth/AuthProvider'
import { LoadingScreen, ProtectedRoute, RoleRoute } from '../features/auth/ProtectedRoute'
import { TenantProvider } from '../features/tenant/TenantProvider'
import { getTenantSlug } from '../lib/tenant'

// Pages are split into separate chunks so the customer menu stays light.
function page<T extends Record<string, unknown>>(load: () => Promise<T>, name: keyof T) {
  return lazy(() => load().then((module) => ({ default: module[name] as ComponentType })))
}

const LandingPage = page(() => import('../features/platform/LandingPage'), 'LandingPage')
const SignupPage = page(() => import('../features/platform/SignupPage'), 'SignupPage')
const LoginPage = page(() => import('../features/auth/LoginPage'), 'LoginPage')
const MenuPage = page(() => import('../features/menu/MenuPage'), 'MenuPage')
const DashboardPage = page(() => import('../features/dashboard/DashboardPage'), 'DashboardPage')
const OrdersPage = page(() => import('../features/orders/OrdersPage'), 'OrdersPage')
const NewOrderPage = page(() => import('../features/orders/NewOrderPage'), 'NewOrderPage')
const OrderDetailPage = page(() => import('../features/orders/OrderDetailPage'), 'OrderDetailPage')
const ProductsPage = page(() => import('../features/products/ProductsPage'), 'ProductsPage')
const CategoriesPage = page(() => import('../features/categories/CategoriesPage'), 'CategoriesPage')
const CustomersPage = page(() => import('../features/customers/CustomersPage'), 'CustomersPage')
const UsersPage = page(() => import('../features/users/UsersPage'), 'UsersPage')
const AuditPage = page(() => import('../features/audit/AuditPage'), 'AuditPage')
const SettingsPage = page(() => import('../features/settings/SettingsPage'), 'SettingsPage')

function PlatformRoutes() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/cadastro" element={<SignupPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function TenantRoutes() {
  return (
    <TenantProvider>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<MenuPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/painel" element={<ProtectedRoute />}>
            <Route element={<AppShell />}>
              <Route path="pedidos" element={<OrdersPage />} />
              <Route path="pedidos/novo" element={<NewOrderPage />} />
              <Route path="pedidos/:id" element={<OrderDetailPage />} />
              <Route path="clientes" element={<CustomersPage />} />
              <Route element={<RoleRoute roles={['ADMIN']} />}>
                <Route index element={<DashboardPage />} />
                <Route path="produtos" element={<ProductsPage />} />
                <Route path="categorias" element={<CategoriesPage />} />
                <Route path="equipe" element={<UsersPage />} />
                <Route path="auditoria" element={<AuditPage />} />
                <Route path="configuracoes" element={<SettingsPage />} />
              </Route>
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </TenantProvider>
  )
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Suspense fallback={<LoadingScreen />}>
        {getTenantSlug() ? <TenantRoutes /> : <PlatformRoutes />}
      </Suspense>
    </BrowserRouter>
  )
}
