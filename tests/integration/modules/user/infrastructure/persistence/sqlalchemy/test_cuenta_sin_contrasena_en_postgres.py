"""
Una cuenta sin contraseña (solo Google), leída de Postgres, no tiene contraseña.

El composite de SQLAlchemy construía `Password(hashed_value=None)` con la columna a NULL,
y `has_password` daba True: una cuenta solo-Google podía desvincular su único Google y
quedarse sin forma de entrar; la reautenticación decía «contraseña incorrecta» y vincular
pedía una contraseña que no existe (probador de la release, 8 nov 2026; 15 cuentas en PRO).
Los tests unitarios no lo veían: usan repositorios en memoria.

  C1 la cuenta creada con Google, guardada y leída: sin contraseña
  C2 la que pierde la contraseña al tomarla Google, guardada y leída: sin contraseña
  C3 la que tiene contraseña: la conserva y la comprueba
  C4 desvincular su único Google, leída de Postgres: se rechaza
"""

import pytest

from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _relee(db_session, usuario: User) -> User:
    repo = SQLAlchemyUserRepository(db_session)
    await repo.save(usuario)
    await db_session.commit()
    db_session.expunge_all()
    return await repo.find_by_id(usuario.id)


async def test_c1_a_google_only_account_has_no_password(db_session):
    cuenta = User.create_from_oauth(
        first_name="Ana", last_name="Google", email_str="ana_google@test.com", email_verified=True
    )

    leida = await _relee(db_session, cuenta)

    assert leida.password is None
    assert leida.has_password is False


async def test_c2_a_claimed_account_has_no_password_after_reading(db_session):
    cuenta = User.create(
        first_name="Bea",
        last_name="Toma",
        email_str="bea_toma@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    assert cuenta.claim_with_verified_oauth()

    leida = await _relee(db_session, cuenta)

    assert leida.has_password is False


async def test_c3_an_account_with_a_password_keeps_it(db_session):
    cuenta = User.create(
        first_name="Cris",
        last_name="Clave",
        email_str="cris_clave@test.com",
        plain_password="SecureP@ssw0rd123",
    )

    leida = await _relee(db_session, cuenta)

    assert leida.has_password is True
    assert leida.verify_password("SecureP@ssw0rd123")
