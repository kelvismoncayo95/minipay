# minipay

Billetera digital de dinero de juguete. Demo pública para demostrar que se puede construir un backend donde el dinero se mueve sin errores: nada se cobra dos veces, ningún saldo se descuadra, y todo movimiento queda registrado.

> Advertencia: dinero de mentira. Demo pública. No usar para nada real.

## Estado

En construcción. Pasos 0 a 7 completados: entorno, Docker Compose, esquema del libro contable con migraciones, datos demo, login, API de saldo y movimientos, transferencias seguras ante concurrencia, idempotencia, límites, cobros de comercios, worker en segundo plano y frontend web.

**Frontend:** `http://localhost:8000/` (HTML, CSS y JavaScript sin frameworks, servido por la misma API). Botones para entrar como cada usuario demo; pantallas para persona, comercio y admin; funciona en el celular.

**Conciliación automática:** un worker (Arq + Redis) suma todo el libro cada 15 minutos; tiene que dar exactamente 0. El admin la consulta en `GET /admin/reconciliation` o la corre en `POST /admin/reconciliation`.

**Límites de la demo:** saldo de $1 a $5.000; máximo $5.000 por transferencia; $10.000 enviados por día (UTC); 5 cambios de saldo por hora (429 si se supera).

| Endpoint | Qué hace |
|---|---|
| `POST /auth/login` | usuario + contraseña → token |
| `GET /auth/me` | quién soy |
| `GET /me/balance` | mi saldo (en centavos) |
| `PUT /me/balance` | elegir mi saldo de juguete ($1 a $5.000) |
| `POST /me/transfers` | mandarle dinero a otra persona |
| `GET /me/movements` | mis últimos 50 movimientos |
| `POST /merchant/charges` | (comercio) cobrarle a una persona |
| `GET /merchant/charges` | (comercio) mis cobros |
| `GET /me/charges` | cobros que me hicieron |
| `POST /me/charges/{id}/pay` | pagar un cobro (con `Idempotency-Key`) |
| `POST /me/charges/{id}/reject` | rechazar un cobro |

**Concurrencia:** dos transferencias simultáneas desde la misma cuenta no pueden dejarla en negativo. Cada transferencia bloquea las dos cuentas (`SELECT ... FOR UPDATE`, siempre en el mismo orden para evitar deadlocks). Hay un test que lanza dos hilos a la vez y que **falla si se quita el bloqueo** (comprobado).

**Idempotencia:** `POST /me/transfers` exige el header `Idempotency-Key` (un UUID nuevo por transferencia). Si el mismo pedido llega dos veces (doble click, reintento por mala señal), se cobra **una sola vez** y la segunda respuesta trae `Idempotent-Replayed: true`. Funciona también con los dos pedidos llegando al mismo tiempo (`INSERT ... ON CONFLICT DO NOTHING`).

```bash
curl -X POST localhost:8000/me/transfers \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(python3 -c 'import uuid; print(uuid.uuid4())')" \
  -d '{"to_username":"luis","amount_cents":10000}'
```

## Probar la demo

Usuarios: `ana`, `luis`, `marta`, `pedro`, `clinica-del-sur`, `admin`. Contraseña (pública, igual para todos): `demo1234`.

```bash
curl -X POST localhost:8000/auth/login -H "Content-Type: application/json" \
  -d '{"username":"ana","password":"demo1234"}'
```

La documentación interactiva de la API está en `http://localhost:8000/docs`. Ver [docs/Plan.md](docs/Plan.md).

## Cómo funciona el dinero

- **Libro de doble entrada:** cada movimiento tiene renglones que suman cero. El saldo se calcula, no se guarda.
- **Centavos en enteros** (`BIGINT`), nunca `float`.
- **Solo agregar:** los movimientos no se modifican ni se borran.

Detalle en [docs/BackendSchema.md](docs/BackendSchema.md).

## Cómo correrlo (local)

```bash
# 1. Clonar el repo
git clone <url-del-repo>
cd minipay

# 2. Crear y activar el entorno virtual
python3 -m venv venv
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements-dev.txt

# 4. Crear el .env con POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB,
#    DATABASE_URL y REDIS_URL (apuntando a localhost) y JWT_SECRET
#    (generarlo con: python3 -c "import secrets; print(secrets.token_urlsafe(48))")

# 5. Levantar la base y aplicar migraciones
docker compose up -d postgres
alembic upgrade head

# 6. Cargar los datos demo (se puede repetir sin duplicar)
python3 -m app.seed

# 7. Correr los tests (usan una base aparte: <nombre>_test)
pytest -v
```

Para levantar todo (api + base + redis): `docker compose up -d` y probar `curl http://localhost:8000/health`.

## Stack

- Python 3.12
- FastAPI
- PostgreSQL 17
- SQLAlchemy 2 + Alembic
- Redis
- Docker Compose
- pytest

## Documentación

- [docs/BackendSchema.md](docs/BackendSchema.md) — Base de datos y decisiones
- [docs/Plan.md](docs/Plan.md) — Los 17 pasos

## Licencia

Proyecto de demostración. Sin licencia definida todavía.
