import { Camera, ClipboardPaste, Copy, ExternalLink, FileUp, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { Modal } from '../../components/ui/Modal'
import { formatMoney, moneyToInput, parseMoney } from '../../lib/format'
import { apiErrorMessage } from '../../services/api'
import { applyMenuImport, readMenuPhotos, type MenuDraft } from '../../services/catalog'

const MAX_FILES = 4

// Free path: the owner sends the photos to Claude (claude.ai, free plan) with this request and pastes the answer back.
const CLAUDE_REQUEST = `Estas fotos são o cardápio do meu restaurante. Transcreva TODOS os itens à venda.

- Mantenha os nomes como estão escritos (corrija só caixa alta exagerada).
- Agrupe nas categorias do próprio cardápio (ex.: Lanches, Espetinhos, Porções, Bebidas).
- description: só o que estiver escrito (ingredientes, acompanhamentos). Não invente.
- price: em reais, número com ponto (R$ 25,90 -> 25.90). Se não der para ler, use null.
- sizes: quando o item tiver preço por tamanho (P/M/G, 300 ml/600 ml, meia/inteira), liste cada um e deixe price com o menor. Senão, [].
- Ignore endereço, telefone, horário e promoções sem preço.

Responda SOMENTE com o JSON abaixo, sem nenhum texto antes ou depois:
{"categories":[{"name":"Lanches","products":[{"name":"X-Bacon","description":"Pão, hambúrguer e bacon","price":28.90,"sizes":[]}]}]}`

const toNumber = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') {
    const parsed = parseMoney(value.replace(/R\$\s*/i, ''))
    return parsed === null ? null : Number(parsed)
  }
  return null
}

/** Reads what the owner pasted from Claude: tolerant of text around the JSON and of prices written as "25,90". */
export function parsePastedMenu(text: string): MenuDraft | null {
  const start = text.indexOf('{')
  const end = text.lastIndexOf('}')
  if (start < 0 || end <= start) return null
  let data: unknown
  try { data = JSON.parse(text.slice(start, end + 1)) } catch { return null }
  const categories = (data as { categories?: unknown })?.categories
  if (!Array.isArray(categories)) return null
  const draft: MenuDraft = {
    categories: categories.map((c) => ({
      name: String(c?.name ?? 'Cardápio'),
      products: (Array.isArray(c?.products) ? c.products : [])
        .filter((p: { name?: unknown }) => typeof p?.name === 'string' && p.name.trim())
        .map((p: { name: string; description?: unknown; price?: unknown; sizes?: unknown }) => ({
          name: p.name,
          description: typeof p.description === 'string' ? p.description : null,
          price: toNumber(p.price),
          sizes: (Array.isArray(p.sizes) ? p.sizes : [])
            .map((size: { name?: unknown; price?: unknown }) => ({ name: String(size?.name ?? ''), price: toNumber(size?.price) }))
            .filter((size: { name: string; price: number | null }): size is { name: string; price: number } => !!size.name && size.price !== null),
        })),
    })).filter((c) => c.products.length > 0),
  }
  return draft.categories.length ? draft : null
}

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
export function MenuImportModal({ photoReading, onClose, onDone }: { photoReading: boolean; onClose: () => void; onDone: () => void }) {
  const [mode, setMode] = useState<'photo' | 'paste'>(photoReading ? 'photo' : 'paste')
  const [pasted, setPasted] = useState('')
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

  function usePasted() {
    const draft = parsePastedMenu(pasted)
    if (!draft) return setError('Não reconheci a resposta. Copie a resposta inteira do Claude (o bloco que começa com { ) e cole de novo.')
    setError(''); setGroups(toGroups(draft))
  }

  if (!groups && mode === 'paste') {
    return (
      <Modal
        title="Importar cardápio com o Claude"
        onClose={onClose}
        footer={<><button className="btn" onClick={onClose}>Cancelar</button><button className="btn primary" disabled={!pasted.trim()} onClick={usePasted}>Conferir produtos</button></>}
      >
        <ol className="import-steps">
          <li>
            <strong>Copie o pedido</strong>
            <button className="btn small" onClick={() => { void navigator.clipboard?.writeText(CLAUDE_REQUEST); toast.success('Pedido copiado') }}><Copy size={14} /> Copiar pedido</button>
          </li>
          <li>
            <strong>Abra o Claude (grátis), anexe as fotos do cardápio e cole o pedido</strong>
            <a className="btn small" href="https://claude.ai/new" target="_blank" rel="noreferrer"><ExternalLink size={14} /> Abrir o Claude</a>
          </li>
          <li>
            <strong>Copie a resposta do Claude e cole aqui</strong>
            <label className="field"><span className="sr-only">Resposta do Claude</span>
              <textarea rows={6} value={pasted} onChange={(e) => { setPasted(e.target.value); setError('') }} placeholder='{"categories": [ ... ]}' />
            </label>
          </li>
        </ol>
        {photoReading && <button className="btn ghost small" onClick={() => { setMode('photo'); setError('') }}><Camera size={14} /> Prefiro enviar as fotos aqui</button>}
        {error && <div className="alert error" role="alert">{error}</div>}
      </Modal>
    )
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
        <button className="btn ghost small" onClick={() => { setMode('paste'); setError('') }}><ClipboardPaste size={14} /> Usar o Claude grátis e colar a resposta</button>
        {error && <div className="alert error" role="alert">{error}</div>}
      </Modal>
    )
  }

  return (
    <Modal
      title="Confira o cardápio"
      onClose={onClose}
      size="lg"
      footer={<><button className="btn" onClick={() => { setGroups(null); setError('') }} disabled={busy}>Voltar</button><button className="btn primary" disabled={busy || chosen.length === 0} onClick={() => void create()}>{busy ? 'Criando…' : `Criar ${chosen.length} ${chosen.length === 1 ? 'produto' : 'produtos'}`}</button></>}
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
