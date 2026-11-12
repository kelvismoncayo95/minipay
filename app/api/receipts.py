"""Endpoint del comprobante en PDF."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models import User
from app.services.receipts import receipt_for, render_pdf

router = APIRouter(prefix="/me", tags=["comprobantes"])


@router.get("/receipts/{transaction_id}", response_class=Response)
def receipt(
    transaction_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """PDF de una transferencia o pago en el que participé (si no, 404)."""
    datos = receipt_for(db, transaction_id, user.id)
    if datos is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comprobante no encontrado.")
    return Response(
        render_pdf(datos),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="minipay-{datos.referencia}.pdf"'},
    )
