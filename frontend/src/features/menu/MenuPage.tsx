import { Clock, ClipboardList, Instagram, MapPin, MessageCircle, Phone, Plus, Receipt, Repeat2, Search, ShoppingBag, UtensilsCrossed, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { EmptyState, Skeleton } from '../../components/ui/parts'
import { DAYS, formatMoney, formatPhone, orderStatusLabels, serviceLabels } from '../../lib/format'
import { mediaUrl } from '../../lib/media'
import { readJson, writeJson } from '../../lib/storage'
import { APP_NAME, platformUrl } from '../../lib/tenant'
import { apiErrorMessage } from '../../services/api'
import { getMenu, trackOrder, type Menu, type MenuProduct, type Tracking } from '../../services/publicMenu'
import type { DayKey, OrderStatus } from '../../types'
import { buildLine, cartCount, cartSubtotal, repeatLines, type CartLine } from './cart'
import { CartModal } from './CartModal'
import { OrdersModal, TrackModal } from './OrderModals'
import { ProductModal } from './ProductModal'
import { TabModal } from './TabModal'
import { findTableTab, getPublicTab, tabStatusLabels, type PublicTab, type TabOrder } from '../../services/tabs'

type Modal = { kind: 'product'; product: MenuProduct } | { kind: 'cart' } | { kind: 'orders' } | { kind: 'track'; token: string; isNew: boolean } | { kind: 'tab'; highlight?: number } | null

const ACTIVE_TAB = ['PENDING', 'OPEN', 'CLOSING']
const COOKING = ['RECEIVED', 'PREPARING']

/** wa.me link for a Brazilian phone saved with or without the country code. */
function whatsappLink(phone: string | null) {
  const digits = (phone ?? '').replace(/\D/g, '')
  if (digits.length < 10) return null
  return `https://wa.me/${digits.length <= 11 ? `55${digits}` : digits}`
}

function Thumb({ product }: { product: MenuProduct }) {
  return product.image_url
    ? <img src={mediaUrl(product.image_url)} alt="" loading="lazy" />
    : <div className="product-placeholder" aria-hidden="true"><UtensilsCrossed size={26} /></div>
}

const JS_DAY_TO_KEY: DayKey[] = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat']

function HoursList({ hours }: { hours: Menu['tenant']['opening_hours'] }) {
  const today = JS_DAY_TO_KEY[new Date().getDay()]
  return (
    <div className="hours-pop">
      {DAYS.map(({ key, label }) => (
        <div key={key} className={key === today ? 'today' : ''}>
          <span>{label}</span>
          <span>{(hours[key] ?? []).length ? (hours[key] ?? []).map(([a, b]) => `${a} – ${b}`).join(', ') : 'Fechado'}</span>
        </div>
      ))}
    </div>
  )
}

export function MenuPage() {
  const [params] = useSearchParams()
  const [menu, setMenu] = useState<Menu | null>(null)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [activeCategory, setActiveCategory] = useState<string | null>(null)
  const [lines, setLines] = useState<CartLine[]>([])
  const [modal, setModal] = useState<Modal>(null)
  const [showHours, setShowHours] = useState(false)
  const [tokens, setTokens] = useState<string[]>([])
  const [latest, setLatest] = useState<{ token: string; data: Tracking } | null>(null)
  const sections = useRef(new Map<string, HTMLElement>())
  const tableFromQr = params.get('mesa') ?? ''
  const [tab, setTab] = useState<PublicTab | null>(null)
  const [now, setNow] = useState(() => Date.now())
  const [dismissedRound, setDismissedRound] = useState<string | null>(null)

  const load = useCallback(() => {
    setError('')
    getMenu().then(setMenu).catch((err) => setError(apiErrorMessage(err, 'Não foi possível carregar o cardápio.')))
  }, [])
  useEffect(load, [load])

  const slug = menu?.tenant.slug
  useEffect(() => { if (slug) setTokens(readJson<string[]>(`mesa:${slug}:tokens`, [])) }, [slug])

  // Comanda: find the bill already open at this table (another phone may have opened it) or the one this phone follows.
  const tabsEnabled = Boolean(menu?.tenant.tabs_enabled)
  const tabKey = slug ? `mesa:${slug}:tab` : ''
  const forgetTab = useCallback(() => { setTab(null); if (tabKey) writeJson(tabKey, null) }, [tabKey])
  useEffect(() => {
    if (!tabsEnabled || !tabKey) return
    const saved = readJson<{ token: string; table: string } | null>(tabKey, null)
    const lookup = tableFromQr ? findTableTab(tableFromQr) : saved ? getPublicTab(saved.token) : null
    lookup
      ?.then((found) => {
        if (ACTIVE_TAB.includes(found.status)) { setTab(found); writeJson(tabKey, { token: found.public_token, table: found.table_label }) }
        else forgetTab()
      })
      .catch(() => forgetTab())
  }, [tabsEnabled, tabKey, tableFromQr, forgetTab])

  // Live bill: keeps every phone at the table in sync and notices when the staff closes it.
  const tabToken = tab?.public_token
  useEffect(() => {
    if (!tabToken) return
    const timer = window.setInterval(() => {
      setNow(Date.now())
      getPublicTab(tabToken)
        .then((fresh) => {
          if (ACTIVE_TAB.includes(fresh.status)) return setTab(fresh)
          forgetTab()
          toast.success(fresh.status === 'CLOSED' ? 'Conta fechada. Obrigado pela visita!' : 'A comanda da mesa foi encerrada.', { duration: 5000 })
        })
        .catch(() => undefined)
    }, 8000)
    return () => window.clearInterval(timer)
  }, [tabToken, forgetTab])

  // Banner for the most recent order that is still in progress.
  useEffect(() => {
    const token = tokens[0]
    if (!token) { setLatest(null); return }
    let active = true
    let timer = 0
    const poll = () => trackOrder(token)
      .then((data) => {
        if (!active) return
        const finished = data.status === 'FINISHED' || data.status === 'CANCELLED'
        setLatest(finished ? null : { token, data })
        if (!finished) timer = window.setTimeout(poll, 8000)
      })
      .catch(() => { if (active) setLatest(null) })
    void poll()
    return () => { active = false; window.clearTimeout(timer) }
  }, [tokens])

  const products = useMemo(() => menu?.products ?? [], [menu])
  const term = search.trim().toLowerCase()
  const visible = useMemo(
    () => products.filter((p) => !term || `${p.name} ${p.description ?? ''}`.toLowerCase().includes(term)),
    [products, term],
  )
  // Photos sell: featured items with a picture lead the carousel.
  const featured = !term ? products.filter((p) => p.featured && p.available).sort((a, b) => Number(Boolean(b.image_url)) - Number(Boolean(a.image_url))) : []
  const quantities = useMemo(() => {
    const map = new Map<string, number>()
    lines.forEach((line) => map.set(line.productId, (map.get(line.productId) ?? 0) + line.quantity))
    return map
  }, [lines])

  // Highlight the category chip of the section currently on screen.
  useEffect(() => {
    if (!menu) return
    const observer = new IntersectionObserver(
      (entries) => {
        const top = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0]
        if (top) setActiveCategory((top.target as HTMLElement).dataset.cat ?? null)
      },
      { rootMargin: '-80px 0px -65% 0px' },
    )
    sections.current.forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [menu, visible.length])

  function addLine(line: CartLine) {
    setLines((current) => {
      const existing = current.find((l) => l.key === line.key)
      return existing
        ? current.map((l) => (l.key === line.key ? { ...l, quantity: Math.min(20, l.quantity + line.quantity) } : l))
        : [...current, line]
    })
    setModal(null)
    toast.success(`${line.name} adicionado`, { duration: 1500 })
  }

  async function onOrdered({ token, tabToken: newTab, number }: { token: string; tabToken: string | null; number: number }) {
    if (!slug) return
    if (newTab) {
      setLines([])
      try {
        const fresh = await getPublicTab(newTab)
        setTab(fresh)
        writeJson(tabKey, { token: fresh.public_token, table: fresh.table_label })
      } catch {
        // The order is placed either way; the bill shows up on the next refresh.
      }
      setModal({ kind: 'tab', highlight: number })
      return
    }
    const next = [token, ...tokens.filter((t) => t !== token)].slice(0, 10)
    setTokens(next)
    writeJson(`mesa:${slug}:tokens`, next)
    setLines([])
    setModal({ kind: 'track', token, isNew: true })
  }

  /** "Repetir a rodada": the same items again, straight into the cart. */
  function repeat(order: TabOrder) {
    const { lines: again, skipped } = repeatLines(products, order.items)
    if (again.length === 0) return toast.error('Esses itens não estão mais disponíveis.')
    setLines((current) => {
      const merged = [...current]
      for (const line of again) {
        const existing = merged.find((l) => l.key === line.key)
        if (existing) existing.quantity = Math.min(20, existing.quantity + line.quantity)
        else merged.push(line)
      }
      return merged
    })
    if (skipped) toast.message(`${skipped} item(ns) não estão mais disponíveis e ficaram de fora.`)
    setModal({ kind: 'cart' })
  }

  function scrollTo(categoryId: string) {
    sections.current.get(categoryId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    setActiveCategory(categoryId)
  }

  if (error) return <div className="auth-loading column"><p>{error}</p><button className="btn" onClick={load}>Tentar de novo</button></div>
  if (!menu) {
    return (
      <div className="menu-page"><div className="menu-hero" /><div className="menu-info"><Skeleton lines={4} height={20} /></div></div>
    )
  }

  const { tenant } = menu
  const canOrder = tenant.is_open
  const count = cartCount(lines)
  const hasCart = count > 0 && modal === null
  const tabOrders = tab?.orders.filter((o) => o.status !== 'CANCELLED') ?? []
  const lastRound = tabOrders[tabOrders.length - 1]
  // Automation: after a while without ordering (and nothing still cooking), suggest another round.
  const idleFor = tab?.last_order_at ? (now - new Date(tab.last_order_at).getTime()) / 60_000 : 0
  const offerRound = Boolean(
    tab && tab.status === 'OPEN' && lastRound && !hasCart && modal === null && canOrder
    && idleFor >= tenant.tab_idle_minutes && !tabOrders.some((o) => COOKING.includes(o.status))
    && dismissedRound !== tab.last_order_at,
  )
  // One tap adds simple products; products with sizes/extras open the modal so the customer sees the add-ons.
  const quickAdd = (product: MenuProduct) => {
    if (product.options.length > 0) setModal({ kind: 'product', product })
    else addLine(buildLine(product, {}, 1))
  }
  const productCard = (product: MenuProduct) => {
    const quantity = quantities.get(product.id) ?? 0
    return (
      <div className={`product-card-wrap ${product.available ? '' : 'sold-out'}`} key={product.id}>
        <button className="product-card" onClick={() => setModal({ kind: 'product', product })}>
          <div className="product-info">
            <h3>{product.name}</h3>
            {product.description && <p>{product.description}</p>}
            <span className="product-price">
              {product.options.length > 0 && Number(product.price) > 0 && <small>a partir de </small>}
              {formatMoney(product.price)}
            </span>
          </div>
          <div className="product-thumb">
            <Thumb product={product} />
            {quantity > 0 && <span className="product-qty">{quantity}</span>}
            {!product.available && <span className="product-flag">Esgotado</span>}
          </div>
        </button>
        {canOrder && product.available && (
          <button className="quick-add" onClick={() => quickAdd(product)} aria-label={`Adicionar ${product.name}`}><Plus size={18} /></button>
        )}
      </div>
    )
  }

  return (
    <div className={`menu-page ${hasCart || latest || tab ? 'has-cart' : ''}`}>
      <div className="menu-hero">
        {tenant.cover_url && <img src={mediaUrl(tenant.cover_url)} alt="" />}
        <div className="menu-topbar">
          {whatsappLink(tenant.phone) && (
            <a className="icon-btn" href={whatsappLink(tenant.phone)!} target="_blank" rel="noreferrer" aria-label="Falar no WhatsApp"><MessageCircle size={19} /></a>
          )}
          <button className="icon-btn" onClick={() => setModal({ kind: 'orders' })} aria-label="Meus pedidos"><ClipboardList size={19} /></button>
        </div>
      </div>

      <section className="menu-info">
        <div className="menu-info-head">
          {tenant.logo_url ? <img className="menu-logo" src={mediaUrl(tenant.logo_url)} alt="" /> : <div className="menu-logo">{tenant.name.charAt(0)}</div>}
          <div>
            <h1>{tenant.name}</h1>
            <span className={`chip ${tenant.is_open ? 'ok' : 'off'}`}><i className="dot-live" />{tenant.is_open ? 'Aberto agora' : tenant.accepting_orders ? 'Fora do horário' : 'Fechado'}</span>
          </div>
        </div>
        {tenant.description && <p className="menu-desc">{tenant.description}</p>}
        <div className="menu-meta">
          {tenant.address && <span><MapPin size={14} /> {tenant.address}</span>}
          {tenant.phone && <a href={`tel:${tenant.phone}`}><Phone size={14} /> {formatPhone(tenant.phone)}</a>}
          {tenant.instagram && <a href={`https://instagram.com/${tenant.instagram.replace('@', '')}`} target="_blank" rel="noreferrer"><Instagram size={14} /> {tenant.instagram.startsWith('@') ? tenant.instagram : `@${tenant.instagram}`}</a>}
          {tenant.hours_mode === 'SCHEDULE' && <a href="#horarios" onClick={(e) => { e.preventDefault(); setShowHours((v) => !v) }}><Clock size={14} /> Horários</a>}
        </div>
        {showHours && <HoursList hours={tenant.opening_hours} />}
        <div className="menu-chips">
          {tableFromQr && <span className="chip ok">Você está na mesa {tableFromQr}</span>}
          {tenant.enabled_services.map((s) => <span className="chip" key={s}>{serviceLabels[s]}</span>)}
          {Number(tenant.min_order_value) > 0 && <span className="chip">Pedido mín. {formatMoney(tenant.min_order_value)}</span>}
          {Number(tenant.delivery_fee) > 0 && tenant.enabled_services.includes('DELIVERY') && <span className="chip">Entrega {formatMoney(tenant.delivery_fee)}</span>}
        </div>
      </section>

      {!canOrder && (
        <div className="alert warn menu-closed">
          {tenant.accepting_orders ? 'Estamos fora do horário de atendimento. Você pode ver o cardápio, mas ainda não é possível pedir.' : 'No momento não estamos aceitando pedidos pelo cardápio digital.'}
        </div>
      )}

      <div className="menu-body">
        <label className="search menu-search">
          <Search size={16} />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar no cardápio" aria-label="Buscar no cardápio" />
          {search && <button className="icon-btn" onClick={() => setSearch('')} aria-label="Limpar busca"><X size={14} /></button>}
        </label>

        {menu.categories.length > 1 && !term && (
          <nav className="cat-nav" aria-label="Categorias">
            {menu.categories.map((c) => (
              <button key={c.id} className={activeCategory === c.id ? 'active' : ''} onClick={() => scrollTo(c.id)}>{c.name}</button>
            ))}
          </nav>
        )}

        {products.length === 0 && <EmptyState icon={<ShoppingBag size={26} />} title="Cardápio em preparação" hint="Em breve os produtos estarão disponíveis aqui." />}

        {featured.length > 0 && (
          <section>
            <h2 className="section-title">Destaques</h2>
            <div className="featured-row">
              {featured.map((p) => (
                <button className="featured-card" key={p.id} onClick={() => setModal({ kind: 'product', product: p })}>
                  <Thumb product={p} />
                  <div>
                    <strong>{p.name}</strong>
                    <span className="product-price">
                      {p.options.length > 0 && Number(p.price) > 0 && <small>a partir de </small>}
                      {formatMoney(p.price)}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </section>
        )}

        {menu.categories.map((c) => {
          const items = visible.filter((p) => p.category_id === c.id)
          if (items.length === 0) return null
          return (
            <section key={c.id} className="menu-section" data-cat={c.id} ref={(el) => { if (el) sections.current.set(c.id, el); else sections.current.delete(c.id) }}>
              <h2 className="section-title">{c.name}</h2>
              <div className="product-list">{items.map(productCard)}</div>
            </section>
          )
        })}
        {products.length > 0 && visible.length === 0 && <EmptyState icon={<Search size={24} />} title="Nada encontrado" hint={`Não achamos “${search}” no cardápio.`} />}
        {/* Customers' data: the privacy policy is reachable from every menu, even white-label ones. */}
        <p className="menu-legal"><a href={platformUrl('/privacidade')} target="_blank" rel="noreferrer">Privacidade</a></p>
        {tenant.show_platform_badge && (
          <a className="menu-footer" href={platformUrl('/')} target="_blank" rel="noreferrer">
            Cardápio digital por <strong>{APP_NAME}</strong> · Crie o seu grátis
          </a>
        )}
      </div>

      {offerRound && tab && lastRound && (
        <div className="round-offer" role="status">
          <span className="round-emoji" aria-hidden="true">🍻</span>
          <div><strong>Mais uma rodada?</strong><small>Repita o último pedido da mesa com um toque.</small></div>
          <button className="btn primary small" onClick={() => repeat(lastRound)}><Repeat2 size={15} /> Repetir</button>
          <button className="icon-btn" onClick={() => setDismissedRound(tab.last_order_at)} aria-label="Agora não"><X size={16} /></button>
        </div>
      )}
      {tab && !hasCart && (
        <button className={`tab-bar tab-${tab.status.toLowerCase()}`} onClick={() => setModal({ kind: 'tab' })}>
          <span className="tab-bar-label"><Receipt size={18} /> Mesa {tab.table_label} · {tabStatusLabels[tab.status]}</span>
          <strong>{formatMoney(tab.totals.total)}</strong>
        </button>
      )}
      {latest && !hasCart && !tab && (
        <button className="active-order-bar" onClick={() => setModal({ kind: 'track', token: latest.token, isNew: false })}>
          <span>Pedido #{latest.data.order_number}</span>
          <span className={`badge status-${latest.data.status.toLowerCase()}`}>{orderStatusLabels[latest.data.status as OrderStatus]}</span>
        </button>
      )}
      {hasCart && (
        <button className="cart-bar" onClick={() => setModal({ kind: 'cart' })}>
          <span className="cart-count"><ShoppingBag size={18} /> {count}</span>
          <span>Ver pedido</span>
          <strong>{formatMoney(cartSubtotal(lines))}</strong>
        </button>
      )}

      {modal?.kind === 'product' && <ProductModal product={modal.product} canOrder={canOrder && modal.product.available} onClose={() => setModal(null)} onAdd={addLine} />}
      {modal?.kind === 'cart' && (
        <CartModal tenant={tenant} lines={lines} setLines={setLines} tableFromQr={tableFromQr} onClose={() => setModal(null)} onOrdered={onOrdered} />
      )}
      {modal?.kind === 'orders' && <OrdersModal tokens={tokens} onClose={() => setModal(null)} onOpen={(token) => setModal({ kind: 'track', token, isNew: false })} />}
      {modal?.kind === 'tab' && tab && (
        <TabModal
          tab={tab}
          tenant={tenant}
          highlight={modal.highlight}
          onClose={() => setModal(null)}
          onOrderMore={() => setModal(null)}
          onRepeat={repeat}
          onUpdated={setTab}
        />
      )}
      {modal?.kind === 'track' && <TrackModal token={modal.token} tenant={tenant} isNew={modal.isNew} onClose={() => setModal(null)} />}
    </div>
  )
}
