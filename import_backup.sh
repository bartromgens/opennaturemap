#!/usr/bin/env bash
set -euo pipefail

SKIP_IMPORT=false
BACKUP_FILE="${HOME}/backup/opennaturemap/20260607_103742/db.sql.gz"

for arg in "$@"; do
    case "${arg}" in
        --skip-import) SKIP_IMPORT=true ;;
        *) BACKUP_FILE="${arg}" ;;
    esac
done

CONTAINER="onm_import_db"
PG_USER="opennaturemap"
PG_DB="opennaturemap"
SQLITE_FILE="$(cd "$(dirname "$0")" && pwd)/db.sqlite3"
VENV="$(cd "$(dirname "$0")" && pwd)/env"

cleanup() {
    local exit_code=$?
    if [[ "${exit_code}" -eq 0 ]]; then
        echo "==> Cleaning up Postgres container..."
        docker rm -f "${CONTAINER}" 2>/dev/null || true
    else
        echo "==> Left container '${CONTAINER}' running. Resume with: ./import_backup.sh --skip-import" >&2
    fi
    exit "${exit_code}"
}
trap cleanup EXIT

on_error() {
    echo "ERROR: script failed at line ${1}" >&2
}
trap 'on_error ${LINENO}' ERR

# ---------------------------------------------------------------------------
if [[ "${SKIP_IMPORT}" == "false" ]]; then
    echo "==> [1/4] Starting temporary Postgres container..."
    docker run -d \
        --name "${CONTAINER}" \
        -e POSTGRES_DB="${PG_DB}" \
        -e POSTGRES_USER="${PG_USER}" \
        -e POSTGRES_HOST_AUTH_METHOD=trust \
        -p 127.0.0.1:5432:5432 \
        postgres:16-alpine

    echo "==> Waiting for Postgres to be ready..."
    until docker exec "${CONTAINER}" psql -U "${PG_USER}" -d "${PG_DB}" -c '\q' 2>/dev/null; do
        sleep 1
    done

    echo "==> [2/4] Importing backup: ${BACKUP_FILE}..."
    gunzip -c "${BACKUP_FILE}" \
        | docker exec -i "${CONTAINER}" psql -U "${PG_USER}" "${PG_DB}"
else
    echo "==> [1-2/4] Skipping import, using existing container '${CONTAINER}'."
fi

# ---------------------------------------------------------------------------
echo "==> [3/4] Converting Postgres -> SQLite with db-to-sqlite..."
source "${VENV}/bin/activate"
rm -f "${SQLITE_FILE}"
db-to-sqlite "postgresql://${PG_USER}@127.0.0.1/${PG_DB}" "${SQLITE_FILE}" --all

# ---------------------------------------------------------------------------
echo "==> [4/4] Running Django migrations on SQLite..."
python manage.py migrate

# ---------------------------------------------------------------------------
echo "==> Done. SQLite database written to: ${SQLITE_FILE}"
