import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type PropsWithChildren } from 'react'
import { toast } from 'sonner'
import { readJson, writeJson } from '../../lib/storage'
import { getBoard, type Order } from '../../services/orders'

const POLL_MS = 8000
const SOUND_KEY = 'mesa-sound'

type LiveValue = {
  orders: Order[]
  loading: boolean
  offline: boolean
  newCount: number
  freshIds: Set<string>
  soundOn: boolean
  setSoundOn: (on: boolean) => void
  refresh: () => Promise<void>
  replace: (order: Order) => void
}

const LiveContext = createContext<LiveValue | null>(null)

function beep() {
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
export function LiveOrdersProvider({ children }: PropsWithChildren) {
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [offline, setOffline] = useState(false)
  const [freshIds, setFreshIds] = useState<Set<string>>(new Set())
  const [soundOn, setSoundState] = useState(() => readJson<boolean>(SOUND_KEY, true))
  const known = useRef<Set<string> | null>(null)
  const soundRef = useRef(soundOn)
  soundRef.current = soundOn

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
          toast.info(arrived.length === 1 ? `Novo pedido #${arrived[0].order_number}` : `${arrived.length} novos pedidos`)
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
    const timer = window.setInterval(() => { if (!document.hidden) void refresh() }, POLL_MS)
    const onVisible = () => { if (!document.hidden) void refresh() }
    document.addEventListener('visibilitychange', onVisible)
    return () => { window.clearInterval(timer); document.removeEventListener('visibilitychange', onVisible) }
  }, [refresh])

  const newCount = useMemo(() => orders.filter((o) => o.status === 'RECEIVED').length, [orders])

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
    () => ({ orders, loading, offline, newCount, freshIds, soundOn, setSoundOn, refresh, replace }),
    [orders, loading, offline, newCount, freshIds, soundOn, setSoundOn, refresh, replace],
  )
  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>
}

export function useLiveOrders() {
  const context = useContext(LiveContext)
  if (!context) throw new Error('useLiveOrders precisa estar dentro de LiveOrdersProvider')
  return context
}
