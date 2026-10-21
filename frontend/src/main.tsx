import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Toaster } from 'sonner'
import { AppRouter } from './app/router'
import './styles/globals.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppRouter />
    {/* Top: the bottom of the screen belongs to the cart and the table bill bars. */}
    <Toaster position="top-center" richColors visibleToasts={3} />
  </StrictMode>,
)
