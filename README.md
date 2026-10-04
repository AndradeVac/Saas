# Mesa Digital

Plataforma SaaS multi-tenant de cardápio digital e gestão de pedidos para restaurantes, padarias e cafeterias.
Base: Hookah Driver (mesma arquitetura em camadas), reestruturada para vários clientes.

Cada cliente (tenant) ganha o próprio endereço `https://<slug>.<domínio>` com cardápio público, QR Code por mesa
e painel com login e senha da equipe.

| Parte | Stack |
|---|---|
| `backend/` | Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL (Neon) |
| `frontend/` | React 19, TypeScript, Vite |

## Como funciona o multi-tenant

- Banco único; toda tabela de dados tem `tenant_id` e todo repositório filtra por ele.
- O frontend lê o subdomínio e envia `X-Tenant: <slug>` em todas as chamadas. O token JWT carrega o tenant
  (`tid`) e só vale nele; usuários, e-mails, categorias e pedidos são separados por tenant.
- Sem subdomínio (`localhost:5173`) abre o site da plataforma: página inicial e `/cadastro`.
- Rotas do tenant: `/` cardápio público (`/?mesa=5` pré-preenche a mesa), `/login`, `/painel/...`.
- Os testes em `backend/tests/test_isolation.py` garantem que um tenant nunca vê nem altera dados de outro.

## Rodando localmente

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env.development      # preencha DATABASE_URL e JWT_SECRET_KEY
alembic upgrade head
python -m scripts.seed_demo             # conta demo: http://demo.localhost:5173
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev     # http://localhost:5173 (site) e http://<slug>.localhost:5173 (cada cliente)
```

Navegadores resolvem `*.localhost` para a própria máquina, então não é preciso mexer no arquivo hosts.
Novo cliente pelo terminal: `python -m scripts.create_tenant --slug minha-padaria --name "Minha Padaria" --type BAKERY --email dono@exemplo.com`.

## Testes

```bash
cd backend && pytest        # integração contra o DATABASE_URL (cada teste cria e apaga o próprio tenant)
cd frontend && npm run lint && npm run build
```

## Produção

- **API (Render):** `render.yaml`. Defina `DATABASE_URL`, `JWT_SECRET_KEY` (gerada), `FRONTEND_URL`
  (ex.: `https://mesadigital.app,https://*.mesadigital.app`) e `ROOT_DOMAIN`.
- **Frontend (Vercel):** root `frontend`, `VITE_API_URL=https://api.<domínio>`, `VITE_ROOT_DOMAIN=<domínio>`.
  Configure o domínio raiz e o curinga `*.<domínio>` no projeto da Vercel (DNS wildcard).
- Em produção a API recusa subir sem `JWT_SECRET_KEY` forte e com origens `localhost`.
- `seed_demo` não roda em produção.

## Roadmap (fora do escopo desta versão)

- Pagamento online (Pix/cartão) com credenciais por tenant, guardadas criptografadas.
- Upload de imagens (hoje o produto aceita link de foto).
- Planos e cobrança (o tenant já tem `status`, `plan` e `trial_ends_at`) e painel de super-admin.
- Domínio próprio por cliente, variações e adicionais de produto, entrega com endereço e taxa.
- Rate limit em Redis ao escalar para mais de uma instância.
