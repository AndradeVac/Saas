import { useEffect, useState } from 'react'
import { moneyToInput, parseMoney } from '../../lib/format'

type Props = {
  label: string
  value: string
  onChange: (value: string) => void
  hint?: string
  required?: boolean
}

/** BRL input: the user types "12,50"; the parent always receives a canonical "12.50" (or "" while invalid). */
export function MoneyInput({ label, value, onChange, hint, required }: Props) {
  const [text, setText] = useState(value === '' ? '' : moneyToInput(value))
  // Re-sync only when the parent changed the value from outside (not while the user is mid-typing).
  useEffect(() => {
    setText((current) => ((parseMoney(current) ?? '') === value ? current : value === '' ? '' : moneyToInput(value)))
  }, [value])
  const invalid = text.trim() !== '' && parseMoney(text) === null

  return (
    <label className="field">
      <span>{label}</span>
      <div className="money-input">
        <i>R$</i>
        <input
          inputMode="decimal"
          required={required}
          value={text}
          aria-invalid={invalid}
          placeholder="0,00"
          onChange={(e) => {
            setText(e.target.value)
            onChange(parseMoney(e.target.value) ?? '')
          }}
        />
      </div>
      {invalid && <small className="field-error">Use o formato 12,50</small>}
      {hint && !invalid && <small className="muted">{hint}</small>}
    </label>
  )
}
