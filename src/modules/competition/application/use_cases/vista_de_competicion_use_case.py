"""
Vista de una competición: lo que devuelven las rutas tras escribir y la ficha.

Antes cada ruta, después de su caso de uso, volvía a leer la competición con el
repositorio y la pasaba por el mapper; la ficha además buscaba la invitación
pendiente de quien mira y hasta dónde ve los inscritos. Ahora se pide aquí, y la
ruta no toca la unidad de trabajo (fase 5 del plan de calidad).
"""

from datetime import datetime

from src.modules.competition.application.dto.competition_dto import (
    CompetitionResponseDTO,
    MyPendingInvitationDTO,
)
from src.modules.competition.application.exceptions import CompetitionNotFoundError
from src.modules.competition.application.mappers.competition_mapper import CompetitionDTOMapper
from src.modules.competition.application.services.invitacion_de_la_ficha import (
    invitacion_pendiente,
    se_le_ofrece_aceptar,
)
from src.modules.competition.application.services.quien_ve_los_inscritos import (
    VISIBILIDAD_DE_LOS_INSCRITOS,
    alcance_de,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class VistaDeCompeticionUseCase:
    """La competición como la ve quien la pide, leída en el momento."""

    def __init__(
        self, uow: CompetitionUnitOfWorkInterface, user_uow: UserUnitOfWorkInterface
    ) -> None:
        """
        Args:
            uow: Unidad de trabajo de competiciones.
            user_uow: La de usuarios, para los datos del creador.
        """
        self._uow = uow
        self._user_uow = user_uow

    async def de(
        self, competition_id: CompetitionId, quien: UserId, *, es_admin: bool = False
    ) -> CompetitionResponseDTO:
        """
        La competición con lo que depende de quien mira (si es su creador, su inscripción).

        Raises:
            CompetitionNotFoundError: Si no existe (también si se borró justo después
                de escribirla).
        """
        async with self._uow, self._user_uow:
            competition = await self._lee(competition_id)
            return await CompetitionDTOMapper.to_response_dto(
                competition, quien, self._uow, self._user_uow, is_admin=es_admin
            )

    async def ficha(
        self,
        competition_id: CompetitionId,
        quien: UserId,
        *,
        es_admin: bool = False,
        email: str | None = None,
    ) -> CompetitionResponseDTO:
        """
        Lo de `de`, más la invitación pendiente de quien mira y lo que ve de los inscritos.

        La invitación va solo si aceptarla puede salir bien (27 oct 2026). Lo que ve
        de los inscritos va para que la ficha no lo adivine comparando la lista con el
        número (/code-review del front); la invitación ya está leída, y quien organiza
        lo resuelve la regla antes.

        Raises:
            CompetitionNotFoundError: Si no existe.
        """
        async with self._uow, self._user_uow:
            competition = await self._lee(competition_id)
            dto = await CompetitionDTOMapper.to_response_dto(
                competition, quien, self._uow, self._user_uow, is_admin=es_admin
            )
            pendiente = await invitacion_pendiente(
                self._uow, competition, quien, email, datetime.now()
            )
            if pendiente is not None and se_le_ofrece_aceptar(
                competition, pendiente, inscrito=dto.user_enrollment_status is not None
            ):
                dto.my_pending_invitation = MyPendingInvitationDTO(
                    id=pendiente.id.value, expires_at=pendiente.expires_at
                )
            alcance = await alcance_de(
                self._uow,
                competition,
                quien,
                es_admin=es_admin,
                email=email,
                invitado=None if competition.is_creator(quien) else pendiente is not None,
            )
            dto.enrolled_visibility = VISIBILIDAD_DE_LOS_INSCRITOS[alcance]
            return dto

    async def _lee(self, competition_id: CompetitionId) -> Competition:
        """La competición, o CompetitionNotFoundError. Con el `uow` abierto."""
        competition = await self._uow.competitions.find_by_id(competition_id)
        if competition is None:
            raise CompetitionNotFoundError(f"No existe competición con ID {competition_id.value}")
        return competition
