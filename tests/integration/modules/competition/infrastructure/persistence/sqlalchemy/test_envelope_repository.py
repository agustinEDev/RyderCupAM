"""
Tests de integración del repositorio de sobres (FE #655).

Las filas del sobre viajan como JSONB —una lista de listas de UUID— y eso no lo
ejercita ningún test en memoria: allí el repositorio guarda el objeto Python tal
cual. Aquí se comprueba contra PostgreSQL que el ORDEN vuelve intacto, que es
todo el dato, y que no puede haber dos sobres del mismo equipo para la misma
sesión.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.envelope import Envelope
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_repository import (
    SQLAlchemyCompetitionRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.envelope_repository import (
    SQLAlchemyEnvelopeRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.round_repository import (
    SQLAlchemyRoundRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode

pytestmark = [pytest.mark.integration]

BASE_DATE = date(2026, 6, 1)
AHORA = datetime(2030, 6, 1, 10, 0, 0)


async def _insert_user(db_session, user_id: UserId) -> None:
    """Fila mínima de usuario: la clave ajena del sobre la exige."""
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
            "email": f"envelope-{user_id.value}@example.com",
            "pw": "$2b$04$placeholder",
            "ca": now,
            "ua": now,
            "ev": False,
            "fla": 0,
            "ia": False,
        },
    )


@pytest_asyncio.fixture
async def jugadores(db_session) -> list[UserId]:
    ids = [UserId.generate() for _ in range(4)]
    for user_id in ids:
        await _insert_user(db_session, user_id)
    await db_session.commit()
    return ids


@pytest_asyncio.fixture
async def ronda(db_session, jugadores) -> Round:
    """Una competición con una sesión de parejas, que es el caso con más enjundia."""
    competition = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=jugadores[0],
        name=CompetitionName(f"Envelope Cup {uuid4().hex[:6]}"),
        dates=DateRange(start_date=BASE_DATE, end_date=BASE_DATE + timedelta(days=5)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.SCRATCH,
        team_1_name="Team A",
        team_2_name="Team B",
    )
    await SQLAlchemyCompetitionRepository(db_session).add(competition)
    await db_session.commit()

    # El campo tiene que existir: la ronda lo exige por clave ajena
    golf_course_id = uuid4()
    await db_session.execute(
        text(
            "INSERT INTO golf_courses (id, name, country_code, course_type, creator_id, "
            "approval_status, physical_holes, is_pending_update, created_at, updated_at) "
            "VALUES (:id, :n, :c, :t, :cr, :s, :ph, false, :ca, :ua)"
        ),
        {
            "id": str(golf_course_id),
            "n": f"Campo {uuid4().hex[:6]}",
            "c": "ES",
            "t": "STANDARD_18",
            "cr": str(jugadores[0].value),
            "s": "APPROVED",
            "ph": 18,
            "ca": AHORA,
            "ua": AHORA,
        },
    )
    from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId

    entidad = Round.create(
        competition_id=competition.id,
        golf_course_id=GolfCourseId(golf_course_id),
        round_date=BASE_DATE,
        session_type=SessionType.MORNING,
        match_format=MatchFormat.FOURBALL,
    )
    await SQLAlchemyRoundRepository(db_session).add(entidad)
    await db_session.commit()
    return entidad


class TestGuardarYLeerElSobre:
    async def test_el_orden_de_las_parejas_vuelve_intacto(self, db_session, ronda, jugadores):
        """
        Given: un sobre de parejas entregado por el capitán
        When: se vuelve a leer de la base de datos
        Then: vuelven las mismas parejas, en el mismo orden y con quién lo entregó
        """
        repo = SQLAlchemyEnvelopeRepository(db_session)
        sobre = Envelope.create(
            competition_id=ronda.competition_id,
            round_id=ronda.id,
            team="A",
            match_format=MatchFormat.FOURBALL,
        )
        sobre.submit(
            [[jugadores[2], jugadores[0]], [jugadores[3], jugadores[1]]],
            equipo=jugadores,
            por=jugadores[0],
            ahora=AHORA,
        )
        await repo.add(sobre)
        await db_session.commit()
        db_session.expunge_all()

        leido = await repo.find_by_round_and_team(ronda.id, "A")

        assert leido.entries == (
            (jugadores[2], jugadores[0]),
            (jugadores[3], jugadores[1]),
        )
        assert leido.submitted_by == jugadores[0]
        assert leido.submitted_at == AHORA
        assert leido.automatic is False
        assert leido.is_sealed() is True

    async def test_uno_abierto_vuelve_abierto(self, db_session, ronda, jugadores):
        repo = SQLAlchemyEnvelopeRepository(db_session)
        sobre = Envelope.create(
            competition_id=ronda.competition_id,
            round_id=ronda.id,
            team="B",
            match_format=MatchFormat.FOURBALL,
        )
        sobre.fill([(uid, i) for i, uid in enumerate(jugadores)], ahora=AHORA)
        sobre.reveal()
        await repo.add(sobre)
        await db_session.commit()
        db_session.expunge_all()

        leido = await repo.find_by_round_and_team(ronda.id, "B")

        assert leido.is_sealed() is False
        assert leido.automatic is True
        assert leido.submitted_by is None

    async def test_los_dos_de_una_sesion_se_leen_juntos(self, db_session, ronda, jugadores):
        repo = SQLAlchemyEnvelopeRepository(db_session)
        for team in ("A", "B"):
            sobre = Envelope.create(
                competition_id=ronda.competition_id,
                round_id=ronda.id,
                team=team,
                match_format=MatchFormat.FOURBALL,
            )
            sobre.submit(
                [[jugadores[0], jugadores[1]], [jugadores[2], jugadores[3]]],
                equipo=jugadores,
                por=jugadores[0],
                ahora=AHORA,
            )
            await repo.add(sobre)
        await db_session.commit()
        db_session.expunge_all()

        leidos = await repo.find_by_round(ronda.id)

        assert sorted(s.team for s in leidos) == ["A", "B"]

    async def test_no_hay_dos_sobres_del_mismo_equipo_para_una_sesion(
        self, db_session, ronda, jugadores
    ):
        """Serían dos listas a la vez para el mismo cruce, y nadie sabría cuál manda."""
        repo = SQLAlchemyEnvelopeRepository(db_session)
        for _ in range(2):
            sobre = Envelope.create(
                competition_id=ronda.competition_id,
                round_id=ronda.id,
                team="A",
                match_format=MatchFormat.FOURBALL,
            )
            sobre.submit(
                [[jugadores[0], jugadores[1]], [jugadores[2], jugadores[3]]],
                equipo=jugadores,
                por=jugadores[0],
                ahora=AHORA,
            )
            await repo.add(sobre)

        with pytest.raises(Exception, match="(?i)unique|duplicate"):
            await db_session.commit()

    async def test_la_lectura_con_bloqueo_trae_lo_guardado(self, db_session, ronda, jugadores):
        """Sin `populate_existing`, SQLAlchemy devuelve el objeto que ya tenía en
        la sesión y la fila bloqueada se lee para nada."""
        repo = SQLAlchemyEnvelopeRepository(db_session)
        sobre = Envelope.create(
            competition_id=ronda.competition_id,
            round_id=ronda.id,
            team="A",
            match_format=MatchFormat.FOURBALL,
        )
        sobre.submit(
            [[jugadores[0], jugadores[1]], [jugadores[2], jugadores[3]]],
            equipo=jugadores,
            por=jugadores[0],
            ahora=AHORA,
        )
        await repo.add(sobre)
        await db_session.commit()
        await db_session.execute(
            text("UPDATE envelopes SET revealed = true WHERE round_id = :rid AND team = 'A'"),
            {"rid": str(ronda.id.value)},
        )
        await db_session.commit()

        bloqueado = await repo.find_by_round_and_team_for_update(ronda.id, "A")

        assert bloqueado.is_sealed() is False

    async def test_los_dos_se_borran_juntos(self, db_session, ronda, jugadores):
        """Rehacer los sobres borra los DOS de una vez (FE #655).

        Visto en el Kind el 23 sep: al confirmar «Rehacer los sobres» el
        servidor devolvía un 503. Para vaciar la sesión, SQLAlchemy ordena por
        clave primaria los objetos que va a borrar, y `EnvelopeId` no se podía
        comparar con otro `EnvelopeId`, así que reventaba con
        `InvalidRequestError`. Con un solo sobre no hay nada que ordenar y no
        se notaba: ni los tests en memoria ni los de aquí lo tocaban.
        """
        repo = SQLAlchemyEnvelopeRepository(db_session)
        for team in ("A", "B"):
            sobre = Envelope.create(
                competition_id=ronda.competition_id,
                round_id=ronda.id,
                team=team,
                match_format=MatchFormat.SINGLES,
            )
            sobre.submit(
                [[jugadores[0]], [jugadores[1]], [jugadores[2]], [jugadores[3]]],
                equipo=jugadores,
                por=jugadores[0],
                ahora=AHORA,
            )
            await repo.add(sobre)
        await db_session.commit()

        await repo.delete_by_round(ronda.id)
        await db_session.commit()
        db_session.expunge_all()

        assert await repo.find_by_round(ronda.id) == []
