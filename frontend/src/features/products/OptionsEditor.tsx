import { Plus, Trash2 } from 'lucide-react'
import { MoneyInput } from '../../components/ui/MoneyInput'
import type { OptionGroup } from '../../types'

const newId = () => Math.random().toString(16).slice(2, 12)

type Props = { value: OptionGroup[]; onChange: (groups: OptionGroup[]) => void }

/** Editor for the choices a customer makes on a product: size, extras, doneness… */
export function OptionsEditor({ value, onChange }: Props) {
  const update = (index: number, patch: Partial<OptionGroup>) =>
    onChange(value.map((group, i) => (i === index ? { ...group, ...patch } : group)))

  const addGroup = () =>
    onChange([
      ...value,
      { id: newId(), name: '', required: false, min: 0, max: 1, options: [{ id: newId(), name: '', price: '0.00', active: true }] },
    ])

  return (
    <div>
      {value.length === 0 && (
        <p className="muted">Use para tamanhos, adicionais, ponto da carne, sabores… O cliente escolhe ao pedir e o preço soma automaticamente.</p>
      )}
      {value.map((group, gi) => (
        <div className="opt-editor" key={group.id}>
          <div className="opt-editor-head">
            <label className="field">
              <span>Nome do grupo</span>
              <input value={group.name} placeholder="Ex.: Tamanho, Adicionais" onChange={(e) => update(gi, { name: e.target.value })} />
            </label>
            <label className="field" style={{ maxWidth: 160 }}>
              <span>Regra</span>
              <select
                value={group.required ? 'required' : 'optional'}
                onChange={(e) => update(gi, { required: e.target.value === 'required', min: e.target.value === 'required' ? Math.max(1, group.min) : 0 })}
              >
                <option value="optional">Opcional</option>
                <option value="required">Obrigatório</option>
              </select>
            </label>
            <label className="field" style={{ maxWidth: 110 }}>
              <span>Escolhe até</span>
              <input type="number" min={1} max={40} value={group.max} onChange={(e) => update(gi, { max: Math.max(1, Number(e.target.value) || 1) })} />
            </label>
            <button type="button" className="icon-btn" onClick={() => onChange(value.filter((_, i) => i !== gi))} aria-label="Remover grupo"><Trash2 size={17} /></button>
          </div>

          {group.options.map((option, oi) => (
            <div className="opt-item-row" key={option.id}>
              <input
                value={option.name}
                placeholder="Nome da opção"
                onChange={(e) => update(gi, { options: group.options.map((o, i) => (i === oi ? { ...o, name: e.target.value } : o)) })}
                aria-label="Nome da opção"
              />
              <MoneyInput
                label=""
                value={option.price}
                onChange={(price) => update(gi, { options: group.options.map((o, i) => (i === oi ? { ...o, price: price || '0.00' } : o)) })}
              />
              <label className="check" style={{ margin: 0 }}>
                <input type="checkbox" checked={option.active} onChange={(e) => update(gi, { options: group.options.map((o, i) => (i === oi ? { ...o, active: e.target.checked } : o)) })} />
                Ativa
              </label>
              <button
                type="button"
                className="icon-btn"
                disabled={group.options.length === 1}
                onClick={() => update(gi, { options: group.options.filter((_, i) => i !== oi) })}
                aria-label="Remover opção"
              ><Trash2 size={15} /></button>
            </div>
          ))}
          <button
            type="button"
            className="btn small"
            onClick={() => update(gi, { options: [...group.options, { id: newId(), name: '', price: '0.00', active: true }] })}
          ><Plus size={14} /> Adicionar opção</button>
        </div>
      ))}
      <button type="button" className="btn" onClick={addGroup}><Plus size={16} /> Adicionar grupo de opções</button>
    </div>
  )
}
