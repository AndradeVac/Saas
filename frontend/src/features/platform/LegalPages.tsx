import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { LEGAL } from '../../lib/legal'
import { APP_NAME } from '../../lib/tenant'
import { getPlanCatalog } from '../../services/plans'

function useContact() {
  const [whatsapp, setWhatsapp] = useState('')
  useEffect(() => { getPlanCatalog().then((c) => setWhatsapp(c.sales_whatsapp)).catch(() => setWhatsapp('')) }, [])
  return whatsapp
}

function Contact({ whatsapp }: { whatsapp: string }) {
  const phone = whatsapp.replace(/^55(\d{2})(\d{4,5})(\d{4})$/, '($1) $2-$3')
  return (
    <ul>
      {LEGAL.privacyEmail && <li>E-mail: <a href={`mailto:${LEGAL.privacyEmail}`}>{LEGAL.privacyEmail}</a></li>}
      {whatsapp && <li>WhatsApp: <a href={`https://wa.me/${whatsapp}`} target="_blank" rel="noreferrer">{phone}</a></li>}
    </ul>
  )
}

function LegalLayout({ title, children }: { title: string; children: ReactNode }) {
  useEffect(() => { document.title = `${title} · ${APP_NAME}` }, [title])
  return (
    <div className="legal-page">
      <header className="landing-header"><Link className="landing-logo" to="/">{APP_NAME}</Link><Link className="btn small" to="/">Voltar</Link></header>
      <article className="legal">
        <h1>{title}</h1>
        <p className="muted">Versão de {LEGAL.versionLabel}.</p>
        {children}
        <hr />
        <p className="muted">
          {LEGAL.companyName ? <>{LEGAL.brand} é operado por {LEGAL.companyName}{LEGAL.document ? `, inscrito(a) sob ${LEGAL.document}` : ''}. </> : null}
          Veja também: <Link to="/termos">Termos de Uso</Link> · <Link to="/privacidade">Política de Privacidade</Link>
        </p>
      </article>
    </div>
  )
}

export function TermsPage() {
  const whatsapp = useContact()
  return (
    <LegalLayout title="Termos de Uso">
      <p>Estes Termos regulam o uso do {LEGAL.brand} ("plataforma"), um sistema online de cardápio digital, pedidos e gestão para restaurantes, padarias, cafeterias e negócios semelhantes ("estabelecimento" ou "cliente"). Ao criar uma conta, você declara que leu e aceita estes Termos e a <Link to="/privacidade">Política de Privacidade</Link>.</p>

      <h2>1. O serviço</h2>
      <p>A plataforma permite ao estabelecimento publicar um cardápio digital com endereço próprio, receber pedidos dos seus consumidores (por QR Code, link ou pela equipe), acompanhar a comanda das mesas e gerir produtos, equipe, cupons e relatórios. A plataforma <strong>não processa pagamentos</strong>: o pagamento dos consumidores é feito diretamente ao estabelecimento, pelos meios que ele escolher.</p>

      <h2>2. Conta e acesso</h2>
      <ul>
        <li>Quem cria a conta precisa ter capacidade legal e poderes para representar o estabelecimento.</li>
        <li>O estabelecimento é responsável pelas pessoas a quem dá acesso ao painel e pelo sigilo das senhas.</li>
        <li>As informações do cadastro devem ser verdadeiras e mantidas atualizadas.</li>
      </ul>

      <h2>3. Período de teste e planos</h2>
      <ul>
        <li>Novas contas começam com um período de teste gratuito, com limites de produtos, equipe e pedidos descritos na página de preços.</li>
        <li>Terminado o teste, o cardápio continua visível, mas deixa de receber pedidos até a contratação de um plano.</li>
        <li>Os planos são mensais, com os preços e recursos publicados no site no momento da contratação. Reajustes serão avisados com pelo menos 30 dias de antecedência.</li>
        <li>O cliente pode cancelar a qualquer momento, sem multa; o acesso segue até o fim do período já pago. Não há reembolso proporcional de mensalidades já iniciadas, salvo previsão legal.</li>
        <li>A falta de pagamento pode levar à suspensão do recebimento de pedidos e, depois de 60 dias, ao encerramento da conta.</li>
      </ul>

      <h2>4. Responsabilidades do estabelecimento</h2>
      <ul>
        <li>O conteúdo do cardápio (nomes, descrições, fotos, preços, alergênicos, disponibilidade) e o cumprimento das regras de defesa do consumidor, vigilância sanitária e tributárias são de responsabilidade do estabelecimento.</li>
        <li>O preparo, a entrega e a cobrança dos pedidos, assim como o atendimento aos seus consumidores, cabem ao estabelecimento.</li>
        <li>O estabelecimento só deve publicar fotos e marcas que tenha direito de usar.</li>
        <li>Os dados dos consumidores coletados pelo cardápio pertencem ao estabelecimento, que deve tratá-los conforme a LGPD (veja a Política de Privacidade).</li>
      </ul>

      <h2>5. Uso aceitável</h2>
      <p>É proibido usar a plataforma para atividades ilegais, para vender produtos proibidos, enviar conteúdo ofensivo ou enganoso, tentar acessar dados de outros estabelecimentos, sobrecarregar ou atacar o sistema. Nesses casos a conta pode ser suspensa imediatamente.</p>

      <h2>6. Disponibilidade e suporte</h2>
      <p>Trabalhamos para manter a plataforma disponível o tempo todo, mas podem ocorrer interrupções para manutenção ou por falhas de fornecedores de infraestrutura. Avisaremos manutenções programadas sempre que possível. O suporte é prestado pelos canais indicados ao final.</p>

      <h2>7. Limitação de responsabilidade</h2>
      <p>A plataforma é uma ferramenta de apoio. Na máxima extensão permitida pela lei, não respondemos por lucros cessantes, pedidos não realizados durante indisponibilidades, nem por atos do estabelecimento perante seus consumidores. Quando houver responsabilidade, ela fica limitada ao valor pago pelo cliente nos 3 meses anteriores ao fato.</p>

      <h2>8. Seus dados ao sair</h2>
      <p>O cliente pode exportar pedidos, clientes e relatórios pelo painel (nos planos que incluem exportação) e pode pedir a exclusão da conta. Depois do encerramento, os dados são apagados em até 90 dias, exceto os que a lei obrigar a guardar.</p>

      <h2>9. Alterações</h2>
      <p>Estes Termos podem ser atualizados. Mudanças relevantes serão comunicadas no painel ou por e-mail com antecedência; o uso continuado depois da vigência significa concordância.</p>

      <h2>10. Lei e foro</h2>
      <p>Aplica-se a lei brasileira.{LEGAL.forum ? ` Fica eleito o foro da comarca de ${LEGAL.forum}, ressalvado o direito do consumidor de propor ação no seu domicílio.` : ' Eventuais disputas serão resolvidas no foro previsto em lei, ressalvado o direito do consumidor de propor ação no seu domicílio.'}</p>

      <h2>Contato</h2>
      <Contact whatsapp={whatsapp} />
    </LegalLayout>
  )
}

export function PrivacyPage() {
  const whatsapp = useContact()
  return (
    <LegalLayout title="Política de Privacidade">
      <p>Esta Política explica como o {LEGAL.brand} trata dados pessoais, em conformidade com a Lei Geral de Proteção de Dados (Lei nº 13.709/2018, "LGPD").</p>

      <h2>1. Quem é responsável por quais dados</h2>
      <ul>
        <li><strong>Dados dos estabelecimentos e de suas equipes</strong> (quem usa o painel): o {LEGAL.brand} é o <em>controlador</em>.</li>
        <li><strong>Dados dos consumidores</strong> que fazem pedidos pelo cardápio de um estabelecimento: o estabelecimento é o <em>controlador</em> e o {LEGAL.brand} atua como <em>operador</em>, tratando esses dados apenas para prestar o serviço ao estabelecimento.</li>
      </ul>

      <h2>2. Dados que coletamos</h2>
      <ul>
        <li><strong>Cadastro do estabelecimento:</strong> nome do negócio, endereço, telefone/WhatsApp, Instagram, logo e fotos, chave PIX (se informada).</li>
        <li><strong>Usuários do painel:</strong> nome, e-mail, senha (guardada de forma criptografada, nunca em texto puro) e registro das ações feitas no painel (auditoria).</li>
        <li><strong>Consumidores:</strong> nome, telefone, mesa ou endereço de entrega, itens pedidos, observações e histórico de pedidos naquele estabelecimento.</li>
        <li><strong>Dados técnicos:</strong> endereço IP e informações do navegador, usados para segurança (por exemplo, limitar tentativas de login) e para manter o sistema funcionando.</li>
      </ul>

      <h2>3. Para que usamos e com qual base legal</h2>
      <ul>
        <li>Prestar o serviço contratado: cardápio, pedidos, comandas, painel e relatórios (execução de contrato).</li>
        <li>Enviar avisos do serviço, como recuperação de senha e mudanças nos termos (execução de contrato).</li>
        <li>Proteger a plataforma contra fraudes e abusos (legítimo interesse).</li>
        <li>Cumprir obrigações legais e fiscais (obrigação legal).</li>
      </ul>
      <p>Não vendemos dados pessoais e não usamos os dados dos consumidores de um estabelecimento para fins próprios de marketing.</p>

      <h2>4. Com quem compartilhamos</h2>
      <p>Somente com fornecedores necessários para operar a plataforma, sob contrato e com medidas de segurança:</p>
      <ul>
        <li>Hospedagem da aplicação: Fly.io (servidores em São Paulo).</li>
        <li>Banco de dados: Supabase (servidores em São Paulo).</li>
        <li>Rede, proteção contra ataques e armazenamento de imagens: Cloudflare.</li>
        <li>Envio de e-mails do sistema: Resend.</li>
      </ul>
      <p>Alguns desses fornecedores têm sede fora do Brasil; quando houver transferência internacional, ela ocorre com as garantias previstas na LGPD. Também podemos compartilhar dados por ordem judicial ou exigência legal.</p>

      <h2>5. Por quanto tempo guardamos</h2>
      <p>Enquanto a conta do estabelecimento estiver ativa. Após o encerramento, os dados são apagados em até 90 dias, salvo os que a lei exigir guardar por mais tempo. O estabelecimento pode pedir a exclusão de dados de consumidores a qualquer momento pelos canais de contato abaixo.</p>

      <h2>6. Segurança</h2>
      <p>Usamos conexão criptografada (HTTPS) em todo o site, senhas com hash forte, separação dos dados de cada estabelecimento no banco de dados, controle de acesso por perfis e registro de auditoria. Nenhum sistema é 100% invulnerável; em caso de incidente relevante, os afetados e a ANPD serão comunicados conforme a lei.</p>

      <h2>7. Armazenamento no navegador</h2>
      <p>Não usamos cookies de rastreamento nem publicidade. O site guarda no seu próprio navegador apenas o necessário para funcionar: a sessão de login do painel, o carrinho, a comanda da mesa e preferências como tema claro/escuro.</p>

      <h2>8. Seus direitos</h2>
      <p>Você pode pedir confirmação de tratamento, acesso, correção, anonimização ou exclusão dos seus dados, portabilidade, informação sobre compartilhamentos e revogação de consentimento, nos termos do art. 18 da LGPD. Consumidores de um estabelecimento podem fazer o pedido diretamente a ele ou a nós, que o encaminharemos. Respondemos em até 15 dias.</p>

      <h2>9. Contato e encarregado (DPO)</h2>
      <Contact whatsapp={whatsapp} />

      <h2>10. Alterações</h2>
      <p>Esta Política pode ser atualizada; a versão vigente estará sempre nesta página, com a data no topo.</p>
    </LegalLayout>
  )
}
