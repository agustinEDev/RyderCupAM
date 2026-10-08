"""Las plazas en franjas, en memoria (tests)."""

from src.modules.competition.domain.entities.plaza_en_franja import PlazaEnFranja
from src.modules.competition.domain.repositories.plaza_en_franja_repository_interface import (
    PlazaEnFranjaRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


class InMemoryPlazaEnFranjaRepository(PlazaEnFranjaRepositoryInterface):
    def __init__(self):
        self._plazas: list[PlazaEnFranja] = []

    async def add(self, plaza: PlazaEnFranja) -> None:
        if any(p.round_id == plaza.round_id and p.user_id == plaza.user_id for p in self._plazas):
            raise ValueError("Ya tiene plaza en esa franja")
        self._plazas.append(plaza)

    async def quitar(self, round_id: RoundId, user_id: UserId) -> None:
        self._plazas = [
            p for p in self._plazas if not (p.round_id == round_id and p.user_id == user_id)
        ]

    async def quitar_del_jugador(self, competition_id: CompetitionId, user_id: UserId) -> None:
        self._plazas = [
            p
            for p in self._plazas
            if not (p.competition_id == competition_id and p.user_id == user_id)
        ]

    async def de_la_competicion(self, competition_id: CompetitionId) -> list[PlazaEnFranja]:
        return [p for p in self._plazas if p.competition_id == competition_id]
