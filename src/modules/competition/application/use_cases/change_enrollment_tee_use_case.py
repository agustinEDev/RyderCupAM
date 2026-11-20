"""
Caso de Uso: cambiar las barras de una inscripción (BE #912, 20 nov 2026).

Una jugadora invitada se quedaba en las barras por defecto aunque el campo no
las tuviera valoradas para ella, y nadie podía cambiárselas: la generación de
partidos se bloqueaba sin salida. Decidido con Agustín:

- Antes de empezar: el propio jugador, el capitán de SU equipo, el organizador
  o un admin. Ya empezada: el capitán de su equipo, el organizador o un admin
  (para desbloquear la sesión 2 de una Ryder, que se genera ya empezada); la
  capitana, también las suyas. Terminada o cancelada: nadie. Sin equipos
  formados no hay capitanes, y el subcapitán no cuenta.
- No se cambia lo ya jugado, pero sí lo que queda por jugar. En sus partidos de
  Ryder sin empezar y sus partidas de stroke play que aún no salieron («tienen
  golpes o les llegó su hora», #544) cambia SU barra y lo que depende de ella;
  los demás se quedan como se generaron (su barra y su hándicap índice
  guardados). Lo que se genere después ya sale con las nuevas.
- Si sus barras nuevas no están valoradas en el campo de algo pendiente: 422,
  y no cambia nada. Si lo que falla es de otro (su barra guardada, el campo, la
  franja), 409 con un código fijo, sin datos de nadie.
- Solo barras valoradas para su género, o sin género, en alguno de los campos
  de la competición; en SCRATCH valen también las que solo tienen tarjeta. Sin
  género en el perfil, solo las mixtas.
- Sin barras (null) vuelve a las habituales de su género.

Quién se comprueba antes de bloquear nada, y otra vez tras bloquear (el estado
pudo cambiar). Los bloqueos, en el orden de siempre: la competición, la
inscripción y sus partidos. Todo se calcula antes de escribir: si algo falla,
no se ha tocado nada, y el rollback de la unidad de trabajo cubre el resto.
"""

import logging
from collections.abc import Callable
from datetime import datetime

from src.modules.competition.application.dto.enrollment_dto import (
    ChangeEnrollmentTeeRequestDTO,
    ChangeEnrollmentTeeResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    EnrollmentNotFoundError,
    NotCompetitionCreatorError,
    PendingGameNotRecalculableError,
    TeeNotRatedForPlayerError,
)
from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.application.services.jugadores_de_la_partida import (
    JugadoresDeLaPartida,
)
from src.modules.competition.application.services.jugadores_del_partido import (
    JugadoresDelPartido,
)
from src.modules.competition.application.services.salidas_de_la_franja import las_que_salieron
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.jugador_de_partida import JugadorDePartida
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.golf_course.domain.services.stroke_context import StrokeContextBuilder
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.instante_utc import ahora_en_utc
from src.shared.domain.services.tee_lookup import TeeKey, tee_key_for
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.play_mode import PlayMode

logger = logging.getLogger(__name__)

# Antes de empezar las cambia también el propio jugador
_ANTES_DE_EMPEZAR = frozenset(
    {CompetitionStatus.DRAFT, CompetitionStatus.ACTIVE, CompetitionStatus.CLOSED}
)
# Empezada, solo quien gestiona: su capitán, el organizador o un admin
_SE_PUEDEN_CAMBIAR = _ANTES_DE_EMPEZAR | {CompetitionStatus.IN_PROGRESS}

_PartidoRehecho = tuple[Match, list[MatchPlayer], list[MatchPlayer]]
_PartidaRehecha = tuple[Partida, list[JugadorDePartida]]


class TeeNotAvailableError(Exception):
    """
    Esas barras no valen para él: ningún campo de la competición las tiene
    valoradas para su género, o no lo están en el campo de algo que le queda por
    jugar.
    """

    error_code = "TEE_NOT_AVAILABLE"


class TeeChangeClosedError(Exception):
    """La competición ya terminó o se canceló: ya no se cambian barras."""

    error_code = "TEE_CHANGE_CLOSED"


class EnrollmentNotApprovedError(Exception):
    """Solo se cambian las barras de una inscripción aprobada."""

    error_code = "ENROLLMENT_NOT_APPROVED"


class ChangeEnrollmentTeeUseCase:
    """
    El propio jugador (antes de empezar), el capitán de su equipo, el organizador o
    un admin cambia las barras de una inscripción, y con ellas lo que le queda por
    jugar.
    """

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        golf_course_repository: IGolfCourseRepository,
        user_repository: UserRepositoryInterface,
        zonas: ICompetitionTimezone | None = None,
        reloj: Callable[[], datetime] = ahora_en_utc,
    ):
        """
        Args:
            zonas: La zona de cada campo, para saber qué partidas ya salieron por su
                hora; sin ellas cuentan solo las que tienen golpes
            reloj: El momento del cambio
        """
        self._uow = uow
        self._campos = golf_course_repository
        self._usuarios = user_repository
        self._zonas = zonas
        self._reloj = reloj
        # El mismo cálculo que al generar y al reasignar: sin reglas propias
        self._del_partido = JugadoresDelPartido(golf_course_repository, user_repository)
        self._de_la_partida = JugadoresDeLaPartida(golf_course_repository, user_repository)

    async def execute(
        self, request: ChangeEnrollmentTeeRequestDTO, quien: UserId, is_admin: bool = False
    ) -> ChangeEnrollmentTeeResponseDTO:
        """
        Cambia las barras y rehace lo que le queda por jugar.

        Args:
            request: La inscripción y sus barras nuevas (o None)
            quien: Quien lo pide
            is_admin: Si quien lo pide es administrador

        Raises:
            EnrollmentNotFoundError: Si la inscripción no existe
            CompetitionNotFoundError: Si su competición no existe
            NotCompetitionCreatorError: Si no es el jugador (antes de empezar), el
                capitán de su equipo, el organizador ni un admin
            EnrollmentNotApprovedError: Si la inscripción no está aprobada
            TeeChangeClosedError: Si la competición terminó o se canceló
            TeeNotAvailableError: Si esas barras no valen para él
            PendingGameNotRecalculableError: Si algo pendiente no se puede rehacer
                por otra cosa que sus barras
        """
        enrollment_id = EnrollmentId(request.enrollment_id)
        async with self._uow:
            # Quién, sin bloquear nada: a quien no puede no se le dice nada más
            enrollment = await self._uow.enrollments.find_by_id(enrollment_id)
            if enrollment is None:
                raise EnrollmentNotFoundError(f"Inscripción no encontrada: {enrollment_id}")
            competition = await self._uow.competitions.find_by_id(enrollment.competition_id)
            if competition is None:
                raise CompetitionNotFoundError(
                    f"Competición no encontrada: {enrollment.competition_id}"
                )
            await self._comprobar_quien(competition, enrollment, quien, is_admin)

            # Con la competición bloqueada, como la baja, la generación y la
            # reasignación; y otra vez quién, que el estado pudo cambiar
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
            como = await self._comprobar_quien(competition, enrollment, quien, is_admin)

            if not enrollment.is_approved():
                raise EnrollmentNotApprovedError("La inscripción no está aprobada")
            if competition.status not in _SE_PUEDEN_CAMBIAR:
                raise TeeChangeClosedError(
                    f"No se cambian barras en una competición {competition.status.value}"
                )
            usuario = await self._usuarios.find_by_id(enrollment.user_id)
            genero: Gender | None = usuario.gender if usuario else None
            if request.tee_color is not None and not await self._la_tiene_algun_campo(
                competition, request.tee_color, genero
            ):
                raise TeeNotAvailableError(
                    f"Ningún campo de la competición tiene barras {request.tee_color.value} "
                    "valoradas para este jugador"
                )

            # Todo calculado antes de escribir nada
            try:
                partidos = await self._partidos_rehechos(
                    competition, enrollment.user_id, request.tee_color, genero
                )
                partidas = await self._partidas_rehechas(
                    competition, enrollment.user_id, request.tee_color, genero
                )
            except TeeNotRatedForPlayerError as e:
                raise TeeNotAvailableError(
                    "Sus barras nuevas no están valoradas en el campo de algo que le "
                    "queda por jugar"
                ) from e

            antes = enrollment.tee_color
            enrollment.set_tee_color(request.tee_color)
            await self._uow.enrollments.update(enrollment)
            for partido, team_a, team_b in partidos:
                partido.recalcular_jugadores(team_a, team_b)
                await self._uow.matches.update(partido)
            for partida, jugadores in partidas:
                partida.recalcular(jugadores)
            if partidas:
                await self._uow.partidas.guardar([p for p, _ in partidas])

        # Sin nombres: quién, de qué inscripción, cómo y cuánto se rehízo (A09)
        logger.info(
            "Tee change: enrollment=%s by=%s as=%s from=%s to=%s matches=%d tee_groups=%d",
            enrollment.id.value,
            quien.value,
            como,
            antes.value if antes else None,
            request.tee_color.value if request.tee_color else None,
            len(partidos),
            len(partidas),
        )
        return ChangeEnrollmentTeeResponseDTO(
            id=enrollment.id.value,
            competition_id=enrollment.competition_id.value,
            user_id=enrollment.user_id.value,
            tee_color=enrollment.tee_color.value if enrollment.tee_color else None,
            updated_at=enrollment.updated_at,
        )

    async def _partidos_rehechos(
        self,
        competition: Competition,
        user_id: UserId,
        tee_color: TeeColor | None,
        genero: Gender | None,
    ) -> list[_PartidoRehecho]:
        """Sus partidos de Ryder sin empezar, con su barra nueva; cada uno, bloqueado."""
        rondas = {r.id: r for r in await self._uow.rounds.find_by_competition(competition.id)}
        if not rondas:
            return []
        rehechos: list[_PartidoRehecho] = []
        for leido in await self._uow.matches.find_by_rounds_for_player(list(rondas), user_id):
            if leido.status != MatchStatus.SCHEDULED:
                continue
            partido = await self._uow.matches.find_by_id_for_update(leido.id)
            if partido is None or partido.status != MatchStatus.SCHEDULED:
                continue
            bandos = await self._del_partido.con_otra_barra(
                rondas[partido.round_id], competition, partido, user_id, tee_color, genero
            )
            if bandos is not None:
                rehechos.append((partido, *bandos))
        return rehechos

    async def _partidas_rehechas(
        self,
        competition: Competition,
        user_id: UserId,
        tee_color: TeeColor | None,
        genero: Gender | None,
    ) -> list[_PartidaRehecha]:
        """
        Sus partidas de stroke play que aún no salieron, con su foto nueva; cada una,
        bloqueada. «Salió» es la regla única: tiene golpes o le llegó su hora (#544).
        """
        ahora = self._reloj()
        rehechas: list[_PartidaRehecha] = []
        for leida in await self._uow.partidas.del_jugador(competition.id, user_id):
            partida = await self._uow.partidas.find_by_id_for_update(leida.id)
            if partida is None:
                continue
            franja = await self._uow.rounds.find_by_id(partida.round_id)
            if franja is None:
                # Una partida sin su franja no se puede ni fechar: mejor decirlo que
                # dejarla con las barras viejas sin que nadie lo sepa
                raise PendingGameNotRecalculableError("La franja de una partida ya no existe")
            if partida.id in await las_que_salieron(franja, [partida], self._zonas, ahora):
                continue
            foto = next(j for j in partida.jugadores if j.user_id == user_id)
            nueva = await self._de_la_partida.con_otra_barra(
                competition, franja, foto, tee_color, genero
            )
            if nueva is not None:
                rehechas.append(
                    (partida, [nueva if j.user_id == user_id else j for j in partida.jugadores])
                )
        return rehechas

    async def _comprobar_quien(
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
        if competition.status in _ANTES_DE_EMPEZAR and enrollment.user_id == quien:
            return "player"
        raise NotCompetitionCreatorError(
            "Solo el jugador, el capitán de su equipo o el organizador cambian sus barras"
        )

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

    async def _la_tiene_algun_campo(
        self, competition: Competition, color: TeeColor, genero: Gender | None
    ) -> bool:
        """
        Si alguno de sus campos tiene esas barras para su género o sin género, con
        la regla de siempre (`tee_key_for`): valoradas, y en SCRATCH también con
        solo tarjeta, que sin golpes no hace falta valoración.

        Sin género en el perfil (o sin usuario) solo valen las mixtas: es lo que
        `tee_key_for` encuentra con género None, y nunca las de un solo género.
        """
        en_scratch = competition.play_mode == PlayMode.SCRATCH
        for del_campo in competition.golf_courses:
            campo = await self._campos.find_by_id(del_campo.golf_course_id)
            if campo is None:
                continue
            contexto = StrokeContextBuilder.build(campo)
            barras: set[TeeKey] = set(contexto.tee_ratings)
            if en_scratch:
                barras |= set(contexto.holes_by_tee)
            su_genero = genero.value if genero else None
            if tee_key_for(dict.fromkeys(barras), color.value, su_genero) is not None:
                return True
        return False
