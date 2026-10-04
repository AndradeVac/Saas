import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  ClipboardList,
  ExternalLink,
  History,
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
import { getTenantSettings } from '../../services/tenant'

type Item = { label: string; to: string; icon: typeof Menu; end?: boolean; badge?: boolean }

const operation: Item[] = [
  { label: 'Visão geral', to: '/painel', icon: LayoutDashboard, end: true },
  { label: 'Pedidos', to: '/painel/pedidos', icon: ClipboardList, end: true, badge: true },
  { label: 'Histórico', to: '/painel/historico', icon: History },
  { label: 'Clientes', to: '/painel/clientes', icon: UsersRound },
]
const management: Item[] = [
  { label: 'Produtos', to: '/painel/produtos', icon: Package },
  { label: 'Categorias', to: '/painel/categorias', icon: Tags },
  { label: 'Cupons', to: '/painel/cupons', icon: Ticket },
  { label: 'Equipe', to: '/painel/equipe', icon: UserCog },
  { label: 'Auditoria', to: '/painel/auditoria', icon: ShieldCheck },
  { label: 'Configurações', to: '/painel/configuracoes', icon: Settings },
]

function NavItems({ items, onNavigate }: { items: Item[]; onNavigate: () => void }) {
  const { newCount } = useLiveOrders()
  return (
    <>
      {items.map(({ label, to, icon: Icon, end, badge }) => (
        <NavLink key={to} to={to} end={end} onClick={onNavigate}>
          <Icon size={18} /> {label}
          {badge && newCount > 0 && <span className="nav-count" aria-label={`${newCount} pedidos novos`}>{newCount}</span>}
        </NavLink>
      ))}
    </>
  )
}

function TrialBanner() {
  const [days, setDays] = useState<number | null>(null)
  useEffect(() => {
    getTenantSettings()
      .then((s) => setDays(s.status === 'TRIAL' && s.trial_ends_at ? Math.ceil((new Date(s.trial_ends_at).getTime() - Date.now()) / 86_400_000) : null))
      .catch(() => setDays(null))
  }, [])
  if (days === null || days > 5) return null
  return (
    <div className="alert warn no-print" style={{ margin: '12px 16px 0' }}>
      {days > 0 ? `Seu período de teste termina em ${days} ${days === 1 ? 'dia' : 'dias'}.` : 'Seu período de teste terminou.'} Fale com o suporte para ativar seu plano.
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
          <TrialBanner />
          <Outlet />
        </main>
      </div>
    </LiveOrdersProvider>
  )
}
