"""
La purga del historial de aceptaciones de cuentas borradas (decisión de Agustín).

Las filas de una cuenta borrada se conservan TERMS_ACCEPTANCE_RETENTION_YEARS
desde el borrado; después la purga las elimina. Las de cuentas vivas, nunca.
"""

from datetime import UTC, datetime

import pytest

from src.modules.user.application.dto.user_dto import PurgeTermsAcceptancesRequestDTO
from src.modules.user.application.use_cases.purge_terms_acceptances_use_case import (
    PurgeTermsAcceptancesUseCase,
)
from src.modules.user.domain.entities.terms_acceptance import TermsAcceptance
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio

AHORA = datetime(2029, 10, 20, 12, tzinfo=UTC)


def _fila(email: str, borrada: datetime | None = None) -> TermsAcceptance:
    fila = TermsAcceptance.record(
        user_id=UserId.generate(),
        user_email=email,
        terms_version="2026-10-20",
        accepted_at=datetime(2026, 1, 1, tzinfo=UTC),
        ip_address=None,
        user_agent=None,
    )
    if borrada is not None:
        fila.detach_from_deleted_user(borrada)
    return fila


async def test_purge_deletes_only_rows_of_accounts_deleted_over_three_years_ago():
    """
    Given: Una fila de una cuenta borrada hace más de 3 años, otra borrada hace
        1 año, otra borrada justo en el corte y otra de una cuenta viva antigua
    When: Se purga el 20 oct 2029
    Then: Solo se va la primera; la respuesta dice cuántas y el corte
    """
    uow = InMemoryUnitOfWork()
    vieja = _fila("vieja@example.com", datetime(2026, 10, 1, tzinfo=UTC))
    reciente = _fila("reciente@example.com", datetime(2028, 10, 20, tzinfo=UTC))
    en_el_corte = _fila("corte@example.com", datetime(2026, 10, 20, 12, tzinfo=UTC))
    viva = _fila("viva@example.com")
    async with uow:
        for fila in (vieja, reciente, en_el_corte, viva):
            await uow.terms_acceptances.save(fila)

    respuesta = await PurgeTermsAcceptancesUseCase(uow).execute(
        PurgeTermsAcceptancesRequestDTO(now=AHORA)
    )

    assert respuesta.deleted == 1
    assert respuesta.cutoff == datetime(2026, 10, 20, 12, tzinfo=UTC)
    quedan = {fila.user_email for fila in uow.terms_acceptances.all_rows()}
    assert quedan == {"reciente@example.com", "corte@example.com", "viva@example.com"}


async def test_purge_with_nothing_to_delete_returns_zero():
    """
    Given: Un historial sin cuentas borradas
    When: Se purga
    Then: Cero, y no se toca nada
    """
    uow = InMemoryUnitOfWork()
    async with uow:
        await uow.terms_acceptances.save(_fila("viva@example.com"))

    respuesta = await PurgeTermsAcceptancesUseCase(uow).execute(
        PurgeTermsAcceptancesRequestDTO(now=AHORA)
    )

    assert respuesta.deleted == 0
    assert len(uow.terms_acceptances.all_rows()) == 1


async def test_purge_requires_a_utc_now():
    """
    Given: Un "ahora" sin zona horaria
    When: Se construye la petición
    Then: Error de validación
    """
    with pytest.raises(ValueError):
        PurgeTermsAcceptancesRequestDTO(now=datetime(2029, 10, 20))
