#!/usr/bin/env bash
# Sobe tudo localmente (macOS/Linux): ./dev.sh
# Uso:  DATABASE_URL='postgresql://...' ./dev.sh   (ou o script pergunta)
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"

PY=""
for c in python3.13 python3.12 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3,12))'; then PY="$c"; break; fi
done
[ -n "$PY" ] || { echo "Precisa de Python 3.12+ (brew install python@3.12)"; exit 1; }
command -v npm >/dev/null || { echo "Precisa de Node.js (brew install node)"; exit 1; }

cd "$ROOT/backend"
[ -d .venv ] || "$PY" -m venv .venv
. .venv/bin/activate
pip install -q -r requirements-dev.txt

if [ ! -f .env.development ]; then
  cp .env.example .env.development
  if [ -z "${DATABASE_URL:-}" ]; then
    read -r -p "DATABASE_URL (Neon/Postgres): " DATABASE_URL
  fi
  JWT="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
  DATABASE_URL="$DATABASE_URL" JWT="$JWT" python - <<'PYEOF'
import os, re
p = ".env.development"
s = open(p).read()
s = re.sub(r"^DATABASE_URL=.*$", lambda m: "DATABASE_URL=" + os.environ["DATABASE_URL"], s, flags=re.M)
s = re.sub(r"^JWT_SECRET_KEY=.*$", lambda m: "JWT_SECRET_KEY=" + os.environ["JWT"], s, flags=re.M)
open(p, "w").write(s)
PYEOF
fi

alembic upgrade head
python -m scripts.seed_demo || true

cd "$ROOT/frontend"
[ -d node_modules ] || npm install

uvicorn_pid=""
trap '[ -n "$uvicorn_pid" ] && kill "$uvicorn_pid" 2>/dev/null' EXIT
(cd "$ROOT/backend" && . .venv/bin/activate && uvicorn app.main:app --reload --port 8010) &
uvicorn_pid=$!

echo
echo "Contas demo (Chrome/Firefox), uma por plano:"
echo "  Teste:        http://demo.localhost:5173/login            teste@demo.com / teste1234"
echo "  Essencial:    http://demo-essencial.localhost:5173/login  essencial@demo.com / essencial123"
echo "  Profissional: http://demo-pro.localhost:5173/login        pro@demo.com / profissional123"
echo "Safari não resolve *.localhost: adicione '127.0.0.1 demo.localhost' ao /etc/hosts."
echo
npm run dev
