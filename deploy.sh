#!/usr/bin/env bash
set -euo pipefail

VPS_USER="bart"
VPS_HOST="opennaturemaps.org"
VPS_PATH="/home/bart/opennaturemap"

ssh "${VPS_USER}@${VPS_HOST}" bash <<EOF
  set -euo pipefail
  cd "${VPS_PATH}"
  git pull
  docker compose -f docker-compose.prod.yml build
  docker compose -f docker-compose.prod.yml up -d
  docker compose -f docker-compose.prod.yml exec -T api python manage.py migrate --noinput
EOF
