"""EsperaEnFranja - Un jugador en la lista de espera de una franja de stroke play (#251)."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from src.modules.user.domain.value_objects.user_id import UserId

from ..value_objects.competition_id import CompetitionId
from ..value_objects.round_id import RoundId


@dataclass(frozen=True)
class EsperaEnFranja:
    """Un jugador esperando plaza en una franja; el orden es el de llegada."""

    id: uuid.UUID
    competition_id: CompetitionId
    round_id: RoundId
    user_id: UserId
    creada: datetime

    @classmethod
    def crear(
        cls, competition_id: CompetitionId, round_id: RoundId, user_id: UserId, momento: datetime
    ) -> "EsperaEnFranja":
        """Una espera nueva, al final de la lista."""
        return cls(uuid.uuid4(), competition_id, round_id, user_id, momento)
