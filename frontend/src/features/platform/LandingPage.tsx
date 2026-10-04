import { ArrowRight, BarChart3, QrCode, Store } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { APP_NAME, tenantUrl } from '../../lib/tenant'
import { slugify } from '../../lib/format'

export function LandingPage() {
  const [slug, setSlug] = useState('')

  function goToTenant(event: FormEvent) {
    event.preventDefault()
    const clean = slugify(slug)
    if (clean) window.location.href = tenantUrl(clean, '/login')
  }

  return (
    <div className="landing">
      <header className="landing-header">
        <strong className="landing-logo">{APP_NAME}</strong>
        <nav>
          <Link className="btn ghost" to="/cadastro">Criar conta</Link>
        </nav>
      </header>

      <main>
        <section className="hero">
          <h1>Cardápio digital e pedidos para o seu restaurante, padaria ou cafeteria.</h1>
          <p>
            Seus clientes escaneiam o QR Code da mesa, pedem pelo celular e acompanham o preparo.
            Você recebe tudo em um painel simples, com o endereço da sua marca.
          </p>
          <div className="hero-actions">
            <Link className="btn primary large" to="/cadastro">Testar grátis <ArrowRight size={18} /></Link>
          </div>
        </section>

        <section className="features">
          <article className="card"><QrCode size={26} /><h3>QR Code por mesa</h3><p>Gere os QR Codes e o pedido já chega com o número da mesa.</p></article>
          <article className="card"><Store size={26} /><h3>Seu endereço</h3><p>Cada negócio tem seu próprio endereço, logo e cor, com login e senha da equipe.</p></article>
          <article className="card"><BarChart3 size={26} /><h3>Gestão completa</h3><p>Fila de pedidos em tempo real, produtos, equipe e relatórios de vendas.</p></article>
        </section>

        <section className="card access-card">
          <h2>Já tem conta?</h2>
          <p className="muted">Digite o endereço do seu estabelecimento para entrar no painel.</p>
          <form className="slug-form" onSubmit={goToTenant}>
            <input value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="meu-restaurante" aria-label="Endereço do estabelecimento" />
            <button className="btn primary" type="submit">Entrar</button>
          </form>
        </section>
      </main>
    </div>
  )
}
