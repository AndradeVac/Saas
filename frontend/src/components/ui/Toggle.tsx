type ToggleProps = {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
  hint?: string
  disabled?: boolean
}

/** Switch with a visible label (the whole row is clickable). */
export function Toggle({ checked, onChange, label, hint, disabled }: ToggleProps) {
  return (
    <label className={`toggle ${disabled ? 'disabled' : ''}`}>
      <span className="toggle-text">
        <strong>{label}</strong>
        {hint && <small>{hint}</small>}
      </span>
      <input type="checkbox" role="switch" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span className="toggle-track" aria-hidden="true"><span className="toggle-thumb" /></span>
    </label>
  )
}
