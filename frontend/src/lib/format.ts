import type { BusinessType, DayKey, OrderStatus, PaymentMethod, ServiceType } from '../types'

const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
const time = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' })
const dateTime = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
const date = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' })

export const formatMoney = (value: string | number) => currency.format(Number(value))
export const formatTime = (value?: string | null) => (value ? time.format(new Date(value)) : '—')
export const formatDateTime = (value?: string | null) => (value ? dateTime.format(new Date(value)) : '—')
export const formatDate = (value?: string | null) => (value ? date.format(new Date(value)) : '—')

/** "12 min", "3 h", "2 dias" for a past instant. */
export function timeAgo(value: string, now = Date.now()) {
  const minutes = Math.max(0, Math.round((now - new Date(value).getTime()) / 60_000))
  if (minutes < 1) return 'agora'
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} h`
  const days = Math.floor(hours / 24)
  return `${days} ${days === 1 ? 'dia' : 'dias'}`
}

export function formatPhone(value?: string | null) {
  const digits = (value ?? '').replace(/\D/g, '')
  if (digits.length === 11) return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`
  if (digits.length === 10) return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`
  return value ?? ''
}

/** Live phone mask while typing: (11) 99999-9999 */
export function maskPhone(value: string) {
  const digits = value.replace(/\D/g, '').slice(0, 11)
  if (digits.length <= 2) return digits
  if (digits.length <= 6) return `(${digits.slice(0, 2)}) ${digits.slice(2)}`
  if (digits.length <= 10) return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`
  return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`
}

export const orderStatusLabels: Record<OrderStatus, string> = {
  RECEIVED: 'Recebido',
  PREPARING: 'Em preparo',
  READY: 'Pronto',
  FINISHED: 'Entregue',
  CANCELLED: 'Cancelado',
}

export const paymentMethodLabels: Record<PaymentMethod, string> = { PIX: 'PIX', CARD: 'Cartão', CASH: 'Dinheiro' }
export const serviceLabels: Record<ServiceType, string> = { DINE_IN: 'Comer aqui', TAKEAWAY: 'Para levar', DELIVERY: 'Entrega' }
export const serviceShortLabels: Record<ServiceType, string> = { DINE_IN: 'Mesa', TAKEAWAY: 'Retirada', DELIVERY: 'Entrega' }

export const businessTypeLabels: Record<BusinessType, string> = {
  RESTAURANT: 'Restaurante',
  BAKERY: 'Padaria',
  CAFE: 'Cafeteria',
  SNACK_BAR: 'Lanchonete',
  PIZZERIA: 'Pizzaria',
  OTHER: 'Outro',
}

export const DAYS: Array<{ key: DayKey; label: string; short: string }> = [
  { key: 'mon', label: 'Segunda-feira', short: 'Seg' },
  { key: 'tue', label: 'Terça-feira', short: 'Ter' },
  { key: 'wed', label: 'Quarta-feira', short: 'Qua' },
  { key: 'thu', label: 'Quinta-feira', short: 'Qui' },
  { key: 'fri', label: 'Sexta-feira', short: 'Sex' },
  { key: 'sat', label: 'Sábado', short: 'Sáb' },
  { key: 'sun', label: 'Domingo', short: 'Dom' },
]

export function slugify(value: string) {
  return value
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
    .slice(0, 40)
}

/** Parses "12,50" / "12.5" into a canonical "12.50" string, or null when invalid. */
export function parseMoney(value: string): string | null {
  const raw = value.trim()
  const normalized = raw.includes(',') ? raw.replace(/\./g, '').replace(',', '.') : raw
  if (!/^\d+(\.\d{1,2})?$/.test(normalized)) return null
  return Number(normalized).toFixed(2)
}

export const moneyToInput = (value: string | number) => Number(value).toFixed(2).replace('.', ',')
