import { toast } from 'sonner'
import type { Order } from '../services/orders'

/** "Seu pedido está pronto" on WhatsApp with one tap, while the automatic WhatsApp is not configured. */
export function offerReadyWhatsapp(order: Order & { public_token?: string }, storeName: string) {
  const digits = (order.customer_phone ?? '').replace(/\D/g, '')
  if (digits.length < 10 || order.table_label) return
  const where = order.service_type === 'DELIVERY' ? 'Ele já está saindo para entrega.' : 'Pode retirar no balcão.'
  const first = (order.customer_name ?? '').split(' ')[0]
  const link = order.public_token ? ` Acompanhe: ${window.location.origin}/?pedido=${order.public_token}` : ''
  const text = `Olá${first ? `, ${first}` : ''}! Seu pedido #${order.order_number} da ${storeName} está pronto. ${where}${link}`
  const url = `https://wa.me/${digits.length <= 11 ? `55${digits}` : digits}?text=${encodeURIComponent(text)}`
  toast.success(`Pedido #${order.order_number} pronto`, {
    duration: 12_000,
    action: { label: 'Avisar no WhatsApp', onClick: () => { window.open(url, '_blank', 'noopener') } },
  })
}
