"""
Purge Terms Acceptances Use Case - Application Layer

Elimina el historial de aceptaciones de las cuentas borradas hace más del
plazo de conservación (TERMS_ACCEPTANCE_RETENTION_YEARS).
"""

from src.modules.user.application.dto.user_dto import (
    PurgeTermsAcceptancesRequestDTO,
    PurgeTermsAcceptancesResponseDTO,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.terms_of_service import terms_acceptance_purge_cutoff


class PurgeTermsAcceptancesUseCase:
    """
    Borra las filas de cuentas borradas antes del corte de conservación.

    Las de cuentas que siguen existiendo no se tocan nunca. Lo ejecuta
    scripts/purge_terms_acceptances.py.
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        self._uow = uow

    async def execute(
        self, request: PurgeTermsAcceptancesRequestDTO
    ) -> PurgeTermsAcceptancesResponseDTO:
        """
        Purga con `request.now` como referencia.

        Returns:
            Cuántas filas se borraron y el corte aplicado
        """
        cutoff = terms_acceptance_purge_cutoff(request.now)
        async with self._uow:
            deleted = await self._uow.terms_acceptances.purge_deleted_before(cutoff)
        return PurgeTermsAcceptancesResponseDTO(deleted=deleted, cutoff=cutoff)
