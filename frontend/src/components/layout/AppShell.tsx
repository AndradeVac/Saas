import { NavLink, Outlet } from 'react-router-dom'
import {
  ClipboardList,
  ExternalLink,
  LayoutDashboard,
  Menu,
  Package,
  Settings,
  ShieldCheck,
  Tags,
  UserCog,
  UsersRound,
  X,
} from 'lucide-react'
import { useState } from 'react'
import { useAuth } from '../../features/auth/AuthProvider'
import { Brand } from '../../features/auth/LoginPage'
import { useTenant } from '../../features/tenant/TenantProvider'

const operation = [
  { label: 'Visão geral', to: '/painel', icon: LayoutDashboard, end: true, admin: true },
  { label: 'Pedidos', to: '/painel/pedidos', icon: ClipboardList },
  { label: 'Clientes', to: '/painel/clientes', icon: UsersRound },
]
const management = [
  { label: 'Produtos', to: '/painel/produtos', icon: Package },
  { label: 'Categorias', to: '/painel/categorias', icon: Tags },
  { label: 'Equipe', to: '/painel/equipe', icon: UserCog },
  { label: 'Auditoria', to: '/painel/auditoria', icon: ShieldCheck },
  { label: 'Configurações', to: '/painel/configuracoes', icon: Settings },
]

export function AppShell() {
  const [open, setOpen] = useState(false)
  const { user, logout } = useAuth()
  const { tenant } = useTenant()
  const isAdmin = user?.role === 'ADMIN'
  const close = () => setOpen(false)

  const link = ({ label, to, icon: Icon, end }: (typeof operation)[number]) => (
    <NavLink key={to} to={to} end={end} onClick={close}><Icon size={18} /> {label}</NavLink>
  )

  return (
    <div className="app-shell">
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="sidebar-head">
          <Brand name={tenant.name} logo={tenant.logo_url} />
          <button className="icon-btn mobile-only" onClick={close} aria-label="Fechar menu"><X size={18} /></button>
        </div>
        <nav>
          <span className="nav-label">Operação</span>
          {operation.filter((item) => !item.admin || isAdmin).map(link)}
          {isAdmin && <>
            <span className="nav-label">Gestão</span>
            {management.map(link)}
          </>}
        </nav>
        <div className="sidebar-foot">
          <a className="nav-link-plain" href="/" target="_blank" rel="noreferrer"><ExternalLink size={16} /> Ver cardápio</a>
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
        <Outlet />
      </main>
    </div>
  )
}
