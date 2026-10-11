import { lazy, Suspense, type ComponentType } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ConfirmProvider } from '../components/ui/Confirm'
import { AuthProvider } from '../features/auth/AuthProvider'
import { LoadingScreen, ProtectedRoute, RoleRoute } from '../features/auth/ProtectedRoute'
import { TenantProvider } from '../features/tenant/TenantProvider'
import { getTenantSlug } from '../lib/tenant'

// Pages are split into separate chunks so the customer menu stays light.
function page<T extends Record<string, unknown>>(load: () => Promise<T>, name: keyof T) {
  return lazy(() => load().then((module) => ({ default: module[name] as ComponentType })))
}

// The panel shell (and the plan gate) stay out of the main bundle the customer menu downloads.
const AppShell = page(() => import('../components/layout/AppShell'), 'AppShell')
const FeatureGate = lazy(() => import('../features/plans/PlanProvider').then((module) => ({ default: module.FeatureGate })))
const LandingPage = page(() => import('../features/platform/LandingPage'), 'LandingPage')
const TermsPage = page(() => import('../features/platform/LegalPages'), 'TermsPage')
const PrivacyPage = page(() => import('../features/platform/LegalPages'), 'PrivacyPage')
const SignupPage = page(() => import('../features/platform/SignupPage'), 'SignupPage')
const LoginPage = page(() => import('../features/auth/LoginPage'), 'LoginPage')
const ForgotPasswordPage = page(() => import('../features/auth/PasswordResetPages'), 'ForgotPasswordPage')
const ResetPasswordPage = page(() => import('../features/auth/PasswordResetPages'), 'ResetPasswordPage')
const MenuPage = page(() => import('../features/menu/MenuPage'), 'MenuPage')
const DashboardPage = page(() => import('../features/dashboard/DashboardPage'), 'DashboardPage')
const OrdersPage = page(() => import('../features/orders/OrdersPage'), 'OrdersPage')
const TablesPage = page(() => import('../features/tables/TablesPage'), 'TablesPage')
const HistoryPage = page(() => import('../features/orders/HistoryPage'), 'HistoryPage')
const NewOrderPage = page(() => import('../features/orders/NewOrderPage'), 'NewOrderPage')
const OrderDetailPage = page(() => import('../features/orders/OrderDetailPage'), 'OrderDetailPage')
const ProductsPage = page(() => import('../features/products/ProductsPage'), 'ProductsPage')
const CategoriesPage = page(() => import('../features/categories/CategoriesPage'), 'CategoriesPage')
const CouponsPage = page(() => import('../features/coupons/CouponsPage'), 'CouponsPage')
const CustomersPage = page(() => import('../features/customers/CustomersPage'), 'CustomersPage')
const UsersPage = page(() => import('../features/users/UsersPage'), 'UsersPage')
const AuditPage = page(() => import('../features/audit/AuditPage'), 'AuditPage')
const PlanPage = page(() => import('../features/plans/PlanPage'), 'PlanPage')
const SettingsPage = page(() => import('../features/settings/SettingsPage'), 'SettingsPage')

function PlatformRoutes() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/cadastro" element={<SignupPage />} />
      <Route path="/termos" element={<TermsPage />} />
      <Route path="/privacidade" element={<PrivacyPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function TenantRoutes() {
  return (
    <TenantProvider>
      <AuthProvider>
        <ConfirmProvider>
          <Routes>
            <Route path="/" element={<MenuPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/esqueci-senha" element={<ForgotPasswordPage />} />
            <Route path="/redefinir-senha" element={<ResetPasswordPage />} />
            <Route path="/painel" element={<ProtectedRoute />}>
              <Route element={<AppShell />}>
                <Route path="pedidos" element={<OrdersPage />} />
                <Route path="pedidos/novo" element={<NewOrderPage />} />
                <Route path="pedidos/:id" element={<OrderDetailPage />} />
                <Route path="mesas" element={<TablesPage />} />
                <Route path="historico" element={<HistoryPage />} />
                <Route path="clientes" element={<CustomersPage />} />
                <Route element={<RoleRoute roles={['ADMIN']} />}>
                  <Route index element={<DashboardPage />} />
                  <Route path="produtos" element={<ProductsPage />} />
                  <Route path="categorias" element={<CategoriesPage />} />
                  <Route path="cupons" element={<FeatureGate feature="coupons" title="Cupons de desconto"><CouponsPage /></FeatureGate>} />
                  <Route path="equipe" element={<UsersPage />} />
                  <Route path="auditoria" element={<FeatureGate feature="audit" title="Auditoria da equipe"><AuditPage /></FeatureGate>} />
                  <Route path="plano" element={<PlanPage />} />
                  <Route path="configuracoes" element={<SettingsPage />} />
                </Route>
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </ConfirmProvider>
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
