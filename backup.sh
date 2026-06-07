#!/usr/bin/env bash
set -euo pipefail

VPS_USER="bart"
VPS_HOST="opennaturemaps.org"
VPS_PATH="/home/bart/opennaturemap"
LOCAL_BACKUP_DIR="${HOME}/backup/opennaturemap"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="${VPS_PATH}/backups/${TIMESTAMP}"

SSH="ssh ${VPS_USER}@${VPS_HOST}"

echo "==> [1/3] Creating backup directory ${BACKUP_DIR}..."
$SSH "mkdir -p '${BACKUP_DIR}'"

echo "==> [2/3] Backing up PostgreSQL..."
$SSH "docker compose -f '${VPS_PATH}/docker-compose.prod.yml' exec -T db \
  pg_dump -U opennaturemap opennaturemap 2>/dev/null | gzip > '${BACKUP_DIR}/db.sql.gz'"

echo "==> [3/3] Removing backups older than 30 days..."
$SSH "find '${VPS_PATH}/backups' -maxdepth 1 -mindepth 1 -type d -mtime +30 -exec rm -rf {} +"

echo "==> Backup complete: ${BACKUP_DIR}"
$SSH "du -sh '${BACKUP_DIR}'/*"

echo "==> Syncing backup to local ${LOCAL_BACKUP_DIR}..."
mkdir -p "${LOCAL_BACKUP_DIR}"
rsync -av --progress \
  "${VPS_USER}@${VPS_HOST}:${BACKUP_DIR}/" \
  "${LOCAL_BACKUP_DIR}/${TIMESTAMP}/"

echo "==> Local backup saved to ${LOCAL_BACKUP_DIR}/${TIMESTAMP}/"
du -sh "${LOCAL_BACKUP_DIR}/${TIMESTAMP}/"*
