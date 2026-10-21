import type { MenuProduct } from '../../services/publicMenu'
import type { OptionGroup } from '../../types'

export type CartLine = {
  key: string
  productId: string
  name: string
  quantity: number
  /** Price of one unit with the chosen options already included. */
  unitPrice: number
  options: Array<{ group_id: string; option_id: string; label: string }>
  notes?: string
}

export type Selection = Record<string, string[]> // group id -> chosen option ids

export function lineKey(productId: string, options: Array<{ group_id: string; option_id: string }>, notes?: string) {
  const chosen = options.map((o) => `${o.group_id}:${o.option_id}`).sort().join(',')
  return `${productId}|${chosen}|${(notes ?? '').trim()}`
}

export function selectionPrice(groups: OptionGroup[], selection: Selection) {
  return groups.reduce((sum, group) => {
    const chosen = selection[group.id] ?? []
    return sum + group.options.filter((o) => chosen.includes(o.id)).reduce((s, o) => s + Number(o.price), 0)
  }, 0)
}

/** Which required groups still lack a choice (or exceed the max); empty means valid. */
export function selectionErrors(groups: OptionGroup[], selection: Selection): Record<string, string> {
  const errors: Record<string, string> = {}
  for (const group of groups) {
    const count = (selection[group.id] ?? []).length
    const min = Math.max(group.min, group.required ? 1 : 0)
    if (count < min) errors[group.id] = min === 1 ? 'Escolha uma opção' : `Escolha pelo menos ${min}`
  }
  return errors
}

export function buildLine(product: MenuProduct, selection: Selection, quantity: number, notes?: string): CartLine {
  const options = product.options.flatMap((group) =>
    group.options
      .filter((option) => (selection[group.id] ?? []).includes(option.id))
      .map((option) => ({ group_id: group.id, option_id: option.id, label: option.name })),
  )
  const clean = notes?.trim() || undefined
  return {
    key: lineKey(product.id, options, clean),
    productId: product.id,
    name: product.name,
    quantity,
    unitPrice: Number(product.price) + selectionPrice(product.options, selection),
    options,
    notes: clean,
  }
}

export const cartCount = (lines: CartLine[]) => lines.reduce((sum, line) => sum + line.quantity, 0)
export const cartSubtotal = (lines: CartLine[]) => lines.reduce((sum, line) => sum + line.unitPrice * line.quantity, 0)

type PastItem = { product_id: string; quantity: number; options: Array<{ group: string; name: string }>; notes: string | null }

/** Rebuilds cart lines from an order already placed ("repetir a rodada"). Past orders keep option *names*,
 *  so they are matched back to today's ids; items no longer on the menu (or with changed options) are skipped. */
export function repeatLines(products: MenuProduct[], items: PastItem[]): { lines: CartLine[]; skipped: number } {
  const lines: CartLine[] = []
  let skipped = 0
  for (const item of items) {
    const product = products.find((p) => p.id === item.product_id && p.available)
    if (!product) { skipped += 1; continue }
    const selection: Selection = {}
    let matched = true
    for (const picked of item.options) {
      const group = product.options.find((g) => g.name === picked.group)
      const option = group?.options.find((o) => o.name === picked.name)
      if (!group || !option) { matched = false; break }
      selection[group.id] = [...(selection[group.id] ?? []), option.id]
    }
    if (!matched || Object.keys(selectionErrors(product.options, selection)).length > 0) { skipped += 1; continue }
    lines.push(buildLine(product, selection, item.quantity, item.notes ?? undefined))
  }
  return { lines, skipped }
}
