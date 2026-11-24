#!/usr/bin/env bash
# Database backup: a compressed pg_dump, keeping the newest N copies. Run it from cron, e.g. every night at 02:00:
#   0 2 * * *  DATABASE_URL=postgresql://... /path/to/scripts/backup.sh >> /var/log/upstep-backup.log 2>&1
# Supabase also makes its own daily backups on paid plans; keep one of yours somewhere else too (another cloud, an external disk).
set -euo pipefail
: "${DATABASE_URL:?Set DATABASE_URL}"
DIR="${BACKUP_DIR:-$(dirname "$0")/../backups}"
KEEP="${BACKUP_KEEP:-14}"
mkdir -p "$DIR"
FILE="$DIR/upstep-$(date +%Y%m%d-%H%M%S).sql.gz"
pg_dump --no-owner --no-privileges "$DATABASE_URL" | gzip -9 > "$FILE"
[ -s "$FILE" ] || { echo "Backup is empty, something went wrong" >&2; rm -f "$FILE"; exit 1; }
ls -1t "$DIR"/upstep-*.sql.gz | tail -n +$((KEEP + 1)) | xargs -r rm -f
echo "Backup written: $FILE ($(du -h "$FILE" | cut -f1)); keeping the newest $KEEP"
# Restore into an EMPTY database:  gunzip -c backups/upstep-XXXX.sql.gz | psql "$DATABASE_URL"
