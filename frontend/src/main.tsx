import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Toaster } from 'sonner'
import { AppRouter } from './app/router'
import { ErrorBoundary } from './components/ErrorBoundary'
import { initMonitoring, reportError } from './lib/monitoring'
import './styles/globals.css'

initMonitoring()
// Errors outside React rendering (async handlers, failed promises) are reported too.
window.addEventListener('unhandledrejection', (event) => reportError(event.reason))

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <AppRouter />
    </ErrorBoundary>
    {/* Top: the bottom of the screen belongs to the cart and the table bill bars. */}
    <Toaster position="top-center" richColors visibleToasts={3} />
  </StrictMode>,
)
