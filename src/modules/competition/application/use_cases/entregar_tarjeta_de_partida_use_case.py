"""
Casos de Uso: Entregar la tarjeta y retirarse de una partida (#251, PR 5).

Decidido con Agustín el 9 oct 2026:

- **Entregar es obligatorio** (P3): la firma de la tarjeta, como en un club. La
  partida acaba cuando no queda ninguna en juego.
- **No se entrega con hoyos sin validar** (P4): faltan, o jugador y marcador no
  coinciden. Se dice cuáles; los arregla el organizador si hace falta.
- **Retirarse** (P6): en Medal es NR; en Stableford cuenta lo jugado.

Con la partida bloqueada, como al anotar: un golpe del marcador que llega
mientras se entrega no se cuela después.
"""

from uuid import UUID

from src.modules.competition.application.exceptions import PartidaNotFoundError
from src.modules.competition.application.use_cases.anotar_hoyo_de_partida_use_case import (
    NoEsDeLaPartidaError,
)
from src.modules.competition.domain.entities.partida import Partida, PartidaNoEmpezadaError
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.jugador_de_partida import HOYOS
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.user.domain.value_objects.user_id import UserId


class TarjetaIncompletaError(Exception):
    """Quedan hoyos sin validar: no se entrega (P4)."""

    error_code = "SCORECARD_NOT_READY"

    def __init__(self, hoyos: list[int]):
        self.hoyos = hoyos
        super().__init__(f"Hoyos sin validar: {hoyos}")


async def _bloqueada(uow: CompetitionUnitOfWorkInterface, group_id: UUID, quien: UserId) -> Partida:
    partida = await uow.partidas.find_by_id_for_update(PartidaId(group_id))
    if partida is None:
        raise PartidaNotFoundError(f"No existe la partida {group_id}")
    if quien not in partida.user_ids:
        raise NoEsDeLaPartidaError("No juegas esta partida.")
    return partida


class EntregarTarjetaDePartidaUseCase:
    """El jugador entrega su tarjeta, con los 18 hoyos validados."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, group_id: UUID, quien: UserId) -> None:
        """
        Raises:
            PartidaNotFoundError, NoEsDeLaPartidaError
            TarjetaIncompletaError: Con los hoyos sin validar (P4)
            PartidaNoEmpezadaError, TarjetaCerradaError
        """
        async with self._uow:
            partida = await _bloqueada(self._uow, group_id, quien)
            # Primero si se puede entregar; después qué falta
            if not partida.empezada:
                raise PartidaNoEmpezadaError("La partida aún no ha empezado.")
            validados = {
                g.hoyo
                for g in await self._uow.golpes_de_partida.de_la_partida(partida.id)
                if g.user_id == quien and g.validado
            }
            faltan = [hoyo for hoyo in range(1, HOYOS + 1) if hoyo not in validados]
            if faltan:
                raise TarjetaIncompletaError(faltan)
            partida.entregar(quien)
            await self._uow.partidas.guardar([partida])


class RetirarseDePartidaUseCase:
    """El jugador lo deja a medias (P6)."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, group_id: UUID, quien: UserId) -> None:
        """
        Raises:
            PartidaNotFoundError, NoEsDeLaPartidaError
            PartidaNoEmpezadaError, TarjetaCerradaError
        """
        async with self._uow:
            partida = await _bloqueada(self._uow, group_id, quien)
            partida.retirar(quien)
            await self._uow.partidas.guardar([partida])
