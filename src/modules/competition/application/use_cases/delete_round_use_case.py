"""Caso de Uso: Eliminar Ronda/Sesión de competición."""

from datetime import UTC, datetime

from src.modules.competition.application.dto.round_match_dto import (
    DeleteRoundRequestDTO,
    DeleteRoundResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
    RoundNotFoundError,
    RoundNotModifiableError,
)
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.application.services.franjas import (
    comprobar_agenda,
    comprobar_que_esta_vacia,
)
from src.modules.competition.application.services.lo_jugado import LoJugado
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


class DeleteRoundUseCase:
    """
    Caso de uso para eliminar una ronda de competición.

    Elimina la ronda y todos sus partidos en cascada.

    Restricciones:
    - La ronda debe existir
    - Solo el creador puede eliminar
    - La competición no puede haber terminado ni estar cancelada (BE #365)
    - La ronda debe estar en estado modificable (PENDING_TEAMS/PENDING_MATCHES)
    """

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        actividad: CompetitionActivityPublisherInterface | None = None,
    ):
        """`actividad` olvida lo que Actividad guardaba de la ronda; sin el, nada."""
        self._uow = uow
        self._actividad = AvisosDeActividad(actividad)

    async def execute(
        self, request: DeleteRoundRequestDTO, user_id: UserId, is_admin: bool = False
    ) -> DeleteRoundResponseDTO:
        async with self._uow:
            # 1. Buscar la ronda
            round_id = RoundId(request.round_id)
            round_entity = await self._uow.rounds.find_by_id(round_id)

            if not round_entity:
                raise RoundNotFoundError(f"No existe ronda con ID {request.round_id}")

            # 2. Buscar la competición
            # Bloqueada, como al generar partidos: comprobar que la sesión no
            # tiene partidos y tocarla tiene que ser una sola cosa
            competition = await self._uow.competitions.find_by_id_for_update(
                round_entity.competition_id
            )

            if not competition:
                raise CompetitionNotFoundError("La competición asociada no existe")

            # Releída tras el bloqueo: si mientras se esperaba otra petición
            # generó sus partidos, se decide con eso y no con lo de antes
            round_entity = await self._uow.rounds.find_by_id_for_update(round_id) or round_entity

            # 3. Verificar creador
            if not is_admin and not competition.is_creator(user_id):
                raise NotCompetitionCreatorError("Solo el creador puede eliminar rondas")

            # La agenda se edita desde que la competición existe (BE #365): lo
            # que se protege es la sesión ya jugada, y eso lo mira la sesión. Las
            # franjas de un stroke play, hasta iniciar (#251)
            comprobar_agenda(competition)

            # 5. Verificar ronda modificable
            if not round_entity.can_modify():
                raise RoundNotModifiableError(
                    f"No se puede eliminar la ronda en estado {round_entity.status.value}. "
                    f"Solo PENDING_TEAMS o PENDING_MATCHES"
                )

            # 5b. Una franja con gente dentro no se borra: perderían su sitio (#251).
            #     Antes de tocar nada
            await comprobar_que_esta_vacia(self._uow, round_entity)

            # 5c. Con un golpe apuntado en sus partidas, lo jugado se queda (#251,
            #     PR 5). Bloqueando, como al borrar la competición: entre
            #     preguntar y borrar cabe un golpe
            if await LoJugado(self._uow).en_la_sesion(round_id, bloquear=True):
                raise RoundNotModifiableError("No se puede eliminar una franja ya jugada")

            # 5d. Sus partidas se van con ella: en memoria no hay cascada
            await self._uow.partidas.borrar(await self._uow.partidas.de_la_franja(round_id))

            # 6. Eliminar partidos asociados en cascada
            matches = await self._uow.matches.find_by_round(round_id)
            matches_deleted = 0
            for match in matches:
                await self._uow.matches.delete(match.id)
                matches_deleted += 1

            # 6b. Quien entró esperando en ella y no tiene nada más, sale (28 oct
            #     2026); su espera se va con la franja
            fuera = await self._sin_su_ultima_espera(competition.id, round_id)

            # 7. Eliminar la ronda
            await self._uow.rounds.delete(round_id)

        # Ya borrada: sus avisos de salida retirados se quedarian huerfanos
        # (revisor sin contexto, 22 oct 2026)
        await self._actividad.round_deleted(competition.id, round_id)
        for inscripcion in fuera:
            await self._actividad.left(competition.id, inscripcion.user_id)
            await self._actividad.window_removed(competition, round_entity, inscripcion)

        return DeleteRoundResponseDTO(
            id=request.round_id,
            deleted=True,
            matches_deleted=matches_deleted,
            deleted_at=datetime.now(UTC).replace(tzinfo=None),
        )

    async def _sin_su_ultima_espera(
        self, competition_id: CompetitionId, round_id: RoundId
    ) -> list[Enrollment]:
        """
        Saca de la espera de la franja a todos y, de la competición, a quien entró
        esperando y se queda sin plaza ni otra espera. Devuelve sus inscripciones.
        """
        esperas = await self._uow.esperas.de_la_competicion(competition_id)
        aqui = [e.user_id for e in esperas if e.round_id == round_id]
        if not aqui:
            return []
        con_plaza = {p.user_id for p in await self._uow.plazas.de_la_competicion(competition_id)}
        con_otra = {e.user_id for e in esperas if e.round_id != round_id}
        fuera = []
        for user_id in aqui:
            await self._uow.esperas.quitar(round_id, user_id)
            if user_id in con_plaza or user_id in con_otra:
                continue
            inscripcion = await self._uow.enrollments.find_by_user_and_competition(
                user_id, competition_id
            )
            if (
                inscripcion is None
                or inscripcion.status is not EnrollmentStatus.APPROVED
                or not inscripcion.entered_waiting
            ):
                continue
            inscripcion.withdraw("tee_window_removed")
            await self._uow.enrollments.update(inscripcion)
            fuera.append(inscripcion)
        return fuera
