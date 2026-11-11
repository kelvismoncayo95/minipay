"""Tests del frontend servido por la API (paso 13)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_la_pagina_principal_carga_con_el_aviso() -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Dinero de mentira" in r.text


def test_archivos_estaticos() -> None:
    assert client.get("/app.js").status_code == 200
    assert client.get("/styles.css").status_code == 200


def test_la_api_sigue_respondiendo() -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200


def test_respuestas_de_la_api_no_se_guardan_en_cache() -> None:
    # Si el navegador guarda /me/balance en caché, muestra un saldo viejo.
    r = client.get("/health")
    assert r.headers["cache-control"] == "no-store"
