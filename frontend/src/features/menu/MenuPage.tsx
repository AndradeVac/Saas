import { Clock, ClipboardList, Instagram, MapPin, Phone, Search, ShoppingBag, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { EmptyState, Skeleton } from '../../components/ui/parts'
import { DAYS, formatMoney, formatPhone, orderStatusLabels, serviceLabels } from '../../lib/format'
import { mediaUrl } from '../../lib/media'
import { readJson, writeJson } from '../../lib/storage'
import { APP_NAME } from '../../lib/tenant'
import { apiErrorMessage } from '../../services/api'
import { getMenu, trackOrder, type Menu, type MenuProduct, type Tracking } from '../../services/publicMenu'
import type { DayKey, OrderStatus } from '../../types'
import { cartCount, cartSubtotal, type CartLine } from './cart'
import { CartModal } from './CartModal'
import { OrdersModal, TrackModal } from './OrderModals'
import { ProductModal } from './ProductModal'

type Modal = { kind: 'product'; product: MenuProduct } | { kind: 'cart' } | { kind: 'orders' } | { kind: 'track'; token: string; isNew: boolean } | null

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

  const load = useCallback(() => {
    setError('')
    getMenu().then(setMenu).catch((err) => setError(apiErrorMessage(err, 'Não foi possível carregar o cardápio.')))
  }, [])
  useEffect(load, [load])

  const slug = menu?.tenant.slug
  useEffect(() => { if (slug) setTokens(readJson<string[]>(`mesa:${slug}:tokens`, [])) }, [slug])

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
  const featured = !term ? products.filter((p) => p.featured && p.available) : []
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

  function onOrdered(token: string) {
    if (!slug) return
    const next = [token, ...tokens.filter((t) => t !== token)].slice(0, 10)
    setTokens(next)
    writeJson(`mesa:${slug}:tokens`, next)
    setLines([])
    setModal({ kind: 'track', token, isNew: true })
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
  const productCard = (product: MenuProduct) => {
    const quantity = quantities.get(product.id) ?? 0
    return (
      <button className="product-card" key={product.id} onClick={() => setModal({ kind: 'product', product })}>
        <div className="product-info">
          <h3>{product.name}</h3>
          {product.description && <p>{product.description}</p>}
          <span className="product-price">
            {product.options.length > 0 && Number(product.price) > 0 && <small>a partir de </small>}
            {formatMoney(product.price)}
          </span>
        </div>
        <div className="product-thumb">
          {product.image_url ? <img src={mediaUrl(product.image_url)} alt="" loading="lazy" /> : <div className="product-placeholder">{product.name.charAt(0)}</div>}
          {quantity > 0 && <span className="product-qty">{quantity}</span>}
          {!product.available && <span className="product-flag">Esgotado</span>}
        </div>
      </button>
    )
  }

  return (
    <div className={`menu-page ${hasCart || latest ? 'has-cart' : ''}`}>
      <div className="menu-hero">
        {tenant.cover_url && <img src={mediaUrl(tenant.cover_url)} alt="" />}
        <div className="menu-topbar">
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
                  {p.image_url ? <img src={mediaUrl(p.image_url)} alt="" loading="lazy" /> : <div className="product-placeholder">{p.name.charAt(0)}</div>}
                  <div><strong>{p.name}</strong><span className="product-price">{formatMoney(p.price)}</span></div>
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
        <p className="menu-footer">Cardápio digital por {APP_NAME}</p>
      </div>

      {latest && !hasCart && (
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
      {modal?.kind === 'track' && <TrackModal token={modal.token} tenant={tenant} isNew={modal.isNew} onClose={() => setModal(null)} />}
    </div>
  )
}
