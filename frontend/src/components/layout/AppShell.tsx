import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  ClipboardList,
  Crown,
  ExternalLink,
  History,
  Lock,
  LayoutDashboard,
  Menu,
  Moon,
  Package,
  Settings,
  ShieldCheck,
  Sun,
  Tags,
  Ticket,
  UserCog,
  UsersRound,
  X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useAuth } from '../../features/auth/AuthProvider'
import { Brand } from '../../features/auth/LoginPage'
import { LiveOrdersProvider, useLiveOrders } from '../../features/orders/LiveOrders'
import { useTenant } from '../../features/tenant/TenantProvider'
import { getThemeMode, setThemeMode, type ThemeMode } from '../../lib/theme'
import { PlanProvider, usePlan } from '../../features/plans/PlanProvider'
import type { FeatureKey } from '../../services/plans'

type Item = { label: string; to: string; icon: typeof Menu; end?: boolean; badge?: boolean; feature?: FeatureKey }

const operation: Item[] = [
  { label: 'Visão geral', to: '/painel', icon: LayoutDashboard, end: true },
  { label: 'Pedidos', to: '/painel/pedidos', icon: ClipboardList, end: true, badge: true },
  { label: 'Histórico', to: '/painel/historico', icon: History },
  { label: 'Clientes', to: '/painel/clientes', icon: UsersRound },
]
const management: Item[] = [
  { label: 'Produtos', to: '/painel/produtos', icon: Package },
  { label: 'Categorias', to: '/painel/categorias', icon: Tags },
  { label: 'Cupons', to: '/painel/cupons', icon: Ticket, feature: 'coupons' },
  { label: 'Equipe', to: '/painel/equipe', icon: UserCog },
  { label: 'Auditoria', to: '/painel/auditoria', icon: ShieldCheck, feature: 'audit' },
  { label: 'Configurações', to: '/painel/configuracoes', icon: Settings },
  { label: 'Meu plano', to: '/painel/plano', icon: Crown },
]

function NavItems({ items, onNavigate }: { items: Item[]; onNavigate: () => void }) {
  const { newCount } = useLiveOrders()
  const { has } = usePlan()
  return (
    <>
      {items.map(({ label, to, icon: Icon, end, badge, feature }) => (
        <NavLink key={to} to={to} end={end} onClick={onNavigate}>
          <Icon size={18} /> {label}
          {badge && newCount > 0 && <span className="nav-count" aria-label={`${newCount} pedidos novos`}>{newCount}</span>}
          {feature && !has(feature) && <Lock size={13} className="nav-lock" aria-label="Disponível nos planos pagos" />}
        </NavLink>
      ))}
    </>
  )
}

/** Sidebar card: trial countdown and usage, always one click away from subscribing. */
function PlanCard({ onNavigate }: { onNavigate: () => void }) {
  const { status } = usePlan()
  if (!status || status.status !== 'TRIAL') return null
  const total = status.plan.max_orders
  const days = status.trial_days_left ?? 0
  return (
    <NavLink to="/painel/plano" className="plan-chip" onClick={onNavigate}>
      <span className="plan-chip-head"><Crown size={15} /> Degustação</span>
      <span className="plan-chip-text">
        {status.trial_expired ? 'Teste encerrado' : `${days} ${days === 1 ? 'dia restante' : 'dias restantes'}`}
        {total !== null && ` · ${status.usage.orders}/${total} pedidos`}
      </span>
      <span className="btn primary small block">Assinar agora</span>
    </NavLink>
  )
}

/** Top-of-page warning when the plan stops the menu from taking orders. */
function PlanBanner() {
  const { status } = usePlan()
  if (!status || status.can_take_orders) return null
  return (
    <div className="alert error no-print" style={{ margin: '12px 16px 0' }}>
      <span>{status.trial_expired ? 'Seu período de teste terminou' : 'Você usou todos os pedidos do teste'}: o cardápio está no ar, mas não aceita novos pedidos.</span>
      <NavLink className="btn small" to="/painel/plano">Ver planos</NavLink>
    </div>
  )
}

export function AppShell() {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<ThemeMode>(getThemeMode)
  const { user, logout } = useAuth()
  const { tenant } = useTenant()
  const { pathname } = useLocation()
  const isAdmin = user?.role === 'ADMIN'
  const close = () => setOpen(false)

  useEffect(close, [pathname])

  const dark = mode === 'dark' || (mode === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches)
  const toggleTheme = () => {
    const next: ThemeMode = dark ? 'light' : 'dark'
    setMode(next)
    setThemeMode(next)
  }

  return (
    <PlanProvider>
    <LiveOrdersProvider>
      <div className="app-shell">
        <aside className={`sidebar ${open ? 'open' : ''}`} aria-label="Menu do painel">
          <div className="sidebar-head">
            <Brand name={tenant.name} logo={tenant.logo_url} />
            <button className="icon-btn mobile-only" onClick={close} aria-label="Fechar menu"><X size={18} /></button>
          </div>
          <nav>
            <span className="nav-label">Operação</span>
            <NavItems items={isAdmin ? operation : operation.filter((i) => !i.end || i.to !== '/painel')} onNavigate={close} />
            {isAdmin && <>
              <span className="nav-label">Gestão</span>
              <NavItems items={management} onNavigate={close} />
            </>}
          </nav>
          <div className="sidebar-foot">
            {isAdmin && <PlanCard onNavigate={close} />}
            <a className="nav-link-plain" href="/" target="_blank" rel="noreferrer"><ExternalLink size={16} /> Ver meu cardápio</a>
            <button className="nav-link-plain" onClick={toggleTheme} style={{ background: 'none', border: 0, textAlign: 'left' }}>
              {dark ? <Sun size={16} /> : <Moon size={16} />} {dark ? 'Tema claro' : 'Tema escuro'}
            </button>
            <div className="user-chip">
              <div><strong>{user?.name}</strong><span>{isAdmin ? 'Administrador' : 'Operador'}</span></div>
              <button className="btn small" onClick={logout}>Sair</button>
            </div>
          </div>
        </aside>
        {open && <button className="overlay" onClick={close} aria-label="Fechar menu" />}
        <main className="main">
          <header className="topbar">
            <button className="icon-btn" onClick={() => setOpen(true)} aria-label="Abrir menu"><Menu size={20} /></button>
            <strong>{tenant.name}</strong>
          </header>
          <PlanBanner />
          <Outlet />
        </main>
      </div>
    </LiveOrdersProvider>
    </PlanProvider>
  )
}
