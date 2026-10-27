"""
La clasificacion final de una Ryder, aviso SELF (tabla del 22 oct 2026, I).

| Caso                                        | Resultado                                    |
|---------------------------------------------|----------------------------------------------|
| 15½-12½ para Europa                         | Europa: WON 15½-12½; USA: LOST               |
| 14-14                                       | Los dos equipos: HALVED                      |
| Se reabre                                   | Se retira el aviso                           |
| Se reabre y se completa otra vez            | Sale el nuevo, uno solo por jugador          |
| Amigo de un jugador                         | No lo ve (SELF)                              |
| Sin jugadores en los equipos                | Nada                                         |

Es una variante de TOURNAMENT_FINAL_STANDING (`tournament_type: RYDER_CUP`):
reabrir, borrar el torneo y la unicidad por (jugador, torneo, tipo) ya la cubren.
"""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.social.application.use_cases.get_friends_feed_use_case import (
    GetFriendsFeedUseCase,
)
from src.modules.social.application.use_cases.publish_competition_notices_use_case import (
    PublishCompetitionNoticesUseCase,
    RyderResultRef,
    TournamentRef,
)
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)

pytestmark = pytest.mark.asyncio

T = ActivityEventType


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


@pytest.fixture
def user_uow():
    return InMemoryUserUnitOfWork()


@pytest.fixture
def avisos(social_uow, user_uow):
    return PublishCompetitionNoticesUseCase(social_uow, user_uow)


def _torneo() -> TournamentRef:
    return TournamentRef(
        competition_id=str(uuid4()),
        name="Ryder de Otoño",
        start_date=date(2027, 3, 3),
        end_date=date(2027, 3, 5),
        is_public=True,
    )


async def _user(user_uow) -> User:
    user = User.create(
        first_name="Juan",
        last_name="Lopez",
        email_str=f"ryder_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _de(social_uow, user: User):
    async with social_uow:
        return await social_uow.activity_events.find_in(
            [ActivitySlice(user_ids=(user.id,), types=frozenset(ActivityEventType))], limit=50
        )


def _resultado(europa, usa, puntos_europa: float, puntos_usa: float) -> RyderResultRef:
    return RyderResultRef(
        team_a_name="Europa",
        team_b_name="USA",
        team_a_points=puntos_europa,
        team_b_points=puntos_usa,
        team_a=tuple(u.id for u in europa),
        team_b=tuple(u.id for u in usa),
    )


class TestClasificacionFinalDeLaRyder:
    async def test_i7_cada_uno_gana_o_pierde_con_su_equipo(self, avisos, social_uow, user_uow):
        ana, eva, luz, mar = [await _user(user_uow) for _ in range(4)]
        torneo = _torneo()

        await avisos.ryder_final_result(torneo, _resultado([ana, eva], [luz, mar], 15.5, 12.5))

        (de_ana,) = await _de(social_uow, ana)
        assert de_ana.type == T.TOURNAMENT_FINAL_STANDING
        assert de_ana.source_match_id == torneo.competition_id
        assert de_ana.payload == {
            "competition_id": torneo.competition_id,
            "competition_name": "Ryder de Otoño",
            "start_date": "2027-03-03",
            "end_date": "2027-03-05",
            "tournament_type": "RYDER_CUP",
            "team_a_name": "Europa",
            "team_b_name": "USA",
            "team_a_points": 15.5,
            "team_b_points": 12.5,
            "my_team": "A",
            "outcome": "WON",
        }
        (de_eva,) = await _de(social_uow, eva)
        assert (de_eva.payload["my_team"], de_eva.payload["outcome"]) == ("A", "WON")
        for perdedor in (luz, mar):
            (evento,) = await _de(social_uow, perdedor)
            assert (evento.payload["my_team"], evento.payload["outcome"]) == ("B", "LOST")

    async def test_i7_gana_el_equipo_b(self, avisos, social_uow, user_uow):
        ana, luz = await _user(user_uow), await _user(user_uow)

        await avisos.ryder_final_result(_torneo(), _resultado([ana], [luz], 12.5, 15.5))

        assert (await _de(social_uow, ana))[0].payload["outcome"] == "LOST"
        assert (await _de(social_uow, luz))[0].payload["outcome"] == "WON"

    async def test_i7_empate_a_puntos_es_halved_para_los_dos(self, avisos, social_uow, user_uow):
        ana, luz = await _user(user_uow), await _user(user_uow)

        await avisos.ryder_final_result(_torneo(), _resultado([ana], [luz], 14.0, 14.0))

        for user in (ana, luz):
            (evento,) = await _de(social_uow, user)
            assert evento.payload["outcome"] == "HALVED"
            assert (evento.payload["team_a_points"], evento.payload["team_b_points"]) == (14, 14)

    async def test_i9_reabrir_lo_retira_y_completar_otra_vez_lo_vuelve_a_dar(
        self, avisos, social_uow, user_uow
    ):
        ana, luz = await _user(user_uow), await _user(user_uow)
        torneo = _torneo()
        await avisos.ryder_final_result(torneo, _resultado([ana], [luz], 15.5, 12.5))

        await avisos.reopened(torneo.competition_id)
        assert await _de(social_uow, ana) == []
        await avisos.ryder_final_result(torneo, _resultado([ana], [luz], 13.5, 14.5))

        (evento,) = await _de(social_uow, ana)
        assert evento.payload["outcome"] == "LOST"
        assert evento.payload["team_a_points"] == 13.5

    async def test_completar_dos_veces_sin_reabrir_deja_uno_solo(
        self, avisos, social_uow, user_uow
    ):
        ana, luz = await _user(user_uow), await _user(user_uow)
        torneo = _torneo()
        await avisos.ryder_final_result(torneo, _resultado([ana], [luz], 15.5, 12.5))

        await avisos.ryder_final_result(torneo, _resultado([ana], [luz], 14.0, 14.0))

        (evento,) = await _de(social_uow, ana)
        assert evento.payload["outcome"] == "HALVED"

    async def test_sus_amigos_tambien_lo_ven(self, avisos, social_uow, user_uow):
        """
        Tabla del 27 oct 2026, fila 10: la clasificación final la ven también
        sus amigos, y la de la Ryder es la misma (`TOURNAMENT_FINAL_STANDING`).
        """
        ana, luz, amigo = [await _user(user_uow) for _ in range(3)]
        amistad = Friendship.create(
            id=FriendshipId(uuid4()), requester_id=ana.id, addressee_id=amigo.id
        )
        amistad.accept()
        async with social_uow:
            await social_uow.friendships.add(amistad)

        await avisos.ryder_final_result(_torneo(), _resultado([ana], [luz], 15.5, 12.5))

        feed = await GetFriendsFeedUseCase(
            social_uow, user_uow, InMemoryGolfCourseUnitOfWork()
        ).execute(str(amigo.id.value))
        assert [(e.user_id, e.type) for e in feed.events] == [
            (str(ana.id.value), ActivityEventType.TOURNAMENT_FINAL_STANDING.value)
        ]

    async def test_sin_jugadores_no_publica_nada(self, avisos, social_uow, user_uow):
        ana = await _user(user_uow)

        await avisos.ryder_final_result(_torneo(), _resultado([], [], 0.0, 0.0))

        assert await _de(social_uow, ana) == []
