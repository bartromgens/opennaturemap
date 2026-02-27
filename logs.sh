#!/usr/bin/env bash
set -euo pipefail

VPS_USER="bart"
VPS_HOST="opennaturemaps.org"
VPS_PATH="/home/bart/opennaturemap"

ssh -t "${VPS_USER}@${VPS_HOST}" \
  "cd '${VPS_PATH}' && docker compose -f docker-compose.prod.yml logs -f api"
