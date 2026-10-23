import { api } from '../services/api'

const supported = () => 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window

function keyBytes(base64: string) {
  const padded = (base64 + '='.repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/')
  return Uint8Array.from(atob(padded), (c) => c.charCodeAt(0))
}

export type PushState = 'unsupported' | 'off' | 'on' | 'blocked'

export async function pushState(): Promise<PushState> {
  if (!supported()) return 'unsupported'
  if (Notification.permission === 'denied') return 'blocked'
  const registration = await navigator.serviceWorker.getRegistration('/')
  const subscription = await registration?.pushManager.getSubscription()
  return subscription && Notification.permission === 'granted' ? 'on' : 'off'
}

/** Asks permission and subscribes this browser to new-order alerts (works with the panel closed). */
export async function enablePush(): Promise<PushState> {
  if (!supported()) return 'unsupported'
  const permission = await Notification.requestPermission()
  if (permission !== 'granted') return permission === 'denied' ? 'blocked' : 'off'
  const { data } = await api.get<{ key: string | null }>('/push/public-key')
  const registration = await navigator.serviceWorker.register('/sw.js')
  await navigator.serviceWorker.ready
  if (!data.key) return 'on' // server push not configured: page notifications still work while the panel is open
  const subscription = await registration.pushManager.getSubscription()
    ?? await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(data.key) })
  const json = subscription.toJSON() as { endpoint: string; keys: { p256dh: string; auth: string } }
  await api.post('/push/subscribe', { endpoint: json.endpoint, keys: json.keys })
  return 'on'
}

/** Customer side: a notification on this phone when the order is being prepared / is ready (no login). */
export async function subscribeOrderPush(orderToken: string): Promise<PushState> {
  if (!supported()) return 'unsupported'
  const permission = await Notification.requestPermission()
  if (permission !== 'granted') return permission === 'denied' ? 'blocked' : 'off'
  const { data } = await api.get<{ key: string | null }>('/push/public-key')
  if (!data.key) return 'unsupported'
  const registration = await navigator.serviceWorker.register('/sw.js')
  await navigator.serviceWorker.ready
  const subscription = await registration.pushManager.getSubscription()
    ?? await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(data.key) })
  const json = subscription.toJSON() as { endpoint: string; keys: { p256dh: string; auth: string } }
  await api.post(`/public/orders/${orderToken}/push`, { endpoint: json.endpoint, keys: json.keys })
  return 'on'
}

export const pushSupported = supported
