#!/bin/sh
# Dump schema "mesa" → restore it into a throwaway PostgreSQL to prove it works → encrypt (AES-256)
# → keep it on the machine's volume (BACKUP_DIR) and/or upload to Cloudflare R2 → delete copies older than
# RETENTION_DAYS. A failure e-mails ALERT_EMAIL (Resend).
set -eu

: "${BACKUP_DATABASE_URL:?}" "${BACKUP_PASSPHRASE:?}"
BUCKET="${R2_BUCKET:-mesa-digital-backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
BACKUP_DIR="${BACKUP_DIR:-/data/backups}"
USE_R2=""
if [ -n "${R2_ACCOUNT_ID:-}" ] && [ -n "${R2_ACCESS_KEY_ID:-}" ] && [ -n "${R2_SECRET_ACCESS_KEY:-}" ]; then
  USE_R2=1
  export AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" AWS_DEFAULT_REGION=auto
  export AWS_REQUEST_CHECKSUM_CALCULATION=when_required AWS_RESPONSE_CHECKSUM_VALIDATION=when_required  # R2 compatibility
  S3="aws s3 --endpoint-url https://$R2_ACCOUNT_ID.r2.cloudflarestorage.com"
fi
USE_DIR=""
[ -d "$(dirname "$BACKUP_DIR")" ] && mkdir -p "$BACKUP_DIR" && USE_DIR=1
[ -n "$USE_R2$USE_DIR" ] || { echo "Nenhum destino: monte um volume em $(dirname "$BACKUP_DIR") ou configure o R2."; exit 1; }
WORK=/tmp/backup
STEP="início"

alert() {
  [ -n "${RESEND_API_KEY:-}" ] && [ -n "${ALERT_EMAIL:-}" ] || return 0
  curl -sS -o /dev/null https://api.resend.com/emails -H "Authorization: Bearer $RESEND_API_KEY" -H "Content-Type: application/json" \
    -d "{\"from\":\"Mesa Digital <nao-responda@mesadig.com.br>\",\"to\":[\"$ALERT_EMAIL\"],\"subject\":\"Backup do banco FALHOU\",\"text\":\"O backup diário falhou na etapa: $STEP. Veja: fly logs -a mesa-digital-backup\"}" || true
}
trap 'status=$?; [ $status -eq 0 ] || { echo "FALHOU na etapa: $STEP"; alert; }' EXIT

rm -rf "$WORK" && mkdir -p "$WORK" && chown postgres "$WORK"
name="mesa-digital-$(date -u +%Y-%m-%d).dump.gpg"

STEP="cópia do banco (pg_dump)"
pg_dump "$BACKUP_DATABASE_URL" --schema=mesa --no-owner --no-privileges --enable-row-security --format=custom --file="$WORK/backup.dump"

STEP="restauração de prova"
su-exec postgres initdb -D "$WORK/pg" -U postgres --auth=trust >/dev/null
su-exec postgres pg_ctl -D "$WORK/pg" -o "-c listen_addresses='' -k $WORK" -w start >/dev/null
pg_restore --host="$WORK" --username=postgres --dbname=postgres --no-owner --no-privileges --exit-on-error "$WORK/backup.dump"
q() { psql --host="$WORK" --username=postgres --dbname=postgres -At -c "$1"; }
tenants=$(q "select count(*) from mesa.tenants")
echo "Restaurado com sucesso: $tenants estabelecimentos, $(q 'select count(*) from mesa.orders') pedidos, $(q 'select count(*) from mesa.products') produtos"
test "$tenants" -gt 0
su-exec postgres pg_ctl -D "$WORK/pg" -w stop >/dev/null

STEP="criptografia"
gpg --batch --yes --pinentry-mode loopback --passphrase "$BACKUP_PASSPHRASE" --symmetric --cipher-algo AES256 \
  --output "$WORK/$name" "$WORK/backup.dump"

cutoff=$(date -u -d "@$(( $(date +%s) - RETENTION_DAYS * 86400 ))" +%Y-%m-%d)
if [ -n "$USE_DIR" ]; then
  STEP="cópia no disco"
  cp "$WORK/$name" "$BACKUP_DIR/$name"
  echo "Guardado no disco: $BACKUP_DIR/$name ($(wc -c < "$WORK/$name") bytes)"
  for old in "$BACKUP_DIR"/mesa-digital-*.dump.gpg; do
    base=$(basename "$old")
    if echo "$base mesa-digital-$cutoff" | awk '{ exit !($1 < $2) }'; then
      rm -f "$old" && echo "Apagado do disco (mais de $RETENTION_DAYS dias): $base"
    fi
  done
  echo "Cópias no disco: $(ls "$BACKUP_DIR" | wc -l)"
fi
if [ -n "$USE_R2" ]; then
  STEP="envio para o R2"
  $S3 cp "$WORK/$name" "s3://$BUCKET/$name" --only-show-errors
  echo "Enviado ao R2: $name"
  STEP="limpeza dos backups antigos no R2"
  $S3 ls "s3://$BUCKET/" | awk -v c="mesa-digital-$cutoff" '$4 ~ /^mesa-digital-/ && $4 < c {print $4}' | while read -r old; do
    $S3 rm "s3://$BUCKET/$old" --only-show-errors && echo "Apagado do R2 (mais de $RETENTION_DAYS dias): $old"
  done
fi
rm -rf "$WORK"
echo "Backup concluído."
