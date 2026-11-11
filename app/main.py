"""API de minipay: punto de entrada."""

from fastapi import FastAPI

from app.api import auth

app = FastAPI(
    title="minipay",
    description="Billetera digital de dinero de juguete. Demo pública.",
    version="0.1.0",
)

app.include_router(auth.router)


@app.get("/health")
def health() -> dict[str, str]:
    """Smoke test: la API está viva."""
    return {"status": "ok"}
