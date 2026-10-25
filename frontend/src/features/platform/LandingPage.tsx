import { ArrowRight, BarChart3, BellRing, Check, ChefHat, Clock, Gift, MessageCircle, Percent, QrCode, Smartphone, Sparkles, Store, Tag, Utensils } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { formatMoney, slugify } from '../../lib/format'
import { APP_NAME, tenantUrl } from '../../lib/tenant'
import { LEGAL } from '../../lib/legal'
import { getPlanCatalog, paidPlans, salesLink, type PlanCatalog } from '../../services/plans'

// Account shown inside the phone mockup; `python -m scripts.seed_demo` creates it locally.
const DEMO_SLUG = import.meta.env.VITE_DEMO_SLUG ?? 'demo'

const features = [
  { icon: QrCode, title: 'QR Code por mesa', text: 'O cliente escaneia, escolhe e pede pelo celular. O pedido já chega com o número da mesa.' },
  { icon: Utensils, title: 'Cardápio com fotos', text: 'Fotos, tamanhos, adicionais, destaques e produtos esgotados, tudo editável por você em segundos.' },
  { icon: Clock, title: 'Abre e fecha sozinho', text: 'Horários por dia, pedido mínimo, taxa de entrega e de serviço, formas de pagamento e PIX.' },
  { icon: Tag, title: 'Cupons que trazem cliente', text: 'Cupons percentuais ou em reais, com validade, limite de uso e pedido mínimo.' },
  { icon: Store, title: 'Seu endereço, sua marca', text: 'Endereço próprio, logo, capa e cores. A equipe entra com login e senha.' },
  { icon: BarChart3, title: 'Gestão de verdade', text: 'Pedidos ao vivo, clientes, equipe, fechamento de caixa e relatórios em Excel e PDF.' },
  { icon: Gift, title: 'Cliente que volta', text: 'Cartão fidelidade digital e a lista de clientes sumidos para chamar no WhatsApp com um toque.' },
  { icon: BellRing, title: 'Nenhum pedido perdido', text: 'Aviso no celular mesmo com o painel fechado, lembrete sonoro e impressão automática da comanda.' },
  { icon: ChefHat, title: 'Comanda e PIX na mesa', text: 'Cada mesa com sua conta: o cliente pede várias vezes, divide e paga pelo PIX com o valor exato.' },
]

const steps = [
  { title: 'Crie sua conta', text: 'Escolha o endereço do seu cardápio. Leva menos de 2 minutos.' },
  { title: 'Monte o cardápio', text: 'Cadastre produtos com foto, preço e adicionais direto do celular.' },
  { title: 'Receba pedidos', text: 'Imprima os QR Codes das mesas e compartilhe o link no Instagram e no WhatsApp.' },
]

const faq = [
  { q: 'Preciso de cartão de crédito para testar?', a: 'Não. Por 14 dias está tudo liberado, sem limite de produtos ou pedidos e sem informar pagamento.' },
  { q: 'Vocês cadastram o meu cardápio?', a: 'Sim. Você pode importar por foto em minutos ou pedir para a nossa equipe cadastrar tudo para você.' },
  { q: 'Tem fidelidade ou multa para cancelar?', a: 'Não. O plano mensal é sem fidelidade: cancele quando quiser pelo próprio painel.' },
  { q: 'Vocês cobram comissão por pedido?', a: 'Não. Você paga só a mensalidade do plano. O cliente pede direto com você e o dinheiro é todo seu.' },
  { q: 'O cliente precisa baixar aplicativo?', a: 'Não. O cardápio abre no navegador do celular, pelo QR Code ou pelo link.' },
  { q: 'Consigo mudar preços e fotos sozinho?', a: 'Sim. Tudo é editado pelo painel e aparece no cardápio na hora, inclusive marcar um item como esgotado.' },
  { q: 'O que acontece quando o teste acaba?', a: 'Seu cardápio continua salvo. Para voltar a receber pedidos, basta escolher um plano.' },
]

export function LandingPage() {
  const [slug, setSlug] = useState('')
  const [catalog, setCatalog] = useState<PlanCatalog | null>(null)

  useEffect(() => { getPlanCatalog().then(setCatalog).catch(() => setCatalog(null)) }, [])

  function goToTenant(event: FormEvent) {
    event.preventDefault()
    const clean = slugify(slug)
    if (clean) window.location.href = tenantUrl(clean, '/login')
  }

  const trialDays = catalog?.trial_days ?? 14
  const whatsapp = salesLink(catalog, 'Olá! Quero saber mais sobre o Mesa Digital para o meu restaurante.')
  const setupLink = salesLink(catalog, 'Olá! Quero que vocês cadastrem o cardápio do meu restaurante no Mesa Digital.')
  const [sales, setSales] = useState(15000)
  const [rate, setRate] = useState(27)
  const proPrice = Number(catalog?.plans.find((p) => p.key === 'pro')?.price ?? 149.9)
  const commission = (sales * rate) / 100
  const plans = catalog ? paidPlans(catalog) : []

  return (
    <div className="landing-page">
      {whatsapp && <a className="whatsapp-fab" href={whatsapp} target="_blank" rel="noreferrer" aria-label="Falar no WhatsApp"><MessageCircle size={26} /></a>}
      <header className="landing-header">
        <strong className="landing-logo">{APP_NAME}</strong>
        <nav className="landing-nav">
          <a href="#recursos">Recursos</a>
          <a href="#precos">Preços</a>
          <a href="#entrar">Entrar</a>
          <Link className="btn primary small" to="/cadastro">Testar grátis</Link>
        </nav>
      </header>

      <section className="landing-hero">
        <div className="hero-copy">
          <span className="hero-eyebrow"><Sparkles size={14} /> Cardápio digital + pedidos + gestão</span>
          <h1>Venda mais com um cardápio que dá vontade de pedir.</h1>
          <p>
            Fotos que dão água na boca, pedido pelo celular em segundos e um painel onde você controla tudo.
            Sem comissão por pedido e sem depender de aplicativo de entrega.
          </p>
          <div className="hero-actions">
            <Link className="btn primary large" to="/cadastro">Criar meu cardápio grátis <ArrowRight size={18} /></Link>
            <a className="btn large" href={tenantUrl(DEMO_SLUG, '/')} target="_blank" rel="noreferrer"><Smartphone size={18} /> Ver um exemplo</a>
          </div>
          <ul className="hero-trust">
            <li><Check size={16} /> {trialDays} dias grátis</li>
            <li><Check size={16} /> Sem cartão de crédito</li>
            <li><Check size={16} /> Pronto em 5 minutos</li>
          </ul>
        </div>
        <div className="phone" aria-label="Exemplo de cardápio digital">
          <div className="phone-notch" />
          <iframe title="Cardápio de exemplo" src={tenantUrl(DEMO_SLUG, '/')} loading="lazy" />
        </div>
      </section>

      <section className="landing-band">
        <div className="band-item"><Percent size={22} /><div><strong>0% de comissão</strong><span>Apps de entrega cobram uma fatia de cada pedido. Aqui, o lucro é todo seu.</span></div></div>
        <div className="band-item"><Smartphone size={22} /><div><strong>Sem baixar nada</strong><span>Abre direto no celular do cliente, pelo QR Code ou link.</span></div></div>
        <div className="band-item"><Clock size={22} /><div><strong>Pedido na hora</strong><span>Chega no painel com aviso sonoro, mesa e forma de pagamento.</span></div></div>
      </section>

      <section className="landing-section calculator" id="calculadora">
        <h2 className="landing-title">Quanto os aplicativos levam do seu faturamento?</h2>
        <p className="landing-sub">Faça a conta com o seu número de verdade.</p>
        <div className="calc card">
          <label className="field"><span>Vendas por aplicativos de entrega, por mês</span>
            <input type="range" min={2000} max={100000} step={1000} value={sales} onChange={(e) => setSales(Number(e.target.value))} />
            <strong>{formatMoney(sales)}</strong>
          </label>
          <label className="field"><span>Comissão do aplicativo</span>
            <input type="range" min={10} max={30} step={1} value={rate} onChange={(e) => setRate(Number(e.target.value))} />
            <strong>{rate}%</strong>
          </label>
          <div className="calc-result">
            <div><span>Você paga de comissão por mês</span><strong className="danger">{formatMoney(commission)}</strong></div>
            <div><span>Com o Mesa Digital Profissional</span><strong>{formatMoney(proPrice)}</strong></div>
            <div className="calc-save"><span>Fica no seu bolso por ano, se metade desses clientes pedir direto com você</span><strong>{formatMoney(Math.max(0, (commission / 2 - proPrice) * 12))}</strong></div>
          </div>
          <Link className="btn primary large block" to="/cadastro">Quero parar de pagar comissão <ArrowRight size={18} /></Link>
        </div>
      </section>

      <section className="landing-section">
        <h2 className="landing-title">Do cadastro ao primeiro pedido em 3 passos</h2>
        <div className="steps">
          {steps.map((step, index) => (
            <div className="step" key={step.title}>
              <span className="step-number">{index + 1}</span>
              <h3>{step.title}</h3>
              <p className="muted">{step.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="landing-section" id="recursos">
        <h2 className="landing-title">Tudo o que o seu negócio precisa</h2>
        <p className="landing-sub">Feito para restaurantes, padarias, cafeterias, lanchonetes e pizzarias.</p>
        <div className="features">
          {features.map(({ icon: Icon, title, text }) => (
            <article className="card" key={title}><Icon size={26} /><h3>{title}</h3><p>{text}</p></article>
          ))}
        </div>
      </section>

      <section className="landing-section" id="precos">
        <h2 className="landing-title">Planos simples, sem surpresa</h2>
        <p className="landing-sub">Comece grátis por {trialDays} dias. Depois, escolha o plano que cabe no seu momento.</p>
        <div className="plan-grid">
          <div className="plan-card">
            <h3>Degustação</h3>
            <div className="plan-price"><strong>Grátis</strong><span>/{trialDays} dias</span></div>
            <p className="muted plan-tagline">O sistema inteiro, com tudo liberado, para você testar com clientes de verdade.</p>
            <ul className="plan-list">
              <li><Check size={15} /> Produtos e pedidos ilimitados</li>
              <li><Check size={15} /> Equipe, cupons e relatórios</li>
              <li><Check size={15} /> Análises e clientes para reconquistar</li>
              <li><Check size={15} /> Sem cartão de crédito</li>
            </ul>
            <Link className="btn block" to="/cadastro">Começar grátis</Link>
          </div>
          {plans.map((plan) => (
            <div key={plan.key} className={`plan-card ${plan.highlight ? 'highlight' : ''}`}>
              {plan.highlight && <span className="plan-ribbon"><Sparkles size={13} /> Mais escolhido</span>}
              <h3>{plan.name}</h3>
              <div className="plan-price"><strong>{formatMoney(plan.price)}</strong><span>/mês</span></div>
              <p className="muted plan-tagline">{plan.tagline}</p>
              <ul className="plan-list">
                <li><Check size={15} /> {plan.max_products === null ? 'Produtos ilimitados' : `Até ${plan.max_products} produtos`}</li>
                <li><Check size={15} /> {plan.max_users === null ? 'Equipe ilimitada' : `Até ${plan.max_users} pessoas na equipe`}</li>
                <li><Check size={15} /> Pedidos ilimitados, sem comissão</li>
                {plan.features.map((feature) => <li key={feature}><Check size={15} /> {catalog?.feature_names[feature]}</li>)}
              </ul>
              <Link className={`btn ${plan.highlight ? 'primary' : ''} block`} to="/cadastro">Testar grátis</Link>
            </div>
          ))}
        </div>
      </section>

      <section className="landing-section narrow">
        <h2 className="landing-title">Perguntas frequentes</h2>
        <div className="faq">
          {faq.map((item) => (
            <details key={item.q}><summary>{item.q}</summary><p>{item.a}</p></details>
          ))}
        </div>
      </section>

      {setupLink && (
        <section className="landing-section">
          <div className="card setup-card">
            <div><h3>Sem tempo para cadastrar o cardápio?</h3><p className="muted">Mande as fotos do seu cardápio no WhatsApp que a nossa equipe cadastra tudo para você, com fotos e preços.</p></div>
            <a className="btn primary" href={setupLink} target="_blank" rel="noreferrer"><MessageCircle size={16} /> Quero que cadastrem para mim</a>
          </div>
        </section>
      )}

      <section className="landing-cta">
        <h2>Seu cardápio digital pode estar no ar hoje.</h2>
        <p>Crie a conta, cadastre seus produtos e compartilhe o link. Simples assim.</p>
        <Link className="btn large light" to="/cadastro">Criar meu cardápio grátis <ArrowRight size={18} /></Link>
      </section>

      <section className="card access-card" id="entrar">
        <h2>Já tem conta?</h2>
        <p className="muted">Digite o endereço do seu estabelecimento para entrar no painel.</p>
        <form className="slug-form" onSubmit={goToTenant}>
          <input value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="meu-restaurante" aria-label="Endereço do estabelecimento" />
          <button className="btn primary" type="submit">Entrar</button>
        </form>
      </section>

      <footer className="landing-footer">
        © {new Date().getFullYear()} {APP_NAME} · <Link to="/termos">Termos de Uso</Link> · <Link to="/privacidade">Política de Privacidade</Link>
        <br /><small>{LEGAL.companyName} · {LEGAL.document}{LEGAL.privacyEmail ? ` · ${LEGAL.privacyEmail}` : ''}</small>
      </footer>
    </div>
  )
}
