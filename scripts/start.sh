#!/bin/sh
# Arranque en producción (y en el compose): migraciones → datos demo → (worker) → API.
set -e
alembic upgrade head
python -m app.seed

# En Render gratis no hay "background workers": si RUN_WORKER=true, el worker de Arq
# corre en el MISMO contenedor, en segundo plano. En local (compose) el worker es otro servicio.
if [ "${RUN_WORKER:-false}" = "true" ]; then
  arq app.worker.settings.WorkerSettings &
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
