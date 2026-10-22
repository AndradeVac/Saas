import { Component, type ErrorInfo, type ReactNode } from 'react'
import { reportError } from '../lib/monitoring'

/** Last line of defence: a friendly screen (and an error report) instead of a blank page. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    reportError(error)
    console.error(error, info.componentStack)
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <main className="center-page">
        <div className="card auth-card" style={{ textAlign: 'center' }}>
          <h1>Algo deu errado</h1>
          <p className="muted">Já fomos avisados e vamos corrigir. Tente carregar a página de novo.</p>
          <button className="btn primary block large" onClick={() => window.location.reload()}>Recarregar</button>
        </div>
      </main>
    )
  }
}
