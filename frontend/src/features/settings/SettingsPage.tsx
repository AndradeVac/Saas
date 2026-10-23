import { Copy, Download, Plus, Printer, Trash2 } from 'lucide-react'
import { downloadCsv } from '../../services/orders'
import { usePlan } from '../plans/PlanProvider'
import QRCode from 'qrcode'
import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { ImageUpload } from '../../components/ui/ImageUpload'
import { MoneyInput } from '../../components/ui/MoneyInput'
import { ErrorBanner, PageHeader, Skeleton } from '../../components/ui/parts'
import { Toggle } from '../../components/ui/Toggle'
import { Modal } from '../../components/ui/Modal'
import { DAYS, businessTypeLabels, formatDate, maskPhone, paymentMethodLabels, realPaymentMethods, serviceLabels } from '../../lib/format'
import { tenantUrl } from '../../lib/tenant'
import { apiErrorMessage } from '../../services/api'
import { changePassword } from '../../services/auth'
import { useSearchParams } from 'react-router-dom'
import { writeJson } from '../../lib/storage'
import { getTableQrCodes } from '../../services/tabs'
import { getMediaUsage, getPixPreview, getTenantSettings, updateTenantSettings, type UploadResult } from '../../services/tenant'
import type { BusinessType, DayKey, DeliveryZone, OpeningHours, ServiceType, TenantSettings } from '../../types'
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
  name: s.name, business_type: s.business_type, description: s.description, phone: s.phone, address: s.address, city: s.city,
  instagram: s.instagram, pix_key: s.pix_key, logo_url: s.logo_url, cover_url: s.cover_url, primary_color: s.primary_color,
  accepting_orders: s.accepting_orders, hours_mode: s.hours_mode, opening_hours: s.opening_hours,
  enabled_services: s.enabled_services, accepted_payments: s.accepted_payments,
  delivery_fee: s.delivery_fee, min_order_value: s.min_order_value, service_fee_percent: s.service_fee_percent,
  tabs_enabled: s.tabs_enabled, tabs_auto_approve: s.tabs_auto_approve, tab_idle_minutes: s.tab_idle_minutes,
  prep_minutes: s.prep_minutes, delivery_minutes: s.delivery_minutes, delivery_zones: s.delivery_zones, require_pix_delivery: s.require_pix_delivery,
  require_pix_takeaway: s.require_pix_takeaway,
  loyalty_enabled: s.loyalty_enabled, loyalty_goal: s.loyalty_goal, loyalty_reward: s.loyalty_reward || null,
  google_review_url: s.google_review_url || null, scheduling_enabled: s.scheduling_enabled, notify_customers: s.notify_customers,
})

/** Neighbourhoods served and the fee of each (empty list = one flat fee for any address). */
function DeliveryZones({ zones, onChange }: { zones: DeliveryZone[]; onChange: (zones: DeliveryZone[]) => void }) {
  const update = (index: number, data: Partial<DeliveryZone>) => onChange(zones.map((z, i) => (i === index ? { ...z, ...data } : z)))
  return (
    <div className="zones">
      <h4>Bairros atendidos (opcional)</h4>
      <p className="card-sub">Com a lista, o cliente escolhe o bairro e paga a taxa dele. Sem lista, vale a taxa de entrega única.</p>
      {zones.map((zone, index) => (
        <div className="zone-row" key={index}>
          <input className="input" value={zone.name} placeholder="Bairro" maxLength={60} onChange={(e) => update(index, { name: e.target.value })} aria-label="Bairro" />
          <MoneyInput label="Taxa" value={zone.fee} onChange={(v) => update(index, { fee: v || '0.00' })} />
          <button type="button" className="icon-btn" aria-label={`Remover ${zone.name || 'bairro'}`} onClick={() => onChange(zones.filter((_, i) => i !== index))}><Trash2 size={16} /></button>
        </div>
      ))}
      <button type="button" className="btn small" onClick={() => onChange([...zones, { name: '', fee: '5.00' }])}><Plus size={14} /> Adicionar bairro</button>
    </div>
  )
}

function toggleIn<T>(list: T[], item: T, on: boolean) {
  return on ? [...list.filter((x) => x !== item), item] : list.filter((x) => x !== item)
}

/** Generates a R$ 1,00 QR Code for the typed key, so the owner can pay it and see the money arrive. */
function PixTest({ pixKey }: { pixKey: string }) {
  const [qr, setQr] = useState<{ img: string; code: string } | null>(null)
  const [error, setError] = useState('')
  async function test() {
    setError('')
    try {
      const pix = await getPixPreview(pixKey)
      setQr({ img: await QRCode.toDataURL(pix.code, { margin: 1, width: 260 }), code: pix.code })
    } catch (err) {
      setError(apiErrorMessage(err, 'Chave PIX inválida.'))
    }
  }
  return (
    <div>
      <button type="button" className="btn small" onClick={() => void test()}>Testar minha chave (QR de R$ 1,00)</button>
      {error && <p className="field-error">{error}</p>}
      {qr && (
        <Modal title="Teste da chave PIX" onClose={() => setQr(null)} size="sm">
          <p className="muted">Pague este QR de <strong>R$ 1,00</strong> pelo app do seu banco. Se o dinheiro cair na sua conta, está tudo certo: é assim que seus clientes vão pagar.</p>
          <img className="pix-qr" src={qr.img} alt="QR Code PIX de teste" />
          <div className="pix-box"><code className="pix-code">{qr.code}</code><button className="btn small" onClick={() => { void navigator.clipboard?.writeText(qr.code); toast.success('PIX copiado') }}><Copy size={14} /> Copiar</button></div>
        </Modal>
      )}
    </div>
  )
}

export function SettingsPage() {
  const { setTenant } = useTenant()
  const plan = usePlan()
  const [saved, setSaved] = useState<TenantSettings | null>(null)
  const [form, setForm] = useState<TenantSettings | null>(null)
  // ?aba=tables (etc.) opens a tab directly, e.g. from the dashboard's first steps.
  const [params] = useSearchParams()
  const [tab, setTab] = useState<Tab>(() => (tabs.some((t) => t.key === params.get('aba')) ? (params.get('aba') as Tab) : 'business'))
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
        phone: form.phone || null, address: form.address || null, city: form.city || null, instagram: form.instagram || null,
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
        {tabs.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            className={tab === t.key ? 'active' : ''}
            onClick={() => setTab(t.key)}
            ref={(el) => { if (el && tab === t.key) el.scrollIntoView({ block: 'nearest', inline: 'center' }) }}
          >{t.label}</button>
        ))}
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
          <div className="grid-2">
            <label className="field"><span>Endereço</span><input maxLength={200} placeholder="Rua, número – bairro" value={form.address ?? ''} onChange={(e) => set('address', e.target.value)} /></label>
            <label className="field"><span>Cidade</span><input maxLength={60} placeholder="Ex.: São Paulo" value={form.city ?? ''} onChange={(e) => set('city', e.target.value)} /><small className="muted">Aparece no PIX que o cliente paga pela mesa.</small></label>
          </div>
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
            <h3>Comanda por mesa</h3>
            <p className="card-sub">Substitui fichas e comandas de papel: o cliente pede pelo QR Code da mesa quantas vezes quiser e paga tudo no final.</p>
            <Toggle
              label="Comanda aberta nas mesas (pague ao final)"
              hint="Pedidos na mesa vão para a conta da mesa. Retirada e entrega continuam pagando no pedido."
              checked={form.tabs_enabled}
              onChange={(on) => set('tabs_enabled', on)}
            />
            {form.tabs_enabled && (
              <>
                <Toggle
                  label="Confirmar automaticamente mesas novas"
                  hint="Desligado (recomendado): o garçom confirma o primeiro pedido de cada mesa, para evitar pedidos de quem não está no salão."
                  checked={form.tabs_auto_approve}
                  onChange={(on) => set('tabs_auto_approve', on)}
                />
                <label className="field" style={{ marginTop: 12, maxWidth: 320 }}>
                  <span>Sugerir “mais uma rodada” após (minutos)</span>
                  <input type="number" min={5} max={180} value={form.tab_idle_minutes} onChange={(e) => set('tab_idle_minutes', Number(e.target.value) || 20)} />
                  <small className="muted">O cliente recebe o convite no celular e a mesa fica destacada para o garçom.</small>
                </label>
              </>
            )}
          </div>
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
            {realPaymentMethods.map((m) => (
              <Toggle
                key={m}
                label={paymentMethodLabels[m]}
                checked={form.accepted_payments.includes(m)}
                disabled={form.accepted_payments.length === 1 && form.accepted_payments.includes(m)}
                onChange={(on) => set('accepted_payments', toggleIn(form.accepted_payments, m, on))}
              />
            ))}
            {form.accepted_payments.includes('PIX') && (
              <>
                <label className="field" style={{ marginTop: 12 }}><span>Chave PIX</span><input value={form.pix_key ?? ''} maxLength={100} placeholder="CPF, CNPJ, e-mail, celular ou chave aleatória" onChange={(e) => set('pix_key', e.target.value)} /><small className="muted">Com a chave, cada pedido pago por PIX (retirada, entrega e a conta da mesa) mostra um <strong>QR Code com o valor exato</strong>. O dinheiro cai direto na sua conta; você confere no banco e marca como pago.</small></label>
                {form.pix_key && <PixTest pixKey={form.pix_key} />}
                {form.pix_key && form.enabled_services.includes('TAKEAWAY') && (
                  <Toggle label="Para viagem com PIX: preparar só depois do pagamento" hint="Evita fazer pedido que ninguém busca. Desligado, o pedido vai direto para a cozinha e você confere o PIX depois." checked={form.require_pix_takeaway} onChange={(on) => set('require_pix_takeaway', on)} />
                )}
                {form.enabled_services.includes('DELIVERY') && (
                  <Toggle label="Entrega só com PIX antecipado" hint="Contra trote: o pedido de entrega só vai para a cozinha depois que o PIX é confirmado." checked={form.require_pix_delivery} onChange={(on) => set('require_pix_delivery', on)} />
                )}
              </>
            )}
          </div>
          <div className="card">
            <h3>Valores</h3>
            <div className="grid-3">
              <MoneyInput label="Pedido mínimo" value={form.min_order_value} onChange={(v) => set('min_order_value', v || '0.00')} hint="0 = sem mínimo" />
              <MoneyInput label="Taxa de entrega" value={form.delivery_fee} onChange={(v) => set('delivery_fee', v || '0.00')} />
              <label className="field"><span>Taxa de serviço (%)</span><input type="number" min={0} max={30} step="0.5" value={form.service_fee_percent} onChange={(e) => set('service_fee_percent', e.target.value)} /><small className="muted">Só pedidos na mesa. É opcional para o cliente (por lei, gorjeta não é obrigatória).</small></label>
            </div>
            <div className="grid-2">
              <label className="field"><span>Tempo de preparo (min)</span><input type="number" min={5} max={240} value={form.prep_minutes} onChange={(e) => set('prep_minutes', Number(e.target.value))} /><small className="muted">Aparece para o cliente: “pronto em ~{form.prep_minutes} min”.</small></label>
              {form.enabled_services.includes('DELIVERY') && <label className="field"><span>Tempo de entrega (min)</span><input type="number" min={10} max={300} value={form.delivery_minutes} onChange={(e) => set('delivery_minutes', Number(e.target.value))} /></label>}
            </div>
            {form.enabled_services.includes('DELIVERY') && <DeliveryZones zones={form.delivery_zones} onChange={(zones) => set('delivery_zones', zones)} />}
          </div>
          <div className="card">
            <h3>Fidelidade, avaliações e encomendas</h3>
            {plan.has('loyalty') ? (
              <>
                <Toggle label="Cartão fidelidade" hint="A cada X pedidos entregues, o cliente ganha um prêmio. Ele acompanha os carimbos pela tela do pedido." checked={form.loyalty_enabled} onChange={(on) => set('loyalty_enabled', on)} />
                {form.loyalty_enabled && (
                  <div className="grid-2">
                    <label className="field"><span>Pedidos para ganhar</span><input type="number" min={2} max={50} value={form.loyalty_goal} onChange={(e) => set('loyalty_goal', Number(e.target.value))} /></label>
                    <label className="field"><span>Prêmio</span><input maxLength={120} placeholder="Ex.: 1 hambúrguer Clássico grátis" value={form.loyalty_reward ?? ''} onChange={(e) => set('loyalty_reward', e.target.value)} /></label>
                  </div>
                )}
              </>
            ) : (
              <button type="button" className="toggle disabled" onClick={() => plan.openUpgrade('O cartão fidelidade é do plano Profissional.')}><span className="toggle-text"><strong>Cartão fidelidade</strong><small>Disponível no plano Profissional.</small></span></button>
            )}
            <label className="field" style={{ marginTop: 12 }}><span>Link de avaliação do Google (opcional)</span><input value={form.google_review_url ?? ''} placeholder="https://g.page/r/..." onChange={(e) => set('google_review_url', e.target.value)} /><small className="muted">Quem der 5 estrelas no pedido é convidado a avaliar você no Google. Pegue o link no seu Perfil da Empresa no Google → “Pedir avaliações”.</small></label>
            <Toggle label="Avisar o cliente automaticamente" hint={plan.catalog?.whatsapp_auto ? 'Mensagem no WhatsApp do cliente quando o pedido entra em preparo e quando fica pronto (ou sai para entrega).' : 'Notificação no celular do cliente quando o pedido fica pronto. Quando marcar “pronto”, aparece também um botão para avisar pelo WhatsApp com um toque.'} checked={form.notify_customers} onChange={(on) => set('notify_customers', on)} />
            <Toggle label="Aceitar encomendas (pedido agendado)" hint="O cliente escolhe dia e hora para retirar ou receber, mesmo com a loja fechada. Ótimo para bolos e salgados de festa." checked={form.scheduling_enabled} onChange={(on) => set('scheduling_enabled', on)} />
          </div>
        </>
      )}

      {tab === 'tables' && <TablesTab menuUrl={menuUrl} slugForFlag={form.slug} />}
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

function TablesTab({ menuUrl, slugForFlag }: { menuUrl: string; slugForFlag: string }) {
  const [count, setCount] = useState(10)
  const [prefix, setPrefix] = useState('')
  const [qrs, setQrs] = useState<Array<{ label: string; src: string }>>([])
  const [menuQr, setMenuQr] = useState('')

  useEffect(() => { void QRCode.toDataURL(menuUrl, { margin: 1, width: 360 }).then(setMenuQr) }, [menuUrl])

  const tableLabels = () => {
    const params = new URLSearchParams()
    Array.from({ length: Math.min(Math.max(1, count), 200) }, (_, i) => `${prefix ? `${prefix} ` : ''}${i + 1}`).forEach((l) => params.append('labels', l))
    return params
  }
  async function download(path: string, params: URLSearchParams | undefined, name: string) {
    try {
      await downloadCsv(path, params, name)
      writeJson(`mesa:${slugForFlag}:qr-generated`, true)
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível gerar o material.'))
    }
  }

  async function generate() {
    const total = Math.min(Math.max(1, count), 200)
    const labels = Array.from({ length: total }, (_, i) => `${prefix ? `${prefix} ` : ''}${i + 1}`)
    try {
      // Each link carries the table's secret code (the comanda only accepts orders from the QR on that table).
      const links = await getTableQrCodes(labels)
      writeJson(`mesa:${slugForFlag}:qr-generated`, true)
      setQrs(await Promise.all(links.map(async (link, i) => ({
        label: labels[i], src: await QRCode.toDataURL(link.url, { margin: 1, width: 260 }),
      }))))
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível gerar os QR Codes.'))
    }
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
        <p className="card-sub">Cada QR abre o cardápio já na mesa certa, com um código de segurança: só quem está na mesa consegue pedir na comanda dela. Imprima e cole nas mesas. Se reimprimir, os QR antigos continuam valendo.</p>
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
      <div className="card no-print">
        <h3>Material de divulgação</h3>
        <p className="card-sub">Pronto para imprimir e postar, com a sua logo e a sua cor.</p>
        <div className="row">
          <button className="btn" onClick={() => void download('/marketing/table-cards.pdf', tableLabels(), 'qr-mesas.pdf')}><Download size={16} /> Displays de mesa ({Math.min(Math.max(1, count), 200)} mesas, PDF)</button>
          <button className="btn" onClick={() => void download('/marketing/poster.pdf', undefined, 'cartaz.pdf')}><Download size={16} /> Cartaz para a vitrine (PDF)</button>
          <button className="btn" onClick={() => void download('/marketing/instagram.png', undefined, 'post-instagram.png')}><Download size={16} /> Post para o Instagram</button>
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
