"""Historial de aceptaciones de los Términos en memoria, para los tests."""

from datetime import datetime

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
        # Como el UNIQUE(user_id, terms_version) de la base de datos
        if any(
            row.user_id is not None
            and row.user_id == acceptance.user_id
            and row.terms_version == acceptance.terms_version
            for row in self._rows
        ):
            raise ValueError("duplicate terms acceptance (user_id, terms_version)")
        self._rows.append(acceptance)

    async def has_accepted(self, user_id: UserId, terms_version: str) -> bool:
        return any(
            row.user_id == user_id and row.terms_version == terms_version for row in self._rows
        )

    async def find_by_user_id(self, user_id: UserId) -> list[TermsAcceptance]:
        filas = [row for row in self._rows if row.user_id == user_id]
        return sorted(filas, key=lambda row: row.accepted_at)

    async def detach_deleted_user(self, user_id: UserId, deleted_at: datetime) -> int:
        filas = [row for row in self._rows if row.user_id == user_id]
        for row in filas:
            row.detach_from_deleted_user(deleted_at)
        return len(filas)

    async def purge_deleted_before(self, cutoff: datetime) -> int:
        antes = len(self._rows)
        self._rows = [
            row
            for row in self._rows
            if row.user_deleted_at is None or row.user_deleted_at >= cutoff
        ]
        return antes - len(self._rows)

    def all_rows(self) -> list[TermsAcceptance]:
        """Todas las filas, para los tests."""
        return list(self._rows)
