import { Camera, FileUp, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { Modal } from '../../components/ui/Modal'
import { formatMoney, moneyToInput, parseMoney } from '../../lib/format'
import { apiErrorMessage } from '../../services/api'
import { applyMenuImport, readMenuPhotos, type MenuDraft } from '../../services/catalog'

const MAX_FILES = 4

type Row = { key: number; include: boolean; name: string; description: string; price: string; sizes: { name: string; price: number }[] }
type Group = { key: number; name: string; rows: Row[] }

let nextKey = 0
const toGroups = (draft: MenuDraft): Group[] => draft.categories.map((category) => ({
  key: nextKey++,
  name: category.name,
  rows: category.products.map((p) => ({
    key: nextKey++, include: true, name: p.name, description: p.description ?? '', sizes: p.sizes,
    price: p.price === null ? '' : moneyToInput(p.price),
  })),
}))

/** "Importar cardápio por foto": upload -> AI reads it -> the owner reviews and fixes -> products are created. */
export function MenuImportModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [files, setFiles] = useState<File[]>([])
  const [groups, setGroups] = useState<Group[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  function pick(list: FileList | null) {
    const chosen = [...files, ...Array.from(list ?? [])].slice(0, MAX_FILES)
    setFiles(chosen); setError('')
  }

  async function read() {
    setBusy(true); setError('')
    try {
      setGroups(toGroups(await readMenuPhotos(files)))
    } catch (err) {
      setError(apiErrorMessage(err, 'Não foi possível ler o cardápio.'))
    } finally {
      setBusy(false)
    }
  }

  const updateRow = (groupKey: number, rowKey: number, data: Partial<Row>) => setGroups((current) => current?.map((g) => (
    g.key !== groupKey ? g : { ...g, rows: g.rows.map((r) => (r.key === rowKey ? { ...r, ...data } : r)) }
  )) ?? null)

  const chosen = groups?.flatMap((g) => g.rows.filter((r) => r.include)) ?? []
  const missingPrice = chosen.filter((r) => parseMoney(r.price) === null || !r.name.trim()).length

  async function create() {
    if (!groups) return
    if (missingPrice) return setError(`Confira nome e preço de ${missingPrice === 1 ? '1 produto' : `${missingPrice} produtos`} (marcados em vermelho) ou desmarque.`)
    setBusy(true); setError('')
    try {
      const payload = {
        categories: groups
          .map((g) => ({
            name: g.name.trim() || 'Cardápio',
            products: g.rows.filter((r) => r.include).map((r) => ({
              name: r.name.trim(),
              description: r.description.trim() || null,
              price: parseMoney(r.price) as string,
              sizes: r.sizes.map((s) => ({ name: s.name, price: s.price.toFixed(2) })),
            })),
          }))
          .filter((g) => g.products.length > 0),
      }
      const result = await applyMenuImport(payload)
      toast.success(`${result.created} produtos criados em ${result.categories} categorias.`)
      if (result.hidden) toast.info(`${result.hidden} ficaram ocultos por causa do limite do plano. Escolha quais mostrar ou assine para liberar todos.`, { duration: 9000 })
      onDone()
    } catch (err) {
      setError(apiErrorMessage(err, 'Não foi possível criar os produtos.'))
      setBusy(false)
    }
  }

  if (!groups) {
    return (
      <Modal
        title="Importar cardápio por foto"
        onClose={onClose}
        footer={<><button className="btn" onClick={onClose}>Cancelar</button><button className="btn primary" disabled={busy || files.length === 0} onClick={() => void read()}>{busy ? 'Lendo o cardápio… (até 1 minuto)' : 'Ler cardápio'}</button></>}
      >
        <p className="muted">Tire foto do cardápio impresso (ou envie um PDF). A gente lê os produtos e preços e você confere tudo antes de salvar.</p>
        <label className="import-drop">
          <input type="file" accept="image/*,application/pdf" multiple onChange={(e) => { pick(e.target.files); e.target.value = '' }} disabled={busy || files.length >= MAX_FILES} />
          <Camera size={26} />
          <strong>{files.length ? 'Adicionar outra foto' : 'Escolher fotos ou PDF'}</strong>
          <small className="muted">Até {MAX_FILES} arquivos. Foto de frente, com boa luz e sem cortar os preços.</small>
        </label>
        {files.length > 0 && (
          <ul className="import-files">
            {files.map((file, index) => (
              <li key={`${file.name}-${index}`}>
                <FileUp size={15} /> <span>{file.name}</span>
                <button className="icon-btn" aria-label={`Remover ${file.name}`} disabled={busy} onClick={() => setFiles(files.filter((_, i) => i !== index))}><Trash2 size={15} /></button>
              </li>
            ))}
          </ul>
        )}
        {error && <div className="alert error" role="alert">{error}</div>}
      </Modal>
    )
  }

  return (
    <Modal
      title="Confira o cardápio"
      onClose={onClose}
      size="lg"
      footer={<><button className="btn" onClick={() => setGroups(null)} disabled={busy}>Voltar</button><button className="btn primary" disabled={busy || chosen.length === 0} onClick={() => void create()}>{busy ? 'Criando…' : `Criar ${chosen.length} ${chosen.length === 1 ? 'produto' : 'produtos'}`}</button></>}
    >
      <p className="muted">Corrija o que a leitura errou e desmarque o que não quer cadastrar. Fotos dos produtos você coloca depois.</p>
      {groups.map((group) => (
        <div key={group.key} className="import-group">
          <label className="field"><span>Categoria</span>
            <input value={group.name} onChange={(e) => setGroups(groups.map((g) => (g.key === group.key ? { ...g, name: e.target.value } : g)))} />
          </label>
          {group.rows.map((row) => {
            const invalid = row.include && (parseMoney(row.price) === null || !row.name.trim())
            return (
              <div key={row.key} className={`import-row ${row.include ? '' : 'off'} ${invalid ? 'invalid' : ''}`}>
                <input type="checkbox" checked={row.include} onChange={(e) => updateRow(group.key, row.key, { include: e.target.checked })} aria-label={`Incluir ${row.name}`} />
                <div className="import-fields">
                  <input className="input" value={row.name} onChange={(e) => updateRow(group.key, row.key, { name: e.target.value })} aria-label="Nome" placeholder="Nome" />
                  <input className="input" value={row.description} onChange={(e) => updateRow(group.key, row.key, { description: e.target.value })} aria-label="Descrição" placeholder="Descrição (opcional)" />
                  {row.sizes.length > 1 && <small className="muted">Tamanhos: {row.sizes.map((s) => `${s.name} ${formatMoney(s.price)}`).join(' · ')}</small>}
                </div>
                <div className="money-input import-price">
                  <i>R$</i>
                  <input inputMode="decimal" value={row.price} placeholder="0,00" aria-label="Preço" aria-invalid={invalid} onChange={(e) => updateRow(group.key, row.key, { price: e.target.value })} />
                </div>
              </div>
            )
          })}
        </div>
      ))}
      {error && <div className="alert error" role="alert">{error}</div>}
    </Modal>
  )
}
