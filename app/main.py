"""API de minipay: punto de entrada."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import accounts, admin, auth, charges

app = FastAPI(
    title="minipay",
    description="Billetera digital de dinero de juguete. Demo pública.",
    version="0.1.0",
)

app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(charges.merchant_router)
app.include_router(charges.payer_router)
app.include_router(admin.router)


@app.get("/health")
def health() -> dict[str, str]:
    """Smoke test: la API está viva."""
    return {"status": "ok"}


# Frontend (HTML/CSS/JS). Va AL FINAL: las rutas de la API de arriba tienen prioridad.
app.mount(
    "/",
    StaticFiles(directory=Path(__file__).parent / "static", html=True),
    name="frontend",
)
