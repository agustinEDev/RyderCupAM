"""Match Repository - SQLAlchemy Implementation."""

from sqlalchemy import cast, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.repositories.match_repository_interface import (
    MatchRepositoryInterface,
)
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.infrastructure.persistence.sqlalchemy.mappers import (
    matches_table,
    rounds_table,
)
from src.modules.user.domain.value_objects.user_id import UserId


class SQLAlchemyMatchRepository(MatchRepositoryInterface):
    """Implementacion asincrona del repositorio de partidos con SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, match: Match) -> None:
        self._session.add(match)

    async def update(self, match: Match) -> None:
        self._session.add(match)

    async def find_by_id(self, match_id: MatchId) -> Match | None:
        return await self._session.get(Match, match_id)

    async def find_completed_for_player(
        self, user_id: UserId, limit: int | None = None
    ) -> list[Match]:
        """
        Partidos terminados del jugador, del más reciente al más antiguo.

        Los jugadores viven en dos columnas JSONB (`team_a_players` y
        `team_b_players`), sin clave ajena, así que se buscan por contención
        (`@>`) igual que las partidas rápidas buscan a sus participantes.

        Ojo al rendimiento: esas columnas no tienen índice, de modo que esto
        recorre la tabla entera de partidos. Con el tamaño actual no supone
        nada; si `matches` crece, el sitio donde poner un índice GIN es este.

        La fecha sale de la ronda, no del partido: `matches` no guarda cuándo
        se jugó, solo cuándo se creó la fila.
        """
        player_in_match = or_(
            matches_table.c.team_a_players.op("@>")(cast([{"user_id": str(user_id.value)}], JSONB)),
            matches_table.c.team_b_players.op("@>")(cast([{"user_id": str(user_id.value)}], JSONB)),
        )

        statement = (
            select(Match)
            .join(rounds_table, matches_table.c.round_id == rounds_table.c.id)
            .where(player_in_match)
            .where(matches_table.c.status == MatchStatus.COMPLETED)
            .order_by(rounds_table.c.round_date.desc(), matches_table.c.match_number.asc())
        )
        if limit is not None:
            statement = statement.limit(limit)

        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def find_by_round(self, round_id: RoundId) -> list[Match]:
        statement = (
            select(Match).where(Match._round_id == round_id).order_by(Match._match_number.asc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def delete(self, match_id: MatchId) -> bool:
        match = await self.find_by_id(match_id)
        if match is None:
            return False
        await self._session.delete(match)
        return True
