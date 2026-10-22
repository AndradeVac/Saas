// Error reporting (Sentry), loaded only when VITE_SENTRY_DSN is set so the customer menu stays light otherwise.
// Privacy: no user data, URLs keep only the path (query strings such as ?k= table codes are dropped).
type Reporter = { captureException: (error: unknown) => void }
let reporter: Reporter | null = null

export function initMonitoring() {
  const dsn = import.meta.env.VITE_SENTRY_DSN
  if (!dsn) return
  void import('@sentry/react').then((Sentry) => {
    Sentry.init({
      dsn,
      environment: import.meta.env.MODE,
      tracesSampleRate: 0,
      beforeSend(event) {
        if (event.request?.url) event.request.url = event.request.url.split('?')[0]
        delete event.user
        return event
      },
    })
    reporter = Sentry
  })
}

export const reportError = (error: unknown) => reporter?.captureException(error)
