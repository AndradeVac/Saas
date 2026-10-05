# Colocando o Mesa Digital no ar

Arquitetura (custo inicial: só o Fly.io, cerca de US$ 4–6/mês):

```
Cliente ──► Cloudflare (DNS, HTTPS, proteção) ──► Fly.io São Paulo (site + API, 1 app)
                 │                                        │
                 └── R2: fotos.SEU-DOMINIO.com            └── Neon São Paulo (Postgres)
```

- **Fly.io (região `gru`)**: um app só serve o site e a API (`/api`), sempre ligado.
- **Neon**: o banco que você já usa, também em São Paulo.
- **Cloudflare (grátis)**: DNS do domínio, certificado para `*.SEU-DOMINIO.com` e cache.
- **Cloudflare R2 (grátis até 10 GB)**: as fotos, servidas direto de `fotos.SEU-DOMINIO.com`.

Nos comandos abaixo, troque `SEU-DOMINIO.com` pelo seu domínio e `mesa-digital` pelo nome do app no Fly.

---

## 1. Domínio (grátis no seu plano Hostinger)

1. hPanel → **Domínios** → resgate o domínio grátis incluído no plano.
2. Ainda não mexa no DNS: no passo 2 ele passa a ser gerenciado pela Cloudflare.

## 2. Cloudflare

1. Crie a conta em <https://dash.cloudflare.com> → **Add a domain** → informe o domínio → plano **Free**.
2. A Cloudflare mostra **2 nameservers**. No hPanel: **Domínios → seu domínio → DNS / Nameservers →
   Alterar nameservers** e cole os dois. A troca leva de minutos a algumas horas.
3. Em **SSL/TLS → Overview**, escolha **Full (strict)**.
4. Em **SSL/TLS → Edge Certificates**, ligue **Always Use HTTPS**.

## 3. Banco (Neon)

O banco atual vira o de **produção**. Para desenvolver sem mexer nele:

1. No Neon: **Branches → Create branch** com o nome `dev`.
2. Copie a connection string do branch `dev` e use-a em `backend/.env.development`.
   Os testes automáticos criam e apagam contas, então devem rodar no `dev`, nunca na produção.

## 4. Fly.io

```bash
curl -L https://fly.io/install.sh | sh          # instala o flyctl (sem sudo)
fly auth login                                   # abre o navegador (o Fly pede cartão)
fly apps create mesa-digital                     # se o nome estiver em uso, escolha outro
```

Edite o `fly.toml`: o nome do app (`app = ...`) e `SEU-DOMINIO.com` (3 lugares).

Segredos (ficam criptografados no Fly e nunca vão para o git):

```bash
fly secrets set \
  DATABASE_URL='postgresql://...neon.tech/neondb?sslmode=require' \
  JWT_SECRET_KEY="$(openssl rand -base64 48)" \
  SALES_WHATSAPP=55DDDSEUNUMERO
```

Primeiro deploy (o Fly monta a imagem nos servidores dele e roda as migrations antes de liberar):

```bash
fly deploy
fly open /api/health                             # deve mostrar {"status":"ok","database":"ok"}
```

## 5. Domínio apontando para o Fly

```bash
fly ips allocate-v4 --shared                     # IPv4 compartilhado (grátis)
fly ips allocate-v6
fly ips list                                     # anote os dois IPs
fly certs add SEU-DOMINIO.com
fly certs add "*.SEU-DOMINIO.com"
fly certs show "*.SEU-DOMINIO.com"               # mostra o registro _acme-challenge
```

Na Cloudflare, em **DNS → Records**, crie os registros com a nuvem **cinza (DNS only)**:

| Tipo | Nome | Valor |
|---|---|---|
| A | `@` | IPv4 do Fly |
| AAAA | `@` | IPv6 do Fly |
| A | `*` | IPv4 do Fly |
| AAAA | `*` | IPv6 do Fly |
| CNAME | `_acme-challenge` | o valor mostrado por `fly certs show` |

Espere `fly certs show SEU-DOMINIO.com` e `fly certs show "*.SEU-DOMINIO.com"` dizerem **Issued**. Depois mude
os registros `@` e `*` para a nuvem **laranja (Proxied)**. Deixe o `_acme-challenge` sempre cinza, para o Fly
conseguir renovar o certificado.

## 6. Fotos no Cloudflare R2

1. Cloudflare → **R2 Object Storage**. O R2 pede um cartão cadastrado, mas até 10 GB não cobra nada.
2. **Create bucket** com o nome `mesa-digital-fotos`.
3. No bucket: **Settings → Custom Domains → Connect Domain** → `fotos.SEU-DOMINIO.com`.
4. R2 → **Manage API tokens → Create API token**, com permissão **Object Read & Write** só para esse bucket.
   Anote o **Access Key ID**, o **Secret Access Key** e o **Account ID**.
5. No Fly:

```bash
fly secrets set \
  R2_ACCOUNT_ID=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=... \
  R2_BUCKET=mesa-digital-fotos MEDIA_PUBLIC_URL=https://fotos.SEU-DOMINIO.com
```

Novas fotos passam a ir para o R2. As antigas continuam no banco e seguem funcionando.

## 7. Contas demo em produção (opcional)

O exemplo de cardápio da página de vendas mostra a conta `demo`. Para criá-la no banco de produção, rode da sua
máquina (o script não roda com `ENVIRONMENT=production`):

```bash
cd backend
DATABASE_URL='<url do banco de produção>' python -m scripts.seed_demo
```

As senhas das contas demo estão no README. Em produção, qualquer pessoa que as conheça entra nelas.
Se for divulgar, troque as senhas pelo painel (Equipe → redefinir senha).

## 8. Monitoramento (grátis)

- **UptimeRobot**: monitor HTTP em `https://SEU-DOMINIO.com/api/health`, com aviso por e-mail ou WhatsApp.
- **Logs**: `fly logs`.

## Dia a dia

| Tarefa | Comando |
|---|---|
| Publicar uma nova versão | `fly deploy` |
| Ver logs | `fly logs` |
| Ativar o plano de um cliente | `fly ssh console -C "sh -c 'cd /app/backend && python -m scripts.manage_tenant activate padaria-x --plan pro'"` |
| Listar clientes | `fly ssh console -C "sh -c 'cd /app/backend && python -m scripts.manage_tenant list'"` |
| Voltar para a versão anterior | `fly releases` e depois `fly deploy --image <imagem anterior>` |
