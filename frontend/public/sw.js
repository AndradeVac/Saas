// Service worker: shows "Novo pedido" pushed by the server, even with the panel closed.
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))

self.addEventListener('push', (event) => {
  let data = { title: 'Novo pedido', body: '', url: '/painel/pedidos', tag: 'novo-pedido' }
  try { data = { ...data, ...event.data.json() } } catch { /* plain text push */ }
  event.waitUntil(self.registration.showNotification(data.title, {
    body: data.body, tag: data.tag, renotify: true, requireInteraction: true,
    icon: '/icon-192.png', badge: '/icon-192.png', data: { url: data.url }, vibrate: [200, 100, 200],
  }))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = (event.notification.data && event.notification.data.url) || '/painel/pedidos'
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
    const open = windows.find((w) => w.url.includes('/painel'))
    if (open) { open.navigate(url); return open.focus() }
    return self.clients.openWindow(url)
  }))
})
