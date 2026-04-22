#!/bin/sh
set -e

BACKUP_FILE="/backups/loggator-$(date +%Y%m%d-%H%M%S).sql.gz"

echo "Starting backup to $BACKUP_FILE ..."
PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
  -h postgres \
  -U "$POSTGRES_USER" \
  "$POSTGRES_DB" \
  | gzip > "$BACKUP_FILE"

echo "Pruning backups older than 7 days..."
find /backups -name '*.sql.gz' -mtime +7 -delete

echo "Backup completed: $BACKUP_FILE"
