"""Datos demo: Banco de juguete, 4 usuarios, la Clínica y el admin.

Se puede correr muchas veces: lo que ya existe no se duplica (idempotente).
Uso: python3 -m app.seed
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Account, User
from app.services.auth import hash_password
from app.services.daily_reset import ensure_daily_reset

# Contraseña PÚBLICA de la demo (a propósito). Es la misma para todos los usuarios demo.
DEMO_PASSWORD = "demo1234"

# (username, display_name, role)
DEMO_USERS = [
    ("ana", "Ana", "user"),
    ("luis", "Luis", "user"),
    ("marta", "Marta", "user"),
    ("pedro", "Pedro", "user"),
    ("clinica-del-sur", "Clínica del Sur (demo)", "merchant"),
    ("admin", "Administrador", "admin"),
]

# Roles que manejan dinero y por eso tienen cuenta.
ROLES_CON_CUENTA = {"user", "merchant"}


def seed_demo(db: Session) -> None:
    """Crea lo que falte de los datos demo. No hace commit."""
    if db.scalars(select(Account).where(Account.kind == "system")).first() is None:
        db.add(Account(kind="system"))

    for username, display_name, role in DEMO_USERS:
        user = db.scalars(select(User).where(User.username == username)).first()
        if user is None:
            user = User(username=username, display_name=display_name, role=role)
            db.add(user)
            db.flush()

        if user.password_hash is None:
            user.password_hash = hash_password(DEMO_PASSWORD)

        if role in ROLES_CON_CUENTA:
            tiene_cuenta = db.scalars(
                select(Account).where(Account.user_id == user.id)
            ).first()
            if tiene_cuenta is None:
                db.add(Account(kind="user", user_id=user.id))

    db.flush()


def main() -> None:
    with SessionLocal() as db:
        seed_demo(db)
        db.commit()
        # Primer arranque (o servidor que estuvo apagado): deja el día de demo listo.
        if ensure_daily_reset(db):
            db.commit()
            print("Reinicio diario aplicado.")
    print("Datos demo listos.")


if __name__ == "__main__":
    main()
