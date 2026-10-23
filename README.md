# Mesa Digital

Cardápio digital, pedidos e comanda por mesa para restaurantes, hamburguerias, padarias e cafeterias, vendido
como assinatura mensal (SaaS). No ar em **https://mesadig.com.br**.

Cada estabelecimento (um *tenant*) ganha:

- um endereço próprio, `https://<slug>.mesadig.com.br`, com o **cardápio público** que o cliente abre no celular;
- **QR Codes por mesa**, que abrem o cardápio já na mesa certa;
- um **painel** (`/painel`) com login da equipe para receber pedidos, controlar as mesas e cuidar do cardápio.

---

## Sumário

1. [Como funciona, do ponto de vista de cada pessoa](#1-como-funciona-do-ponto-de-vista-de-cada-pessoa)
2. [Planos, degustação e assinatura](#2-planos-degustação-e-assinatura)
3. [Pagamentos](#3-pagamentos)
4. [Importar cardápio por foto](#4-importar-cardápio-por-foto)
5. [Arquitetura](#5-arquitetura)
6. [Estrutura de pastas](#6-estrutura-de-pastas)
7. [Multi-tenant, segurança e privacidade](#7-multi-tenant-segurança-e-privacidade)
8. [Rodando localmente](#8-rodando-localmente)
9. [Testes](#9-testes)
10. [Produção e operação](#10-produção-e-operação)
11. [Ferramentas do dono da plataforma](#11-ferramentas-do-dono-da-plataforma)
12. [Configuração (variáveis de ambiente)](#12-configuração-variáveis-de-ambiente)
13. [Pendências e próximos passos](#13-pendências-e-próximos-passos)

---

## 1. Como funciona, do ponto de vista de cada pessoa

### 1.1 O dono do restaurante, ao entrar

1. Abre **mesadig.com.br**, clica em "Começar grátis" e cria a conta: nome do negócio, endereço (`slug`), e-mail e
   senha. Ele aceita os **termos de uso e a política de privacidade**, e o aceite fica registrado com a versão e a data.
2. Entra no painel em **degustação** (14 dias grátis, sem cartão).
3. Cadastra o cardápio de três formas:
   - **um produto por vez**, com foto, preço, descrição e opções;
   - **importando por foto**: tira foto do cardápio impresso e confere a lista pronta (seção 4);
   - **colando a resposta do Claude grátis**, que é a mesma importação sem custo (seção 4).
4. Em **Configurações**, define logo, cores, horários, formas de pagamento, chave PIX, taxas e as mesas. Depois
   imprime os QR Codes.
5. Quando quiser, assina um plano em **Meu plano**, pagando com PIX, boleto ou cartão. O plano é liberado sozinho
   quando o pagamento é confirmado.

### 1.2 O painel (dono e equipe)

| Área | O que faz |
|---|---|
| **Visão geral** | Faturamento, pedidos, ticket médio, gráficos por dia, horário e categoria, e checklist de primeiros passos |
| **Pedidos** | Fila ao vivo (atualiza sozinha, com aviso sonoro e contador na aba), avanço de status, pagamento no caixa, cancelamento com motivo, edição e impressão da comanda |
| **Mesas** | Mapa das mesas com a conta aberta de cada uma. Alertas: mesa nova esperando aprovação, pediu a conta, parada há X minutos, pedido atrasado, "já paguei" pelo PIX. Fechamento com forma de pagamento |
| **Histórico** | Busca por número, cliente, telefone ou mesa, com filtros, paginação e exportação |
| **Produtos** | Foto, preço, descrição, destaque, esgotado, ocultar, ordem e **grupos de opções** (tamanho, adicionais, ponto da carne…) com preço. Botão **Importar cardápio** |
| **Categorias** | Criar, renomear, ordenar e ocultar |
| **Cupons** | Percentual ou valor fixo, pedido mínimo, limite de usos e validade. O uso volta se o pedido for cancelado |
| **Clientes** | Total gasto, último pedido, observações e exportação |
| **Equipe** | Usuários com perfil **Administrador** (tudo) ou **Operador** (pedidos e mesas), redefinição de senha e desativação |
| **Configurações** | Marca (logo, capa, cor), aberto manualmente ou **por horário**, tipos de atendimento (mesa, retirada, entrega), formas de pagamento, chave PIX, pedido mínimo, taxa de entrega e de serviço, QR Codes das mesas e senha |
| **Auditoria** | Quem fez o quê e quando (plano Profissional) |
| **Meu plano** | Uso (produtos, equipe, pedidos), situação da assinatura, assinar, trocar de plano, pagar e cancelar |

### 1.3 O cliente final (no celular, sem instalar nada)

- **Pelo link do restaurante:** vê capa, horários, categorias, destaques e produtos com opções e observações, monta o
  carrinho, aplica cupom e escolhe mesa, retirada ou entrega. Depois acompanha o pedido em tempo real.
- **Pelo QR Code da mesa (comanda):**
  - entra na conta da mesa e pede quantas vezes quiser;
  - **repete a última rodada** com um toque;
  - recebe o convite "Mais uma rodada?" depois de um tempo sem pedir;
  - acompanha a conta ao vivo e pede para fechar;
  - **divide a conta** entre as pessoas;
  - paga com **PIX copia e cola** (a conta inteira ou só a sua parte) e toca em "Já paguei". O garçom confirma no painel
    e a mesa fecha sozinha quando a conta está quitada.

---

## 2. Planos, degustação e assinatura

Tudo é definido num lugar só: `backend/app/core/plans.py`. **A API aplica os limites** (responde **402** com
`code: PLAN_LIMIT`); o painel só espelha, mostrando cadeados, medidores e o convite para assinar.

| | Degustação | Essencial | Profissional |
|---|---|---|---|
| Preço | grátis por 14 dias | **R$ 79,90/mês** | **R$ 149,90/mês** |
| Produtos ativos | 10 | 80 | ilimitados |
| Equipe | só o dono | 3 pessoas | ilimitada |
| Pedidos | 30 no teste (cada mesa conta 1) | ilimitados | ilimitados |
| Cupons e exportações (Excel, PDF, CSV) | — | ✓ | ✓ |
| Auditoria e cardápio sem a marca Mesa Digital | — | — | ✓ |

- **Degustação** é um "gostinho": o fluxo principal funciona, mas o volume é limitado e as ferramentas premium aparecem
  bloqueadas, com a explicação do que liberam. Pedidos cancelados não contam no limite.
- **Teste vencido ou pedidos esgotados:** o cardápio continua no ar e o painel continua editável, mas não entram
  novos pedidos.
- **Assinatura online (Asaas):** "Assinar" pede CPF ou CNPJ e e-mail e leva à página de pagamento do Asaas. O
  **webhook** do Asaas é a única coisa que libera o plano: o navegador nunca é confiável para dizer "paguei".
- **Atraso:** são **5 dias de tolerância**. Depois disso o cardápio para de receber pedidos e volta na hora quando o
  pagamento entra.
- **Cancelamento:** o cliente continua com acesso até o fim do período já pago.
- **Trocar de plano:** a mudança vale na hora, e o novo preço entra a partir da próxima cobrança.
- **Cortesia (opcional):** plano completo grátis até uma data, que bloqueia sozinho no fim se ninguém assinar (comando
  na seção 11). Se o dono assinar durante a cortesia, a primeira cobrança só vence quando ela acaba.

Sem `ASAAS_API_KEY`, os botões "Assinar" abrem o WhatsApp de vendas (`SALES_WHATSAPP`) e o plano é ativado à mão.

---

## 3. Pagamentos

| O quê | Como |
|---|---|
| **Assinatura do restaurante** (o restaurante paga você) | Asaas: assinatura mensal por PIX, boleto ou cartão. Código em `app/core/asaas.py`, `app/services/billing.py` e `app/api/routes/billing.py`. Webhook em `https://mesadig.com.br/api/billing/webhook`, protegido por token, com eventos processados uma única vez (tabela `billing_events`) |
| **Conta da mesa** (o cliente final paga o restaurante) | PIX copia e cola gerado com a chave PIX do próprio restaurante e o valor exato (`app/core/pix.py`). O dinheiro vai direto para o restaurante; o Mesa Digital não toca nele. Confirmação feita pelo garçom no painel |
| **Pedidos avulsos** | Pagamento no balcão ou na entrega, com a forma registrada no pedido |

---

## 4. Importar cardápio por foto

Em **Produtos → Importar cardápio**, o dono cadastra o cardápio inteiro de uma vez. São dois caminhos, e os dois
terminam na mesma **tela de revisão**, onde ele corrige nomes e preços, desmarca o que não quer e só então cria.

1. **Grátis (sempre disponível):** o painel mostra um pedido pronto para copiar. O dono abre o **Claude grátis**
   (claude.ai), anexa as fotos, cola o pedido e cola a resposta de volta no painel. O leitor aceita texto em volta da
   resposta e preços escritos como "R$ 25,90".
2. **Direto pelo painel (opcional, pago):** com `ANTHROPIC_API_KEY` configurada, o dono envia até 4 fotos ou um PDF
   e o servidor lê com o Claude (`claude-opus-5-5`). Custa centavos por leitura e tem limite de 6 leituras por hora
   por loja. Código em `app/core/menu_ai.py`.

Ao criar os produtos (`POST /menu-import/apply`):

- categorias com o mesmo nome são reaproveitadas;
- preços por tamanho viram a escolha obrigatória **"Tamanho"**: o produto fica com o menor preço e cada tamanho soma a
  diferença;
- os produtos que passam do limite do plano são criados **ocultos**. Na degustação, por exemplo, ficam 10 visíveis e o
  resto oculto, e o dono escolhe quais mostrar.

---

## 5. Arquitetura

```
 Celular do cliente / painel                     Cloudflare (DNS, HTTPS, *.mesadig.com.br)
            │                                                   │
            ▼                                                   ▼
 ┌──────────────────────────── Fly.io · São Paulo (gru) · app "mesa-digital" ────────────────────────────┐
 │  Uma imagem Docker:  React (build do Vite, servido pelo próprio app)  +  API FastAPI (uvicorn)         │
 │  /           → site e cardápio (SPA)                                                                   │
 │  /api/...    → API REST (autenticação JWT, X-Tenant)                                                   │
 └───────────────┬──────────────────────────────┬───────────────────────────┬────────────────────────────┘
                 │                              │                           │
                 ▼                              ▼                           ▼
   Supabase PostgreSQL (sa-east-1)      Asaas (assinaturas)        Resend (e-mails)
   schema "mesa", usuário "mesa_app",   webhook → /api/billing     Sentry (erros, opcional)
   RLS em todas as tabelas              /webhook                   Claude API (leitura de foto, opcional)

 Fly.io · app "mesa-digital-backup": máquina agendada 1x/dia → pg_dump → restauração de prova → GPG → Cloudflare R2
 UptimeRobot: verifica /api/health a cada 5 minutos
```

| Parte | Tecnologia |
|---|---|
| `backend/` | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, PostgreSQL, Pillow, openpyxl e reportlab (exportações) |
| `frontend/` | React 19, TypeScript, Vite 7, React Router 7, lucide-react (ícones), sonner (avisos) |
| Imagens | Validadas, redimensionadas e convertidas para WebP. Ficam no banco, com cota de 100 MB por loja; o Cloudflare R2 é opcional |
| Tempo real | Consulta periódica (*polling*) curta no painel e na comanda |

A API segue camadas: **rotas** (`api/routes`) → **serviços** (regras de negócio, `services`) → **repositórios**
(consultas sempre filtradas pelo tenant, `repositories`) → **modelos** (`models`). Os **schemas** Pydantic validam a
entrada e a saída, com mensagens em português.

---

## 6. Estrutura de pastas

```
backend/
  app/
    main.py              # cria a API e registra as rotas
    web.py               # app de produção: API em /api + site React
    api/routes/          # auth, tenant, products, categories, menu_import, orders, tabs, public,
                         # billing, coupons, customers, users, media, analytics, audit, platform
    core/                # config, segurança, planos, multi-tenant, limitador, PIX, Asaas, e-mail,
                         # Sentry, leitura de cardápio (menu_ai), QR das mesas, termos
    models/ repositories/ schemas/ services/
  alembic/versions/      # 0001…0011: migrações do banco (rodam sozinhas a cada deploy)
  scripts/               # create_tenant, manage_tenant, seed_demo, asaas_webhook
  tests/                 # testes de integração (cada teste cria e apaga a própria loja)
frontend/
  src/
    app/                 # rotas e layout
    features/            # uma pasta por tela: menu (cliente), orders, tables, products, plans, settings…
    components/ui/       # Modal, MoneyInput, ImageUpload, Toggle, ErrorBoundary…
    services/            # chamadas à API
    lib/                 # formatação, termos (legal.ts), monitoramento
backup/                  # backup diário (Dockerfile + backup.sh + fly.toml)
.github/workflows/       # backup manual pelo GitHub Actions (alternativa)
Dockerfile, fly.toml     # imagem e configuração de produção
DEPLOY.md                # passo a passo de infraestrutura
dev.sh                   # sobe tudo localmente
```

---

## 7. Multi-tenant, segurança e privacidade

**Isolamento entre lojas**
- Banco único. Toda tabela de dados tem `tenant_id`, e todo repositório filtra por ele.
- Chaves estrangeiras compostas `(tenant_id, id)` impedem, no próprio banco, ligar um produto a uma categoria de outra
  loja.
- **Row Level Security** está ligado em todas as tabelas do schema `mesa`, e a API usa um usuário próprio (`mesa_app`).
- O frontend lê o subdomínio e envia `X-Tenant`. O token de login (JWT) carrega a loja e só vale nela.
- `tests/test_isolation.py` garante que uma loja nunca vê nem altera dados de outra.

**Proteções**
- Limitador de tentativas por IP real (`Fly-Client-IP` / `CF-Connecting-IP`): login, cadastro, recuperação de senha,
  pedidos públicos e leitura de cardápio.
- O QR Code de cada mesa tem um **código secreto** (HMAC): ninguém abre a conta de outra mesa trocando o número no link.
- Trocar a senha derruba as sessões antigas (`token_version`).
- Exportações CSV e XLSX neutralizam fórmulas, contra injeção em planilha.
- Cabeçalhos de segurança, validação de imagens, cota de armazenamento e mensagens de erro sem detalhes internos.
- Em produção, a API recusa subir com segredo JWT fraco ou com origens `localhost`.

**Privacidade (LGPD)**
- Termos e política em `/termos` e `/privacidade` (`frontend/src/lib/legal.ts`), com aceite registrado.
- O Sentry envia erros **sem dados pessoais**: remove corpo, cookies, parâmetros e usuário, e mascara credenciais. Há
  teste para isso.
- Segredos ficam fora do git: no Fly (`fly secrets`) e em `backend/.env.production.secret` (ignorado pelo git).

**Em caso de erro no navegador**, o cliente vê a tela "Algo deu errado — Recarregar" em vez de uma página em branco.

---

## 8. Rodando localmente

Atalho (macOS/Linux): `./dev.sh`. Ele pergunta a `DATABASE_URL`, instala, migra, popula e sobe a API e o site.

Manual:

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env.development        # preencha DATABASE_URL e JWT_SECRET_KEY
alembic upgrade head
python -m scripts.seed_demo             # 3 lojas demo com fotos, uma por plano
uvicorn app.main:app --reload --port 8010
```

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173 (site) e http://<slug>.localhost:5173 (cada loja)
```

O navegador resolve `*.localhost` para a própria máquina, então não é preciso mexer no arquivo hosts.

### Contas demo locais (só valem no seu computador)

| Plano | Painel | Login |
|---|---|---|
| Degustação | http://demo.localhost:5173/login | teste@demo.com / teste1234 |
| Essencial | http://demo-essencial.localhost:5173/login | essencial@demo.com / essencial123 |
| Profissional | http://demo-pro.localhost:5173/login | pro@demo.com / profissional123 |

O cardápio de cada uma fica no mesmo endereço, sem `/login`. No Safari, use
`http://localhost:5173/login?tenant=demo-pro`. Em produção as demos usam senhas aleatórias
(`seed_demo --random-passwords`).

---

## 9. Testes

```bash
cd backend && pytest                         # 87 testes de integração contra o DATABASE_URL de desenvolvimento
cd frontend && npx tsc -b && npm run build   # checagem de tipos e build
```

Os testes cobrem isolamento entre lojas, planos e limites, pedidos, comanda, PIX da mesa, assinatura (com o Asaas
simulado), importação de cardápio (com o Claude simulado), segurança e monitoramento. Nenhum teste fala com serviços
externos de verdade.

---

## 10. Produção e operação

O passo a passo de infraestrutura está em **[DEPLOY.md](DEPLOY.md)**.

| Serviço | Para quê |
|---|---|
| **Fly.io** (`mesa-digital`, São Paulo) | Site e API, 1 máquina sempre ligada. As migrações rodam a cada deploy (`release_command`) |
| **Supabase** (`mesa-digital-prod`, sa-east-1) | Banco PostgreSQL de produção |
| **Cloudflare** | DNS com curinga `*.mesadig.com.br` e HTTPS. Também hospedará o R2 (backups) e o e-mail de contato |
| **Registro.br** | Domínio `mesadig.com.br` |
| **Asaas** | Cobrança das assinaturas |
| **Resend** | E-mails do sistema (recuperação de senha, alerta de falha no backup) |
| **UptimeRobot** | Avisa se o site cair |
| **Sentry** (opcional) | Avisa de erros no servidor e no navegador |
| **GitHub** (`AndradeVac/Saas`, público) | Código. Fluxo: branch → PR → merge no `main` → deploy |

**Publicar uma versão nova:** `~/.fly/bin/flyctl deploy --remote-only` (na raiz do projeto).

**Backup diário:** a máquina agendada `mesa-digital-backup` copia o banco, **restaura a cópia para provar que
funciona**, criptografa com AES-256 e envia ao Cloudflare R2, guardando 30 dias. Se falhar, manda e-mail. A senha
(`BACKUP_PASSPHRASE`) fica em `backend/.env.production.secret` e precisa estar também num gerenciador de senhas.
A restauração está explicada no DEPLOY.md, seção 7b.

**Saúde:** `https://mesadig.com.br/api/health` responde `{"status":"ok","database":"ok"}`.

---

## 11. Ferramentas do dono da plataforma

Rodam em `backend/`. Em produção, rode com `~/.fly/bin/flyctl ssh console -a mesa-digital -C "python -m scripts.…"`.

```bash
python -m scripts.manage_tenant list                                   # lojas, plano, teste e pedidos
python -m scripts.manage_tenant extend-trial <slug> --days 7           # mais dias de degustação
python -m scripts.manage_tenant activate <slug> --plan essencial|pro   # ativa um plano à mão
python -m scripts.manage_tenant courtesy <slug> --days 15 --plan pro   # cortesia que expira sozinha
python -m scripts.manage_tenant suspend <slug>                         # bloqueia a loja
python -m scripts.create_tenant --slug minha-loja --name "Minha Loja" --type BAKERY --email dono@exemplo.com
python -m scripts.asaas_webhook https://mesadig.com.br/api/billing/webhook   # registra/atualiza o webhook
```

---

## 12. Configuração (variáveis de ambiente)

Lidas de `backend/.env.<ENVIRONMENT>` no desenvolvimento e de `fly secrets` / `fly.toml` em produção.

| Variável | Para quê |
|---|---|
| `DATABASE_URL` | Banco PostgreSQL (obrigatória) |
| `JWT_SECRET_KEY` | Assinatura dos logins (obrigatória e forte em produção) |
| `ROOT_DOMAIN`, `FRONTEND_URL`, `PUBLIC_SCHEME`, `PUBLIC_PORT` | Domínio e links das lojas |
| `TRIAL_DAYS` | Dias de degustação (padrão 14) |
| `SALES_WHATSAPP` | WhatsApp de vendas, quando não há cobrança online |
| `ASAAS_API_KEY`, `ASAAS_WEBHOOK_TOKEN`, `BILLING_GRACE_DAYS` | Assinatura online e tolerância de atraso |
| `RESEND_API_KEY`, `EMAIL_FROM` | E-mails do sistema |
| `ANTHROPIC_API_KEY` | Leitura de cardápio por foto direto no painel (sem ela, só o caminho grátis) |
| `SENTRY_DSN` (servidor) e `VITE_SENTRY_DSN` (site, no build) | Aviso de erros |
| `R2_*`, `MEDIA_PUBLIC_URL` | Fotos no Cloudflare R2 (opcional) |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `WEB_CONCURRENCY` | Conexões e processos |

---

## 13. Pendências e próximos passos

**Para colocar clientes reais com tranquilidade**
- [ ] **Backup:** ativar o Cloudflare R2 e configurar as chaves no app `mesa-digital-backup`.
- [ ] **E-mail `contato@mesadig.com.br`:** ativar o Email Routing da Cloudflare e colocar o endereço em
      `legal.ts` (`privacyEmail`).
- [ ] **Sentry:** criar o projeto e configurar o DSN.

**Negócio**
- [ ] Contador: CNAE de software (62.03-1/00 ou 63.11-9/00), MEI ou ME, e nota fiscal de serviço em São Caetano do Sul.
- [ ] Asaas no CNPJ (hoje está no CPF) e conta bancária PJ para saque.
- [ ] Advogado revisar `/termos` e `/privacidade`.

**Produto (ideias)**
- PIX da mesa com confirmação automática (subcontas Asaas).
- Painel da plataforma para ver todas as lojas, receita e assinaturas.
- Domínio próprio por loja, avisos por WhatsApp e impressão direta em impressora térmica.
