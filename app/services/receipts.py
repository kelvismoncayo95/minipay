"""Comprobantes en PDF de transferencias y pagos (paso 11).

Se generan al momento (un PDF de una página tarda milisegundos), así no hay que
guardar archivos. Solo los puede bajar alguien que participó del movimiento.
"""

import io
import uuid
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A5
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.demo import TIMEZONE
from app.models import Account, LedgerEntry, LedgerTransaction, User
from app.services.ledger import dinero

TIPOS = {"transfer": ("TRF", "Comprobante de transferencia"), "payment": ("PAG", "Comprobante de pago")}


@dataclass
class Receipt:
    referencia: str
    titulo: str
    de: str
    para: str
    monto: str
    fecha: str
    transaction_id: str


def receipt_for(db: Session, transaction_id: uuid.UUID, user_id: uuid.UUID) -> Receipt | None:
    """Datos del comprobante, o None si no existe, no es transferencia/pago o el usuario no participó."""
    tx = db.get(LedgerTransaction, transaction_id)
    if tx is None or tx.kind not in TIPOS:
        return None
    filas = db.execute(
        select(LedgerEntry.amount, User.id, User.display_name)
        .join(Account, LedgerEntry.account_id == Account.id)
        .join(User, Account.user_id == User.id)
        .where(LedgerEntry.transaction_id == tx.id)
    ).all()
    if user_id not in {f.id for f in filas}:
        return None  # 404: no revelamos que existe
    origen = next(f for f in filas if f.amount < 0)
    destino = next(f for f in filas if f.amount > 0)
    prefijo, titulo = TIPOS[tx.kind]
    fecha = tx.created_at.astimezone(ZoneInfo(TIMEZONE)).strftime("%d/%m/%Y %H:%M (hora de Uruguay)")
    return Receipt(
        referencia=f"{prefijo}-{str(tx.id)[:8].upper()}",
        titulo=titulo,
        de=origen.display_name,
        para=destino.display_name,
        monto=dinero(destino.amount),
        fecha=fecha,
        transaction_id=str(tx.id),
    )


def render_pdf(r: Receipt) -> bytes:
    """Dibuja el comprobante (A5) con la identidad de minipay."""
    violeta, tinta, gris = HexColor("#5b3df5"), HexColor("#14112b"), HexColor("#6b6785")
    buffer = io.BytesIO()
    ancho, alto = A5
    c = canvas.Canvas(buffer, pagesize=A5)
    c.setTitle(f"minipay {r.referencia}")

    # Cabecera violeta
    c.setFillColor(tinta)
    c.rect(0, alto - 70, ancho, 70, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(30, alto - 45, "minipay")
    c.setFont("Helvetica", 9)
    c.drawRightString(ancho - 30, alto - 45, "Dinero de mentira · Demo pública")

    # Título y monto
    c.setFillColor(tinta)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(30, alto - 110, r.titulo)
    c.setFillColor(violeta)
    c.setFont("Helvetica-Bold", 30)
    c.drawString(30, alto - 150, r.monto)

    # Detalle
    y = alto - 195
    for etiqueta, valor in [
        ("Referencia", r.referencia),
        ("De", r.de),
        ("Para", r.para),
        ("Fecha", r.fecha),
        ("Estado", "Completada"),
    ]:
        c.setFillColor(gris)
        c.setFont("Helvetica", 10)
        c.drawString(30, y, etiqueta)
        c.setFillColor(tinta)
        c.setFont("Helvetica-Bold", 11)
        c.drawRightString(ancho - 30, y, valor)
        c.setStrokeColor(HexColor("#e5e2f2"))
        c.line(30, y - 8, ancho - 30, y - 8)
        y -= 30

    # Pie
    c.setFillColor(gris)
    c.setFont("Helvetica", 7)
    c.drawString(30, 50, f"ID del movimiento: {r.transaction_id}")
    c.drawString(30, 38, "Comprobante de una demo de portafolio. El dinero es de mentira y no tiene valor real.")
    c.showPage()
    c.save()
    return buffer.getvalue()
