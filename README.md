# minipay

Billetera digital de dinero de juguete. Demo pública para demostrar que se puede construir un backend donde el dinero se mueve sin errores: nada se cobra dos veces, ningún saldo se descuadra, y todo movimiento queda registrado.

> Advertencia: dinero de mentira. Demo pública. No usar para nada real.

## Estado

En construcción. Paso 0 completado: entorno, .gitignore, README y test de humo.

## Cómo correrlo (local)

```bash
# 1. Clonar el repo
git clone <url-del-repo>
cd minipay

# 2. Crear y activar el entorno virtual
python3 -m venv venv
source venv/bin/activate

# 3. Instalar dependencias
pip install pytest

# 4. Correr los tests
pytest -v
```

## Stack

- Python 3.12
- FastAPI (a partir del paso 1)
- PostgreSQL 17 (a partir del paso 1)
- Redis (a partir del paso 1)
- Docker Compose (a partir del paso 1)
- pytest

## Documentación

Los documentos de diseño están en `docs/`:

- `PRD.md` — Qué es y para qué existe
- `TRD.md` — Diseño técnico
- `AppFlow.md` — Cómo navega el usuario
- `UXUI.md` — Pantallas y mensajes
- `BackendSchema.md` — Base de datos
- `Plan.md` — Los 17 pasos

## Licencia

Proyecto de demostración. Sin licencia definida todavía.
