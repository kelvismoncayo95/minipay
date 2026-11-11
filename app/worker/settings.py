"""Configuración del worker de Arq.

Arrancar: `arq app.worker.settings.WorkerSettings`
"""

from arq import cron
from arq.connections import RedisSettings

from app.core.config import settings
from app.worker.tasks import reconcile_ledger


class WorkerSettings:
    functions = [reconcile_ledger]
    # Cada 15 minutos, y una vez al arrancar.
    cron_jobs = [cron(reconcile_ledger, minute={0, 15, 30, 45}, run_at_startup=True)]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
