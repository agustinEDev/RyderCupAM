"""
Lo jugado de una privada: sus clasificaciones y sus partidas (tabla del 27 oct 2026).

La regla de Agustín: en una privada, quien no está no ve nada, tampoco
publicada. Está dentro el organizador, un admin y quien tiene su inscripción
aprobada (los capitanes lo son). La llave de quien está fuera es su Actividad:
si le sale un evento de un amigo en esa competición, ve la clasificación y la
partida de ese amigo; las demás partidas, no. Las públicas siguen abiertas.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum

from src.modules.competition.application.ports.eventos_de_amigos_interface import (
    EventosDeAmigosInterface,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.user.domain.value_objects.user_id import UserId


class Acceso(Enum):
    """Hasta dónde llega lo que ve de lo jugado."""

    # Todo: está dentro, o es pública
    ENTERO = "ENTERO"
    # La clasificación y las partidas de sus amigos con evento (la llave)
    SUS_AMIGOS = "SUS_AMIGOS"
    # Nada
    NADA = "NADA"


class NoPuedeVerloError(Exception):
    """Lo jugado de una privada en la que no está, sin llave para verlo."""


@dataclass(frozen=True)
class LoJugadoQueVe:
    """Lo que ve de lo jugado quien mira; con la llave, de qué amigos."""

    acceso: Acceso
    amigos: frozenset[UserId] = field(default_factory=frozenset)
    # Quien mira: su propia partida la ve siempre, aunque se retirara (/code-review)
    quien: UserId | None = None

    @property
    def ve_la_clasificacion(self) -> bool:
        """Si ve la clasificación: dentro, o con la llave."""
        return self.acceso is not Acceso.NADA

    def ve_la_partida(self, jugadores: Iterable[UserId]) -> bool:
        """
        Si ve una partida (o un partido): entero, la suya, o si juega en ella
        un amigo con evento.
        """
        if self.acceso is Acceso.ENTERO:
            return True
        jugadores = list(jugadores)
        if self.quien is not None and self.quien in jugadores:
            return True
        return self.acceso is Acceso.SUS_AMIGOS and any(j in self.amigos for j in jugadores)


class PuertaDeLoJugado:
    """
    Quien pregunta por lo jugado de una competición. Lee con su `uow` y,
    cerrado este, pregunta por la llave al módulo social: las unidades de
    trabajo comparten sesión y no se abren una dentro de otra.

    Lo que no existe no lo corta: su caso de uso da después su 404.
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface, eventos: EventosDeAmigosInterface):
        self._uow = uow
        self._eventos = eventos

    async def de_la_competicion(
        self, competition_id: CompetitionId, quien: UserId, *, es_admin: bool = False
    ) -> LoJugadoQueVe | None:
        """Lo que ve de lo jugado de esa competición; None si no existe."""
        async with self._uow:
            dentro = await self._dentro(competition_id, quien, es_admin)
        return await self._con_la_llave(dentro, competition_id, quien)

    async def exigir_la_clasificacion(
        self, competition_id: CompetitionId, quien: UserId, *, es_admin: bool = False
    ) -> LoJugadoQueVe | None:
        """
        Lo que ve de la clasificación de esa competición, para filtrar los
        partidos de la Ryder; None si no existe.

        Raises:
            NoPuedeVerloError: Si es de una privada en la que no está, sin llave
        """
        ve = await self.de_la_competicion(competition_id, quien, es_admin=es_admin)
        if ve is not None and not ve.ve_la_clasificacion:
            raise NoPuedeVerloError
        return ve

    async def exigir_la_clasificacion_de_la_ronda(
        self, round_id: RoundId, quien: UserId, *, es_admin: bool = False
    ) -> None:
        """
        Raises:
            NoPuedeVerloError: Si la ronda es de una privada en la que no está, sin llave
        """
        async with self._uow:
            ronda = await self._uow.rounds.find_by_id(round_id)
            if ronda is None:
                return
            competition_id = ronda.competition_id
            dentro = await self._dentro(competition_id, quien, es_admin)
        ve = await self._con_la_llave(dentro, competition_id, quien)
        if ve is not None and not ve.ve_la_clasificacion:
            raise NoPuedeVerloError

    async def exigir_el_partido(
        self, match_id: MatchId, quien: UserId, *, es_admin: bool = False
    ) -> None:
        """Un partido de la Ryder: el suyo, o el de un amigo con evento."""
        async with self._uow:
            partido = await self._uow.matches.find_by_id(match_id)
            ronda = partido and await self._uow.rounds.find_by_id(partido.round_id)
            if ronda is None:
                return
            competition_id = ronda.competition_id
            jugadores = [p.user_id for p in (*partido.team_a_players, *partido.team_b_players)]
            dentro = await self._dentro(competition_id, quien, es_admin)
        await self._exigir_la_partida(dentro, competition_id, quien, jugadores)

    async def exigir_la_partida(
        self, partida_id: PartidaId, quien: UserId, *, es_admin: bool = False
    ) -> None:
        """Una partida de stroke play: la suya, o la de un amigo con evento."""
        async with self._uow:
            partida = await self._uow.partidas.find_by_id(partida_id)
            if partida is None:
                return
            competition_id = partida.competition_id
            jugadores = list(partida.user_ids)
            dentro = await self._dentro(competition_id, quien, es_admin)
        await self._exigir_la_partida(dentro, competition_id, quien, jugadores)

    async def _exigir_la_partida(
        self,
        dentro: bool | None,
        competition_id: CompetitionId,
        quien: UserId,
        jugadores: list[UserId],
    ) -> None:
        ve = await self._con_la_llave(dentro, competition_id, quien)
        if ve is not None and not ve.ve_la_partida(jugadores):
            raise NoPuedeVerloError

    async def _dentro(
        self, competition_id: CompetitionId, quien: UserId, es_admin: bool
    ) -> bool | None:
        """Si está dentro (o es pública); None si la competición no existe. Con el `uow` abierto."""
        competition = await self._uow.competitions.find_by_id(competition_id)
        if competition is None:
            return None
        if competition.visibility is Visibility.PUBLIC or es_admin or competition.is_creator(quien):
            return True
        suya = await self._uow.enrollments.find_by_user_and_competition(quien, competition_id)
        return suya is not None and suya.status == EnrollmentStatus.APPROVED

    async def _con_la_llave(
        self, dentro: bool | None, competition_id: CompetitionId, quien: UserId
    ) -> LoJugadoQueVe | None:
        if dentro is None:
            return None
        return await con_la_llave(dentro, competition_id, quien, self._eventos)


async def con_la_llave(
    dentro: bool,
    competition_id: CompetitionId,
    quien: UserId,
    eventos: EventosDeAmigosInterface | None,
) -> LoJugadoQueVe:
    """
    Lo que ve de lo jugado quien está dentro (o no): fuera, con la llave de su
    Actividad. Fuera del `uow` de competiciones. Sin puerto, ninguna llave.
    """
    if dentro:
        return LoJugadoQueVe(Acceso.ENTERO)
    if eventos is None:
        return LoJugadoQueVe(Acceso.NADA, quien=quien)
    amigos = await eventos.amigos_con_evento_en(quien, competition_id)
    return LoJugadoQueVe(Acceso.SUS_AMIGOS if amigos else Acceso.NADA, amigos, quien)
