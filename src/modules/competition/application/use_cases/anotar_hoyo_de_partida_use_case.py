"""
Caso de Uso: Anotar un hoyo en una partida de stroke play (#251, PR 5).

Decidido con Agustín (decisión 11 de la #251 y P1-P4, P10, P11 el 9 oct 2026):

- Cada jugador apunta **su golpe** y **el de quien marca**; vale cuando
  coinciden. El cuerpo es el de la Ryder: omitir un campo no es mandarlo nulo
  (#301), y nulo es levantar bola, que en Medal no vale.
- La anotación abre para **toda la franja a su primera salida** (P1), con el
  reloj del servidor a la llegada, nunca uno del cliente (BE #305). Antes,
  `SCORING_NOT_OPEN_YET` con la hora: la cola del móvil lo guarda y reintenta.
- El **primer golpe** pone la partida en juego, y la competición si aún estaba
  cerrada (P2), con las filas bloqueadas: dos primeros golpes a la vez la
  arrancarían dos veces.
- Una tarjeta cerrada (entregada, retirado, no presentado) ya no se toca desde
  aquí: su lado se ignora, como en la Ryder, para que un golpe tardío de la cola
  no la reabra (P3, P10). La corrige el organizador (P9).
- En una partida de uno no hay marcador (P11): su golpe sí, el de un marcado no.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from src.modules.competition.application.dto.scoring_dto import SubmitHoleScoreBodyDTO
from src.modules.competition.application.exceptions import (
    InvalidHoleNumberError,
    NotYourMarkedPlayerError,
    PartidaNotFoundError,
    ScoringNotOpenYetError,
)
from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.application.services.jornadas_de_la_competicion import (
    ZonaDesconocidaError,
)
from src.modules.competition.application.services.vista_de_la_franja import primera_salida
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.golpe_de_partida import (
    PRIMER_HOYO,
    ULTIMO_HOYO,
    GolpeDePartida,
)
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.estado_de_tarjeta import EstadoDeTarjeta
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.user.domain.value_objects.user_id import UserId


class NoEsDeLaPartidaError(Exception):
    """Quien anota no juega esa partida."""

    error_code = "NOT_GROUP_PLAYER"


class SinMarcadorError(Exception):
    """En una partida de uno no hay a quién marcar (P11): lo valida el organizador."""

    error_code = "GROUP_WITHOUT_MARKER"


class PartidaNoAnotableError(Exception):
    """La competición no está cerrada ni en juego: no se anota."""

    error_code = "GROUP_NOT_SCORING"


_ANOTABLE = frozenset({CompetitionStatus.CLOSED, CompetitionStatus.IN_PROGRESS})


async def comprobar_que_abrio(
    uow: CompetitionUnitOfWorkInterface,
    zonas: ICompetitionTimezone,
    partida: Partida,
    llegada: datetime,
) -> None:
    """
    La anotación abre para toda la franja a su primera salida (P1).

    Raises:
        ScoringNotOpenYetError: Antes, con la hora
        PartidaNoAnotableError: Sin zona horaria no se sabe cuándo abre
    """
    franja = await uow.rounds.find_by_id(partida.round_id)
    if franja is None:
        raise PartidaNotFoundError(f"No existe la franja de la partida {partida.id}")
    try:
        abre = await primera_salida(franja, zonas)
    except ZonaDesconocidaError as e:
        raise PartidaNoAnotableError("El campo de la franja no tiene zona horaria.") from e
    if llegada < abre:
        raise ScoringNotOpenYetError("La anotación de la franja aún no ha abierto", abre)


async def arrancar_la_competicion(
    uow: CompetitionUnitOfWorkInterface, competicion: Competition
) -> None:
    """La competición en juego con su fila bloqueada (como la Ryder, BE #375)."""
    bloqueada = await uow.competitions.find_by_id_for_update(competicion.id)
    if bloqueada is None or bloqueada.status not in _ANOTABLE:
        raise PartidaNoAnotableError("Esta competición no está en juego.")
    if bloqueada.status == CompetitionStatus.CLOSED:
        bloqueada.start()
        await uow.competitions.update(bloqueada)


class AnotarHoyoDePartidaUseCase:
    """Un jugador apunta su golpe y el de quien marca en un hoyo."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        zonas: ICompetitionTimezone,
        reloj: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._uow = uow
        self._zonas = zonas
        self._reloj = reloj

    async def execute(
        self, group_id: UUID, hoyo: int, body: SubmitHoleScoreBodyDTO, quien: UserId
    ) -> None:
        """
        Raises:
            PartidaNotFoundError: Si no existe
            InvalidHoleNumberError: Fuera del 1 al 18
            NoEsDeLaPartidaError: Si quien anota no la juega
            NotYourMarkedPlayerError: Si no es a quien le toca marcar
            SinMarcadorError: Un golpe de marcado en una partida de uno
            PartidaNoAnotableError: Competición ni cerrada ni en juego
            ScoringNotOpenYetError: Antes de la primera salida de la franja
            RayaNoPermitidaError: Levantar bola en Medal
        """
        # El instante en que LLEGA: las consultas no deben abrir lo que aún no abría
        llegada = self._reloj()
        if not PRIMER_HOYO <= hoyo <= ULTIMO_HOYO:
            raise InvalidHoleNumberError(f"Hoyo invalido: {hoyo}")
        async with self._uow:
            partida = await self._uow.partidas.find_by_id(PartidaId(group_id))
            if partida is None:
                raise PartidaNotFoundError(f"No existe la partida {group_id}")
            marcado = self._comprobar_quien(partida, quien, body)
            competicion = await self._uow.competitions.find_by_id(partida.competition_id)
            if competicion is None or competicion.status not in _ANOTABLE:
                raise PartidaNoAnotableError("Esta competición no está en juego.")
            await comprobar_que_abrio(self._uow, self._zonas, partida, llegada)
            # Una raya en Medal, antes de abrir nada
            acepta_raya = competicion.tournament_type == TournamentType.STABLEFORD
            for campo in ("own_score", "marked_score"):
                if campo in body.model_fields_set:
                    GolpeDePartida.comprobar(getattr(body, campo), acepta_raya)

            # Primero la competición, después la partida: el mismo orden que el
            # resto de lo que toca partidas, y solo en el primer golpe
            if competicion.status == CompetitionStatus.CLOSED:
                await arrancar_la_competicion(self._uow, competicion)
            bloqueada = await self._uow.partidas.find_by_id_for_update(partida.id)
            if bloqueada is None:
                raise PartidaNotFoundError(f"No existe la partida {group_id}")
            if bloqueada.estado == EstadoPartida.SCHEDULED:
                bloqueada.empezar()
                await self._uow.partidas.guardar([bloqueada])

            await self._apuntar(bloqueada, competicion, hoyo, body, quien, marcado, llegada)

    @staticmethod
    def _comprobar_quien(
        partida: Partida, quien: UserId, body: SubmitHoleScoreBodyDTO
    ) -> UserId | None:
        """A quién marca, si manda su golpe; antes de abrir ni guardar nada."""
        if quien not in partida.user_ids:
            raise NoEsDeLaPartidaError("No juegas esta partida.")
        if "marked_score" not in body.model_fields_set:
            return None
        marcado = partida.marcadores.get(quien)
        if marcado is None:
            raise SinMarcadorError("En una partida de uno no hay a quién marcar.")
        if body.marked_player_id != str(marcado.value):
            raise NotYourMarkedPlayerError()
        return marcado

    async def _apuntar(
        self,
        partida: Partida,
        competicion: Competition,
        hoyo: int,
        body: SubmitHoleScoreBodyDTO,
        quien: UserId,
        marcado: UserId | None,
        llegada: datetime,
    ) -> None:
        acepta_raya = competicion.tournament_type == TournamentType.STABLEFORD
        tarjetas = partida.estados_de_tarjeta
        golpes = {
            (g.user_id, g.hoyo): g
            for g in await self._uow.golpes_de_partida.de_la_partida(partida.id)
        }

        def golpe_de(user_id: UserId) -> GolpeDePartida:
            return golpes.get((user_id, hoyo)) or GolpeDePartida.crear(
                partida.id, partida.round_id, partida.competition_id, user_id, hoyo, llegada
            )

        cambiados = []
        if "own_score" in body.model_fields_set and tarjetas[quien] == EstadoDeTarjeta.JUGANDO:
            propio = golpe_de(quien)
            propio.anotar_propio(body.own_score, acepta_raya, quien, llegada)
            cambiados.append(propio)
        if marcado is not None and tarjetas[marcado] == EstadoDeTarjeta.JUGANDO:
            suyo = golpe_de(marcado)
            suyo.anotar_del_marcador(body.marked_score, acepta_raya, quien, llegada)
            cambiados.append(suyo)
        for golpe in cambiados:
            await self._uow.golpes_de_partida.guardar(golpe)
