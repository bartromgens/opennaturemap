#!/usr/bin/env bash
set -euo pipefail

LOCKFILE="/tmp/import_nature_reserves.lock"
COMPOSE_FILE="/home/bart/opennaturemap/docker-compose.prod.yml"
LOG_FILE="/home/bart/opennaturemap/logs/import_nature_reserves.log"

mkdir -p "$(dirname "$LOG_FILE")"
exec >> "$LOG_FILE" 2>&1

exec 9>"$LOCKFILE"
if ! flock -n 9; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') Import already running, skipping."
    exit 0
fi

echo "=== $(date '+%Y-%m-%d %H:%M:%S') Starting import ==="
docker compose -f "$COMPOSE_FILE" exec -T api \
    python manage.py import_nature_reserves --region world --resume
echo "=== $(date '+%Y-%m-%d %H:%M:%S') Import finished ==="
