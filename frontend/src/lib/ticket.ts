import { formatMoney, paymentMethodLabels } from './format'
import type { Order } from '../services/orders'

const SERVICE: Record<string, string> = { DINE_IN: 'MESA', TAKEAWAY: 'RETIRADA', DELIVERY: 'ENTREGA' }
const escape = (text: string) => text.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c] as string)

/** Kitchen ticket (80 mm thermal printer), printed from a hidden frame so the panel stays as it is. */
export function printTicket(order: Order, storeName: string) {
  const lines = order.items.map((item) => `
    <div class="item"><b>${item.quantity}x ${escape(item.product_name)}</b>
      ${item.options.length ? `<div class="opt">${item.options.map((o) => escape(o.name)).join(' · ')}</div>` : ''}
      ${item.notes ? `<div class="opt">» ${escape(item.notes)}</div>` : ''}
    </div>`).join('')
  const html = `<!doctype html><html><head><meta charset="utf-8"><title>Pedido ${order.order_number}</title><style>
    @page { size: 80mm auto; margin: 3mm; }
    body { font-family: ui-monospace, Menlo, monospace; font-size: 13px; width: 74mm; margin: 0; color: #000; }
    h1 { font-size: 26px; margin: 0; text-align: center; } h2 { font-size: 15px; margin: 2px 0 6px; text-align: center; }
    .meta { text-align: center; font-size: 12px; } hr { border: 0; border-top: 1px dashed #000; margin: 6px 0; }
    .item { margin: 5px 0; font-size: 14px; } .opt { font-size: 12px; padding-left: 10px; } .total { font-size: 15px; text-align: right; }
  </style></head><body>
    <div class="meta">${escape(storeName)}</div>
    <h1>#${order.order_number}</h1>
    <h2>${SERVICE[order.service_type] ?? ''}${order.table_label ? ` · MESA ${escape(order.table_label)}` : ''}</h2>
    <div class="meta">${new Date(order.created_at).toLocaleString('pt-BR')}<br>${escape(order.customer_name ?? '')}</div>
    <hr>${lines}<hr>
    ${order.notes ? `<div class="opt">Obs.: ${escape(order.notes)}</div><hr>` : ''}
    ${order.delivery_address ? `<div class="opt">Entrega: ${escape(order.delivery_address)}</div><hr>` : ''}
    <div class="total">Total ${formatMoney(order.total)}<br><small>${paymentMethodLabels[order.payment_method]}${order.payment_status === 'PAID' ? ' · PAGO' : ''}</small></div>
  </body></html>`
  const frame = document.createElement('iframe')
  frame.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0'
  document.body.appendChild(frame)
  const doc = frame.contentDocument
  if (!doc) return
  doc.open(); doc.write(html); doc.close()
  frame.onload = () => {
    frame.contentWindow?.focus()
    frame.contentWindow?.print()
    window.setTimeout(() => frame.remove(), 60_000)
  }
}
