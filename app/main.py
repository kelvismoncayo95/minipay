"""API de minipay: punto de entrada. Solo /health por ahora."""

from fastapi import FastAPI


app = FastAPI(
    title="minipay",
    description="Billetera digital de dinero de juguete. Demo pública.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Smoke test: la API está viva."""
    return {"status": "ok"}
