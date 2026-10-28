"""Las partidas de stroke play, en memoria para los tests (#251, PR 4)."""

from collections.abc import Sequence
from copy import deepcopy

from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.repositories.partida_repository_interface import (
    PartidaRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


class InMemoryPartidaRepository(PartidaRepositoryInterface):
    """
    Guarda y devuelve copias, como una base de datos: un caso de uso que cambia
    una partida y no la guarda se nota en los tests.
    """

    def __init__(self):
        self._partidas: dict[PartidaId, Partida] = {}

    async def reemplazar_franja(self, round_id: RoundId, partidas: Sequence[Partida]) -> None:
        self._partidas = {i: p for i, p in self._partidas.items() if p.round_id != round_id}
        for partida in partidas:
            self._partidas[partida.id] = deepcopy(partida)

    async def anadir(self, partidas: Sequence[Partida]) -> None:
        for partida in partidas:
            self._partidas[partida.id] = deepcopy(partida)

    async def guardar(self, partidas: Sequence[Partida]) -> None:
        for partida in partidas:
            if partida.id in self._partidas:
                self._partidas[partida.id] = deepcopy(partida)

    async def borrar(self, partidas: Sequence[Partida]) -> None:
        for partida in partidas:
            self._partidas.pop(partida.id, None)

    async def find_by_id(self, partida_id: PartidaId) -> Partida | None:
        partida = self._partidas.get(partida_id)
        return deepcopy(partida) if partida else None

    async def find_by_id_for_update(self, partida_id: PartidaId) -> Partida | None:
        # En memoria no hay transacciones concurrentes que bloquear
        return await self.find_by_id(partida_id)

    async def de_la_franja(self, round_id: RoundId) -> list[Partida]:
        return self._donde(lambda p: p.round_id == round_id)

    async def de_la_competicion(self, competition_id: CompetitionId) -> list[Partida]:
        return self._donde(lambda p: p.competition_id == competition_id)

    async def existe_en_la_competicion(self, competition_id: CompetitionId) -> bool:
        """Si la competición tiene alguna partida."""
        return bool(self._donde(lambda p: p.competition_id == competition_id))

    async def de_las_competiciones(self, competition_ids: list[CompetitionId]) -> list[Partida]:
        pedidas = set(competition_ids)
        return self._donde(lambda p: p.competition_id in pedidas)

    async def del_jugador(self, competition_id: CompetitionId, user_id: UserId) -> list[Partida]:
        return self._donde(lambda p: p.competition_id == competition_id and user_id in p.user_ids)

    async def existe_con_jugador(self, user_id: UserId) -> bool:
        return any(user_id in p.user_ids for p in self._partidas.values())

    def _donde(self, condicion) -> list[Partida]:
        """Por franja y número, como en Postgres."""
        return [
            deepcopy(p)
            for p in sorted(self._partidas.values(), key=lambda p: (str(p.round_id), p.numero))
            if condicion(p)
        ]

    async def competiciones_con_los_dos(
        self, user_id: UserId, other_id: UserId
    ) -> list[CompetitionId]:
        de_uno = {p.competition_id for p in self._donde(lambda p: user_id in p.user_ids)}
        del_otro = {p.competition_id for p in self._donde(lambda p: other_id in p.user_ids)}
        return list(de_uno & del_otro)

    async def con_los_dos(self, user_id: UserId, other_id: UserId) -> list[Partida]:
        return self._donde(lambda p: user_id in p.user_ids and other_id in p.user_ids)

    async def completadas_de_jugadores(self, user_ids: Sequence[UserId]) -> list[Partida]:
        buscados = set(user_ids)
        return self._donde(
            lambda p: p.estado == EstadoPartida.COMPLETED and bool(buscados & set(p.user_ids))
        )
