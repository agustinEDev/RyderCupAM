"""
Casos de Uso: Lo que hace el organizador con la anotación de las partidas (#251, PR 5).

Decidido con Agustín (decisión 11 de la #251 y P3, P4, P6, P9, P11 el 9 oct 2026):

- **Corregir un hoyo**: mete el lado del jugador, el del marcador o los dos;
  así resuelve un desacuerdo (P4) y hace de marcador en una partida de uno
  (P11). Queda registrado que lo metió él (P9). Una tarjeta cerrada se reabre
  antes, a propósito: que la corrección se vea.
- **Reabrir una tarjeta** (P9) y **marcar a alguien como no presentado** (P6).
- **Cerrar la franja**, la red (P3): las tarjetas aún en juego quedan
  entregadas si están completas, no presentado si no tienen ningún hoyo
  validado, y retirado si van a medias.

Solo el organizador o un admin, con la partida bloqueada.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from src.modules.competition.application.dto.partidas_dto import (
    CorrectHoleBodyDTO,
    TeeGroupsResponseDTO,
)
from src.modules.competition.application.exceptions import (
    InvalidHoleNumberError,
    NotCompetitionCreatorError,
    PartidaNotFoundError,
    RoundNotFoundError,
)
from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.application.services.vista_de_la_franja import vista_de_la_franja
from src.modules.competition.application.use_cases.anotar_hoyo_de_partida_use_case import (
    PartidaNoAnotableError,
    arrancar_la_competicion,
    comprobar_que_abrio,
    comprobar_que_abrio_la_franja,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.golpe_de_partida import (
    PRIMER_HOYO,
    ULTIMO_HOYO,
    GolpeDePartida,
)
from src.modules.competition.domain.entities.partida import Partida, TarjetaCerradaError
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.estado_de_tarjeta import EstadoDeTarjeta
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.competition.domain.value_objects.jugador_de_partida import HOYOS
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


async def _del_organizador(
    uow: CompetitionUnitOfWorkInterface, group_id: UUID, quien: UserId, is_admin: bool
) -> tuple[Partida, Competition]:
    """La partida y su competición, si quien pide la organiza. Sin bloquear aún."""
    partida = await uow.partidas.find_by_id(PartidaId(group_id))
    if partida is None:
        raise PartidaNotFoundError(f"No existe la partida {group_id}")
    competicion = await uow.competitions.find_by_id(partida.competition_id)
    if competicion is None:
        raise PartidaNotFoundError(f"No existe la partida {group_id}")
    if not (is_admin or competicion.is_creator(quien)):
        raise NotCompetitionCreatorError("Solo el organizador corrige la anotación")
    return partida, competicion


async def _bloqueada(uow: CompetitionUnitOfWorkInterface, partida: Partida) -> Partida:
    bloqueada = await uow.partidas.find_by_id_for_update(partida.id)
    if bloqueada is None:
        raise PartidaNotFoundError(f"No existe la partida {partida.id}")
    return bloqueada


def _del_jugador(partida: Partida, user_id: UUID) -> UserId:
    jugador = UserId(user_id)
    if jugador not in partida.user_ids:
        raise PartidaNotFoundError("Ese jugador no está en la partida")
    return jugador


class CorregirHoyoDePartidaUseCase:
    """El organizador mete uno o los dos lados de un hoyo de un jugador."""

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
        self,
        group_id: UUID,
        user_id: UUID,
        hoyo: int,
        body: CorrectHoleBodyDTO,
        quien: UserId,
        is_admin: bool,
    ) -> None:
        """
        Raises:
            PartidaNotFoundError, NotCompetitionCreatorError, InvalidHoleNumberError
            PartidaNoAnotableError, ScoringNotOpenYetError, RayaNoPermitidaError
            TarjetaCerradaError: Si su tarjeta está cerrada: se reabre antes
        """
        llegada = self._reloj()
        if not PRIMER_HOYO <= hoyo <= ULTIMO_HOYO:
            raise InvalidHoleNumberError(f"Hoyo invalido: {hoyo}")
        async with self._uow:
            partida, competicion = await _del_organizador(self._uow, group_id, quien, is_admin)
            jugador = _del_jugador(partida, user_id)
            if competicion.status not in (CompetitionStatus.CLOSED, CompetitionStatus.IN_PROGRESS):
                raise PartidaNoAnotableError("Esta competición no está en juego.")
            await comprobar_que_abrio(self._uow, self._zonas, partida, llegada)
            acepta_raya = competicion.tournament_type == TournamentType.STABLEFORD
            for campo in ("own_score", "marker_score"):
                if campo in body.model_fields_set:
                    GolpeDePartida.comprobar(getattr(body, campo), acepta_raya)

            if competicion.status == CompetitionStatus.CLOSED:
                await arrancar_la_competicion(self._uow, competicion)
            bloqueada = await _bloqueada(self._uow, partida)
            if bloqueada.estados_de_tarjeta[jugador] != EstadoDeTarjeta.JUGANDO:
                raise TarjetaCerradaError("Esa tarjeta está cerrada: reábrela para corregirla.")
            if bloqueada.estado == EstadoPartida.SCHEDULED:
                bloqueada.empezar()
                await self._uow.partidas.guardar([bloqueada])

            golpe = next(
                (
                    g
                    for g in await self._uow.golpes_de_partida.de_la_partida(bloqueada.id)
                    if g.user_id == jugador and g.hoyo == hoyo
                ),
                None,
            ) or GolpeDePartida.crear(
                bloqueada.id, bloqueada.round_id, bloqueada.competition_id, jugador, hoyo, llegada
            )
            if "own_score" in body.model_fields_set:
                golpe.anotar_propio(body.own_score, acepta_raya, quien, llegada)
            if "marker_score" in body.model_fields_set:
                golpe.anotar_del_marcador(body.marker_score, acepta_raya, quien, llegada)
            await self._uow.golpes_de_partida.guardar(golpe)


class ReabrirTarjetaUseCase:
    """El organizador vuelve a abrir una tarjeta cerrada para corregirla (P9)."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, group_id: UUID, user_id: UUID, quien: UserId, is_admin: bool) -> None:
        async with self._uow:
            partida, _ = await _del_organizador(self._uow, group_id, quien, is_admin)
            bloqueada = await _bloqueada(self._uow, partida)
            bloqueada.reabrir_tarjeta(_del_jugador(bloqueada, user_id))
            await self._uow.partidas.guardar([bloqueada])


class MarcarNoPresentadoUseCase:
    """El organizador marca a alguien como no presentado (P6)."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, group_id: UUID, user_id: UUID, quien: UserId, is_admin: bool) -> None:
        async with self._uow:
            partida, _ = await _del_organizador(self._uow, group_id, quien, is_admin)
            bloqueada = await _bloqueada(self._uow, partida)
            bloqueada.no_presentado(_del_jugador(bloqueada, user_id))
            await self._uow.partidas.guardar([bloqueada])


class CerrarFranjaUseCase:
    """El organizador cierra todas las partidas sin acabar de una franja (P3)."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        zonas: ICompetitionTimezone,
        user_repository: UserRepositoryInterface,
        reloj: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._uow = uow
        self._zonas = zonas
        self._usuarios = user_repository
        self._reloj = reloj

    async def execute(self, round_id: UUID, quien: UserId, is_admin: bool) -> TeeGroupsResponseDTO:
        """
        Raises:
            RoundNotFoundError, NotCompetitionCreatorError
            ScoringNotOpenYetError: Antes de su primera salida: se cerraría con
                todos no presentados y la franja ya no podría rehacerse
            PartidaNoAnotableError: Con la competición sin jugarse
        """
        llegada = self._reloj()
        async with self._uow:
            franja = await self._uow.rounds.find_by_id(RoundId(round_id))
            if franja is None or franja.hoja_de_salidas is None:
                raise RoundNotFoundError(f"No existe la franja {round_id}")
            competicion = await self._uow.competitions.find_by_id_for_update(franja.competition_id)
            if competicion is None:
                raise RoundNotFoundError(f"No existe la franja {round_id}")
            if not (is_admin or competicion.is_creator(quien)):
                raise NotCompetitionCreatorError("Solo el organizador cierra la franja")
            if competicion.status not in (CompetitionStatus.CLOSED, CompetitionStatus.IN_PROGRESS):
                raise PartidaNoAnotableError("Esta competición no está en juego.")
            await comprobar_que_abrio_la_franja(franja, self._zonas, llegada)
            # Cada partida, bloqueada antes de decidir, y los golpes leídos
            # después: anotar, entregar o retirarse bloquean la partida, y sin
            # esto un 18 anotado a la vez quedaría como retirado
            partidas = [
                bloqueada
                for p in await self._uow.partidas.de_la_franja(franja.id)
                if (bloqueada := await self._uow.partidas.find_by_id_for_update(p.id))
            ]
            golpes = await self._uow.golpes_de_partida.de_la_franja(franja.id)
            validados: dict[UserId, int] = {}
            for golpe in golpes:
                if golpe.validado:
                    validados[golpe.user_id] = validados.get(golpe.user_id, 0) + 1
            sin_acabar = [p for p in partidas if p.estado != EstadoPartida.COMPLETED]
            for partida in sin_acabar:
                partida.cerrar(
                    completas={u for u in partida.user_ids if validados.get(u, 0) == HOYOS},
                    sin_hoyos={u for u in partida.user_ids if validados.get(u, 0) == 0},
                )
            await self._uow.partidas.guardar(sin_acabar)
            return await vista_de_la_franja(
                self._uow, competicion, franja, partidas, self._zonas, self._usuarios, llegada
            )
