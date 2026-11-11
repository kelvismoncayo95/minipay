"""Reglas de la demo pública (decididas por el autor el 2026-11-11).

Hay un fondo FIJO que circula entre las personas. Todos los días a las 3:00
(hora de Uruguay) la demo vuelve a empezar: cada cuenta vuelve a su saldo inicial.
Montos en centavos de dólar.
"""

CURRENCY = "USD"
TIMEZONE = "America/Montevideo"
RESET_HOUR = 3  # 3:00 hora de Uruguay

# Saldo con el que arranca cada cuenta todos los días. Total: US$10.000.
INITIAL_BALANCES = {
    "ana": 250_000,  # US$2.500
    "luis": 250_000,
    "marta": 250_000,
    "pedro": 250_000,
    "clinica-del-sur": 0,
}
TOTAL_POOL = sum(INITIAL_BALANCES.values())

MAX_TRANSFER = 50_000  # US$500 por operación
DAILY_TRANSFER_LIMIT = 100_000  # US$1.000 enviados por día de demo
