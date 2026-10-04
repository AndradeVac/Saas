import type { ReactNode } from 'react'

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  )
}

export function EmptyState({ icon, title, hint, action }: { icon?: ReactNode; title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      {icon && <div className="empty-icon">{icon}</div>}
      <strong>{title}</strong>
      {hint && <p className="muted">{hint}</p>}
      {action}
    </div>
  )
}

export function Skeleton({ lines = 3, height = 18 }: { lines?: number; height?: number }) {
  return (
    <div className="skeleton-stack" aria-hidden="true">
      {Array.from({ length: lines }, (_, i) => <div className="skeleton" key={i} style={{ height, width: `${90 - (i % 3) * 18}%` }} />)}
    </div>
  )
}

export function Spinner() {
  return <span className="spinner" role="status" aria-label="Carregando" />
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  if (!message) return null
  return (
    <div className="alert error" role="alert">
      <span>{message}</span>
      {onRetry && <button className="btn small" onClick={onRetry}>Tentar de novo</button>}
    </div>
  )
}
