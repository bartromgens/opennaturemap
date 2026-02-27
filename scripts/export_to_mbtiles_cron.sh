#!/usr/bin/env bash
set -euo pipefail

LOCKFILE="/tmp/export_to_mbtiles.lock"
COMPOSE_FILE="/home/bart/opennaturemap/docker-compose.prod.yml"
LOG_FILE="/home/bart/opennaturemap/logs/export_to_mbtiles.log"

mkdir -p "$(dirname "$LOG_FILE")"
exec >> "$LOG_FILE" 2>&1

exec 9>"$LOCKFILE"
if ! flock -n 9; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') Export already running, skipping."
    exit 0
fi

echo "=== $(date '+%Y-%m-%d %H:%M:%S') Starting mbtiles export ==="
docker compose -f "$COMPOSE_FILE" exec -T api \
    python manage.py export_to_mbtiles --force
echo "=== $(date '+%Y-%m-%d %H:%M:%S') Mbtiles export finished ==="

echo "=== $(date '+%Y-%m-%d %H:%M:%S') Restarting tileserver ==="
docker compose -f "$COMPOSE_FILE" restart tileserver
echo "=== $(date '+%Y-%m-%d %H:%M:%S') Tileserver restarted ==="
