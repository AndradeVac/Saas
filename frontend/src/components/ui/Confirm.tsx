import { createContext, useCallback, useContext, useRef, useState, type PropsWithChildren } from 'react'
import { Modal } from './Modal'

type ConfirmOptions = {
  title: string
  message?: string
  confirmLabel?: string
  danger?: boolean
  /** Ask for a typed reason (e.g. cancelling an order). The promise resolves with the text. */
  reason?: { label: string; required?: boolean }
}

type Resolver = (result: { ok: boolean; reason: string }) => void
const ConfirmContext = createContext<((options: ConfirmOptions) => Promise<{ ok: boolean; reason: string }>) | null>(null)

/** Replaces window.confirm/prompt with an in-app dialog. */
export function ConfirmProvider({ children }: PropsWithChildren) {
  const [options, setOptions] = useState<ConfirmOptions | null>(null)
  const [reason, setReason] = useState('')
  const resolver = useRef<Resolver | null>(null)

  const confirm = useCallback((next: ConfirmOptions) => {
    setReason('')
    setOptions(next)
    return new Promise<{ ok: boolean; reason: string }>((resolve) => { resolver.current = resolve })
  }, [])

  const close = (ok: boolean) => {
    resolver.current?.({ ok, reason: reason.trim() })
    resolver.current = null
    setOptions(null)
  }

  const blocked = Boolean(options?.reason?.required) && reason.trim().length === 0

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {options && (
        <Modal
          title={options.title}
          size="sm"
          onClose={() => close(false)}
          footer={
            <>
              <button className="btn" onClick={() => close(false)}>Voltar</button>
              <button className={`btn ${options.danger ? 'danger-solid' : 'primary'}`} disabled={blocked} onClick={() => close(true)}>
                {options.confirmLabel ?? 'Confirmar'}
              </button>
            </>
          }
        >
          {options.message && <p className="muted">{options.message}</p>}
          {options.reason && (
            <label className="field">
              <span>{options.reason.label}</span>
              <textarea rows={3} autoFocus maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
            </label>
          )}
        </Modal>
      )}
    </ConfirmContext.Provider>
  )
}

export function useConfirm() {
  const confirm = useContext(ConfirmContext)
  if (!confirm) throw new Error('useConfirm precisa estar dentro de ConfirmProvider')
  return confirm
}
