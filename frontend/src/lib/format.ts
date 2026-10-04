import type { BusinessType, OrderStatus, PaymentMethod, ServiceType } from '../types'

const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
const time = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' })
const dateTime = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })

export const formatMoney = (value: string | number) => currency.format(Number(value))
export const formatTime = (value?: string | null) => (value ? time.format(new Date(value)) : '—')
export const formatDateTime = (value?: string | null) => (value ? dateTime.format(new Date(value)) : '—')

export function formatPhone(value?: string | null) {
  const digits = (value ?? '').replace(/\D/g, '')
  if (digits.length === 11) return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`
  if (digits.length === 10) return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`
  return value ?? ''
}

export const orderStatusLabels: Record<OrderStatus, string> = {
  RECEIVED: 'Recebido',
  PREPARING: 'Em preparo',
  READY: 'Pronto',
  FINISHED: 'Entregue',
  CANCELLED: 'Cancelado',
}

export const paymentMethodLabels: Record<PaymentMethod, string> = { PIX: 'PIX', CARD: 'Cartão', CASH: 'Dinheiro' }
export const serviceLabels: Record<ServiceType, string> = { DINE_IN: 'Comer aqui', TAKEAWAY: 'Para levar' }

export const businessTypeLabels: Record<BusinessType, string> = {
  RESTAURANT: 'Restaurante',
  BAKERY: 'Padaria',
  CAFE: 'Cafeteria',
  SNACK_BAR: 'Lanchonete',
  PIZZERIA: 'Pizzaria',
  OTHER: 'Outro',
}

export function slugify(value: string) {
  return value
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
    .slice(0, 40)
}
