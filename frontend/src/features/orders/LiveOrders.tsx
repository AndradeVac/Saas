import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type PropsWithChildren } from 'react'
import { toast } from 'sonner'
import { readJson, writeJson } from '../../lib/storage'
import { formatMoney } from '../../lib/format'
import { printTicket } from '../../lib/ticket'
import { getBoard, type Order } from '../../services/orders'

const POLL_MS = 8000
const SOUND_KEY = 'mesa-sound'
const PRINT_KEY = 'mesa-auto-print'
// An order nobody has opened keeps ringing, so a busy counter does not miss it.
const REMIND_MS = 30_000

type LiveValue = {
  orders: Order[]
  loading: boolean
  offline: boolean
  newCount: number
  freshIds: Set<string>
  soundOn: boolean
  setSoundOn: (on: boolean) => void
  autoPrint: boolean
  setAutoPrint: (on: boolean) => void
  refresh: () => Promise<void>
  replace: (order: Order) => void
}

const LiveContext = createContext<LiveValue | null>(null)

export function beep() {
  try {
    const Context = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
    const audio = new Context()
    const now = audio.currentTime
    ;[880, 1175].forEach((frequency, i) => {
      const oscillator = audio.createOscillator()
      const gain = audio.createGain()
      oscillator.frequency.value = frequency
      oscillator.connect(gain)
      gain.connect(audio.destination)
      gain.gain.setValueAtTime(0.0001, now + i * 0.18)
      gain.gain.exponentialRampToValueAtTime(0.25, now + i * 0.18 + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.18 + 0.28)
      oscillator.start(now + i * 0.18)
      oscillator.stop(now + i * 0.18 + 0.3)
    })
    window.setTimeout(() => void audio.close(), 900)
  } catch {
    // Audio is a nicety; the visual alert still shows.
  }
}

/** Keeps the kitchen board fresh for the whole panel, and alerts when a new order arrives. */
function notify(title: string, body: string) {
  try {
    if (!('Notification' in window) || Notification.permission !== 'granted' || !document.hidden) return
    const notification = new Notification(title, { body, icon: '/icon-192.png', tag: 'novo-pedido', requireInteraction: true })
    notification.onclick = () => { window.focus(); notification.close() }
  } catch {
    // Some browsers (iOS in a tab) do not allow page notifications; the sound and the title still work.
  }
}

export function LiveOrdersProvider({ children, storeName = '' }: PropsWithChildren<{ storeName?: string }>) {
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [offline, setOffline] = useState(false)
  const [freshIds, setFreshIds] = useState<Set<string>>(new Set())
  const [soundOn, setSoundState] = useState(() => readJson<boolean>(SOUND_KEY, true))
  const [autoPrint, setAutoPrintState] = useState(() => readJson<boolean>(PRINT_KEY, false))
  const known = useRef<Set<string> | null>(null)
  const soundRef = useRef(soundOn)
  soundRef.current = soundOn
  const printRef = useRef(autoPrint)
  printRef.current = autoPrint
  const setAutoPrint = useCallback((on: boolean) => { setAutoPrintState(on); writeJson(PRINT_KEY, on) }, [])

  const setSoundOn = useCallback((on: boolean) => {
    setSoundState(on)
    writeJson(SOUND_KEY, on)
    if (on) beep() // also unlocks audio playback, which browsers only allow after a click
  }, [])

  const refresh = useCallback(async () => {
    try {
      const data = await getBoard()
      setOffline(false)
      const ids = new Set(data.map((o) => o.id))
      if (known.current) {
        const arrived = data.filter((o) => !known.current!.has(o.id) && o.status === 'RECEIVED')
        if (arrived.length > 0) {
          setFreshIds((current) => new Set([...current, ...arrived.map((o) => o.id)]))
          if (soundRef.current) beep()
          const title = arrived.length === 1 ? `Novo pedido #${arrived[0].order_number}` : `${arrived.length} novos pedidos`
          toast.info(title)
          notify(title, arrived.map((o) => `${o.customer_name ?? ''} · ${formatMoney(o.total)}`).join('\n'))
          if (printRef.current) arrived.forEach((o) => printTicket(o, storeName))
        }
      }
      known.current = ids
      setOrders(data)
    } catch {
      setOffline(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
    // Keeps checking with the tab in the background too (that is when orders were being missed).
    const timer = window.setInterval(() => void refresh(), POLL_MS)
    const onVisible = () => { if (!document.hidden) void refresh() }
    document.addEventListener('visibilitychange', onVisible)
    return () => { window.clearInterval(timer); document.removeEventListener('visibilitychange', onVisible) }
  }, [refresh])

  const newCount = useMemo(() => orders.filter((o) => o.status === 'RECEIVED').length, [orders])

  // Reminder: rings again while a new order waits, until someone moves it forward.
  useEffect(() => {
    if (newCount === 0) return
    const timer = window.setInterval(() => { if (soundRef.current) beep() }, REMIND_MS)
    return () => window.clearInterval(timer)
  }, [newCount])

  // Keeps the tablet screen on while the panel is open (where supported).
  useEffect(() => {
    let lock: { release: () => Promise<void> } | null = null
    const request = async () => {
      try {
        const wakeLock = (navigator as unknown as { wakeLock?: { request: (type: 'screen') => Promise<{ release: () => Promise<void> }> } }).wakeLock
        if (wakeLock && !document.hidden) lock = await wakeLock.request('screen')
      } catch {
        // Not allowed (battery saver, old browser): nothing to do.
      }
    }
    void request()
    const onVisible = () => { if (!document.hidden) void request() }
    document.addEventListener('visibilitychange', onVisible)
    return () => { document.removeEventListener('visibilitychange', onVisible); void lock?.release() }
  }, [])

  // Tab title shows how many orders wait for the kitchen.
  useEffect(() => {
    const base = document.title.replace(/^\(\d+\)\s*/, '')
    document.title = newCount > 0 ? `(${newCount}) ${base}` : base
    return () => { document.title = base }
  }, [newCount])

  const replace = useCallback((order: Order) => {
    setOrders((current) => current.map((o) => (o.id === order.id ? order : o)))
  }, [])

  const value = useMemo(
    () => ({ orders, loading, offline, newCount, freshIds, soundOn, setSoundOn, autoPrint, setAutoPrint, refresh, replace }),
    [orders, loading, offline, newCount, freshIds, soundOn, setSoundOn, autoPrint, setAutoPrint, refresh, replace],
  )
  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>
}

export function useLiveOrders() {
  const context = useContext(LiveContext)
  if (!context) throw new Error('useLiveOrders precisa estar dentro de LiveOrdersProvider')
  return context
}
