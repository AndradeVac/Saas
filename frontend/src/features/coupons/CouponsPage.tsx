import { Plus, Ticket, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { useConfirm } from '../../components/ui/Confirm'
import { Modal } from '../../components/ui/Modal'
import { MoneyInput } from '../../components/ui/MoneyInput'
import { EmptyState, ErrorBanner, PageHeader, Skeleton } from '../../components/ui/parts'
import { formatDate, formatMoney } from '../../lib/format'
import { apiErrorMessage } from '../../services/api'
import { createCoupon, deleteCoupon, getCoupons, updateCoupon, type Coupon } from '../../services/catalog'

type Draft = { code: string; kind: 'PERCENT' | 'FIXED'; value: string; min_order: string; max_uses: string; expires: string }
const blank: Draft = { code: '', kind: 'PERCENT', value: '', min_order: '', max_uses: '', expires: '' }

function describe(c: Coupon) {
  return c.kind === 'PERCENT' ? `${Number(c.value)}% de desconto` : `${formatMoney(c.value)} de desconto`
}

export function CouponsPage() {
  const confirm = useConfirm()
  const [coupons, setCoupons] = useState<Coupon[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [draft, setDraft] = useState<Draft | null>(null)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(() => getCoupons()
    .then((c) => { setCoupons(c); setError('') })
    .catch(() => setError('Não foi possível carregar os cupons.'))
    .finally(() => setLoading(false)), [])
  useEffect(() => { void load() }, [load])

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!draft) return
    setFormError('')
    if (draft.value === '') return setFormError('Informe o valor do desconto.')
    setSaving(true)
    try {
      await createCoupon({
        code: draft.code,
        kind: draft.kind,
        value: draft.value,
        min_order: draft.min_order || '0',
        max_uses: draft.max_uses ? Number(draft.max_uses) : null,
        // End of the chosen day, local time.
        expires_at: draft.expires ? new Date(`${draft.expires}T23:59:59`).toISOString() : null,
      })
      setDraft(null)
      toast.success('Cupom criado')
      await load()
    } catch (err) {
      setFormError(apiErrorMessage(err, 'Não foi possível criar o cupom.'))
    } finally {
      setSaving(false)
    }
  }

  async function toggle(coupon: Coupon) {
    try {
      await updateCoupon(coupon.id, { active: !coupon.active })
      await load()
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível alterar o cupom.'))
    }
  }

  async function remove(coupon: Coupon) {
    const result = await confirm({ title: `Excluir o cupom ${coupon.code}?`, message: 'Pedidos que já usaram o cupom não são alterados.', confirmLabel: 'Excluir', danger: true })
    if (!result.ok) return
    try {
      await deleteCoupon(coupon.id)
      await load()
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível excluir.'))
    }
  }

  const expired = (c: Coupon) => c.expires_at !== null && new Date(c.expires_at) <= new Date()
  const spent = (c: Coupon) => c.max_uses !== null && c.used_count >= c.max_uses

  return (
    <section className="page narrow">
      <PageHeader
        title="Cupons"
        subtitle="Descontos que o cliente aplica ao finalizar o pedido."
        actions={<button className="btn primary" onClick={() => { setFormError(''); setDraft(blank) }}><Plus size={16} /> Novo cupom</button>}
      />
      <ErrorBanner message={error} onRetry={() => void load()} />
      <div className="card" style={{ padding: '4px 20px' }}>
        {loading ? <Skeleton lines={3} height={44} /> : coupons.length === 0 ? (
          <EmptyState icon={<Ticket size={26} />} title="Nenhum cupom criado" hint="Crie um cupom de boas-vindas ou de fidelidade e divulgue o código aos seus clientes." />
        ) : coupons.map((c) => (
          <div className={`list-row ${c.active && !expired(c) && !spent(c) ? '' : 'off'}`} key={c.id}>
            <div>
              <strong><span className="kbd">{c.code}</span> {expired(c) && <span className="badge danger">Expirado</span>}{spent(c) && <span className="badge danger">Esgotado</span>}{!c.active && <span className="badge">Desativado</span>}</strong>
              <small>
                {describe(c)}
                {Number(c.min_order) > 0 && ` · pedido mín. ${formatMoney(c.min_order)}`}
                {` · usado ${c.used_count}${c.max_uses ? ` de ${c.max_uses}` : ''} ${c.used_count === 1 ? 'vez' : 'vezes'}`}
                {c.expires_at && ` · vale até ${formatDate(c.expires_at)}`}
              </small>
            </div>
            <div className="row-actions">
              <button className="btn small" onClick={() => void toggle(c)}>{c.active ? 'Desativar' : 'Ativar'}</button>
              <button className="icon-btn" onClick={() => void remove(c)} aria-label={`Excluir ${c.code}`}><Trash2 size={16} /></button>
            </div>
          </div>
        ))}
      </div>

      {draft && (
        <Modal
          title="Novo cupom"
          size="sm"
          onClose={() => setDraft(null)}
          footer={<><button type="button" className="btn" onClick={() => setDraft(null)}>Cancelar</button><button type="submit" form="coupon-form" className="btn primary" disabled={saving}>{saving ? 'Criando…' : 'Criar cupom'}</button></>}
        >
          <form id="coupon-form" onSubmit={save}>
            {formError && <div className="alert error" role="alert">{formError}</div>}
            <label className="field"><span>Código</span><input required autoFocus minLength={3} maxLength={40} placeholder="BEMVINDO10" style={{ textTransform: 'uppercase' }} value={draft.code} onChange={(e) => setDraft({ ...draft, code: e.target.value })} /></label>
            <div className="segmented" style={{ marginBottom: 14 }}>
              <button type="button" className={draft.kind === 'PERCENT' ? 'active' : ''} onClick={() => setDraft({ ...draft, kind: 'PERCENT', value: '' })}>Percentual (%)</button>
              <button type="button" className={draft.kind === 'FIXED' ? 'active' : ''} onClick={() => setDraft({ ...draft, kind: 'FIXED', value: '' })}>Valor fixo (R$)</button>
            </div>
            {draft.kind === 'PERCENT'
              ? <label className="field"><span>Desconto (%)</span><input required type="number" min={1} max={100} step="0.5" value={draft.value} onChange={(e) => setDraft({ ...draft, value: e.target.value })} /></label>
              : <MoneyInput label="Desconto" required value={draft.value} onChange={(value) => setDraft({ ...draft, value })} />}
            <div className="grid-2">
              <MoneyInput label="Pedido mínimo (opcional)" value={draft.min_order} onChange={(min_order) => setDraft({ ...draft, min_order })} />
              <label className="field"><span>Limite de usos (opcional)</span><input type="number" min={1} value={draft.max_uses} onChange={(e) => setDraft({ ...draft, max_uses: e.target.value })} /></label>
            </div>
            <label className="field"><span>Vale até (opcional)</span><input type="date" min={new Date().toISOString().slice(0, 10)} value={draft.expires} onChange={(e) => setDraft({ ...draft, expires: e.target.value })} /></label>
          </form>
        </Modal>
      )}
    </section>
  )
}
