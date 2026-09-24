"""
Tests de integración del repositorio de la sala de draft (FE #653).

Las elecciones viajan como JSONB en la misma fila de la sala, y eso no lo
ejercita ningún test en memoria: allí el repositorio guarda el objeto Python
tal cual. Aquí se comprueba contra PostgreSQL que una sala a medias vuelve
entera —con su turno, su reloj y sus elecciones en orden—, que la fila es una
por competición, y que la lectura con bloqueo devuelve lo que hay guardado y no
lo que la sesión tenía en memoria, que es de lo que depende no elegir dos veces
en el mismo turno.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.draft import Draft
from src.modules.competition.domain.services.snake_draft_service import PlayerForDraft
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.draft_status import DraftStatus
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_repository import (
    SQLAlchemyCompetitionRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.draft_repository import (
    SQLAlchemyDraftRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode

pytestmark = [pytest.mark.integration]

BASE_DATE = date(2026, 6, 1)
AHORA = datetime(2030, 6, 1, 10, 0, 0)


async def _insert_user(db_session, user_id: UserId) -> None:
    """Fila mínima de usuario: las claves ajenas de la sala la exigen."""
    now = datetime.now(UTC).replace(tzinfo=None)
    await db_session.execute(
        text(
            "INSERT INTO users (id, first_name, last_name, email, password, "
            "created_at, updated_at, email_verified, failed_login_attempts, is_admin) "
            "VALUES (:id, :fn, :ln, :email, :pw, :ca, :ua, :ev, :fla, :ia)"
        ),
        {
            "id": str(user_id.value),
            "fn": "Test",
            "ln": "Player",
            "email": f"draft-{user_id.value}@example.com",
            "pw": "$2b$04$placeholder",
            "ca": now,
            "ua": now,
            "ev": False,
            "fla": 0,
            "ia": False,
        },
    )


@pytest_asyncio.fixture
async def capitanes(db_session) -> tuple[UserId, UserId]:
    ana, bea = UserId.generate(), UserId.generate()
    await _insert_user(db_session, ana)
    await _insert_user(db_session, bea)
    return ana, bea


@pytest_asyncio.fixture
async def competition_id(db_session, capitanes) -> CompetitionId:
    competition = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=capitanes[0],
        name=CompetitionName(f"Draft Cup {uuid4().hex[:6]}"),
        dates=DateRange(start_date=BASE_DATE, end_date=BASE_DATE + timedelta(days=5)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.SCRATCH,
        team_1_name="Team A",
        team_2_name="Team B",
    )
    await SQLAlchemyCompetitionRepository(db_session).add(competition)
    await db_session.commit()
    return competition.id


@pytest_asyncio.fixture
async def elegibles(db_session) -> list[PlayerForDraft]:
    jugadores = []
    for handicap in ("5.0", "12.0", "18.0", "24.0"):
        user_id = UserId.generate()
        await _insert_user(db_session, user_id)
        jugadores.append(PlayerForDraft(user_id=user_id, handicap=Decimal(handicap)))
    await db_session.commit()
    return jugadores


async def _sala_guardada(db_session, competition_id, capitanes) -> Draft:
    draft = Draft.create(
        competition_id=competition_id,
        team_a_captain_id=capitanes[0],
        team_b_captain_id=capitanes[1],
    )
    draft.start(first_pick="A", ahora=AHORA)
    await SQLAlchemyDraftRepository(db_session).add(draft)
    await db_session.commit()
    return draft


class TestGuardarYLeerLaSala:
    async def test_una_sala_a_medias_vuelve_entera(
        self, db_session, competition_id, capitanes, elegibles
    ):
        """
        Given: una sala con dos elecciones, una a mano y otra de la aplicación
        When: se vuelve a leer de la base de datos
        Then: vuelven el turno, el reloj y las dos elecciones en orden
        """
        repo = SQLAlchemyDraftRepository(db_session)
        draft = await _sala_guardada(db_session, competition_id, capitanes)
        draft.pick(elegibles[1].user_id, elegibles, AHORA + timedelta(seconds=30))
        draft.pick_for_expired_turn(elegibles, AHORA + timedelta(seconds=90))
        await repo.update(draft)
        await db_session.commit()
        db_session.expunge_all()

        leida = await repo.find_by_competition(competition_id)

        assert leida.status == DraftStatus.IN_PROGRESS
        assert leida.first_pick == "A"
        assert leida.current_team == "A"
        assert leida.turn_started_at == AHORA + timedelta(seconds=90)
        assert [(p.user_id, p.team, p.order, p.automatic) for p in leida.picks] == [
            (elegibles[1].user_id, "A", 1, False),
            (elegibles[0].user_id, "B", 2, True),
        ]

    async def test_una_sala_terminada_conserva_sus_equipos(
        self, db_session, competition_id, capitanes, elegibles
    ):
        """Los equipos salen de las elecciones: si no vuelven, el draft se pierde."""
        repo = SQLAlchemyDraftRepository(db_session)
        draft = await _sala_guardada(db_session, competition_id, capitanes)
        # El último no se elige: entra solo al elegir el penúltimo
        for jugador in elegibles[:-1]:
            draft.pick(jugador.user_id, elegibles, AHORA)
        await repo.update(draft)
        await db_session.commit()
        db_session.expunge_all()

        leida = await repo.find_by_competition(competition_id)

        assert leida.status == DraftStatus.COMPLETED
        assert leida.current_team is None
        assert leida.turn_started_at is None
        assert leida.teams() == draft.teams()
        assert (leida.picks[-1].last_remaining, leida.picks[-1].automatic) == (True, False)

    async def test_sin_sala_devuelve_none(self, db_session, competition_id):
        repo = SQLAlchemyDraftRepository(db_session)

        assert await repo.find_by_competition(competition_id) is None

    async def test_la_lectura_con_bloqueo_trae_lo_guardado(
        self, db_session, competition_id, capitanes, elegibles
    ):
        """
        No basta con `with_for_update()`: sin `populate_existing`, SQLAlchemy
        devuelve el objeto que ya tenía en la sesión y la fila bloqueada se
        lee para nada. Eso es exactamente lo que dejaría elegir dos veces en el
        mismo turno.
        """
        repo = SQLAlchemyDraftRepository(db_session)
        await _sala_guardada(db_session, competition_id, capitanes)
        # Otra sesión elige: se simula escribiendo la fila por SQL directo
        await db_session.execute(
            text("UPDATE drafts SET current_team = 'B' WHERE competition_id = :cid"),
            {"cid": str(competition_id.value)},
        )
        await db_session.commit()

        bloqueada = await repo.find_by_competition_for_update(competition_id)

        assert bloqueada.current_team == "B"

    async def test_una_sola_sala_por_competicion(self, db_session, competition_id, capitanes):
        """Dos salas de la misma competición serían dos draft a la vez."""
        await _sala_guardada(db_session, competition_id, capitanes)
        otra = Draft.create(
            competition_id=competition_id,
            team_a_captain_id=capitanes[0],
            team_b_captain_id=capitanes[1],
        )

        with pytest.raises(Exception, match="(?i)unique|duplicate"):
            await SQLAlchemyDraftRepository(db_session).add(otra)
            await db_session.commit()
