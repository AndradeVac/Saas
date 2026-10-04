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
| **Histórico** | Busca por nº/cliente/telefone/mesa, filtros de status/pagamento/atendimento/período, paginação e exportação CSV |
| **Produtos** | Foto (upload), preço, descrição, destaque, esgotado, ocultar, ordem, e **grupos de opções** (tamanho, adicionais…) com preço |
| **Categorias** | Criar, renomear, ordenar, ocultar |
| **Cupons** | Percentual ou valor fixo, pedido mínimo, limite de usos, validade; o uso volta se o pedido for cancelado |
| **Clientes** | Lista com total gasto e último pedido, busca, edição, observações, exportação CSV |
| **Equipe** | Criar usuários, perfis (Administrador/Operador), redefinir senha, desativar |
| **Configurações** | Dados e marca (logo, capa, cor), abertura manual ou **por horário**, tipos de atendimento (mesa/retirada/entrega), formas de pagamento, chave PIX, pedido mínimo, taxa de entrega e de serviço, QR Codes por mesa, senha |
| **Auditoria** | Quem fez o quê, com filtro e paginação |

Cliente final (`/`): capa e informações do negócio, horários, busca, categorias com rolagem, destaques, produtos com
opções/observações, carrinho, cupom, mesa/entrega, acompanhamento do pedido em tempo real e histórico no aparelho.

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

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env.development      # preencha DATABASE_URL e JWT_SECRET_KEY
alembic upgrade head
python -m scripts.seed_demo             # conta demo: http://demo.localhost:5173
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

## Testes

```bash
cd backend && pytest        # 41 testes de integração contra o DATABASE_URL (cada teste cria e apaga o próprio tenant)
cd frontend && npm run lint && npm run build
```

## Produção

- **API (Render):** `render.yaml`. Defina `DATABASE_URL`, `JWT_SECRET_KEY` (gerada), `FRONTEND_URL`
  (ex.: `https://mesadigital.app,https://*.mesadigital.app`) e `ROOT_DOMAIN`.
- **Frontend (Vercel):** root `frontend`, `VITE_API_URL=https://api.<domínio>`, `VITE_ROOT_DOMAIN=<domínio>`.
  Configure o domínio raiz e o curinga `*.<domínio>` no projeto da Vercel (DNS wildcard).
- Em produção a API recusa subir sem `JWT_SECRET_KEY` forte e com origens `localhost`; `seed_demo` não roda.
- O limitador de requisições é por processo (em memória). Com muitos workers/instâncias, mova para Redis.

## Roadmap

- Pagamento online (Pix/cartão) com credenciais por tenant, guardadas criptografadas.
- Cobrança por planos (o tenant já tem `status`, `plan` e `trial_ends_at`; hoje só há aviso de fim do teste) e painel de super-admin.
- Domínio próprio por cliente, notificações por WhatsApp/e-mail, impressora térmica direta.
- Armazenamento de imagens em S3/R2 quando o volume crescer.
