import QRCode from 'qrcode'
import { useEffect, useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { businessTypeLabels } from '../../lib/format'
import { tenantUrl } from '../../lib/tenant'
import { apiErrorMessage } from '../../services/api'
import { changePassword } from '../../services/auth'
import { getTenantSettings, updateTenantSettings } from '../../services/admin'
import type { BusinessType, TenantSettings } from '../../types'
import { useTenant } from '../tenant/TenantProvider'

export function SettingsPage() {
  const { setTenant } = useTenant()
  const [settings, setSettings] = useState<TenantSettings | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [passwords, setPasswords] = useState({ current: '', next: '' })
  const [tables, setTables] = useState(10)
  const [qrs, setQrs] = useState<Array<{ table: number; src: string }>>([])

  useEffect(() => {
    getTenantSettings().then(setSettings).catch(() => setError('Não foi possível carregar as configurações.'))
  }, [])

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!settings) return
    setSaving(true)
    setError('')
    try {
      const updated = await updateTenantSettings({
        name: settings.name,
        business_type: settings.business_type,
        phone: settings.phone || null,
        logo_url: settings.logo_url || null,
        primary_color: settings.primary_color,
        accepting_orders: settings.accepting_orders,
      })
      setSettings(updated)
      setTenant(updated)
      toast.success('Configurações salvas.')
    } catch (err) {
      setError(apiErrorMessage(err, 'Não foi possível salvar.'))
    } finally {
      setSaving(false)
    }
  }

  async function updatePassword(event: FormEvent) {
    event.preventDefault()
    try {
      await changePassword(passwords.current, passwords.next)
      setPasswords({ current: '', next: '' })
      toast.success('Senha alterada.')
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível alterar a senha.'))
    }
  }

  async function generateQrs() {
    if (!settings) return
    const count = Math.min(Math.max(1, tables), 200)
    const items = await Promise.all(Array.from({ length: count }, async (_, i) => ({
      table: i + 1,
      src: await QRCode.toDataURL(tenantUrl(settings.slug, `/?mesa=${i + 1}`), { margin: 1, width: 240 }),
    })))
    setQrs(items)
  }

  if (!settings) return <section className="page">{error ? <div className="alert error">{error}</div> : <div className="empty">Carregando…</div>}</section>
  const menuUrl = tenantUrl(settings.slug, '/')
  const set = <K extends keyof TenantSettings>(key: K, value: TenantSettings[K]) => setSettings({ ...settings, [key]: value })
  const trialDays = settings.trial_ends_at ? Math.ceil((new Date(settings.trial_ends_at).getTime() - Date.now()) / 86_400_000) : null

  return (
    <section className="page narrow">
      <div className="page-head"><div><h1>Configurações</h1><p className="muted">Endereço do cardápio: <a href={menuUrl} target="_blank" rel="noreferrer">{menuUrl}</a></p></div></div>
      {settings.status === 'TRIAL' && trialDays !== null && (
        <div className="alert warn">Período de teste: {trialDays > 0 ? `${trialDays} dia(s) restantes` : 'encerrado'}.</div>
      )}
      {error && <div className="alert error">{error}</div>}

      <form className="card" onSubmit={save}>
        <h3>Seu estabelecimento</h3>
        <div className="grid-2">
          <label className="field"><span>Nome</span><input required value={settings.name} onChange={(e) => set('name', e.target.value)} /></label>
          <label className="field"><span>Tipo</span>
            <select value={settings.business_type} onChange={(e) => set('business_type', e.target.value as BusinessType)}>
              {(Object.keys(businessTypeLabels) as BusinessType[]).map((t) => <option key={t} value={t}>{businessTypeLabels[t]}</option>)}
            </select>
          </label>
          <label className="field"><span>Telefone</span><input value={settings.phone ?? ''} onChange={(e) => set('phone', e.target.value)} /></label>
          <label className="field"><span>Cor da marca</span><input type="color" value={settings.primary_color} onChange={(e) => set('primary_color', e.target.value)} /></label>
        </div>
        <label className="field"><span>Link da logo (opcional)</span><input type="url" placeholder="https://…" value={settings.logo_url ?? ''} onChange={(e) => set('logo_url', e.target.value)} /></label>
        <label className="check"><input type="checkbox" checked={settings.accepting_orders} onChange={(e) => set('accepting_orders', e.target.checked)} /> Aceitando pedidos pelo cardápio digital</label>
        <button className="btn primary" disabled={saving}>{saving ? 'Salvando…' : 'Salvar'}</button>
      </form>

      <div className="card">
        <h3>QR Codes das mesas</h3>
        <p className="muted">Cada QR abre o cardápio já com o número da mesa preenchido.</p>
        <div className="inline-form">
          <input className="input" type="number" min={1} max={200} value={tables} onChange={(e) => setTables(Number(e.target.value))} aria-label="Quantidade de mesas" />
          <button className="btn" onClick={() => void generateQrs()}>Gerar QR Codes</button>
          {qrs.length > 0 && <button className="btn" onClick={() => window.print()}>Imprimir</button>}
        </div>
        <div className="qr-grid">
          {qrs.map((q) => <figure key={q.table}><img src={q.src} alt={`QR da mesa ${q.table}`} /><figcaption>Mesa {q.table}</figcaption></figure>)}
        </div>
      </div>

      <form className="card" onSubmit={updatePassword}>
        <h3>Alterar minha senha</h3>
        <div className="grid-2">
          <label className="field"><span>Senha atual</span><input type="password" required autoComplete="current-password" value={passwords.current} onChange={(e) => setPasswords({ ...passwords, current: e.target.value })} /></label>
          <label className="field"><span>Nova senha (mín. 8)</span><input type="password" required minLength={8} autoComplete="new-password" value={passwords.next} onChange={(e) => setPasswords({ ...passwords, next: e.target.value })} /></label>
        </div>
        <button className="btn">Alterar senha</button>
      </form>
    </section>
  )
}
