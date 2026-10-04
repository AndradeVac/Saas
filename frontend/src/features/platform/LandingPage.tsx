import { ArrowRight, BarChart3, Clock, QrCode, Store, Tag, Utensils } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { slugify } from '../../lib/format'
import { APP_NAME, tenantUrl } from '../../lib/tenant'

const features = [
  { icon: QrCode, title: 'QR Code por mesa', text: 'O cliente escaneia, escolhe e pede pelo celular. O pedido já chega com o número da mesa.' },
  { icon: Utensils, title: 'Cardápio completo', text: 'Fotos, adicionais, tamanhos, destaques e produtos esgotados, tudo editável por você.' },
  { icon: Clock, title: 'Horários e regras', text: 'Abre e fecha sozinho, define pedido mínimo, taxa de serviço, entrega e formas de pagamento.' },
  { icon: Tag, title: 'Cupons de desconto', text: 'Crie cupons percentuais ou em reais, com validade, limite de uso e pedido mínimo.' },
  { icon: Store, title: 'Seu endereço e sua marca', text: 'Cada negócio tem endereço próprio, logo, capa e cores, com login e senha da equipe.' },
  { icon: BarChart3, title: 'Gestão e relatórios', text: 'Fila de pedidos em tempo real, clientes, equipe, vendas por horário e exportação em Excel.' },
]

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
        <Link className="btn" to="/cadastro">Criar conta</Link>
      </header>

      <main>
        <section className="hero">
          <h1>O cardápio digital do seu restaurante, padaria ou cafeteria.</h1>
          <p>
            Seus clientes pedem pelo celular, você recebe tudo em um painel simples e controla cada detalhe do seu negócio,
            sem depender de ninguém.
          </p>
          <div className="hero-actions">
            <Link className="btn primary large" to="/cadastro">Testar grátis <ArrowRight size={18} /></Link>
          </div>
        </section>

        <section className="features">
          {features.map(({ icon: Icon, title, text }) => (
            <article className="card" key={title}><Icon size={26} /><h3>{title}</h3><p>{text}</p></article>
          ))}
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
