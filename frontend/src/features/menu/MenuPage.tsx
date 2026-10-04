import { ClipboardList, Minus, Plus, Search, ShoppingBag, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { formatMoney } from '../../lib/format'
import { readJson, writeJson } from '../../lib/storage'
import { apiErrorMessage } from '../../services/api'
import { getMenu, type Menu, type MenuProduct } from '../../services/publicMenu'
import { Brand } from '../auth/LoginPage'
import { CartSheet, type Cart } from './CartSheet'
import { OrdersSheet, TrackSheet } from './OrderSheets'

type Sheet = 'cart' | 'orders' | { track: string } | null

export function MenuPage() {
  const [params] = useSearchParams()
  const [menu, setMenu] = useState<Menu | null>(null)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState<string | null>(null)
  const [cart, setCart] = useState<Cart>({})
  const [sheet, setSheet] = useState<Sheet>(null)
  const tableFromQr = params.get('mesa') ?? ''

  useEffect(() => {
    getMenu().then(setMenu).catch((err) => setError(apiErrorMessage(err, 'Não foi possível carregar o cardápio.')))
  }, [])

  const storageKey = menu ? `mesa:${menu.tenant.slug}:tokens` : ''
  const [tokens, setTokens] = useState<string[]>([])
  useEffect(() => { if (storageKey) setTokens(readJson<string[]>(storageKey, [])) }, [storageKey])

  const products = menu?.products ?? []
  const byId = useMemo(() => new Map(products.map((p) => [p.id, p])), [products])
  const lines = Object.entries(cart).filter(([, line]) => line.quantity > 0)
  const count = lines.reduce((sum, [, line]) => sum + line.quantity, 0)
  const total = lines.reduce((sum, [id, line]) => sum + Number(byId.get(id)?.price ?? 0) * line.quantity, 0)

  const visible = useMemo(() => {
    const term = search.trim().toLowerCase()
    return products.filter((p) =>
      (!category || p.category_id === category) &&
      (!term || `${p.name} ${p.description ?? ''}`.toLowerCase().includes(term)))
  }, [products, search, category])
  const featured = !search && !category ? products.filter((p) => p.featured) : []

  function change(product: MenuProduct, delta: number) {
    setCart((current) => {
      const quantity = Math.min(20, Math.max(0, (current[product.id]?.quantity ?? 0) + delta))
      return { ...current, [product.id]: { ...current[product.id], quantity } }
    })
  }

  function onOrdered(token: string) {
    const next = [token, ...tokens.filter((t) => t !== token)].slice(0, 10)
    setTokens(next)
    writeJson(storageKey, next)
    setCart({})
    toast.success('Pedido enviado!')
    setSheet({ track: token })
  }

  if (error) return <div className="auth-loading column"><p>{error}</p><button className="btn" onClick={() => window.location.reload()}>Tentar de novo</button></div>
  if (!menu) return <div className="auth-loading">Carregando cardápio…</div>

  const { tenant } = menu
  const card = (product: MenuProduct) => {
    const quantity = cart[product.id]?.quantity ?? 0
    return (
      <article className="product-card" key={product.id}>
        <div className="product-info">
          <h3>{product.name}</h3>
          {product.description && <p>{product.description}</p>}
          <strong>{formatMoney(product.price)}</strong>
        </div>
        <div className="product-side">
          {product.image_url
            ? <img src={product.image_url} alt="" loading="lazy" />
            : <div className="product-placeholder">{product.name.charAt(0)}</div>}
          {quantity === 0 ? (
            <button className="btn primary small add-btn" disabled={!tenant.accepting_orders} onClick={() => change(product, 1)}>
              <Plus size={14} /> Adicionar
            </button>
          ) : (
            <div className="stepper">
              <button onClick={() => change(product, -1)} aria-label="Diminuir"><Minus size={14} /></button>
              <span>{quantity}</span>
              <button onClick={() => change(product, 1)} aria-label="Aumentar"><Plus size={14} /></button>
            </div>
          )}
        </div>
      </article>
    )
  }

  return (
    <div className="menu-page">
      <header className="menu-header">
        <Brand name={tenant.name} logo={tenant.logo_url} />
        <div className="menu-header-actions">
          {tableFromQr && <span className="chip">Mesa {tableFromQr}</span>}
          <span className={`chip ${tenant.accepting_orders ? 'ok' : 'off'}`}>{tenant.accepting_orders ? 'Aberto' : 'Fechado'}</span>
          <button className="icon-btn" onClick={() => setSheet('orders')} aria-label="Meus pedidos"><ClipboardList size={20} /></button>
        </div>
      </header>

      {!tenant.accepting_orders && <div className="alert warn">No momento não estamos aceitando pedidos pelo cardápio digital.</div>}

      <label className="search">
        <Search size={16} />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar no cardápio" />
        {search && <button className="icon-btn" onClick={() => setSearch('')} aria-label="Limpar"><X size={14} /></button>}
      </label>

      <nav className="chips" aria-label="Categorias">
        <button className={!category ? 'active' : ''} onClick={() => setCategory(null)}>Tudo</button>
        {menu.categories.map((c) => (
          <button key={c.id} className={category === c.id ? 'active' : ''} onClick={() => setCategory(c.id)}>{c.name}</button>
        ))}
      </nav>

      {products.length === 0 && <div className="empty">O cardápio ainda está sendo montado.</div>}

      {featured.length > 0 && (
        <section>
          <h2 className="section-title">Destaques</h2>
          <div className="product-list">{featured.map(card)}</div>
        </section>
      )}

      {menu.categories.map((c) => {
        const items = visible.filter((p) => p.category_id === c.id)
        if (items.length === 0) return null
        return (
          <section key={c.id}>
            <h2 className="section-title">{c.name}</h2>
            <div className="product-list">{items.map(card)}</div>
          </section>
        )
      })}
      {products.length > 0 && visible.length === 0 && <div className="empty">Nada encontrado para “{search}”.</div>}

      {count > 0 && sheet === null && (
        <button className="cart-bar" onClick={() => setSheet('cart')}>
          <span className="cart-count"><ShoppingBag size={18} /> {count}</span>
          <span>Ver pedido</span>
          <strong>{formatMoney(total)}</strong>
        </button>
      )}

      {sheet === 'cart' && (
        <CartSheet
          tenant={tenant}
          products={byId}
          cart={cart}
          setCart={setCart}
          tableFromQr={tableFromQr}
          onClose={() => setSheet(null)}
          onOrdered={onOrdered}
        />
      )}
      {sheet === 'orders' && <OrdersSheet slug={tenant.slug} tokens={tokens} onClose={() => setSheet(null)} onOpen={(token) => setSheet({ track: token })} />}
      {typeof sheet === 'object' && sheet && <TrackSheet token={sheet.track} onClose={() => setSheet(null)} />}
    </div>
  )
}
