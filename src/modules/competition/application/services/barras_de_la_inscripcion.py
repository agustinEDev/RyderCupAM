"""
BarrasDeLaInscripcion - Quién toca las barras de una inscripción y cuáles valen (BE #912).

Una sola regla para cambiarlas (`PUT /enrollments/{id}/tee`) y para ofrecerlas
(`GET /enrollments/{id}/tees`): el selector del front no puede enseñar una barra
que luego el cambio rechace, ni esconder una que aceptaría. El front no conoce
el género de los demás inscritos, así que las barras válidas las calcula el back.
"""

from collections.abc import Mapping

from src.modules.competition.application.exceptions import (
    NotCompetitionCreatorError,
    PendingGameNotRecalculableError,
)
from src.modules.competition.application.services.course_context import contexto_del_campo
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.barra_del_jugador import (
    la_barra_vale,
    se_puede_elegir,
)
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.golf_course.domain.services.stroke_context import StrokeContext
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.tee_lookup import TeeKey
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.play_mode import PlayMode

# Antes de empezar las cambia también el propio jugador
ANTES_DE_EMPEZAR = frozenset(
    {CompetitionStatus.DRAFT, CompetitionStatus.ACTIVE, CompetitionStatus.CLOSED}
)
# Empezada, solo quien gestiona: su capitán, el organizador o un admin
SE_PUEDEN_CAMBIAR = ANTES_DE_EMPEZAR | {CompetitionStatus.IN_PROGRESS}


class BarrasDeLaInscripcion:
    """Quién puede tocar las barras de una inscripción, y cuáles le valen."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface, campos: IGolfCourseRepository):
        self._uow = uow
        self._campos = campos

    async def comprobar_quien(
        self, competition: Competition, enrollment: Enrollment, quien: UserId, is_admin: bool
    ) -> str:
        """
        Como qué lo pide: admin, organizador, capitán de su equipo o el propio
        jugador (solo antes de empezar).

        Raises:
            NotCompetitionCreatorError: Si no es ninguno de ellos
        """
        if is_admin:
            return "admin"
        if competition.is_creator(quien):
            return "organizer"
        if await self._es_su_capitan(competition, enrollment.user_id, quien):
            return "captain"
        if competition.status in ANTES_DE_EMPEZAR and enrollment.user_id == quien:
            return "player"
        raise NotCompetitionCreatorError(
            "Solo el jugador, el capitán de su equipo o el organizador cambian sus barras"
        )

    async def comprobar_quien_consulta(
        self, competition: Competition, enrollment: Enrollment, quien: UserId, is_admin: bool
    ) -> str:
        """
        Como qué consulta sus barras: lo mismo que quien las cambia, pero en
        cualquier estado de la competición (es una lectura). El propio jugador
        siempre: son sus datos.

        Raises:
            NotCompetitionCreatorError: Si no es el jugador, el capitán de su
                equipo, el organizador ni un admin
        """
        if is_admin:
            return "admin"
        if competition.is_creator(quien):
            return "organizer"
        if enrollment.user_id == quien:
            return "player"
        if await self._es_su_capitan(competition, enrollment.user_id, quien):
            return "captain"
        raise NotCompetitionCreatorError(
            "Solo el jugador, el capitán de su equipo o el organizador ven sus barras"
        )

    @staticmethod
    def comprobar_organizador(competition: Competition, quien: UserId, is_admin: bool) -> str:
        """
        La barra de un campo para todos los de un género: solo el organizador o un
        admin (barras por campo).

        Raises:
            NotCompetitionCreatorError: Si no es ninguno de los dos
        """
        if is_admin:
            return "admin"
        if competition.is_creator(quien):
            return "organizer"
        raise NotCompetitionCreatorError("Solo el organizador fija la barra de un campo")

    async def _es_su_capitan(
        self, competition: Competition, jugador: UserId, quien: UserId
    ) -> bool:
        """Si `quien` capitanea el equipo del jugador. Sin equipos formados, nadie."""
        ryder_cup = competition.ryder_cup
        if ryder_cup is None:
            return False
        equipos = await self._uow.team_assignments.find_by_competition(competition.id)
        equipo = equipos.get_player_team(jugador) if equipos else None
        return equipo is not None and ryder_cup.is_captain_of(equipo, quien)

    async def vale_en_el_campo(
        self,
        competition: Competition,
        golf_course_id: GolfCourseId,
        color: TeeColor,
        genero: Gender | None,
        contextos: dict[GolfCourseId, StrokeContext],
    ) -> bool:
        """
        Si ese campo tiene esas barras para su género o sin género, con la regla de
        siempre (`tee_key_for`) y el MISMO contexto que el cálculo
        (`contexto_del_campo`, el de `JugadoresDelPartido` y `JugadoresDeLaPartida`):
        valoradas, y en SCRATCH también con tarjeta propia, que sin golpes no hace
        falta valoración. «Con tarjeta» es lo que mira cada cálculo: la Ryder,
        `holes_by_tee`; el stroke play, `pars_by_tee` (salen juntas del campo).

        Sin género en el perfil (o sin usuario) solo valen las mixtas: es lo que
        `tee_key_for` encuentra con género None, y nunca las de un solo género. Un
        campo que ya no existe no la tiene.
        """
        try:
            contexto = await contexto_del_campo(self._campos, golf_course_id, contextos)
        except PendingGameNotRecalculableError:
            return False
        con_tarjeta: Mapping[TeeKey, object] | None = None
        if competition.play_mode == PlayMode.SCRATCH:
            con_tarjeta = (
                contexto.holes_by_tee if competition.ryder_cup is not None else contexto.pars_by_tee
            )
        return la_barra_vale(color, genero, contexto.tee_ratings, con_tarjeta)

    async def las_que_valen_en_el_campo(
        self,
        competition: Competition,
        golf_course_id: GolfCourseId,
        genero: Gender | None,
        contextos: dict[GolfCourseId, StrokeContext],
    ) -> list[TeeColor]:
        """
        Las barras que le valen en ese campo, en el orden de `TeeColor`. Nunca las
        que no se eligen (OTHER, 21 nov 2026): el cambio las rechazaría.
        """
        return [
            color
            for color in TeeColor
            if se_puede_elegir(color)
            and await self.vale_en_el_campo(competition, golf_course_id, color, genero, contextos)
        ]
