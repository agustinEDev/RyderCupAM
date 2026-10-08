"""Las listas de espera, en memoria (tests)."""

from src.modules.competition.domain.entities.espera_en_franja import EsperaEnFranja
from src.modules.competition.domain.repositories.espera_en_franja_repository_interface import (
    EsperaEnFranjaRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


class InMemoryEsperaEnFranjaRepository(EsperaEnFranjaRepositoryInterface):
    def __init__(self):
        self._esperas: list[EsperaEnFranja] = []

    async def add(self, espera: EsperaEnFranja) -> None:
        if any(
            e.round_id == espera.round_id and e.user_id == espera.user_id for e in self._esperas
        ):
            raise ValueError("Ya espera en esa franja")
        self._esperas.append(espera)

    async def quitar(self, round_id: RoundId, user_id: UserId) -> None:
        self._esperas = [
            e for e in self._esperas if not (e.round_id == round_id and e.user_id == user_id)
        ]

    async def de_la_competicion(self, competition_id: CompetitionId) -> list[EsperaEnFranja]:
        return [e for e in self._esperas if e.competition_id == competition_id]

    async def vaciar(self, competition_id: CompetitionId) -> None:
        self._esperas = [e for e in self._esperas if e.competition_id != competition_id]
