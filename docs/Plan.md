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
| 8 | Límites | máximo por operación, límite diario, 5 cambios de saldo por hora (contados en la base, bajo el bloqueo) | ✅ 2026-11-11 |
| 9 | Comercios y cobros | la Clínica del Sur (demo) cobra a un usuario | ✅ 2026-11-11 |
| 10 | Cola en segundo plano | worker con Arq; conciliación "todo suma cero" cada 15 min | ✅ 2026-11-11 |
| 11 | Comprobantes PDF | comprobante de transferencias, pagos y reembolsos (ReportLab, al momento) | ✅ 2026-11-11 |
| 12 | Reembolsos (webhooks fuera) | reembolso total de un cobro pagado; webhooks descartados: el comercio demo no tiene servidor (diseño en el README) | ✅ 2026-11-11 |
| 13 | Frontend | HTML/CSS/JS vanilla, con aviso "dinero de mentira" | ✅ 2026-11-11 (adelantado) |
| 14 | Deploy | Render + Neon + Upstash con `render.yaml` (worker en el mismo contenedor) — https://minipay-kcxy.onrender.com | ✅ 2026-11-11 |
| 15 | CI | GitHub Actions: tests + gitleaks en cada push | ✅ 2026-11-11 |
| 16 | Panel admin y control | conciliación "todo suma cero" (automática y a pedido) | ✅ 2026-11-11 |
| 17 | Cierre de portafolio | README en inglés con demo en vivo, capturas y decisiones | ✅ 2026-11-11 |

**Orden cambiado el 2026-11-11 (pedido de Kelvis):** después del paso 10 se hace 13 → 14 → 15, y luego 11, 12, 16 y 17. Así se llega antes a una demo pública.

## Reglas de cada paso

- Rama `paso-N` desde `main`.
- Tests primero en lo importante (saldo, transferencias, idempotencia).
- `pytest -v` en verde antes de cada commit.
- Al cerrar: merge a `main` y actualizar la documentación.
