"""
Si una sesion —o una competicion entera— llego a jugarse (BE #347).

Se protege lo jugado, no lo montado (decidido con el dueno del producto el 21 y
22 sep): un calendario sin jugar o un sorteo de equipos se rehacen; un golpe no.
Lo usan el borrado de una competicion y el reset de los sobres de una sesion, y
vive aqui porque las dos tienen que contestar EXACTAMENTE lo mismo.
"""

from collections.abc import Sequence

from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.domain.value_objects.round_id import RoundId


class LoJugado:
    """Contesta si hay algo jugado que proteger."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Args:
            uow: Unit of Work del modulo
        """
        self._uow = uow

    async def en_la_sesion(self, round_id: RoundId, bloquear: bool = False) -> bool:
        """Indica si esa sesion llego a jugarse, aunque sea un hoyo.

        Jugado es un partido terminado —con resultado, walkover o concedido,
        aunque no tenga golpes— o un hoyo anotado en uno abierto. Tener
        tarjetas no basta: se crean vacias al abrir el partido, y la anotacion
        se abre sola a la hora de la sesion (BE #305) sin que nadie haya
        jugado. Los partidos SCHEDULED no se miran: sus tarjetas nacen al
        empezar, y nada devuelve un partido a SCHEDULED.

        Args:
            round_id: La sesion
            bloquear: Lee partidos y tarjetas con su fila bloqueada. Lo usa
                quien va a borrar: anotar un hoyo, conceder o terminar no
                bloquean la competicion, asi que entre preguntar y borrar cabe
                un golpe. Si llega antes, el borrado lo espera y lo ve; si
                llega despues, ya no encuentra la fila. La pregunta de una
                ficha NO bloquea: retendria a quien anota
        """
        # Una franja de stroke play: jugado es un golpe apuntado en una de sus
        # partidas (#251, PR 5). Generarlas no es jugar
        if bloquear:
            await self._bloquear(await self._uow.partidas.de_la_franja(round_id))
        if _alguno_apuntado(await self._uow.golpes_de_partida.de_la_franja(round_id)):
            return True
        return await self._partidos_jugados(round_id, bloquear)

    async def en_la_competicion(
        self, competition_id: CompetitionId, bloquear: bool = False
    ) -> bool:
        """Indica si el torneo llego a jugarse, aunque sea un hoyo.

        Se pregunta aunque el estado diga otra cosa: el estado se puede andar
        hacia atras sin deshacer lo jugado, asi que un torneo ya jugado puede
        estar de vuelta en ACTIVE y la cascada se llevaria sus partidos y sus
        golpes. Los golpes de las partidas se leen una vez para todo el torneo.
        """
        if bloquear:
            await self._bloquear(await self._uow.partidas.de_la_competicion(competition_id))
        if _alguno_apuntado(await self._uow.golpes_de_partida.de_la_competicion(competition_id)):
            return True
        for ronda in await self._uow.rounds.find_by_competition(competition_id):
            if await self._partidos_jugados(ronda.id, bloquear):
                return True
        return False

    async def _bloquear(self, partidas: Sequence[Partida]) -> None:
        """Bloquea cada partida antes de leer sus golpes.

        Anotar bloquea la partida antes de escribir: un primer golpe aun sin
        confirmar no se ve, y sin esperarlo el borrado se llevaria al jugador y
        su golpe reventaria la clave ajena al confirmar (un 500).
        """
        for partida in partidas:
            await self._uow.partidas.find_by_id_for_update(partida.id)

    async def _partidos_jugados(self, round_id: RoundId, bloquear: bool) -> bool:
        partidos_de = (
            self._uow.matches.find_by_round_for_update
            if bloquear
            else self._uow.matches.find_by_round
        )
        tarjetas_de = (
            self._uow.hole_scores.find_by_match_for_update
            if bloquear
            else self._uow.hole_scores.find_by_match
        )
        # Primero los partidos y luego sus tarjetas, el mismo orden en que la
        # anotacion escribe
        for partido in await partidos_de(round_id):
            if partido.status.is_finished():
                return True
            if partido.status == MatchStatus.IN_PROGRESS:
                tarjetas = await tarjetas_de(partido.id)
                if any(tarjeta.is_recorded for tarjeta in tarjetas):
                    return True
        return False


def _alguno_apuntado(golpes: Sequence[GolpeDePartida]) -> bool:
    return any(golpe.propio_enviado or golpe.marcador_enviado for golpe in golpes)
