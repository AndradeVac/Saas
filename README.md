# Mesa Digital

Plataforma SaaS multi-tenant de cardápio digital e gestão de pedidos para restaurantes, padarias e cafeterias.
Base: Hookah Driver (mesma arquitetura em camadas), reestruturada para vários clientes.

Cada cliente (tenant) ganha o próprio endereço `https://<slug>.<domínio>` com cardápio público, QR Code por mesa
e painel com login e senha da equipe.

| Parte | Stack |
|---|---|
| `backend/` | Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL (Neon) |
| `frontend/` | React 19, TypeScript, Vite |

## O que o dono do negócio controla (painel)

| Área | O que faz |
|---|---|
| **Visão geral** | Faturamento, pedidos, ticket médio, gráficos por dia/horário/categoria, exportação Excel/PDF e checklist de primeiros passos |
| **Pedidos** | Fila ao vivo (atualiza sozinha, com aviso sonoro e contador na aba), avanço de status, pagamento no caixa, cancelamento com motivo, edição, impressão de comanda |
| **Mesas (comanda)** | Uma conta aberta por mesa, sem fichas nem papel: o cliente pede pelo QR Code quantas vezes quiser e paga no final. Aprovação da mesa nova, mapa com alertas automáticos (mesa nova, pediu a conta, parada há X min, pedido atrasado), fechamento com forma de pagamento e mesa liberada sozinha |
| **Histórico** | Busca por nº/cliente/telefone/mesa, filtros de status/pagamento/atendimento/período, paginação e exportação CSV |
| **Produtos** | Foto (upload), preço, descrição, destaque, esgotado, ocultar, ordem, e **grupos de opções** (tamanho, adicionais…) com preço |
| **Categorias** | Criar, renomear, ordenar, ocultar |
| **Cupons** | Percentual ou valor fixo, pedido mínimo, limite de usos, validade; o uso volta se o pedido for cancelado |
| **Clientes** | Lista com total gasto e último pedido, busca, edição, observações, exportação CSV |
| **Equipe** | Criar usuários, perfis (Administrador/Operador), redefinir senha, desativar |
| **Configurações** | Dados e marca (logo, capa, cor), abertura manual ou **por horário**, tipos de atendimento (mesa/retirada/entrega), formas de pagamento, chave PIX, pedido mínimo, taxa de entrega e de serviço, QR Codes por mesa, senha |
| **Auditoria** | Quem fez o quê, com filtro e paginação |

Na mesa (comanda ligada): o celular entra na conta da mesa pelo QR Code, acompanha a conta ao vivo, pede mais,
**repete a última rodada** com um toque, recebe o convite "Mais uma rodada?" após um tempo sem pedir e fecha a conta
escolhendo a forma de pagamento e dividindo entre as pessoas.

Cliente final (`/`): capa e informações do negócio, horários, busca, categorias com rolagem, destaques, produtos com
opções/observações, carrinho, cupom, mesa/entrega, acompanhamento do pedido em tempo real e histórico no aparelho.

## Planos e degustação

Definidos em um só lugar: `backend/app/core/plans.py` (preços, limites e recursos). A API aplica os limites
(resposta **402** com `code: PLAN_LIMIT`); o painel só espelha, mostrando cadeados, medidores de uso e o convite para assinar.

| | Degustação (teste) | Essencial | Profissional |
|---|---|---|---|
| Preço | grátis por `TRIAL_DAYS` | R$ 79,90/mês | R$ 149,90/mês |
| Produtos ativos | 10 | 80 | ilimitados |
| Equipe | só o dono | 3 | ilimitada |
| Pedidos | 30 no teste | ilimitados | ilimitados |
| Cupons, exportações | — | ✓ | ✓ |
| Auditoria, cardápio sem a marca da plataforma | — | — | ✓ |

- O teste é um "sabor": o fluxo principal (cardápio com fotos, QR Code, pedidos) funciona, mas o volume é limitado e as
  ferramentas premium aparecem bloqueadas, com a explicação do que liberam.
- Teste vencido ou pedidos do teste esgotados: o cardápio continua no ar e o painel editável, mas não entram novos pedidos.
- Botões "Assinar" abrem o WhatsApp de vendas definido em `SALES_WHATSAPP`; a ativação é feita com
  `python -m scripts.manage_tenant activate <slug> --plan essencial|pro`.

## Multi-tenant e escala

- Banco único; toda tabela de dados tem `tenant_id` e todo repositório filtra por ele. Chaves estrangeiras compostas
  `(tenant_id, id)` impedem, no próprio banco, ligar um produto a uma categoria (ou um pedido a um cliente) de outro tenant.
- O frontend lê o subdomínio e envia `X-Tenant: <slug>`. O JWT carrega o tenant (`tid`) e só vale nele.
- Numeração de pedidos sequencial por tenant (contador atômico); último uso de cupom é atômico (sem corrida).
- Índices por `(tenant_id, …)` nas consultas quentes; listagens paginadas no servidor; busca de cliente por telefone indexada.
- Cardápio público com cache de poucos segundos (por processo e cabeçalhos `Cache-Control`), pensado para picos de QR Code.
- Pool de conexões configurável (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`) e `--workers` no deploy; compatível com o pooler do Neon.
- Imagens enviadas são validadas, redimensionadas e convertidas para WebP; guardadas no banco com cota por tenant (100 MB).
- `backend/tests/test_isolation.py` garante que um tenant nunca vê nem altera dados de outro.

## Rodando localmente

Atalho (macOS/Linux): `./dev.sh` (pergunta a `DATABASE_URL`, faz setup, migra, popula e sobe API + frontend).

Manual:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env.development      # preencha DATABASE_URL e JWT_SECRET_KEY
alembic upgrade head
python -m scripts.seed_demo             # 3 contas demo com fotos, uma por plano (veja abaixo)
uvicorn app.main:app --reload --port 8010
```

```bash
cd frontend
npm install
npm run dev     # http://localhost:5173 (site) e http://<slug>.localhost:5173 (cada cliente)
```

A API local usa a porta **8010** (a 8000 costuma estar com o Hookah Driver). Navegadores resolvem `*.localhost` para a
própria máquina, então não é preciso mexer no arquivo hosts.

Ferramentas de operação (você, dono da plataforma):

```bash
python -m scripts.create_tenant --slug minha-padaria --name "Minha Padaria" --type BAKERY --email dono@exemplo.com
python -m scripts.manage_tenant list
python -m scripts.manage_tenant suspend minha-padaria      # bloqueia o acesso do cliente
python -m scripts.manage_tenant activate minha-padaria --plan pro
python -m scripts.manage_tenant extend-trial minha-padaria --days 7
```

### Contas demo (uma por plano)

| Plano | Painel | Login |
|---|---|---|
| Teste (Degustação) | http://demo.localhost:5173/login | teste@demo.com / teste1234 |
| Essencial | http://demo-essencial.localhost:5173/login | essencial@demo.com / essencial123 |
| Profissional | http://demo-pro.localhost:5173/login | pro@demo.com / profissional123 |

Cardápio de cada uma: mesmo endereço sem `/login`. No Safari, use `http://localhost:5173/login?tenant=demo-pro`.
São credenciais de desenvolvimento, válidas só no seu computador. Em produção as contas demo usam senhas
aleatórias (`seed_demo --random-passwords`), guardadas fora do git em `backend/.env.production.secret`.

## Testes

```bash
cd backend && pytest        # 41 testes de integração contra o DATABASE_URL (cada teste cria e apaga o próprio tenant)
cd frontend && npm run lint && npm run build
```

## Produção

Passo a passo completo em **[DEPLOY.md](DEPLOY.md)**: Fly.io São Paulo (site + API num app só, `app.web`),
Neon, Cloudflare (DNS, HTTPS para `*.<domínio>`) e fotos no Cloudflare R2.

- `Dockerfile` monta o frontend e a API numa imagem; `fly.toml` roda as migrations a cada deploy.
- Em produção a API recusa subir sem `JWT_SECRET_KEY` forte e com origens `localhost`; `seed_demo` não roda.
- O limitador de requisições é por processo (em memória). Com muitas instâncias, mova para Redis.

## Roadmap

- Pagamento online (Pix/cartão) com credenciais por tenant, guardadas criptografadas.
- Cobrança por planos (o tenant já tem `status`, `plan` e `trial_ends_at`; hoje só há aviso de fim do teste) e painel de super-admin.
- Domínio próprio por cliente, notificações por WhatsApp/e-mail, impressora térmica direta.
- Armazenamento de imagens em S3/R2 quando o volume crescer.
