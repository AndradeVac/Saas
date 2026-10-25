import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type PropsWithChildren } from 'react'
import { toast } from 'sonner'
import { getTabs, WAITER_REASONS, type StaffTab } from '../../services/tabs'
import { useTenant } from '../tenant/TenantProvider'
import { beep, useLiveOrders } from '../orders/LiveOrders'

const POLL_MS = 8000

type TablesValue = {
  tabs: StaffTab[]
  loading: boolean
  /** Tables that need someone now: new table to approve or bill requested. */
  attention: number
  refresh: () => Promise<void>
}

const TablesContext = createContext<TablesValue | null>(null)

const needsSomeone = (tab: StaffTab) => tab.alerts.needs_approval || tab.alerts.wants_to_close || tab.alerts.payments_to_confirm > 0 || Boolean(tab.alerts.waiter_call)

/** Watches the open bills for the whole panel and calls the floor staff (sound + toast) when a table needs them. */
export function TablesLiveProvider({ children }: PropsWithChildren) {
  const { tenant } = useTenant()
  const { soundOn } = useLiveOrders()
  const [tabs, setTabs] = useState<StaffTab[]>([])
  const [loading, setLoading] = useState(true)
  const seen = useRef<Map<string, string> | null>(null)
  const seenReports = useRef<Map<string, number>>(new Map())
  const seenCalls = useRef<Map<string, string | null>>(new Map())
  const soundRef = useRef(soundOn)
  soundRef.current = soundOn

  const refresh = useCallback(async () => {
    try {
      const data = await getTabs()
      const before = seen.current
      if (before) {
        // Automation: announce what changed since the last look, once per change.
        for (const tab of data) {
          const was = before.get(tab.id)
          if (tab.alerts.waiter_call && seenCalls.current.get(tab.id) !== tab.alerts.waiter_call) {
            toast.warning(`Mesa ${tab.table_label}: ${WAITER_REASONS[tab.alerts.waiter_call].toLowerCase()}`, { duration: 10000 })
            if (soundRef.current) beep()
          } else if (tab.alerts.needs_approval && was !== 'PENDING') {
            toast.info(`Mesa ${tab.table_label}: novo cliente pedindo. Confirme a mesa.`, { duration: 6000 })
            if (soundRef.current) beep()
          } else if (tab.alerts.payments_to_confirm > (seenReports.current.get(tab.id) ?? 0)) {
            toast.info(`Mesa ${tab.table_label}: cliente pagou com PIX. Confira no banco e confirme.`, { duration: 8000 })
            if (soundRef.current) beep()
          } else if (tab.alerts.wants_to_close && was !== 'CLOSING') {
            toast.info(`Mesa ${tab.table_label} pediu a conta.`, { duration: 6000 })
            if (soundRef.current) beep()
          }
        }
      }
      seen.current = new Map(data.map((tab) => [tab.id, tab.status]))
      seenReports.current = new Map(data.map((tab) => [tab.id, tab.alerts.payments_to_confirm]))
      seenCalls.current = new Map(data.map((tab) => [tab.id, tab.alerts.waiter_call]))
      setTabs(data)
    } catch {
      // Keeps the last known state; the next poll retries.
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!tenant.tabs_enabled) { setLoading(false); return }
    void refresh()
    const timer = window.setInterval(() => { if (!document.hidden) void refresh() }, POLL_MS)
    return () => window.clearInterval(timer)
  }, [tenant.tabs_enabled, refresh])

  const value = useMemo(
    () => ({ tabs, loading, attention: tabs.filter(needsSomeone).length, refresh }),
    [tabs, loading, refresh],
  )
  return <TablesContext.Provider value={value}>{children}</TablesContext.Provider>
}

export function useTablesLive() {
  const context = useContext(TablesContext)
  if (!context) throw new Error('useTablesLive precisa estar dentro de TablesLiveProvider')
  return context
}
