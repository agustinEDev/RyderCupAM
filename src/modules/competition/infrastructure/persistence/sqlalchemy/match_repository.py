"""Match Repository - SQLAlchemy Implementation."""

from collections.abc import Collection, Sequence

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

    async def find_by_id_for_update(self, match_id: MatchId) -> Match | None:
        """
        El partido con su fila bloqueada, para abrir la anotacion una sola vez.

        Dos jugadores mandando su primer golpe a la vez abririan el partido los
        dos y duplicarian los 18 hoyos por jugador, que `add_many` no deduplica
        (BE #305).
        """
        # `populate_existing` no es un adorno: sin el, SQLAlchemy devuelve el
        # objeto que ya tiene en su mapa de identidad —con el estado de antes del
        # bloqueo— y la guarda contra la doble apertura no se dispara nunca.
        # Mismo patron que `quick_match_repository`
        return await self._session.get(
            Match, match_id, with_for_update=True, populate_existing=True
        )

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

    async def find_by_rounds_for_player(
        self, round_ids: Sequence[RoundId], user_id: UserId
    ) -> list[Match]:
        if not round_ids:
            return []
        # Por contención, como `find_completed_for_player`
        jugador = cast([{"user_id": str(user_id.value)}], JSONB)
        statement = (
            select(Match)
            .where(matches_table.c.round_id.in_(list(round_ids)))
            .where(
                or_(
                    matches_table.c.team_a_players.op("@>")(jugador),
                    matches_table.c.team_b_players.op("@>")(jugador),
                )
            )
            .order_by(matches_table.c.match_number.asc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def find_by_round_for_update(self, round_id: RoundId) -> list[Match]:
        # `populate_existing`, como en `find_by_id_for_update`: sin el, un
        # partido ya cargado vuelve con el estado de antes del bloqueo
        statement = (
            select(Match)
            .where(Match._round_id == round_id)
            .order_by(Match._match_number.asc())
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def delete(self, match_id: MatchId) -> bool:
        match = await self.find_by_id(match_id)
        if match is None:
            return False
        await self._session.delete(match)
        return True

    async def find_with_both_players(
        self, user_id: UserId, other_id: UserId, statuses: Collection[MatchStatus]
    ) -> list[Match]:
        """Por contención (`@>`) en los dos bandos, como `find_completed_for_player`."""

        def juega(uid: UserId):
            jugador = cast([{"user_id": str(uid.value)}], JSONB)
            return or_(
                matches_table.c.team_a_players.op("@>")(jugador),
                matches_table.c.team_b_players.op("@>")(jugador),
            )

        statement = (
            select(Match)
            .where(juega(user_id))
            .where(juega(other_id))
            .where(matches_table.c.status.in_(list(statuses)))
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def find_finished_for_players(self, user_ids: Collection[UserId]) -> list[Match]:
        if not user_ids:
            return []
        alguno = or_(
            *[
                columna.op("@>")(cast([{"user_id": str(user_id.value)}], JSONB))
                for user_id in set(user_ids)
                for columna in (matches_table.c.team_a_players, matches_table.c.team_b_players)
            ]
        )
        acabados = [s for s in MatchStatus if s.is_finished()]
        statement = select(Match).where(alguno).where(matches_table.c.status.in_(acabados))
        result = await self._session.execute(statement)
        return list(result.scalars().all())
