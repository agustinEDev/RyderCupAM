"""
El historial de aceptaciones de los Términos contra PostgreSQL.

UNIQUE(user_id, terms_version), la desvinculación al borrar la cuenta (la fila
sobrevive con su email y la fecha de borrado) y la purga a los 3 años.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from scripts.purge_terms_acceptances import purgar
from src.modules.user.domain.entities.terms_acceptance import TermsAcceptance
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.sqlalchemy.terms_acceptance_repository import (
    SQLAlchemyTermsAcceptanceRepository,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)

pytestmark = pytest.mark.integration


async def _usuario(db_session, email: str) -> User:
    user = User.create(
        first_name="Ana", last_name="Lopez", email_str=email, plain_password="ValidPassword123!"
    )
    await SQLAlchemyUserRepository(db_session).save(user)
    await db_session.commit()
    return user


def _fila(user: User, version: str = "2026-10-20") -> TermsAcceptance:
    return TermsAcceptance.record(
        user_id=user.id,
        user_email=user.email.value,
        terms_version=version,
        accepted_at=datetime(2026, 10, 20, tzinfo=UTC),
        ip_address="203.0.113.7",
        user_agent="Mozilla/5.0 Safari",
    )


async def _filas(db_session) -> list[tuple]:
    resultado = await db_session.execute(
        text(
            "SELECT user_id, user_email, terms_version, user_deleted_at "
            "FROM terms_acceptances ORDER BY user_email"
        )
    )
    return [tuple(fila) for fila in resultado.all()]


async def test_the_database_refuses_two_rows_of_the_same_version(db_session):
    """
    Given: Una aceptación de un usuario para una versión
    When: Se intenta guardar otra de la misma versión para el mismo usuario
    Then: La base de datos la rechaza (UNIQUE user_id, terms_version)
    """
    user = await _usuario(db_session, "unica@example.com")
    repo = SQLAlchemyTermsAcceptanceRepository(db_session)
    await repo.save(_fila(user))
    await db_session.commit()

    await repo.save(_fila(user))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_two_versions_of_the_same_user_are_allowed(db_session):
    """
    Given: Un usuario con una aceptación
    When: Acepta otra versión
    Then: Las dos filas conviven
    """
    user = await _usuario(db_session, "dos@example.com")
    repo = SQLAlchemyTermsAcceptanceRepository(db_session)
    await repo.save(_fila(user, "2026-10-20"))
    await repo.save(_fila(user, "2027-01-01"))
    await db_session.commit()

    assert [fila[2] for fila in await _filas(db_session)] == ["2026-10-20", "2027-01-01"]


async def test_deleting_the_user_keeps_its_rows_stamped(db_session):
    """
    Given: Un usuario con una aceptación y otro usuario vivo con la suya
    When: Se borra el primero con el repositorio (como el borrado del admin)
    Then: Su fila sigue, sin usuario, con su email y la fecha de borrado que
        pone la base de datos; la del otro, intacta
    """
    borrado = await _usuario(db_session, "borrado@example.com")
    vivo = await _usuario(db_session, "vivo@example.com")
    repo = SQLAlchemyTermsAcceptanceRepository(db_session)
    await repo.save(_fila(borrado))
    await repo.save(_fila(vivo))
    await db_session.commit()
    antes = (await db_session.execute(text("SELECT now()"))).scalar_one()
    await db_session.commit()

    await SQLAlchemyUserRepository(db_session).delete_by_id(borrado.id)
    await db_session.commit()

    filas = await _filas(db_session)
    assert filas[0][:3] == (None, "borrado@example.com", "2026-10-20")
    assert filas[0][3] is not None
    assert filas[0][3] >= antes
    assert filas[1][1:] == ("vivo@example.com", "2026-10-20", None)
    assert filas[1][0] is not None


async def test_deleting_a_user_with_plain_sql_still_stamps_the_rows(db_session):
    """
    Given: Una aceptación de un usuario
    When: Se borra la cuenta con un DELETE directo, sin pasar por la app
    Then: La fila no se pierde: queda sin usuario y con user_deleted_at relleno
    """
    user = await _usuario(db_session, "directo@example.com")
    await SQLAlchemyTermsAcceptanceRepository(db_session).save(_fila(user))
    await db_session.commit()

    await db_session.execute(text("DELETE FROM users WHERE email = 'directo@example.com'"))
    await db_session.commit()

    filas = await _filas(db_session)
    assert len(filas) == 1
    assert filas[0][:3] == (None, "directo@example.com", "2026-10-20")
    assert filas[0][3] is not None


async def _borrada_el(db_session, user: User, cuando: datetime) -> None:
    """Borra la cuenta y fecha su borrado en `cuando` (para simular el paso del tiempo)."""
    await SQLAlchemyUserRepository(db_session).delete_by_id(user.id)
    await db_session.commit()
    await db_session.execute(
        text("UPDATE terms_acceptances SET user_deleted_at = :cuando WHERE user_email = :email"),
        {"cuando": cuando, "email": user.email.value},
    )
    await db_session.commit()


async def test_purge_script_deletes_only_rows_deleted_over_three_years_ago(db_session):
    """
    Given: Una cuenta borrada hace más de 3 años, otra hace 1 año, otra justo
        en el corte y una viva
    When: Se ejecuta la purga del script el 20 oct 2029 a las 12:00
    Then: Solo se va la fila de la primera
    """
    vieja = await _usuario(db_session, "vieja@example.com")
    reciente = await _usuario(db_session, "reciente@example.com")
    en_el_corte = await _usuario(db_session, "corte@example.com")
    viva = await _usuario(db_session, "viva@example.com")
    repo = SQLAlchemyTermsAcceptanceRepository(db_session)
    for user in (vieja, reciente, en_el_corte, viva):
        await repo.save(_fila(user))
    await db_session.commit()
    await _borrada_el(db_session, vieja, datetime(2026, 10, 1, tzinfo=UTC))
    await _borrada_el(db_session, reciente, datetime(2028, 10, 20, tzinfo=UTC))
    await _borrada_el(db_session, en_el_corte, datetime(2026, 10, 20, 12, tzinfo=UTC))

    respuesta = await purgar(
        lambda: _MismaSesion(db_session), datetime(2029, 10, 20, 12, tzinfo=UTC)
    )

    assert respuesta.deleted == 1
    emails = [fila[1] for fila in await _filas(db_session)]
    assert emails == ["corte@example.com", "reciente@example.com", "viva@example.com"]


class _MismaSesion:
    """Hace pasar la sesión del test por la fábrica de sesiones del script."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *_):
        return False
