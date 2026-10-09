"""
JugadoresDeLaPartida - La foto de cada jugador al generar sus partidas (#251, PR 4).

Decidido con Agustín el 6-9 oct 2026:

- El hándicap es el **fijado al cerrar** las inscripciones (el personalizado si
  lo tiene), no el del perfil: es la foto del torneo (D14).
- Las barras, las de su inscripción con la regla de siempre (`barra_del_jugador`).
- Hándicap de juego individual al 95 % (el de la franja), con el tope de la
  competición; en SCRATCH, 0 y ni se mira el campo, como en la Ryder (D7).
- Los golpes de cada hoyo con signo: un plus los da en los más fáciles.

Gemelo de `JugadoresDelPartido` de la Ryder, que reparte entre dos bandos y
con el hándicap del perfil: aquí cada uno juega contra el campo.
"""

from collections.abc import Sequence

from src.modules.competition.application.services.course_context import course_context_for
from src.modules.competition.application.services.player_names import PlayerNames
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.barra_del_jugador import (
    barra_del_jugador,
    lo_que_le_falta,
)
from src.modules.competition.domain.value_objects.jugador_de_partida import (
    HOYOS,
    JugadorDePartida,
)
from src.modules.competition.domain.value_objects.match_generation_block import (
    MISSING_HANDICAP,
    BlockedPlayer,
)
from src.modules.golf_course.domain.repositories.golf_course_repository import (
    IGolfCourseRepository,
)
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.playing_handicap_calculator import PlayingHandicapCalculator
from src.shared.domain.services.stroke_allocation import allocate_by_hole
from src.shared.domain.value_objects.play_mode import PlayMode


class JugadoresSinHandicapError(Exception):
    """Hay jugadores sin hándicap fijado, y aquí van TODOS."""

    def __init__(self, players: list[BlockedPlayer]):
        self.players = players
        super().__init__(
            "No se pueden generar las partidas: falta el hándicap de "
            + ", ".join(p.name or str(p.user_id) for p in players)
        )


class JugadoresSinBarraError(Exception):
    """Hay jugadores sin barras en el campo, y aquí van TODOS, con lo que le falta a cada uno."""

    def __init__(self, players: list[BlockedPlayer]):
        self.players = players
        super().__init__(
            "No se pueden generar las partidas: falta saber desde qué barras juegan "
            + ", ".join(p.name or str(p.user_id) for p in players)
        )


class JugadoresDeLaPartida:
    """Saca la foto de los jugadores de una franja."""

    def __init__(
        self,
        golf_course_repository: IGolfCourseRepository,
        user_repository: UserRepositoryInterface,
        handicap_calculator: PlayingHandicapCalculator | None = None,
    ):
        self._campos = golf_course_repository
        self._usuarios = user_repository
        self._calculadora = handicap_calculator or PlayingHandicapCalculator()

    async def construir(
        self,
        uow: CompetitionUnitOfWorkInterface,
        competition: Competition,
        franja: Round,
        user_ids: Sequence[UserId],
    ) -> dict[UserId, JugadorDePartida]:
        """
        Raises:
            JugadoresSinHandicapError: Con todos los que no tienen hándicap fijado
            JugadoresSinBarraError: Con todos los que no tienen barras en el campo
        """
        inscripciones = {
            e.user_id: e
            for e in await uow.enrollments.find_by_user_ids_and_competition(
                list(user_ids), competition.id
            )
        }
        generos = {u.id: u.gender for u in await self._usuarios.find_by_ids(list(user_ids))}

        sin_handicap = [
            u for u in user_ids if u not in inscripciones or inscripciones[u].fixed_handicap is None
        ]
        if sin_handicap:
            nombres = await self._nombres(uow, competition, sin_handicap)
            raise JugadoresSinHandicapError(
                [BlockedPlayer(u, nombres.get(u, ""), MISSING_HANDICAP) for u in sin_handicap]
            )

        if competition.play_mode == PlayMode.SCRATCH:
            return {u: self._sin_golpes(u, inscripciones[u], generos.get(u)) for u in user_ids}

        campo = await self._campos.find_by_id(franja.golf_course_id)
        if campo is None:
            raise ValueError(f"No existe el campo de la franja {franja.id}")
        contexto = course_context_for(campo)

        jugadores: dict[UserId, JugadorDePartida] = {}
        sin_barras: list[tuple[UserId, str, str | None]] = []
        for user_id in user_ids:
            inscripcion = inscripciones[user_id]
            genero = generos.get(user_id)
            barra = barra_del_jugador(inscripcion.tee_color, genero, contexto.tee_ratings)
            if barra.tee_rating is None:
                falta = lo_que_le_falta(barra, genero, contexto.tee_ratings)
                # Sin valoración siempre falta algo: el `if` es para mypy
                if falta is not None:
                    sin_barras.append((user_id, *falta))
                continue
            handicap = inscripcion.fixed_handicap
            de_juego = self._calculadora.calculate(
                handicap,
                barra.tee_rating,
                franja.get_effective_allowance(),
                competition.max_playing_handicap,
            )
            reparto = allocate_by_hole(
                de_juego, contexto.holes_for(barra.tee_color, barra.tee_gender)
            )
            jugadores[user_id] = JugadorDePartida(
                user_id=user_id,
                handicap=handicap,
                playing_handicap=de_juego,
                tee_color=barra.tee_color,
                tee_gender=barra.tee_gender,
                golpes_por_hoyo=tuple(reparto.get(hoyo, 0) for hoyo in range(1, HOYOS + 1)),
            )

        if sin_barras:
            nombres = await self._nombres(uow, competition, [u for u, _, _ in sin_barras])
            raise JugadoresSinBarraError(
                [
                    BlockedPlayer(u, nombres.get(u, ""), missing, tee_color=color)
                    for u, missing, color in sin_barras
                ]
            )
        return jugadores

    @staticmethod
    def _sin_golpes(user_id, inscripcion, genero) -> JugadorDePartida:
        """SCRATCH: todos juegan con 0 y las barras no se valoran."""
        barra = barra_del_jugador(inscripcion.tee_color, genero, {})
        return JugadorDePartida(
            user_id=user_id,
            handicap=inscripcion.fixed_handicap,
            playing_handicap=0,
            tee_color=barra.tee_color,
            tee_gender=None,
            golpes_por_hoyo=(0,) * HOYOS,
        )

    async def _nombres(self, uow, competition, user_ids) -> dict[UserId, str]:
        return await PlayerNames.de_la_competicion(user_ids, competition.id, self._usuarios, uow)
