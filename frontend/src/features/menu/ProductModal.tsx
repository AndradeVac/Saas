import { Minus, Plus } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Modal } from '../../components/ui/Modal'
import { formatMoney } from '../../lib/format'
import { mediaUrl } from '../../lib/media'
import type { MenuProduct } from '../../services/publicMenu'
import { buildLine, selectionErrors, selectionPrice, type CartLine, type Selection } from './cart'

type Props = {
  product: MenuProduct
  canOrder: boolean
  onClose: () => void
  onAdd: (line: CartLine) => void
}

export function ProductModal({ product, canOrder, onClose, onAdd }: Props) {
  const [selection, setSelection] = useState<Selection>({})
  const [quantity, setQuantity] = useState(1)
  const [notes, setNotes] = useState('')
  const [submitted, setSubmitted] = useState(false)

  const errors = useMemo(() => selectionErrors(product.options, selection), [product.options, selection])
  const unit = Number(product.price) + selectionPrice(product.options, selection)

  function toggle(groupId: string, optionId: string, max: number) {
    setSelection((current) => {
      const chosen = current[groupId] ?? []
      if (max === 1) return { ...current, [groupId]: chosen[0] === optionId && !product.options.find((g) => g.id === groupId)?.required ? [] : [optionId] }
      if (chosen.includes(optionId)) return { ...current, [groupId]: chosen.filter((id) => id !== optionId) }
      if (chosen.length >= max) return current
      return { ...current, [groupId]: [...chosen, optionId] }
    })
  }

  function add() {
    setSubmitted(true)
    if (Object.keys(errors).length > 0) return
    onAdd(buildLine(product, selection, quantity, notes))
  }

  return (
    <Modal
      title={product.name}
      onClose={onClose}
      footer={
        canOrder ? (
          <div className="product-modal-foot">
            <div className="stepper">
              <button onClick={() => setQuantity((q) => Math.max(1, q - 1))} aria-label="Diminuir"><Minus size={15} /></button>
              <span>{quantity}</span>
              <button onClick={() => setQuantity((q) => Math.min(20, q + 1))} aria-label="Aumentar"><Plus size={15} /></button>
            </div>
            <button className="btn primary large" onClick={add}>Adicionar · {formatMoney(unit * quantity)}</button>
          </div>
        ) : (
          <button className="btn block" onClick={onClose}>Fechar</button>
        )
      }
    >
      {product.image_url && <img className="product-modal-img" src={mediaUrl(product.image_url)} alt="" />}
      {product.description && <p className="muted">{product.description}</p>}
      <strong>{formatMoney(product.price)}</strong>

      {canOrder && product.options.map((group) => {
        const chosen = selection[group.id] ?? []
        const error = submitted ? errors[group.id] : undefined
        const single = group.max === 1
        const rule = group.required || group.min > 0
          ? single ? 'Obrigatório' : `Escolha de ${Math.max(group.min, 1)} a ${group.max}`
          : single ? 'Opcional' : `Até ${group.max}`
        return (
          <fieldset className="opt-group" key={group.id} style={{ border: 0, padding: 0, margin: '16px 0 0' }}>
            <div className="opt-group-head">
              <strong>{group.name}</strong>
              <span className={`opt-rule ${error ? 'error' : group.required ? 'required' : ''}`}>{error ?? rule}</span>
            </div>
            {group.options.map((option) => (
              <label className={`opt-row ${chosen.includes(option.id) ? 'selected' : ''}`} key={option.id}>
                <input
                  type={single ? 'radio' : 'checkbox'}
                  name={group.id}
                  checked={chosen.includes(option.id)}
                  onChange={() => toggle(group.id, option.id, group.max)}
                  disabled={!single && !chosen.includes(option.id) && chosen.length >= group.max}
                />
                <span>{option.name}</span>
                {Number(option.price) > 0 && <em>+ {formatMoney(option.price)}</em>}
              </label>
            ))}
          </fieldset>
        )
      })}

      {canOrder && (
        <label className="field" style={{ marginTop: 16 }}>
          <span>Alguma observação?</span>
          <textarea rows={2} maxLength={300} placeholder="Ex.: sem cebola, bem passado…" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </label>
      )}
    </Modal>
  )
}
