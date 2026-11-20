"""
Caso de Uso: cambiar las barras de una inscripción (BE #912, 20 nov 2026).

Una jugadora invitada se quedaba en las barras por defecto aunque el campo no
las tuviera valoradas para ella, y nadie podía cambiárselas: la generación de
partidos se bloqueaba sin salida. Ahora las cambian el propio jugador y el
organizador (o un admin):

- Solo antes de empezar, y mientras el jugador no tenga partido ni partida
  generados: su hándicap de juego ya salió de esas barras.
- Solo barras valoradas para su género (o sin género) en alguno de los campos
  de la competición. Sin género en su perfil, basta con que el color exista.
- Sin barras (null) vuelve a las habituales de su género.
"""

from src.modules.competition.application.dto.enrollment_dto import (
    ChangeEnrollmentTeeRequestDTO,
    ChangeEnrollmentTeeResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    EnrollmentNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.use_cases.remove_enrolled_player_use_case import (
    PlayerHasMatchesError,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.golf_course.domain.services.stroke_context import StrokeContextBuilder
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender

# Se reexporta: la ruta lo traduce a su código (409)
__all__ = [
    "ChangeEnrollmentTeeUseCase",
    "EnrollmentNotApprovedError",
    "PlayerHasMatchesError",
    "TeeChangeClosedError",
    "TeeNotAvailableError",
]

# Antes de empezar: en juego las barras ya están en los partidos
_SE_PUEDEN_CAMBIAR = frozenset(
    {CompetitionStatus.DRAFT, CompetitionStatus.ACTIVE, CompetitionStatus.CLOSED}
)


class TeeNotAvailableError(Exception):
    """Ningún campo de la competición tiene esas barras valoradas para su género (C4)."""

    error_code = "TEE_NOT_AVAILABLE"


class TeeChangeClosedError(Exception):
    """La competición ya empezó, acabó o se canceló (C6)."""

    error_code = "TEE_CHANGE_CLOSED"


class EnrollmentNotApprovedError(Exception):
    """Solo se cambian las barras de una inscripción aprobada (C8)."""

    error_code = "ENROLLMENT_NOT_APPROVED"


class ChangeEnrollmentTeeUseCase:
    """El propio jugador o el organizador (o un admin) cambia las barras de una inscripción."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        golf_course_repository: IGolfCourseRepository,
        user_repository: UserRepositoryInterface,
    ):
        self._uow = uow
        self._campos = golf_course_repository
        self._usuarios = user_repository

    async def execute(
        self, request: ChangeEnrollmentTeeRequestDTO, quien: UserId, is_admin: bool = False
    ) -> ChangeEnrollmentTeeResponseDTO:
        """
        Cambia las barras.

        Args:
            request: La inscripción y sus barras nuevas (o None)
            quien: Quien lo pide
            is_admin: Si quien lo pide es administrador

        Raises:
            EnrollmentNotFoundError: Si la inscripción no existe
            CompetitionNotFoundError: Si su competición no existe
            NotCompetitionCreatorError: Si no es el jugador, el organizador ni un admin
            EnrollmentNotApprovedError: Si la inscripción no está aprobada
            TeeChangeClosedError: Si la competición ya empezó, acabó o se canceló
            PlayerHasMatchesError: Si el jugador ya tiene partido o partida generados
            TeeNotAvailableError: Si ningún campo tiene esas barras para su género
        """
        enrollment_id = EnrollmentId(request.enrollment_id)
        async with self._uow:
            enrollment = await self._uow.enrollments.find_by_id(enrollment_id)
            if enrollment is None:
                raise EnrollmentNotFoundError(f"Inscripción no encontrada: {enrollment_id}")

            # Con la competición bloqueada, como la baja y la generación: que no se
            # generen sus partidos entre la comprobación y el cambio
            competition = await self._uow.competitions.find_by_id_for_update(
                enrollment.competition_id
            )
            if competition is None:
                raise CompetitionNotFoundError(
                    f"Competición no encontrada: {enrollment.competition_id}"
                )
            enrollment = await self._uow.enrollments.find_by_id_for_update(enrollment_id)
            if enrollment is None:
                raise EnrollmentNotFoundError(f"Inscripción no encontrada: {enrollment_id}")

            es_suya = enrollment.user_id == quien
            if not (es_suya or is_admin or competition.is_creator(quien)):
                raise NotCompetitionCreatorError(
                    "Solo el jugador o el organizador cambian sus barras"
                )
            if not enrollment.is_approved():
                raise EnrollmentNotApprovedError("La inscripción no está aprobada")
            if competition.status not in _SE_PUEDEN_CAMBIAR:
                raise TeeChangeClosedError(
                    f"No se cambian barras en una competición {competition.status.value}"
                )
            if await self._tiene_partido(competition, enrollment.user_id):
                raise PlayerHasMatchesError("Ya tiene partido generado con sus barras")
            if request.tee_color is not None and not await self._la_tiene_algun_campo(
                competition, request.tee_color, enrollment.user_id
            ):
                raise TeeNotAvailableError(
                    f"Ningún campo de la competición tiene barras {request.tee_color.value} "
                    "valoradas para este jugador"
                )

            enrollment.set_tee_color(request.tee_color)
            await self._uow.enrollments.update(enrollment)

        return ChangeEnrollmentTeeResponseDTO(
            id=enrollment.id.value,
            competition_id=enrollment.competition_id.value,
            user_id=enrollment.user_id.value,
            tee_color=enrollment.tee_color.value if enrollment.tee_color else None,
            updated_at=enrollment.updated_at,
        )

    async def _tiene_partido(self, competition: Competition, user_id: UserId) -> bool:
        """Si ya tiene un partido de Ryder o una partida de stroke play generados (C7)."""
        if await self._uow.partidas.del_jugador(competition.id, user_id):
            return True
        rondas = await self._uow.rounds.find_by_competition(competition.id)
        if not rondas:
            return False
        return bool(
            await self._uow.matches.find_by_rounds_for_player([r.id for r in rondas], user_id)
        )

    async def _la_tiene_algun_campo(
        self, competition: Competition, color: TeeColor, user_id: UserId
    ) -> bool:
        """
        Si alguno de sus campos tiene esas barras valoradas para su género o sin
        género (C4). Sin género en el perfil, basta con que exista el color: el
        aviso de género lo verá el organizador al generar.
        """
        usuario = await self._usuarios.find_by_id(user_id)
        genero: Gender | None = usuario.gender if usuario else None
        for del_campo in competition.golf_courses:
            campo = await self._campos.find_by_id(del_campo.golf_course_id)
            if campo is None:
                continue
            valoradas = StrokeContextBuilder.build(campo).tee_ratings
            for barra, su_genero in valoradas:
                if barra != color.value:
                    continue
                if genero is None or su_genero is None or su_genero == genero.value:
                    return True
        return False
