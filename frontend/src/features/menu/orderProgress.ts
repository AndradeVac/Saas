import type { Tracking } from '../../services/publicMenu'

export type Progress = {
  title: string
  detail: string
  percent: number
  tone: 'wait' | 'cook' | 'ready' | 'done' | 'off'
  eta: Date | null
  steps: Array<{ label: string; at: string | null; state: 'done' | 'current' | 'todo' }>
}

const hm = (date: Date) => date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })

/** Everything the customer needs to read the order state at a glance: headline, forecast, progress and step times. */
export function orderProgress(order: Tracking, waitingPix: boolean, now = Date.now()): Progress {
  const at = (status: string) => order.history.find((h) => h.status === status)?.at ?? null
  const prep = (order.prep_minutes || 20) * 60_000
  const start = new Date(order.scheduled_for ? new Date(order.scheduled_for).getTime() - prep : at('PREPARING') ?? order.created_at)
  const eta = order.scheduled_for ? new Date(order.scheduled_for) : new Date(start.getTime() + prep)
  const left = Math.max(0, Math.round((eta.getTime() - now) / 60_000))
  const readyLabel = order.service_type === 'DELIVERY' ? 'Saiu para entrega' : 'Pronto'
  const order_ = ['RECEIVED', 'PREPARING', 'READY', 'FINISHED']
  const index = order_.indexOf(order.status)
  const steps = [
    { label: waitingPix ? 'Pagamento' : 'Recebido', status: 'RECEIVED' },
    { label: 'Preparando', status: 'PREPARING' },
    { label: readyLabel, status: 'READY' },
    { label: order.service_type === 'DELIVERY' ? 'Entregue' : 'Retirado', status: 'FINISHED' },
  ].map((s, i) => ({ label: s.label, at: at(s.status), state: (i < index || order.status === 'FINISHED' ? 'done' : i === index ? 'current' : 'todo') as 'done' | 'current' | 'todo' }))

  if (order.status === 'CANCELLED') return { title: 'Pedido cancelado', detail: 'Fale com o estabelecimento se tiver dúvidas.', percent: 0, tone: 'off', eta: null, steps }
  if (order.status === 'FINISHED') return { title: order.service_type === 'DELIVERY' ? 'Pedido entregue' : 'Pedido finalizado', detail: 'Bom apetite! Obrigado pela preferência.', percent: 100, tone: 'done', eta: null, steps }
  if (order.status === 'READY') {
    const detail = order.service_type === 'DELIVERY' ? 'Seu pedido está a caminho.' : order.table_label ? `Já vai para a mesa ${order.table_label}.` : 'Pode retirar no balcão. É só falar o número do pedido.'
    return { title: order.service_type === 'DELIVERY' ? 'Saiu para entrega!' : 'Seu pedido está pronto!', detail, percent: 88, tone: 'ready', eta: null, steps }
  }
  if (order.status === 'PREPARING') {
    const share = Math.min(1, (now - start.getTime()) / prep)
    return {
      title: 'Preparando seu pedido',
      detail: left > 0 ? `Fica pronto por volta das ${hm(eta)} · faltam cerca de ${left} min` : 'Está quase pronto. Só mais um instante!',
      percent: 30 + Math.round(share * 52), tone: 'cook', eta, steps,
    }
  }
  if (waitingPix) return { title: 'Aguardando o pagamento', detail: 'Pague o PIX abaixo. Assim que for confirmado, o pedido vai para a cozinha.', percent: 8, tone: 'wait', eta: null, steps }
  return {
    title: order.scheduled_for ? 'Encomenda recebida' : 'Pedido recebido',
    detail: order.scheduled_for ? `Para ${new Date(order.scheduled_for).toLocaleString('pt-BR', { weekday: 'long', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}` : `O restaurante já recebeu e logo começa a preparar. Previsão: ${hm(eta)}.`,
    percent: 15, tone: 'wait', eta, steps,
  }
}
