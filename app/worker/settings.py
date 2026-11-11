"""Configuración del worker de Arq.

Arrancar: `arq app.worker.settings.WorkerSettings`
"""

from arq import cron
from arq.connections import RedisSettings

from app.core.config import settings
from app.worker.tasks import daily_reset, reconcile_ledger


class WorkerSettings:
    functions = [reconcile_ledger, daily_reset]
    cron_jobs = [
        # Conciliación cada 15 minutos (y al arrancar).
        cron(reconcile_ledger, minute={0, 15, 30, 45}, run_at_startup=True),
        # Reinicio diario: se revisa cada 15 minutos; solo reinicia una vez por día de demo
        # (a partir de las 3:00 de Uruguay). Así no depende de la zona horaria del servidor.
        cron(daily_reset, minute={1, 16, 31, 46}, run_at_startup=True),
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
