# Daily backup job for the production database: runs as a scheduled Fly Machine (app "mesa-digital-backup").
# Has the PostgreSQL 17 server too, so every run can prove the dump restores. Setup: DEPLOY.md, "Backup e restauração".
FROM postgres:17-alpine
RUN apk add --no-cache gnupg aws-cli curl su-exec
COPY backup.sh /usr/local/bin/backup.sh
ENTRYPOINT ["/bin/sh", "/usr/local/bin/backup.sh"]
