# minipay

Billetera digital de dinero de juguete. Demo pública para demostrar que se puede construir un backend donde el dinero se mueve sin errores: nada se cobra dos veces, ningún saldo se descuadra, y todo movimiento queda registrado.

> Advertencia: dinero de mentira. Demo pública. No usar para nada real.

## Estado

En construcción. Pasos 0 a 3 completados: entorno, Docker Compose, esquema del libro contable con migraciones, datos demo y servicio de saldo. Ver [docs/Plan.md](docs/Plan.md).

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
#    DATABASE_URL y REDIS_URL (apuntando a localhost)

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
