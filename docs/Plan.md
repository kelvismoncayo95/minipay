# Plan — minipay

> Los 17 pasos para construir minipay. Cada paso: rama propia, tests en verde, merge a `main`.
> **Borrador escrito el 2026-11-11.** Se ajusta cuando un paso lo pida.

| # | Paso | Qué se construye | Estado |
|---|---|---|---|
| 0 | Entorno | venv, `.gitignore`, README, test de humo | ✅ 2026-11-09 |
| 1 | Docker Compose | api + PostgreSQL + Redis, `GET /health` | ✅ 2026-11-10 |
| 2 | Esquema del libro | 4 tablas, modelos, Alembic, tests de constraints | ✅ 2026-11-11 |
| 3 | Datos demo y saldo | usuarios demo + Banco de juguete; servicio para calcular y elegir saldo | ✅ 2026-11-11 |
| 4 | Login | `password_hash`, contraseña demo, token de sesión | ✅ 2026-11-11 |
| 5 | API de saldo y movimientos | endpoints para ver saldo, elegir saldo e historial | ✅ 2026-11-11 |
| 6 | Transferencias | Ana → Luis, con bloqueo de filas (sin saldos negativos con concurrencia) | ✅ 2026-11-11 |
| 7 | Idempotencia | la misma operación enviada dos veces se cobra una sola vez | ✅ 2026-11-11 |
| 8 | Límites | máximo por operación, límite diario, 5 cambios de saldo por hora (Redis) | ⏳ |
| 9 | Comercios y cobros | la Clínica del Sur (demo) cobra a un usuario | |
| 10 | Cola en segundo plano | worker con Arq para tareas lentas | |
| 11 | Comprobantes PDF | comprobante de cada movimiento (ReportLab) | |
| 12 | Webhooks y reembolsos | aviso al comercio; reembolso total de un cobro | |
| 13 | Frontend | HTML/CSS/JS vanilla, con aviso "dinero de mentira" | |
| 14 | Deploy | demo pública en internet | |
| 15 | CI | GitHub Actions: tests en cada push | |
| 16 | Panel admin y control | el admin ve todo; verificación "todas las cuentas suman cero" | |
| 17 | Cierre de portafolio | README final, capturas, decisiones explicadas | |

## Reglas de cada paso

- Rama `paso-N` desde `main`.
- Tests primero en lo importante (saldo, transferencias, idempotencia).
- `pytest -v` en verde antes de cada commit.
- Al cerrar: merge a `main` y actualizar la documentación.
