"""Historial de aceptaciones de los Términos en memoria, para los tests."""

from src.modules.user.domain.entities.terms_acceptance import TermsAcceptance
from src.modules.user.domain.repositories.terms_acceptance_repository_interface import (
    TermsAcceptanceRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class InMemoryTermsAcceptanceRepository(TermsAcceptanceRepositoryInterface):
    """Guarda las filas en una lista, en orden de llegada."""

    def __init__(self) -> None:
        self._rows: list[TermsAcceptance] = []

    async def save(self, acceptance: TermsAcceptance) -> None:
        self._rows.append(acceptance)

    async def find_by_user_id(self, user_id: UserId) -> list[TermsAcceptance]:
        filas = [row for row in self._rows if row.user_id == user_id]
        return sorted(filas, key=lambda row: row.accepted_at)
