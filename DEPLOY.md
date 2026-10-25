# Colocando o Mesa Digital no ar

Arquitetura (custo inicial: só o Fly.io, cerca de US$ 4–6/mês):

```
Cliente ──► Cloudflare (DNS, HTTPS, proteção) ──► Fly.io São Paulo (site + API, 1 app)
                 │                                        │
                 └── R2: fotos.mesadig.com.br            └── Neon São Paulo (Postgres)
```

- **Fly.io (região `gru`)**: um app só serve o site e a API (`/api`), sempre ligado.
- **Neon**: o banco que você já usa, também em São Paulo.
- **Cloudflare (grátis)**: DNS do domínio, certificado para `*.mesadig.com.br` e cache.
- **Cloudflare R2 (grátis até 10 GB)**: as fotos, servidas direto de `fotos.mesadig.com.br`.

Domínio: **mesadig.com.br**. Se o nome `mesa-digital` já estiver em uso no Fly, troque-o nos comandos e no `fly.toml`.

---

## 1. Domínio .com.br (Registro.br, cerca de R$ 40/ano)

1. Em <https://registro.br>, pesquise o nome, entre com o seu CPF/CNPJ (crie a conta se precisar) e registre.
   Pague o boleto ou PIX; o domínio é ativado após a compensação.
2. Não precisa configurar o DNS no Registro.br: no passo 2 ele passa a ser gerenciado pela Cloudflare.

## 2. Cloudflare

1. Crie a conta em <https://dash.cloudflare.com> → **Add a domain** → informe o domínio → plano **Free**.
2. A Cloudflare mostra **2 nameservers** (ex.: `ana.ns.cloudflare.com`). No Registro.br: **Painel → seu domínio
   → DNS → Alterar servidores DNS** e cole os dois. A troca leva de minutos a algumas horas.
3. Em **SSL/TLS → Overview**, escolha **Full (strict)**.
4. Em **SSL/TLS → Edge Certificates**, ligue **Always Use HTTPS**.

## 3. Banco

| Ambiente | Banco |
|---|---|
| **Produção** | Supabase `mesa-digital-prod` (São Paulo), schema `mesa`, usuário `mesa_app` |
| **Desenvolvimento** (seu computador e testes) | Neon, via `backend/.env.development` |

- O app entra no Supabase com um usuário próprio (`mesa_app`), não com o administrador `postgres`. O `search_path`
  dele aponta para o schema `mesa`, que **não** é exposto pela API automática do Supabase (Data API): as roles
  `anon`, `authenticated` e `service_role` não têm acesso a ele.
- Conexão pelo **Session pooler** (porta 5432):
  `postgresql://mesa_app.<project-ref>:<senha>@aws-1-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require`.
  A senha fica só no Fly (`fly secrets`) e no arquivo local `backend/.env.production.secret` (ignorado pelo git).
- O pooler gratuito aceita ~15 conexões por usuário; por isso o `fly.toml` usa `DB_POOL_SIZE=3` e `DB_MAX_OVERFLOW=3`.
- Os testes automáticos criam e apagam contas: rode-os sempre no banco de desenvolvimento, nunca na produção.

## 4. Fly.io

```bash
curl -L https://fly.io/install.sh | sh          # instala o flyctl (sem sudo)
fly auth login                                   # abre o navegador (o Fly pede cartão)
fly apps create mesa-digital                     # se o nome estiver em uso, escolha outro
```

O `fly.toml` já está configurado para `mesadig.com.br`.

Segredos (ficam criptografados no Fly e nunca vão para o git):

```bash
fly secrets set \
  DATABASE_URL='postgresql://mesa_app.<project-ref>:<senha>@aws-1-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require' \
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
fly certs add mesadig.com.br
fly certs add "*.mesadig.com.br"
fly certs show "*.mesadig.com.br"               # mostra o registro _acme-challenge
```

Na Cloudflare, em **DNS → Records**, crie os registros com a nuvem **cinza (DNS only)**:

| Tipo | Nome | Valor |
|---|---|---|
| A | `@` | IPv4 do Fly |
| AAAA | `@` | IPv6 do Fly |
| A | `*` | IPv4 do Fly |
| AAAA | `*` | IPv6 do Fly |
| CNAME | `_acme-challenge` | o valor mostrado por `fly certs show` |

Espere `fly certs show mesadig.com.br` e `fly certs show "*.mesadig.com.br"` dizerem **Issued**. Depois mude
os registros `@` e `*` para a nuvem **laranja (Proxied)**. Deixe o `_acme-challenge` sempre cinza, para o Fly
conseguir renovar o certificado.

## 6. Fotos no Cloudflare R2

1. Cloudflare → **R2 Object Storage**. O R2 pede um cartão cadastrado, mas até 10 GB não cobra nada.
2. **Create bucket** com o nome `mesa-digital-fotos`.
3. No bucket: **Settings → Custom Domains → Connect Domain** → `fotos.mesadig.com.br`.
4. R2 → **Manage API tokens → Create API token**, com permissão **Object Read & Write** só para esse bucket.
   Anote o **Access Key ID**, o **Secret Access Key** e o **Account ID**.
5. No Fly:

```bash
fly secrets set \
  R2_ACCOUNT_ID=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=... \
  R2_BUCKET=mesa-digital-fotos MEDIA_PUBLIC_URL=https://fotos.mesadig.com.br
```

Novas fotos passam a ir para o R2. As antigas continuam no banco e seguem funcionando.

## 6b. E-mails do sistema (recuperação de senha)

O "Esqueci minha senha" envia o link por e-mail pelo **Resend** (grátis até 3.000 e-mails/mês).

1. Crie a conta em <https://resend.com> → **Domains → Add Domain** → `mesadig.com.br`.
2. O Resend mostra alguns registros DNS (SPF, DKIM e, opcionalmente, DMARC). Crie-os na Cloudflare
   (**DNS → Records**), sempre com a nuvem **cinza (DNS only)**, e clique em **Verify** no Resend.
3. **API Keys → Create API Key**, com permissão *Sending access*, e configure no Fly:

```bash
fly secrets set RESEND_API_KEY=re_... EMAIL_FROM='Mesa Digital <nao-responda@mesadig.com.br>'
```

Sem a chave, o sistema continua funcionando, mas o e-mail não é enviado; o administrador da equipe pode
redefinir senhas pelo painel (Equipe).

## 7. Contas demo em produção (opcional)

O exemplo de cardápio da página de vendas mostra a conta `demo`. Para criá-la no banco de produção, rode da sua
máquina (o script não roda com `ENVIRONMENT=production`):

```bash
cd backend
DATABASE_URL='<url do banco de produção>' python -m scripts.seed_demo --random-passwords
```

Use `--random-passwords`: as senhas do README valem só no seu computador, e em produção qualquer pessoa que as
conhecesse entraria nas contas demo. As senhas geradas aparecem uma vez na saída do comando; guarde-as.

## 7b. Backup e restauração

**Ligado desde 25/10/2026.** Uma vez por dia, a máquina agendada `backup-diario` (app `mesa-digital-backup`, código em
`backup/`) copia o schema `mesa`, **restaura a cópia num PostgreSQL 17 temporário para provar que funciona**,
criptografa (AES-256) e guarda no **disco do Fly** (volume `backups`, 1 GB, em `/data/backups`), mantendo 30 dias.
O Fly ainda tira snapshots diários do disco (5 guardados). Se o R2 for configurado (`R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`,
`R2_SECRET_ACCESS_KEY` nos segredos do app), cada cópia também vai para o R2, fora do Fly.

- **A senha (`BACKUP_PASSPHRASE`) está em `backend/.env.production.secret`. Guarde-a num gerenciador de senhas: sem ela
  os backups não abrem.**
- Ver o resultado: `fly logs -a mesa-digital-backup` (procure "Restaurado com sucesso" e "Backup concluído").
- Rodar agora: `fly machine start <id> -a mesa-digital-backup` (`fly machines list -a mesa-digital-backup` mostra o id).
- Atualizar o script: `cd backup && fly deploy --build-only --push --image-label latest -a mesa-digital-backup` e
  `fly machine update <id> --image registry.fly.io/mesa-digital-backup:latest -a mesa-digital-backup`.

Baixar uma cópia para o computador:

```bash
fly machine update <id> -a mesa-digital-backup --command "sleep 900" --yes   # mantém a máquina ligada 15 min
fly machine start <id> -a mesa-digital-backup
fly ssh sftp get /data/backups/mesa-digital-AAAA-MM-DD.dump.gpg -a mesa-digital-backup
fly machine update <id> -a mesa-digital-backup --command "" --yes            # volta ao backup normal
```

Restaurar (precisa do cliente do PostgreSQL 17 e do gpg):

```bash
gpg --decrypt mesa-digital-AAAA-MM-DD.dump.gpg > backup.dump          # pede a senha
pg_restore --dbname="postgresql://...banco-novo..." --no-owner --no-privileges backup.dump
```

Depois de restaurar num banco novo, aponte o `DATABASE_URL` do Fly para ele e rode `fly deploy`.
Alternativa manual: `.github/workflows/backup.yml`.

## 7c. Aviso de erros (Sentry)

1. Crie a conta grátis em <https://sentry.io> → **Create project** → plataforma **FastAPI** (nome `mesa-digital`).
2. Copie o **DSN** (Settings → Client Keys). O mesmo projeto serve para o servidor e o navegador.
3. Servidor: `fly secrets set SENTRY_DSN='https://...ingest.sentry.io/...'`
4. Navegador: em `fly.toml`, `[build.args]`, adicione `VITE_SENTRY_DSN = "https://..."` (o DSN é público por natureza) e `fly deploy`.

Os eventos não levam dados pessoais: sem corpo das requisições, cookies, credenciais ou query strings.

## 7d. Avisos automáticos pelo WhatsApp (API oficial da Meta)

O cliente marca "Me avise pelo WhatsApp quando o pedido estiver pronto" no carrinho e recebe, do número do Mesa Digital,
"em preparo" e "pronto" (ou "saiu para entrega"). Sem configurar, o sistema já funciona assim: notificação no celular do
cliente (pela tela do pedido) e, no painel, um botão "Avisar no WhatsApp" com a mensagem pronta quando o pedido fica pronto.

Passo a passo (uma vez, uns 20 minutos):

1. Em https://business.facebook.com crie (ou use) o Gerenciador de Negócios do Mesa Digital e, em
   https://developers.facebook.com, crie um app do tipo **Business** com o produto **WhatsApp**.
2. Em WhatsApp → Configuração da API, adicione um número de telefone que **não** esteja em uso no WhatsApp do celular
   (pode ser um chip novo) e verifique por SMS. Anote o **ID do número de telefone**.
3. Crie um **usuário do sistema** (Configurações do negócio → Usuários do sistema), dê acesso ao app e gere um **token
   permanente** com as permissões `whatsapp_business_messaging` e `whatsapp_business_management`.
4. Em WhatsApp → Modelos de mensagem, crie dois modelos, categoria **Utilidade**, idioma **Português (BR)**:
   - `pedido_em_preparo`: `Olá, {{1}}! Seu pedido #{{2}} da {{3}} já está sendo preparado. Avisamos quando estiver pronto.`
   - `pedido_pronto`: `Olá, {{1}}! Seu pedido #{{2}} da {{3}} está pronto. {{4}}`
   (exemplos para a Meta: `Joana`, `123`, `Hamburgueria do Zé`, `Pode retirar no balcão.`)
5. Com os modelos aprovados, no Terminal do Mac (aspas simples):

```bash
fly secrets set -a mesa-digital WHATSAPP_TOKEN='...' WHATSAPP_PHONE_NUMBER_ID='...'
```

Custo: a Meta cobra por conversa de utilidade (centavos por pedido avisado). Cada loja pode desligar em Configurações →
Pedidos e pagamento → "Avisar o cliente automaticamente".

## 8. Monitoramento (grátis)

- **UptimeRobot**: monitor HTTP em `https://mesadig.com.br/api/health`, com aviso por e-mail ou WhatsApp.
- **Logs**: `fly logs`.

## Dia a dia

| Tarefa | Comando |
|---|---|
| Publicar uma nova versão | `fly deploy` |
| Ver logs | `fly logs` |
| Ativar o plano de um cliente | `fly ssh console -C "sh -c 'cd /app/backend && python -m scripts.manage_tenant activate padaria-x --plan pro'"` |
| Listar clientes | `fly ssh console -C "sh -c 'cd /app/backend && python -m scripts.manage_tenant list'"` |
| Voltar para a versão anterior | `fly releases` e depois `fly deploy --image <imagem anterior>` |
