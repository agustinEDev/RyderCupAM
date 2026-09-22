"""
DraftRoom - Lo que las tres acciones de la sala comparten (FE #653).

Abrirla, mirarla y elegir necesitan lo mismo: la competicion, quien queda por
elegir, y el turno agotado resuelto. Eso ultimo es lo que obliga a compartirlo:
el minuto no lo cuenta ningun proceso de fondo, lo resuelve quien mire la sala
—como la anotacion se abre sola al llegar el primer golpe (BE #305)—, asi que
si una de las tres rutas se olvidara, la sala se quedaria parada segun por
donde se entrase.
"""

from collections.abc import Callable
from datetime import datetime

from src.modules.competition.application.dto.draft_dto import (
    DraftPickDTO,
    DraftPlayerDTO,
    DraftStateDTO,
)
from src.modules.competition.application.exceptions import CompetitionNotFoundError
from src.modules.competition.application.services.draft_roster import DraftRoster
from src.modules.competition.application.services.player_names import PlayerNames
from src.modules.competition.application.services.team_assignment_writer import (
    TeamAssignmentWriter,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.draft import Draft
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.snake_draft_service import PlayerForDraft
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.draft_status import DraftStatus
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.team_assignment_mode import TeamAssignmentMode
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)


class DraftRoom:
    """La sala vista desde la capa de aplicacion."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_repository: UserRepositoryInterface,
        clock: Callable[[], datetime] | None = None,
    ):
        """
        Args:
            uow: Unit of Work del modulo
            user_repository: De donde salen nombres y handicaps
            clock: El reloj del SERVIDOR. Se inyecta para poder moverlo en los
                tests, nunca para que lo ponga el cliente
        """
        self._uow = uow
        self._user_repo = user_repository
        self._clock = clock or datetime.now

    @property
    def ahora(self) -> datetime:
        """La hora del servidor."""
        return self._clock()

    async def competicion(self, competition_id: CompetitionId) -> Competition:
        """La competicion, con su fila bloqueada.

        Bloqueada porque al terminar la sala se le tocan los equipos, y porque
        nombrar capitanes a la vez cambiaria quien puede elegir.

        Raises:
            CompetitionNotFoundError: Si no existe
        """
        competition = await self._uow.competitions.find_by_id_for_update(competition_id)
        if not competition:
            raise CompetitionNotFoundError(f"No existe competición con ID {competition_id.value}")
        return competition

    async def elegibles(self, competition: Competition) -> list[PlayerForDraft]:
        """Los inscritos aprobados que no capitanean, con su handicap.

        Los capitanes no entran: nombrarlos ya los fijo en su equipo (BE #320).
        """
        enrollments = await self._uow.enrollments.find_by_competition_and_status(
            competition.id, EnrollmentStatus.APPROVED
        )
        capitanes = [
            uid
            for uid in (competition.team_a_captain_id, competition.team_b_captain_id)
            if uid is not None
        ]
        return await DraftRoster.de_los_inscritos(enrollments, self._user_repo, capitanes)

    async def al_dia(
        self, competition: Competition, draft: Draft, elegibles: list[PlayerForDraft]
    ) -> None:
        """Resuelve los minutos que se agotaron desde la ultima vez.

        Varios de golpe: si nadie entra en diez minutos, la sala no se queda a
        medias esperando a que alguien la mire diez veces.
        """
        cambios = False
        while draft.turn_expired(self.ahora):
            # Con la hora del vencimiento, no con la de ahora: la aplicación
            # eligió cuando se acabó el minuto, y el turno siguiente empezó
            # ahí. Pasándole `ahora` solo se resolvería un turno por vistazo
            draft.pick_for_expired_turn(elegibles, draft.turn_deadline)
            cambios = True
        if cambios:
            await self.guardar(competition, draft)

    async def guardar(self, competition: Competition, draft: Draft) -> None:
        """Guarda la sala y, si termino, deja los equipos hechos."""
        await self._uow.drafts.update(draft)
        if draft.status == DraftStatus.COMPLETED:
            equipo_a, equipo_b = draft.teams()
            await TeamAssignmentWriter.guardar(
                self._uow, competition, TeamAssignmentMode.DRAFT, equipo_a, equipo_b
            )

    async def estado(
        self, competition: Competition, draft: Draft, elegibles: list[PlayerForDraft]
    ) -> DraftStateDTO:
        """La sala entera, que es lo que la pantalla pinta en directo."""
        cogidos = {pick.user_id for pick in draft.picks}
        disponibles = [p for p in elegibles if p.user_id not in cogidos]
        nombres = await PlayerNames.de_la_competicion(
            [p.user_id for p in disponibles], competition.id, self._user_repo, self._uow
        )
        equipo_a, equipo_b = draft.teams()
        return DraftStateDTO(
            id=draft.id.value,
            competition_id=draft.competition_id.value,
            status=draft.status.value,
            first_pick=draft.first_pick,
            current_team=draft.current_team,
            turn_started_at=draft.turn_started_at,
            seconds_per_turn=draft.seconds_per_turn,
            server_time=self.ahora,
            team_a_captain_id=draft.team_a_captain_id.value,
            team_b_captain_id=draft.team_b_captain_id.value,
            team_a=[uid.value for uid in equipo_a],
            team_b=[uid.value for uid in equipo_b],
            picks=[
                DraftPickDTO(
                    user_id=pick.user_id.value,
                    team=pick.team,
                    order=pick.order,
                    automatic=pick.automatic,
                )
                for pick in draft.picks
            ],
            available_players=[
                DraftPlayerDTO(
                    user_id=p.user_id.value,
                    name=nombres.get(p.user_id, ""),
                    handicap=p.handicap,
                )
                for p in disponibles
            ],
        )
