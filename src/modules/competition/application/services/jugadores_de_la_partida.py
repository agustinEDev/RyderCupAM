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

import logging
from collections.abc import Sequence
from dataclasses import replace
from decimal import Decimal

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
from src.modules.golf_course.domain.services.stroke_context import StrokeContext
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.playing_handicap_calculator import (
    PlayingHandicapCalculator,
    TeeRating,
)
from src.shared.domain.services.stroke_allocation import allocate_by_hole
from src.shared.domain.services.tee_lookup import tee_key_for
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.play_mode import PlayMode

logger = logging.getLogger(__name__)


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

        # El campo hace falta también en SCRATCH: sin golpes, pero con el par de
        # cada hoyo de sus barras para los puntos y el «par» (P12)
        campo = await self._campos.find_by_id(franja.golf_course_id)
        if campo is None:
            raise ValueError(f"No existe el campo de la franja {franja.id}")
        contexto = course_context_for(campo)

        if competition.play_mode == PlayMode.SCRATCH:
            return {
                u: self._sin_golpes(u, inscripciones[u], generos.get(u), contexto) for u in user_ids
            }

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
            jugadores[user_id] = self._foto(
                competition,
                franja,
                contexto,
                user_id,
                inscripcion.fixed_handicap,
                barra.tee_color,
                barra.tee_gender,
                barra.tee_rating,
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

    async def con_otro_handicap(
        self,
        competition: Competition,
        franja: Round,
        foto: JugadorDePartida,
        handicap: Decimal,
    ) -> JugadorDePartida:
        """
        La misma foto con otro hándicap fijado (G1): mismas barras, otro de juego.

        Las barras no se vuelven a elegir: un cambio del perfil (el género) no
        toca la partida (D14). Solo cambia lo que sale del hándicap.
        """
        if competition.play_mode == PlayMode.SCRATCH:
            return replace(foto, handicap=handicap)
        campo = await self._campos.find_by_id(franja.golf_course_id)
        if campo is None:
            raise ValueError(f"No existe el campo de la franja {franja.id}")
        contexto = course_context_for(campo)
        valoracion = contexto.rating_for(foto.tee_color, foto.tee_gender)
        if valoracion is None:
            # Con esas barras se generó: si el campo ya no las valora, se deja como
            # estaba, y que se sepa: la corrección de la RFEG no llega a la partida
            logger.warning(
                "Tee %s of golf course %s is no longer rated: a corrected handicap "
                "does not reach a tee group",
                foto.tee_color,
                franja.golf_course_id,
            )
            return foto
        return self._foto(
            competition,
            franja,
            contexto,
            foto.user_id,
            handicap,
            foto.tee_color,
            foto.tee_gender,
            valoracion,
        )

    def _foto(
        self,
        competition: Competition,
        franja: Round,
        contexto: StrokeContext,
        user_id: UserId,
        handicap: Decimal,
        tee_color: TeeColor,
        tee_gender: Gender | None,
        valoracion: TeeRating,
    ) -> JugadorDePartida:
        """Hándicap de juego con el tope y golpes de cada hoyo, con signo."""
        de_juego = self._calculadora.calculate(
            handicap,
            valoracion,
            franja.get_effective_allowance(),
            competition.max_playing_handicap,
        )
        reparto = allocate_by_hole(de_juego, contexto.holes_for(tee_color, tee_gender))
        return JugadorDePartida(
            user_id=user_id,
            handicap=handicap,
            playing_handicap=de_juego,
            tee_color=tee_color,
            tee_gender=tee_gender,
            golpes_por_hoyo=tuple(reparto.get(hoyo, 0) for hoyo in range(1, HOYOS + 1)),
            par_por_hoyo=_pares(contexto, tee_color, tee_gender),
        )

    @staticmethod
    def _sin_golpes(user_id, inscripcion, genero, contexto: StrokeContext) -> JugadorDePartida:
        """SCRATCH: todos juegan con 0, y las barras no hace falta que estén valoradas."""
        barra = barra_del_jugador(inscripcion.tee_color, genero, contexto.tee_ratings)
        tee_gender = barra.tee_gender
        # Unas barras sin valorar no dan golpes, pero su tarjeta sí cuenta: su
        # género se busca también entre las que la traen (P12)
        con_tarjeta = tee_key_for(
            contexto.pars_by_tee, barra.tee_color.value, genero.value if genero else None
        )
        if tee_gender is None and con_tarjeta is not None and con_tarjeta[1] is not None:
            tee_gender = genero
        return JugadorDePartida(
            user_id=user_id,
            handicap=inscripcion.fixed_handicap,
            playing_handicap=0,
            tee_color=barra.tee_color,
            tee_gender=tee_gender,
            golpes_por_hoyo=(0,) * HOYOS,
            par_por_hoyo=_pares(contexto, barra.tee_color, tee_gender),
        )

    async def _nombres(self, uow, competition, user_ids) -> dict[UserId, str]:
        return await PlayerNames.de_la_competicion(user_ids, competition.id, self._usuarios, uow)


def _pares(contexto: StrokeContext, tee_color: TeeColor, tee_gender: Gender | None) -> tuple:
    """El par de cada hoyo, del 1 al 18, desde esas barras (P12)."""
    pares = contexto.pars_for(tee_color, tee_gender)
    return tuple(pares[hoyo] for hoyo in range(1, HOYOS + 1))
