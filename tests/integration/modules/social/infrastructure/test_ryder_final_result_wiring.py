"""
La clasificacion final de una Ryder contra Postgres (tabla del 22 oct 2026, I):
el adaptador lee el leaderboard oficial y los equipos con las unidades de
trabajo reales, una tras otra sobre la misma sesion, y el aviso queda guardado.
"""

from datetime import timedelta
from uuid import uuid4

import pytest

from src.modules.competition.application.use_cases.clasificaciones_use_case import (
    ClasificacionGeneralUseCase,
)
from src.modules.competition.application.use_cases.get_leaderboard_use_case import (
    GetLeaderboardUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_unit_of_work import (
    SQLAlchemyCompetitionUnitOfWork,
)
from src.modules.social.application.use_cases.publish_competition_notices_use_case import (
    PublishCompetitionNoticesUseCase,
)
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.infrastructure.adapters.competition_activity_publisher import (
    CompetitionActivityPublisher,
)
from src.modules.social.infrastructure.persistence.sqlalchemy.activity_event_repository import (
    SQLAlchemyActivityEventRepository,
)
from src.modules.social.infrastructure.persistence.sqlalchemy.social_unit_of_work import (
    SQLAlchemySocialUnitOfWork,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork as SQLAlchemyUserUnitOfWork,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.play_mode import PlayMode
from tests.integration.modules.social.infrastructure.test_shared_games_repositories import (
    BASE_DATE,
    _campo,
    _jugador_de_partido,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _user(db_session, nombre: str) -> User:
    user = User.create(
        first_name=nombre,
        last_name="Ryder",
        email_str=f"ryder-{uuid4().hex[:8]}@example.com",
        plain_password="ValidPassword123!",
    )
    await SQLAlchemyUserRepository(db_session).save(user)
    await db_session.commit()
    return user


async def test_i_la_ryder_completada_deja_a_cada_uno_su_resultado(db_session):
    ana, luz = await _user(db_session, "Ana"), await _user(db_session, "Luz")
    campo = await _campo(db_session, ana.id)
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    ryder = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=ana.id,
        name=CompetitionName(f"Ryder {uuid4().hex[:6]}"),
        dates=DateRange(start_date=BASE_DATE, end_date=BASE_DATE + timedelta(days=2)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.SCRATCH,
        team_1_name="Europa",
        team_2_name="USA",
    )
    await uow.competitions.add(ryder)
    ronda = Round.create(
        competition_id=ryder.id,
        golf_course_id=campo.id,
        round_date=BASE_DATE,
        session_type=SessionType.MORNING,
        match_format=MatchFormat.SINGLES,
    )
    await uow.rounds.add(ronda)
    await db_session.commit()
    partido = Match.create(
        round_id=ronda.id,
        match_number=1,
        team_a_players=[_jugador_de_partido(ana.id)],
        team_b_players=[_jugador_de_partido(luz.id)],
    )
    partido.start()
    partido.complete({"winner": "A", "score": "3&2"})
    await uow.matches.add(partido)
    await uow.team_assignments.add(
        TeamAssignment.create(ryder.id, TeamAssignmentMode.MANUAL, [ana.id], [luz.id])
    )
    await db_session.commit()

    user_uow = SQLAlchemyUserUnitOfWork(db_session)
    publicador = CompetitionActivityPublisher(
        PublishCompetitionNoticesUseCase(SQLAlchemySocialUnitOfWork(db_session), user_uow),
        ClasificacionGeneralUseCase(uow=uow, user_repository=user_uow.users),
        uow,
        ryder_scoreboard=GetLeaderboardUseCase(uow, user_uow.users, ScoringService()),
    )

    await publicador.completed(ryder)

    eventos = SQLAlchemyActivityEventRepository(db_session)
    for user, bando, desenlace in ((ana, "A", "WON"), (luz, "B", "LOST")):
        (evento,) = await eventos.find_in(
            [ActivitySlice(user_ids=(user.id,), types=frozenset(ActivityEventType))], 10
        )
        assert evento.type == ActivityEventType.TOURNAMENT_FINAL_STANDING
        assert evento.payload["tournament_type"] == "RYDER_CUP"
        assert (evento.payload["team_a_name"], evento.payload["team_b_name"]) == ("Europa", "USA")
        assert (evento.payload["team_a_points"], evento.payload["team_b_points"]) == (1.0, 0.0)
        assert (evento.payload["my_team"], evento.payload["outcome"]) == (bando, desenlace)
