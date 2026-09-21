"""
Refresh Own Handicap Use Case - Application Layer

Refresca desde la RFEG el hándicap del usuario autenticado (RyderCupAM#340).
"""

import logging
from datetime import UTC, datetime

from src.modules.user.application.dto.user_dto import (
    RefreshOwnHandicapRequestDTO,
    RefreshOwnHandicapResponseDTO,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.handicap_service import HandicapService
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)


class RefreshOwnHandicapUseCase:
    """
    Refresca el hándicap del propio usuario, una vez al día y solo en España.

    Vivía dentro del login (HM-2a), y el login esperaba a la RFEG antes de
    contestar: hasta 20 s cuando la federación iba lenta, y el 21 sep 2026 tardó
    un minuto. Ahora el frontend lo pide aparte, después de entrar, y el login
    contesta al momento. Las reglas son las mismas.

    La consulta a la RFEG se hace FUERA de la unidad de trabajo: puede tardar el
    timeout entero, y mientras tanto no tiene sentido tener una conexión a la BD
    ocupada para nada.
    """

    def __init__(self, uow: UserUnitOfWorkInterface, handicap_service: HandicapService):
        """
        Args:
            uow: Unit of Work para leer y guardar el usuario
            handicap_service: Servicio de hándicap de la RFEG
        """
        self._uow = uow
        self._handicap_service = handicap_service

    async def execute(
        self, request: RefreshOwnHandicapRequestDTO
    ) -> RefreshOwnHandicapResponseDTO | None:
        """
        Refresca el hándicap y dice si hay que pedírselo al jugador.

        Args:
            request: El id del usuario autenticado

        Returns:
            El resultado, o None si el usuario ya no existe
        """
        async with self._uow:
            user = await self._uow.users.find_by_id(UserId(request.user_id))
        if user is None:
            return None

        # UTC-aware: handicap_updated_at se guarda en UTC y la comparación de
        # fechas tiene que hacerse en el mismo huso
        ahora = datetime.now(UTC)
        actualizado_hoy = (
            user.handicap_updated_at is not None and user.handicap_updated_at.date() == ahora.date()
        )
        if actualizado_hoy:
            return self._resultado(user, needs_handicap=False)

        pais = user.country_code.value if user.country_code else None
        if pais != "ES":
            return self._resultado(user, needs_handicap=True)

        handicap_value = await self._consultar_rfeg(user)
        if handicap_value is None:
            return self._resultado(user, needs_handicap=True)

        try:
            user.update_handicap(handicap_value)
            async with self._uow:
                await self._uow.users.save(user)
        except Exception:
            logger.error(
                "Failed to persist RFEG handicap for %s",
                user.get_full_name(),
                exc_info=True,
            )
            # La entidad ya lleva el valor nuevo, pero no quedó guardado: devolverlo
            # sería afirmar algo que la BD no tiene
            return RefreshOwnHandicapResponseDTO(needs_handicap=True, handicap=None)

        return self._resultado(user, needs_handicap=False)

    async def _consultar_rfeg(self, user: User) -> float | None:
        """
        El hándicap según la RFEG, o None si no lo da.

        Que no lo encuentre y que no responda acaban igual —hay que pedírselo al
        jugador—, así que el fallo se registra y se trata como un None.
        """
        try:
            return await self._handicap_service.search_handicap(user.get_full_name())
        except Exception:
            logger.warning(
                "RFEG lookup failed for %s during handicap refresh",
                user.get_full_name(),
                exc_info=True,
            )
            return None

    @staticmethod
    def _resultado(user: User, *, needs_handicap: bool) -> RefreshOwnHandicapResponseDTO:
        return RefreshOwnHandicapResponseDTO(
            needs_handicap=needs_handicap,
            handicap=user.handicap.value if user.handicap else None,
        )
