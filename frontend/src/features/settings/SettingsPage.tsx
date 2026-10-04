import { Copy, Plus, Printer, Trash2 } from 'lucide-react'
import QRCode from 'qrcode'
import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { ImageUpload } from '../../components/ui/ImageUpload'
import { MoneyInput } from '../../components/ui/MoneyInput'
import { ErrorBanner, PageHeader, Skeleton } from '../../components/ui/parts'
import { Toggle } from '../../components/ui/Toggle'
import { DAYS, businessTypeLabels, formatDate, maskPhone, paymentMethodLabels, serviceLabels } from '../../lib/format'
import { tenantUrl } from '../../lib/tenant'
import { apiErrorMessage } from '../../services/api'
import { changePassword } from '../../services/auth'
import { getMediaUsage, getTenantSettings, updateTenantSettings, type UploadResult } from '../../services/tenant'
import type { BusinessType, DayKey, OpeningHours, PaymentMethod, ServiceType, TenantSettings } from '../../types'
import { useTenant } from '../tenant/TenantProvider'

type Tab = 'business' | 'look' | 'hours' | 'orders' | 'tables' | 'account'
const tabs: Array<{ key: Tab; label: string }> = [
  { key: 'business', label: 'Negócio' },
  { key: 'look', label: 'Aparência' },
  { key: 'hours', label: 'Horários' },
  { key: 'orders', label: 'Pedidos e pagamento' },
  { key: 'tables', label: 'Mesas e QR Code' },
  { key: 'account', label: 'Minha conta' },
]
const PRESETS = ['#c2410c', '#dc2626', '#d97706', '#65a30d', '#059669', '#0891b2', '#2563eb', '#7c3aed', '#c026d3', '#57534e']

const editable = (s: TenantSettings) => ({
  name: s.name, business_type: s.business_type, description: s.description, phone: s.phone, address: s.address,
  instagram: s.instagram, pix_key: s.pix_key, logo_url: s.logo_url, cover_url: s.cover_url, primary_color: s.primary_color,
  accepting_orders: s.accepting_orders, hours_mode: s.hours_mode, opening_hours: s.opening_hours,
  enabled_services: s.enabled_services, accepted_payments: s.accepted_payments,
  delivery_fee: s.delivery_fee, min_order_value: s.min_order_value, service_fee_percent: s.service_fee_percent,
})

function toggleIn<T>(list: T[], item: T, on: boolean) {
  return on ? [...list.filter((x) => x !== item), item] : list.filter((x) => x !== item)
}

export function SettingsPage() {
  const { setTenant } = useTenant()
  const [saved, setSaved] = useState<TenantSettings | null>(null)
  const [form, setForm] = useState<TenantSettings | null>(null)
  const [tab, setTab] = useState<Tab>('business')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [usage, setUsage] = useState<UploadResult | null>(null)

  useEffect(() => {
    getTenantSettings().then((s) => { setSaved(s); setForm(s) }).catch(() => setError('Não foi possível carregar as configurações.'))
    getMediaUsage().then(setUsage).catch(() => undefined)
  }, [])

  const dirty = useMemo(() => Boolean(saved && form && JSON.stringify(editable(saved)) !== JSON.stringify(editable(form))), [saved, form])

  // Warn before leaving with unsaved changes.
  useEffect(() => {
    if (!dirty) return
    const handler = (event: BeforeUnloadEvent) => { event.preventDefault() }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [dirty])

  if (!form || !saved) return <section className="page narrow">{error ? <ErrorBanner message={error} /> : <Skeleton lines={8} height={28} />}</section>

  const set = <K extends keyof TenantSettings>(key: K, value: TenantSettings[K]) => setForm({ ...form, [key]: value })

  async function save() {
    if (!form) return
    setSaving(true)
    setError('')
    try {
      const updated = await updateTenantSettings({
        ...editable(form),
        phone: form.phone || null, address: form.address || null, instagram: form.instagram || null,
        description: form.description || null, pix_key: form.pix_key || null,
      })
      setSaved(updated)
      setForm(updated)
      setTenant(updated)
      getMediaUsage().then(setUsage).catch(() => undefined)
      toast.success('Configurações salvas')
    } catch (err) {
      setError(apiErrorMessage(err, 'Não foi possível salvar.'))
    } finally {
      setSaving(false)
    }
  }

  const menuUrl = tenantUrl(form.slug, '/')

  return (
    <section className="page narrow">
      <PageHeader title="Configurações" subtitle="Você controla tudo sobre o seu negócio por aqui." />
      <div className="tabs" role="tablist">
        {tabs.map((t) => <button key={t.key} role="tab" aria-selected={tab === t.key} className={tab === t.key ? 'active' : ''} onClick={() => setTab(t.key)}>{t.label}</button>)}
      </div>
      <ErrorBanner message={error} />

      {tab === 'business' && (
        <div className="card">
          <h3>Dados do estabelecimento</h3>
          <p className="card-sub">Aparecem no topo do seu cardápio digital.</p>
          <div className="grid-2">
            <label className="field"><span>Nome</span><input value={form.name} maxLength={120} onChange={(e) => set('name', e.target.value)} /></label>
            <label className="field"><span>Tipo de negócio</span>
              <select value={form.business_type} onChange={(e) => set('business_type', e.target.value as BusinessType)}>
                {(Object.keys(businessTypeLabels) as BusinessType[]).map((t) => <option key={t} value={t}>{businessTypeLabels[t]}</option>)}
              </select>
            </label>
          </div>
          <label className="field"><span>Descrição</span><textarea rows={3} maxLength={500} placeholder="Conte em poucas palavras o que torna sua casa especial." value={form.description ?? ''} onChange={(e) => set('description', e.target.value)} /></label>
          <div className="grid-2">
            <label className="field"><span>Telefone / WhatsApp</span><input inputMode="tel" placeholder="(11) 99999-9999" value={form.phone ? maskPhone(form.phone) : ''} onChange={(e) => set('phone', e.target.value ? maskPhone(e.target.value) : null)} /></label>
            <label className="field"><span>Instagram</span><input placeholder="@suaconta" maxLength={60} value={form.instagram ?? ''} onChange={(e) => set('instagram', e.target.value)} /></label>
          </div>
          <label className="field"><span>Endereço</span><input maxLength={200} placeholder="Rua, número – bairro, cidade" value={form.address ?? ''} onChange={(e) => set('address', e.target.value)} /></label>
        </div>
      )}

      {tab === 'look' && (
        <>
          <div className="card">
            <h3>Marca</h3>
            <p className="card-sub">Logo e capa aparecem no cardápio e no painel.</p>
            <div className="grid-2">
              <ImageUpload label="Logo" value={form.logo_url} onChange={(v) => set('logo_url', v)} hint="Quadrada fica melhor." />
              <ImageUpload label="Capa" shape="banner" value={form.cover_url} onChange={(v) => set('cover_url', v)} hint="Foto larga do local ou dos pratos." />
            </div>
            {usage && <small className="muted">Imagens: {(usage.used_bytes / 1_048_576).toFixed(1)} MB de {(usage.quota_bytes / 1_048_576).toFixed(0)} MB usados.</small>}
          </div>
          <div className="card">
            <h3>Cor principal</h3>
            <p className="card-sub">Usada em botões, destaques e no seu cardápio.</p>
            <div className="row">
              <input type="color" value={form.primary_color} onChange={(e) => set('primary_color', e.target.value)} aria-label="Cor principal" style={{ width: 56, height: 42, border: 0, background: 'none', cursor: 'pointer' }} />
              <code>{form.primary_color}</code>
            </div>
            <div className="color-presets">
              {PRESETS.map((c) => <button key={c} type="button" className={form.primary_color === c ? 'active' : ''} style={{ background: c }} aria-label={`Usar cor ${c}`} onClick={() => set('primary_color', c)} />)}
            </div>
            <div className="card flat" style={{ marginTop: 16, ['--brand' as string]: form.primary_color }}>
              <div className="row between"><strong>Prévia</strong><button type="button" className="btn primary small" style={{ background: form.primary_color, borderColor: form.primary_color }}>Adicionar</button></div>
            </div>
          </div>
        </>
      )}

      {tab === 'hours' && (
        <>
          <div className="card">
            <h3>Recebimento de pedidos</h3>
            <Toggle label="Aceitando pedidos pelo cardápio" hint="Chave geral. Desligue para pausar tudo (ex.: cozinha sobrecarregada)." checked={form.accepting_orders} onChange={(v) => set('accepting_orders', v)} />
            <h4>Como abrir e fechar</h4>
            <div className="segmented choice">
              <button type="button" className={form.hours_mode === 'MANUAL' ? 'active' : ''} onClick={() => set('hours_mode', 'MANUAL')}>Manual</button>
              <button type="button" className={form.hours_mode === 'SCHEDULE' ? 'active' : ''} onClick={() => set('hours_mode', 'SCHEDULE')}>Automático por horário</button>
            </div>
            <p className="muted" style={{ marginTop: 10 }}>
              {form.hours_mode === 'MANUAL' ? 'O cardápio aceita pedidos enquanto a chave acima estiver ligada.' : 'O cardápio só aceita pedidos dentro dos horários abaixo (fuso de Brasília).'}
            </p>
          </div>
          {form.hours_mode === 'SCHEDULE' && <HoursEditor value={form.opening_hours} onChange={(v) => set('opening_hours', v)} />}
        </>
      )}

      {tab === 'orders' && (
        <>
          <div className="card">
            <h3>Tipos de atendimento</h3>
            <p className="card-sub">O cliente só vê as opções que você ativar.</p>
            {(Object.keys(serviceLabels) as ServiceType[]).map((s) => (
              <Toggle
                key={s}
                label={serviceLabels[s]}
                hint={s === 'DINE_IN' ? 'Pedido na mesa, com o número da mesa.' : s === 'TAKEAWAY' ? 'O cliente retira no balcão.' : 'Entrega no endereço do cliente.'}
                checked={form.enabled_services.includes(s)}
                disabled={form.enabled_services.length === 1 && form.enabled_services.includes(s)}
                onChange={(on) => set('enabled_services', toggleIn(form.enabled_services, s, on))}
              />
            ))}
          </div>
          <div className="card">
            <h3>Formas de pagamento</h3>
            <p className="card-sub">O pagamento é feito no caixa; aqui você define o que aceita.</p>
            {(Object.keys(paymentMethodLabels) as PaymentMethod[]).map((m) => (
              <Toggle
                key={m}
                label={paymentMethodLabels[m]}
                checked={form.accepted_payments.includes(m)}
                disabled={form.accepted_payments.length === 1 && form.accepted_payments.includes(m)}
                onChange={(on) => set('accepted_payments', toggleIn(form.accepted_payments, m, on))}
              />
            ))}
            {form.accepted_payments.includes('PIX') && (
              <label className="field" style={{ marginTop: 12 }}><span>Chave PIX (opcional)</span><input value={form.pix_key ?? ''} maxLength={100} placeholder="CPF, CNPJ, e-mail, telefone ou chave aleatória" onChange={(e) => set('pix_key', e.target.value)} /><small className="muted">Mostrada ao cliente que escolher PIX, com botão de copiar.</small></label>
            )}
          </div>
          <div className="card">
            <h3>Valores</h3>
            <div className="grid-3">
              <MoneyInput label="Pedido mínimo" value={form.min_order_value} onChange={(v) => set('min_order_value', v || '0.00')} hint="0 = sem mínimo" />
              <MoneyInput label="Taxa de entrega" value={form.delivery_fee} onChange={(v) => set('delivery_fee', v || '0.00')} />
              <label className="field"><span>Taxa de serviço (%)</span><input type="number" min={0} max={30} step="0.5" value={form.service_fee_percent} onChange={(e) => set('service_fee_percent', e.target.value)} /><small className="muted">Só pedidos na mesa.</small></label>
            </div>
          </div>
        </>
      )}

      {tab === 'tables' && <TablesTab slug={form.slug} menuUrl={menuUrl} />}
      {tab === 'account' && <AccountTab settings={saved} />}

      {dirty && (
        <div className="save-bar no-print" role="status">
          <span>Você tem alterações não salvas.</span>
          <div className="row">
            <button className="btn" onClick={() => setForm(saved)} disabled={saving}>Descartar</button>
            <button className="btn primary" onClick={() => void save()} disabled={saving}>{saving ? 'Salvando…' : 'Salvar alterações'}</button>
          </div>
        </div>
      )}
    </section>
  )
}

function HoursEditor({ value, onChange }: { value: OpeningHours; onChange: (v: OpeningHours) => void }) {
  const setDay = (key: DayKey, intervals: string[][]) => {
    const next = { ...value }
    if (intervals.length) next[key] = intervals
    else delete next[key]
    onChange(next)
  }
  const copyToAll = (key: DayKey) => {
    const source = value[key] ?? []
    onChange(Object.fromEntries(DAYS.map((d) => [d.key, source.map((i) => [...i])])) as OpeningHours)
  }
  return (
    <div className="card">
      <h3>Horário de funcionamento</h3>
      <p className="card-sub">Se fechar depois da meia-noite, use um horário final menor que o inicial (ex.: 18:00 às 02:00).</p>
      <div className="hours-editor">
        {DAYS.map(({ key, label }) => {
          const intervals = value[key] ?? []
          return (
            <div className="hours-day" key={key}>
              <strong style={{ paddingTop: 8 }}>{label}</strong>
              <div className="hours-intervals">
                {intervals.length === 0 && <span className="muted" style={{ paddingTop: 8 }}>Fechado</span>}
                {intervals.map(([open, close], i) => (
                  <div className="hours-interval" key={i}>
                    <input type="time" value={open} onChange={(e) => setDay(key, intervals.map((it, j) => (j === i ? [e.target.value, it[1]] : it)))} aria-label={`${label} abre`} />
                    <span>até</span>
                    <input type="time" value={close} onChange={(e) => setDay(key, intervals.map((it, j) => (j === i ? [it[0], e.target.value] : it)))} aria-label={`${label} fecha`} />
                    <button type="button" className="icon-btn" onClick={() => setDay(key, intervals.filter((_, j) => j !== i))} aria-label="Remover horário"><Trash2 size={15} /></button>
                  </div>
                ))}
                <div className="row">
                  {intervals.length < 4 && <button type="button" className="btn small" onClick={() => setDay(key, [...intervals, intervals.length ? ['18:00', '22:00'] : ['08:00', '18:00']])}><Plus size={13} /> Horário</button>}
                  {intervals.length > 0 && <button type="button" className="btn small ghost" onClick={() => copyToAll(key)}>Copiar para todos os dias</button>}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function TablesTab({ slug, menuUrl }: { slug: string; menuUrl: string }) {
  const [count, setCount] = useState(10)
  const [prefix, setPrefix] = useState('')
  const [qrs, setQrs] = useState<Array<{ label: string; src: string }>>([])
  const [menuQr, setMenuQr] = useState('')

  useEffect(() => { void QRCode.toDataURL(menuUrl, { margin: 1, width: 360 }).then(setMenuQr) }, [menuUrl])

  async function generate() {
    const total = Math.min(Math.max(1, count), 200)
    setQrs(await Promise.all(Array.from({ length: total }, async (_, i) => {
      const label = `${prefix ? `${prefix} ` : ''}${i + 1}`
      return { label, src: await QRCode.toDataURL(tenantUrl(slug, `/?mesa=${encodeURIComponent(label)}`), { margin: 1, width: 260 }) }
    })))
  }

  function print() {
    document.body.classList.add('printing-qr')
    const cleanup = () => { document.body.classList.remove('printing-qr'); window.removeEventListener('afterprint', cleanup) }
    window.addEventListener('afterprint', cleanup)
    window.print()
  }

  return (
    <>
      <div className="card">
        <h3>Link do seu cardápio</h3>
        <p className="card-sub">Divulgue no Instagram, WhatsApp e Google Meu Negócio.</p>
        <div className="share-box">
          <code>{menuUrl}</code>
          <button className="btn small" onClick={() => { void navigator.clipboard?.writeText(menuUrl); toast.success('Link copiado') }}><Copy size={14} /> Copiar</button>
        </div>
        {menuQr && <div style={{ marginTop: 14 }}><img src={menuQr} alt="QR Code do cardápio" width={160} height={160} style={{ borderRadius: 12, background: '#fff', padding: 6 }} /></div>}
      </div>
      <div className={`card ${qrs.length ? 'qr-print-area' : ''}`}>
        <h3>QR Code por mesa</h3>
        <p className="card-sub">Cada QR abre o cardápio com o número da mesa já preenchido. Imprima e cole nas mesas.</p>
        <div className="row no-print">
          <label className="field" style={{ margin: 0, width: 120 }}><span>Quantas mesas</span><input type="number" min={1} max={200} value={count} onChange={(e) => setCount(Number(e.target.value))} /></label>
          <label className="field" style={{ margin: 0, width: 160 }}><span>Prefixo (opcional)</span><input value={prefix} maxLength={12} placeholder="Ex.: Mesa" onChange={(e) => setPrefix(e.target.value)} /></label>
          <button className="btn primary" style={{ alignSelf: 'flex-end' }} onClick={() => void generate()}>Gerar QR Codes</button>
          {qrs.length > 0 && <button className="btn" style={{ alignSelf: 'flex-end' }} onClick={print}><Printer size={16} /> Imprimir</button>}
        </div>
        <div className="qr-grid">
          {qrs.map((q) => <figure key={q.label}><img src={q.src} alt={`QR da mesa ${q.label}`} /><figcaption>{q.label}</figcaption></figure>)}
        </div>
      </div>
    </>
  )
}

function AccountTab({ settings }: { settings: TenantSettings }) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [busy, setBusy] = useState(false)
  const trialDays = settings.trial_ends_at ? Math.ceil((new Date(settings.trial_ends_at).getTime() - Date.now()) / 86_400_000) : null

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    try {
      await changePassword(current, next)
      setCurrent(''); setNext('')
      toast.success('Senha alterada')
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível alterar a senha.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="card">
        <h3>Plano</h3>
        <div className="row between">
          <div>
            <strong>{settings.status === 'TRIAL' ? 'Período de teste' : `Plano ${settings.plan}`}</strong>
            <p className="muted" style={{ margin: 0 }}>
              {settings.status === 'TRIAL' && trialDays !== null ? (trialDays > 0 ? `${trialDays} dia(s) restantes` : 'Teste encerrado') : 'Conta ativa'} · cliente desde {formatDate(settings.created_at)}
            </p>
          </div>
          <span className={`badge ${settings.status === 'ACTIVE' ? 'ok' : 'warn'}`}>{settings.status === 'ACTIVE' ? 'Ativo' : 'Teste'}</span>
        </div>
      </div>
      <form className="card" onSubmit={submit}>
        <h3>Alterar minha senha</h3>
        <div className="grid-2" style={{ marginTop: 10 }}>
          <label className="field"><span>Senha atual</span><input type="password" required autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} /></label>
          <label className="field"><span>Nova senha (mín. 8)</span><input type="password" required minLength={8} autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} /></label>
        </div>
        <button className="btn" disabled={busy}>{busy ? 'Alterando…' : 'Alterar senha'}</button>
      </form>
    </>
  )
}
