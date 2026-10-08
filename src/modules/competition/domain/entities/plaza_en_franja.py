"""PlazaEnFranja - La plaza de un jugador en una franja de stroke play (#251)."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from src.modules.user.domain.value_objects.user_id import UserId

from ..value_objects.competition_id import CompetitionId
from ..value_objects.round_id import RoundId


@dataclass(frozen=True)
class PlazaEnFranja:
    """Un jugador con plaza en una franja."""

    id: uuid.UUID
    competition_id: CompetitionId
    round_id: RoundId
    user_id: UserId
    creada: datetime

    @classmethod
    def crear(
        cls, competition_id: CompetitionId, round_id: RoundId, user_id: UserId, momento: datetime
    ) -> "PlazaEnFranja":
        return cls(uuid.uuid4(), competition_id, round_id, user_id, momento)
