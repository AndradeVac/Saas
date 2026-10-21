import { AlertTriangle, BellRing, Check, Clock, Coffee, Plus, Receipt, Settings, Timer, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { Modal } from '../../components/ui/Modal'
import { EmptyState, PageHeader, Skeleton } from '../../components/ui/parts'
import { formatMoney, orderStatusLabels, paymentMethodLabels } from '../../lib/format'
import { apiErrorMessage } from '../../services/api'
import { approveTab, cancelTab, closeTab, tabStatusLabels, type StaffTab } from '../../services/tabs'
import type { OrderStatus, PaymentMethod } from '../../types'
import { useTenant } from '../tenant/TenantProvider'
import { useTablesLive } from './TablesLive'

/** Who needs the floor staff first: new tables, bills requested, idle tables, then the rest by table number. */
function priority(tab: StaffTab) {
  if (tab.alerts.needs_approval) return 0
  if (tab.alerts.wants_to_close) return 1
  if (tab.alerts.late_orders > 0) return 2
  if (tab.alerts.idle) return 3
  return 4
}

const tableOrder = (a: StaffTab, b: StaffTab) =>
  priority(a) - priority(b) || a.table_label.localeCompare(b.table_label, 'pt-BR', { numeric: true })

function duration(minutes: number) {
  if (minutes < 1) return 'menos de 1 min'
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  return `${hours}h${String(minutes % 60).padStart(2, '0')}`
}

export function TablesPage() {
  const { tenant } = useTenant()
  const { tabs, loading, refresh } = useTablesLive()
  const [closing, setClosing] = useState<StaffTab | null>(null)
  const [cancelling, setCancelling] = useState<StaffTab | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const sorted = useMemo(() => [...tabs].sort(tableOrder), [tabs])
  const openTotal = tabs.reduce((sum, tab) => sum + Number(tab.totals.total), 0)

  async function approve(tab: StaffTab) {
    setBusy(tab.id)
    try {
      await approveTab(tab.id)
      toast.success(`Mesa ${tab.table_label} confirmada. O pedido foi para a cozinha.`)
      await refresh()
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível confirmar a mesa.'))
    } finally {
      setBusy(null)
    }
  }

  if (!tenant.tabs_enabled) {
    return (
      <section className="page narrow">
        <PageHeader title="Mesas" subtitle="Comanda digital por mesa, sem fichas nem papel." />
        <div className="card">
          <EmptyState
            icon={<Receipt size={26} />}
            title="A comanda por mesa está desligada"
            hint="Ligue para que cada mesa tenha uma conta aberta: o cliente pede pelo QR Code quantas vezes quiser e paga tudo no final."
            action={<Link className="btn primary" to="/painel/configuracoes"><Settings size={16} /> Ativar nas configurações</Link>}
          />
        </div>
      </section>
    )
  }

  return (
    <section className="page">
      <PageHeader
        title="Mesas"
        subtitle={tabs.length ? `${tabs.length} ${tabs.length === 1 ? 'mesa aberta' : 'mesas abertas'} · ${formatMoney(openTotal)} em aberto` : 'Nenhuma mesa aberta agora.'}
        actions={<Link className="btn primary" to="/painel/pedidos/novo"><Plus size={16} /> Lançar pedido</Link>}
      />

      {loading ? <Skeleton lines={4} height={120} /> : sorted.length === 0 ? (
        <div className="card">
          <EmptyState icon={<Coffee size={26} />} title="Salão tranquilo" hint="Quando um cliente pedir pelo QR Code da mesa, a comanda aparece aqui na hora." />
        </div>
      ) : (
        <div className="tables-grid">
          {sorted.map((tab) => {
            const { alerts } = tab
            const live = tab.orders.filter((o) => o.status !== 'CANCELLED')
            return (
              <article key={tab.id} className={`table-card prio-${priority(tab)}`}>
                <header>
                  <div>
                    <span className="table-label">Mesa {tab.table_label}</span>
                    <small className="muted">#{tab.number} · aberta há {duration(alerts.minutes_open)}{tab.opened_by ? ` · ${tab.opened_by}` : ''}</small>
                  </div>
                  <span className={`badge tab-${tab.status.toLowerCase()}`}>{tabStatusLabels[tab.status]}</span>
                </header>

                <div className="table-alerts">
                  {alerts.needs_approval && <span className="alert-chip danger"><BellRing size={14} /> Cliente novo: confirme a mesa</span>}
                  {alerts.wants_to_close && (
                    <span className="alert-chip ok">
                      <Receipt size={14} /> Pediu a conta{tab.requested_payment_method ? ` · ${paymentMethodLabels[tab.requested_payment_method]}` : ''}
                      {tab.split_count && tab.split_count > 1 && tab.totals.per_person ? ` · ${tab.split_count}× ${formatMoney(tab.totals.per_person)}` : ''}
                    </span>
                  )}
                  {alerts.late_orders > 0 && <span className="alert-chip warn"><AlertTriangle size={14} /> {alerts.late_orders} {alerts.late_orders === 1 ? 'pedido atrasado' : 'pedidos atrasados'}</span>}
                  {alerts.idle && <span className="alert-chip info"><Timer size={14} /> Parada há {duration(alerts.minutes_since_last_order ?? 0)}: ofereça mais uma rodada</span>}
                </div>

                <ul className="table-orders">
                  {live.slice(-3).map((order) => (
                    <li key={order.id}>
                      <span>#{order.order_number} · {order.items.map((i) => `${i.quantity}× ${i.product_name}`).join(', ')}</span>
                      <span className={`badge status-${order.status.toLowerCase()}`}>{orderStatusLabels[order.status as OrderStatus]}</span>
                    </li>
                  ))}
                  {live.length > 3 && <li className="muted">+ {live.length - 3} pedidos anteriores</li>}
                </ul>

                <footer>
                  <div className="table-total"><small>Total</small><strong>{formatMoney(tab.totals.total)}</strong></div>
                  <div className="row">
                    {tab.status === 'PENDING' ? (
                      <>
                        <button className="btn small" onClick={() => setCancelling(tab)}><X size={15} /> Recusar</button>
                        <button className="btn primary small" disabled={busy === tab.id} onClick={() => void approve(tab)}><Check size={15} /> Confirmar mesa</button>
                      </>
                    ) : (
                      <>
                        <button className="icon-btn" title="Cancelar comanda" onClick={() => setCancelling(tab)}><X size={16} /></button>
                        <Link className="btn small" to={`/painel/pedidos/novo?mesa=${encodeURIComponent(tab.table_label)}`}><Plus size={15} /> Pedido</Link>
                        <button className={`btn small ${alerts.wants_to_close ? 'primary' : ''}`} onClick={() => setClosing(tab)}><Receipt size={15} /> Fechar conta</button>
                      </>
                    )}
                  </div>
                </footer>
              </article>
            )
          })}
        </div>
      )}

      {closing && <CloseTabModal tab={closing} accepted={tenant.accepted_payments} onClose={() => setClosing(null)} onDone={refresh} />}
      {cancelling && <CancelTabModal tab={cancelling} onClose={() => setCancelling(null)} onDone={refresh} />}
    </section>
  )
}

function CloseTabModal({ tab, accepted, onClose, onDone }: { tab: StaffTab; accepted: PaymentMethod[]; onClose: () => void; onDone: () => Promise<void> }) {
  const [method, setMethod] = useState<PaymentMethod>(tab.requested_payment_method ?? accepted[0])
  const [saving, setSaving] = useState(false)
  const cooking = tab.orders.filter((o) => o.status === 'RECEIVED' || o.status === 'PREPARING').length

  async function confirm() {
    setSaving(true)
    try {
      await closeTab(tab.id, method)
      toast.success(`Mesa ${tab.table_label} fechada e liberada.`)
      onClose()
      await onDone()
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível fechar a conta.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      title={`Fechar a conta da mesa ${tab.table_label}`}
      onClose={onClose}
      size="sm"
      footer={<><button className="btn" onClick={onClose}>Voltar</button><button className="btn primary" disabled={saving || cooking > 0} onClick={() => void confirm()}><Check size={16} /> Recebi {formatMoney(tab.totals.total)}</button></>}
    >
      {cooking > 0 && <div className="alert warn">Há {cooking} pedido(s) ainda na cozinha. Entregue ou cancele antes de fechar.</div>}
      <div className="card flat">
        <div className="total-row sub"><span>Consumo</span><span>{formatMoney(tab.totals.subtotal)}</span></div>
        {Number(tab.totals.discount) > 0 && <div className="total-row sub discount"><span>Descontos</span><span>−{formatMoney(tab.totals.discount)}</span></div>}
        {Number(tab.totals.service_fee) > 0 && <div className="total-row sub"><span>Taxa de serviço</span><span>{formatMoney(tab.totals.service_fee)}</span></div>}
        <div className="total-row"><span>Total</span><strong>{formatMoney(tab.totals.total)}</strong></div>
        {tab.split_count && tab.split_count > 1 && tab.totals.per_person && (
          <div className="total-row sub"><span><Clock size={13} /> Dividida em {tab.split_count}</span><span>{formatMoney(tab.totals.per_person)} cada</span></div>
        )}
      </div>
      <h4>Forma de pagamento</h4>
      <div className="pay-grid">
        {accepted.map((m) => <button key={m} className={`pay-option ${method === m ? 'active' : ''}`} onClick={() => setMethod(m)}>{paymentMethodLabels[m]}</button>)}
      </div>
      <p className="muted">Ao confirmar, todos os pedidos da mesa ficam pagos e a mesa é liberada para o próximo cliente.</p>
    </Modal>
  )
}

function CancelTabModal({ tab, onClose, onDone }: { tab: StaffTab; onClose: () => void; onDone: () => Promise<void> }) {
  const pending = tab.status === 'PENDING'
  const [reason, setReason] = useState(pending ? 'Pedido não reconhecido pela mesa' : '')
  const [saving, setSaving] = useState(false)

  async function confirm() {
    setSaving(true)
    try {
      await cancelTab(tab.id, reason)
      toast.success(pending ? `Pedido da mesa ${tab.table_label} recusado.` : `Comanda da mesa ${tab.table_label} cancelada.`)
      onClose()
      await onDone()
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível cancelar.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      title={pending ? `Recusar a mesa ${tab.table_label}?` : `Cancelar a comanda da mesa ${tab.table_label}?`}
      onClose={onClose}
      size="sm"
      footer={<><button className="btn" onClick={onClose}>Voltar</button><button className="btn danger-solid" disabled={saving || reason.trim().length < 2} onClick={() => void confirm()}>{pending ? 'Recusar' : 'Cancelar comanda'}</button></>}
    >
      <p>Os pedidos desta {pending ? 'mesa' : 'comanda'} serão cancelados e não entram no faturamento.</p>
      <label className="field"><span>Motivo</span><input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={200} autoFocus /></label>
    </Modal>
  )
}
