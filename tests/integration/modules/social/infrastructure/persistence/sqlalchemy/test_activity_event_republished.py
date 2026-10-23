"""
Tests de integracion: lo que se vuelve a publicar (decisiones de Agustin del
23 oct 2026, tras la release social 1).

1. El mismo logro (jugador, tipo y vuelta) conserva su fecha de publicacion:
   no sube ni cuenta como nuevo. Lo heredado por otra vuelta si es nuevo.
2. «Campo nuevo» y «primer torneo» heredados nacen ocultos si el que se
   retiro estaba oculto.
3. Lo oculto se recuerda por hoyo en birdie, eagle y hoyo en uno.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.infrastructure.persistence.sqlalchemy.activity_event_repository import (
    SQLAlchemyActivityEventRepository,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)
from src.shared.domain.utc_clock import utc_now

pytestmark = pytest.mark.integration

T = ActivityEventType
JUGADO = datetime(2026, 10, 12, 12, 0)
PRIMERA = datetime(2026, 10, 20, 9, 0)
DESPUES = datetime(2026, 10, 23, 9, 0)
TODOS = frozenset(ActivityEventType)


async def _user(db_session) -> User:
    user = User.create(
        first_name="Diego",
        last_name="Garcia",
        email_str=f"republish-{uuid4().hex[:8]}@example.com",
        plain_password="ValidPassword123!",
    )
    await SQLAlchemyUserRepository(db_session).save(user)
    await db_session.commit()
    return user


def _logro(
    user: User,
    tipo: ActivityEventType,
    origen: str,
    torneo: str = "torneo-1",
    *,
    visible: bool = True,
    publicado: datetime = PRIMERA,
    **extra,
) -> ActivityEvent:
    return ActivityEvent.create(
        user_id=user.id,
        type=tipo,
        occurred_at=JUGADO,
        source_match_id=origen,
        published_at=publicado,
        payload={"competition_id": torneo, "from_tournament": True, **extra},
        visible_to_friends=visible,
    )


async def _hoyos_apuntados(db_session, user: User) -> list:
    filas = await db_session.execute(
        text("SELECT hidden_holes FROM withdrawn_hidden_achievements WHERE user_id = :u"),
        {"u": str(user.id.value)},
    )
    return filas.scalars().all()


async def _eventos(repository, user: User) -> dict[tuple, ActivityEvent]:
    eventos = await repository.find_in([ActivitySlice(user_ids=(user.id,), types=TODOS)], 50)
    return {(e.type, e.source_match_id): e for e in eventos}


# ==================== La tarjeta no se parte ====================


class TestTheCardKeepsItsDate:
    """Hallazgo 2 del revisor: los logros de una vuelta, una tarjeta y una fecha."""

    async def test_a_new_one_next_to_one_that_kept_its_date_takes_that_date(self, db_session):
        """2.1: se vuelve a cerrar con el birdie de antes y un eagle nuevo."""
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1", holes=[4])])
        await repository.delete_for_competition("torneo-1", [T.BIRDIE])
        await db_session.commit()

        await repository.add_many(
            [
                _logro(diego, T.BIRDIE, "grupo-1", publicado=DESPUES, holes=[4]),
                _logro(diego, T.EAGLE_OR_BETTER, "grupo-1", publicado=DESPUES, holes=[9]),
            ]
        )
        await db_session.commit()

        eventos = await _eventos(repository, diego)
        assert eventos[(T.EAGLE_OR_BETTER, "grupo-1")].published_at == PRIMERA

    async def test_one_arriving_at_a_card_already_published_takes_its_date(self, db_session):
        """2.8: el «campo nuevo» heredado entra en la tarjeta que ya estaba."""
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many(
            [
                _logro(diego, T.BIRDIE, "grupo-1", holes=[4]),
                _logro(diego, T.BIRDIE, "grupo-2", publicado=PRIMERA + timedelta(days=1)),
            ]
        )
        await db_session.commit()

        await repository.add_many(
            [_logro(diego, T.NEW_COURSE, "grupo-1", publicado=DESPUES, golf_course_id="c-1")]
        )
        await db_session.commit()

        eventos = await _eventos(repository, diego)
        assert eventos[(T.NEW_COURSE, "grupo-1")].published_at == PRIMERA

    async def test_a_notice_from_the_same_origin_does_not_date_the_card(self, db_session):
        """El «como acabo» de una partida rapida comparte origen con sus logros."""
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many([_logro(diego, T.QUICK_MATCH_FINISHED, "partida-1")])
        await db_session.commit()

        await repository.add_many([_logro(diego, T.BIRDIE, "partida-1", publicado=DESPUES)])
        await db_session.commit()

        assert (await _eventos(repository, diego))[(T.BIRDIE, "partida-1")].published_at == DESPUES

    async def test_a_card_split_before_this_rule_gives_its_oldest_date(self, db_session):
        """Filas de antes, con la tarjeta partida: lo que llega va con la primera."""
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1", holes=[4])])
        await repository.add_many(
            [_logro(diego, T.EAGLE_OR_BETTER, "grupo-1", publicado=PRIMERA + timedelta(days=1))]
        )
        await db_session.execute(
            text(
                "UPDATE activity_events SET published_at = :p "
                "WHERE type = 'EAGLE_OR_BETTER' AND user_id = :u"
            ),
            {"p": PRIMERA + timedelta(days=1), "u": str(diego.id.value)},
        )
        await db_session.commit()

        await repository.add_many([_logro(diego, T.PERSONAL_BEST, "grupo-1", publicado=DESPUES)])
        await db_session.commit()

        eventos = await _eventos(repository, diego)
        assert eventos[(T.PERSONAL_BEST, "grupo-1")].published_at == PRIMERA

    async def test_a_notice_of_that_round_is_not_part_of_the_card(self, db_session):
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many([_logro(diego, T.BIRDIE, "torneo-1", holes=[4])])
        await db_session.commit()

        await repository.add_many(
            [_logro(diego, T.TOURNAMENT_FINAL_STANDING, "torneo-1", publicado=DESPUES)]
        )
        await db_session.commit()

        eventos = await _eventos(repository, diego)
        assert eventos[(T.TOURNAMENT_FINAL_STANDING, "torneo-1")].published_at == DESPUES


# ==================== 1. La fecha del mismo logro ====================


class TestTheSameAchievementKeepsItsDate:
    async def test_reopening_and_closing_keeps_its_date(self, db_session):
        """1.1: no sube ni cuenta como nuevo."""
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1", holes=[4])])
        await repository.delete_for_competition("torneo-1", [T.BIRDIE])
        await db_session.commit()

        await repository.replace_for_competition(
            "torneo-1",
            [T.BIRDIE],
            [_logro(diego, T.BIRDIE, "grupo-1", publicado=DESPUES, holes=[4])],
        )
        await db_session.commit()

        assert (await _eventos(repository, diego))[(T.BIRDIE, "grupo-1")].published_at == PRIMERA

    async def test_a_changed_achievement_of_the_same_round_keeps_its_date(self, db_session):
        """1.2: un birdie mas en esa vuelta, o un record con otro numero."""
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many(
            [
                _logro(diego, T.BIRDIE, "grupo-1", holes=[4]),
                _logro(diego, T.PERSONAL_BEST, "grupo-1", differential="12.4"),
            ]
        )
        await db_session.commit()

        await repository.replace_for_competition(
            "torneo-1",
            [T.BIRDIE, T.PERSONAL_BEST],
            [
                _logro(diego, T.BIRDIE, "grupo-1", publicado=DESPUES, holes=[4, 7]),
                _logro(diego, T.PERSONAL_BEST, "grupo-1", publicado=DESPUES, differential="11.0"),
            ],
        )
        await db_session.commit()

        eventos = await _eventos(repository, diego)
        assert eventos[(T.BIRDIE, "grupo-1")].payload["holes"] == [4, 7]
        assert eventos[(T.BIRDIE, "grupo-1")].published_at == PRIMERA
        assert eventos[(T.PERSONAL_BEST, "grupo-1")].published_at == PRIMERA

    async def test_an_achievement_inherited_by_another_round_is_new(self, db_session):
        """1.3: el «campo nuevo» pasa de una vuelta a otra."""
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many([_logro(diego, T.NEW_COURSE, "grupo-a", golf_course_id="c-1")])
        await repository.delete_pairs(T.NEW_COURSE, [(diego.id, "grupo-a")])
        await db_session.commit()

        await repository.add_many(
            [
                _logro(
                    diego,
                    T.NEW_COURSE,
                    "grupo-b",
                    "torneo-2",
                    publicado=DESPUES,
                    golf_course_id="c-1",
                )
            ]
        )
        await db_session.commit()

        assert (await _eventos(repository, diego))[
            (T.NEW_COURSE, "grupo-b")
        ].published_at == DESPUES

    async def test_a_new_achievement_of_that_round_is_new(self, db_session):
        """1.4: un logro que esa vuelta no habia tenido nunca."""
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1", holes=[4])])
        await repository.delete_for_competition("torneo-1", [T.BIRDIE])
        await db_session.commit()

        await repository.add_many(
            [_logro(diego, T.EAGLE_OR_BETTER, "grupo-1", publicado=DESPUES, holes=[9])]
        )
        await db_session.commit()

        eventos = await _eventos(repository, diego)
        assert eventos[(T.EAGLE_OR_BETTER, "grupo-1")].published_at == DESPUES

    async def test_a_notice_published_again_is_new(self, db_session):
        """1.5: la posicion final al volver a cerrar sale como nueva, como hasta ahora."""
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many([_logro(diego, T.TOURNAMENT_FINAL_STANDING, "torneo-1")])
        await repository.delete_for_competition("torneo-1", [T.TOURNAMENT_FINAL_STANDING])
        await db_session.commit()

        await repository.add_many(
            [_logro(diego, T.TOURNAMENT_FINAL_STANDING, "torneo-1", publicado=DESPUES)]
        )
        await db_session.commit()

        eventos = await _eventos(repository, diego)
        assert eventos[(T.TOURNAMENT_FINAL_STANDING, "torneo-1")].published_at == DESPUES

    async def test_it_keeps_the_first_date_across_several_reopenings(self, db_session):
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1", holes=[4])])
        for vez in range(1, 4):
            await repository.delete_for_competition("torneo-1", [T.BIRDIE])
            await repository.add_many(
                [
                    _logro(
                        diego,
                        T.BIRDIE,
                        "grupo-1",
                        publicado=DESPUES + timedelta(days=vez),
                        holes=[4],
                    )
                ]
            )
            await db_session.commit()

        assert (await _eventos(repository, diego))[(T.BIRDIE, "grupo-1")].published_at == PRIMERA

    async def test_a_row_written_by_the_old_code_does_not_move_the_first_date(self, db_session):
        """
        Durante el despliegue el codigo viejo publica sin mirar los apuntes:
        al retirar esa fila, el apunte se queda con la primera fecha.
        """
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1", holes=[4])])
        await repository.delete_for_competition("torneo-1", [T.BIRDIE])
        await db_session.execute(
            text(
                "INSERT INTO activity_events (id, user_id, type, occurred_at, published_at, "
                "payload, source_match_id) VALUES (:id, :u, 'BIRDIE', :jugado, :despues, "
                "'{\"competition_id\": \"torneo-1\"}', 'grupo-1')"
            ),
            {"id": str(uuid4()), "u": str(diego.id.value), "jugado": JUGADO, "despues": DESPUES},
        )
        await repository.delete_for_competition("torneo-1", [T.BIRDIE])
        await db_session.commit()

        await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1", publicado=DESPUES)])
        await db_session.commit()

        assert (await _eventos(repository, diego))[(T.BIRDIE, "grupo-1")].published_at == PRIMERA

    async def test_writing_it_again_counts_as_a_write_for_the_tournament(self, db_session):
        """
        La fecha que se conserva no tapa la escritura: quien publica un torneo
        mira cuando se escribio por ultima vez para no pisar una herencia.
        """
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many([_logro(diego, T.NEW_COURSE, "grupo-1", golf_course_id="c-1")])
        await repository.delete_pairs(T.NEW_COURSE, [(diego.id, "grupo-1")])
        await db_session.commit()
        antes = utc_now()

        await repository.add_many(
            [_logro(diego, T.NEW_COURSE, "grupo-1", publicado=DESPUES, golf_course_id="c-1")]
        )
        await db_session.commit()

        ultima = await repository.last_written_at("torneo-1", [T.NEW_COURSE])
        assert ultima is not None
        assert ultima >= antes
        assert (await _eventos(repository, diego))[(T.NEW_COURSE, "grupo-1")].published_at == (
            PRIMERA
        )


# ==================== 2. La herencia no destapa ====================


class TestTheInheritanceKeepsItHidden:
    async def test_a_new_course_inherited_from_a_hidden_one_is_hidden(self, db_session):
        """2.1: aunque hoy comparta."""
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many(
            [_logro(diego, T.NEW_COURSE, "grupo-a", visible=False, golf_course_id="c-1")]
        )
        await repository.delete_for_competition("torneo-1", [T.NEW_COURSE])
        await db_session.commit()

        await repository.add_many(
            [_logro(diego, T.NEW_COURSE, "partida-b", "", golf_course_id="c-1")]
        )
        await db_session.commit()

        eventos = await _eventos(repository, diego)
        assert eventos[(T.NEW_COURSE, "partida-b")].visible_to_friends is False

    async def test_only_the_same_course_is_inherited_hidden(self, db_session):
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many(
            [_logro(diego, T.NEW_COURSE, "grupo-a", visible=False, golf_course_id="c-1")]
        )
        await repository.delete_for_competition("torneo-1", [T.NEW_COURSE])
        await db_session.commit()

        await repository.add_many(
            [_logro(diego, T.NEW_COURSE, "partida-b", "", golf_course_id="c-2")]
        )
        await db_session.commit()

        assert (await _eventos(repository, diego))[(T.NEW_COURSE, "partida-b")].visible_to_friends

    async def test_a_first_tournament_inherited_from_a_hidden_one_is_hidden(self, db_session):
        """2.2."""
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many([_logro(diego, T.FIRST_TOURNAMENT, "grupo-a", visible=False)])
        await repository.delete_for_competition("torneo-1", [T.FIRST_TOURNAMENT])
        await db_session.commit()

        await repository.add_many([_logro(diego, T.FIRST_TOURNAMENT, "grupo-b", "torneo-2")])
        await db_session.commit()

        eventos = await _eventos(repository, diego)
        assert eventos[(T.FIRST_TOURNAMENT, "grupo-b")].visible_to_friends is False

    async def test_a_visible_one_is_inherited_with_the_current_switch(self, db_session):
        """2.3."""
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many(
            [
                _logro(diego, T.NEW_COURSE, "grupo-a", golf_course_id="c-1"),
                _logro(diego, T.FIRST_TOURNAMENT, "grupo-a"),
            ]
        )
        await repository.delete_for_competition("torneo-1", [T.NEW_COURSE, T.FIRST_TOURNAMENT])
        await db_session.commit()

        await repository.add_many(
            [
                _logro(diego, T.NEW_COURSE, "grupo-b", "torneo-2", golf_course_id="c-1"),
                _logro(diego, T.FIRST_TOURNAMENT, "grupo-b", "torneo-2"),
            ]
        )
        await db_session.commit()

        eventos = await _eventos(repository, diego)
        assert eventos[(T.NEW_COURSE, "grupo-b")].visible_to_friends is True
        assert eventos[(T.FIRST_TOURNAMENT, "grupo-b")].visible_to_friends is True

    async def test_an_older_round_taking_a_hidden_one_is_born_hidden(self, db_session):
        """2.5: `keep_only_the_oldest` retira el posterior oculto y entra el anterior."""
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many(
            [
                _logro(
                    diego, T.NEW_COURSE, "grupo-b", "torneo-2", visible=False, golf_course_id="c-1"
                )
            ]
        )
        await db_session.commit()

        await repository.delete_pairs(T.NEW_COURSE, [(diego.id, "grupo-b")])
        await repository.add_many(
            [_logro(diego, T.NEW_COURSE, "partida-a", "", golf_course_id="c-1")]
        )
        await db_session.commit()

        eventos = await _eventos(repository, diego)
        assert eventos[(T.NEW_COURSE, "partida-a")].visible_to_friends is False

    async def test_other_achievements_are_not_inherited_hidden(self, db_session):
        """Solo los exclusivos se heredan: un birdie de otra vuelta es otro logro."""
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many([_logro(diego, T.BIRDIE, "grupo-a", visible=False, holes=[4])])
        await repository.delete_for_competition("torneo-1", [T.BIRDIE])
        await db_session.commit()

        await repository.add_many([_logro(diego, T.BIRDIE, "grupo-b", "torneo-2", holes=[4])])
        await db_session.commit()

        assert (await _eventos(repository, diego))[(T.BIRDIE, "grupo-b")].visible_to_friends


# ==================== 3. Lo oculto, por hoyo ====================


class TestHiddenHoles:
    async def _birdie_oculto_en_el_3(self, db_session):
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1", visible=False, holes=[3])])
        await repository.delete_for_competition("torneo-1", [T.BIRDIE])
        await db_session.commit()
        return diego, repository

    async def test_a_birdie_on_another_hole_takes_the_current_switch(self, db_session):
        """3.1."""
        diego, repository = await self._birdie_oculto_en_el_3(db_session)

        await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1", holes=[7])])
        await db_session.commit()

        assert (await _eventos(repository, diego))[(T.BIRDIE, "grupo-1")].visible_to_friends

    async def test_the_same_hole_comes_back_hidden(self, db_session):
        """3.2."""
        diego, repository = await self._birdie_oculto_en_el_3(db_session)

        await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1", holes=[3])])
        await db_session.commit()

        eventos = await _eventos(repository, diego)
        assert eventos[(T.BIRDIE, "grupo-1")].visible_to_friends is False

    async def test_both_holes_together_come_back_hidden(self, db_session):
        """3.3: una sola tarjeta, no se ensena a medias."""
        diego, repository = await self._birdie_oculto_en_el_3(db_session)

        await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1", holes=[3, 7])])
        await db_session.commit()

        eventos = await _eventos(repository, diego)
        assert eventos[(T.BIRDIE, "grupo-1")].visible_to_friends is False

    async def test_the_hidden_hole_is_still_remembered_after_showing_another(self, db_session):
        """3.1 y luego 3.3: el apunte no se gasta al publicar el del 7."""
        diego, repository = await self._birdie_oculto_en_el_3(db_session)
        await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1", holes=[7])])
        await db_session.commit()

        await repository.replace_for_competition(
            "torneo-1", [T.BIRDIE], [_logro(diego, T.BIRDIE, "grupo-1", holes=[3, 7])]
        )
        await db_session.commit()

        eventos = await _eventos(repository, diego)
        assert eventos[(T.BIRDIE, "grupo-1")].visible_to_friends is False

    async def test_the_hidden_holes_of_two_withdrawals_add_up(self, db_session):
        """Oculto el 3, luego oculto el 5: los dos siguen ocultos."""
        diego, repository = await self._birdie_oculto_en_el_3(db_session)
        await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1", visible=False, holes=[5])])
        await repository.delete_for_competition("torneo-1", [T.BIRDIE])
        await db_session.commit()

        assert await _hoyos_apuntados(db_session, diego) == [[3, 5]]

        await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1", holes=[5])])
        await db_session.commit()

        eventos = await _eventos(repository, diego)
        assert eventos[(T.BIRDIE, "grupo-1")].visible_to_friends is False

    async def test_a_note_from_before_still_hides_every_hole_after_another_withdrawal(
        self, db_session
    ):
        """Un apunte de la 2.38.0 (todos los hoyos) sumado a uno del 5: siguen todos."""
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await db_session.execute(
            text(
                "INSERT INTO withdrawn_hidden_achievements (user_id, source_match_id, type) "
                "VALUES (:u, 'grupo-1', 'BIRDIE')"
            ),
            {"u": str(diego.id.value)},
        )
        await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1", visible=False, holes=[5])])
        await repository.delete_for_competition("torneo-1", [T.BIRDIE])
        await db_session.commit()

        assert await _hoyos_apuntados(db_session, diego) == [None]

    async def test_a_hidden_one_without_holes_notes_every_hole_as_sql_null(self, db_session):
        """Sin hoyos en el payload se oculta todo: NULL de SQL, no el `null` de JSON."""
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1", visible=False)])
        await repository.delete_for_competition("torneo-1", [T.BIRDIE])
        await db_session.commit()

        assert await _hoyos_apuntados(db_session, diego) == [None]
        tipo = await db_session.execute(
            text("SELECT jsonb_typeof(hidden_holes) FROM withdrawn_hidden_achievements")
        )
        assert tipo.scalars().all() == [None]

    async def test_a_note_from_before_without_holes_hides_the_whole_achievement(self, db_session):
        """3.4: un apunte de la 2.38.0 no guarda los hoyos."""
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await db_session.execute(
            text(
                "INSERT INTO withdrawn_hidden_achievements (user_id, source_match_id, type) "
                "VALUES (:u, 'grupo-1', 'BIRDIE')"
            ),
            {"u": str(diego.id.value)},
        )
        await db_session.commit()

        await repository.add_many([_logro(diego, T.BIRDIE, "grupo-1", holes=[7])])
        await db_session.commit()

        eventos = await _eventos(repository, diego)
        assert eventos[(T.BIRDIE, "grupo-1")].visible_to_friends is False

    async def test_the_holes_of_an_eagle_and_a_hole_in_one_count_too(self, db_session):
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many(
            [
                _logro(diego, T.EAGLE_OR_BETTER, "grupo-1", visible=False, holes=[5]),
                _logro(diego, T.HOLE_IN_ONE, "grupo-1", visible=False, holes=[8]),
            ]
        )
        await repository.delete_for_competition("torneo-1", [T.EAGLE_OR_BETTER, T.HOLE_IN_ONE])
        await db_session.commit()

        await repository.add_many(
            [
                _logro(diego, T.EAGLE_OR_BETTER, "grupo-1", holes=[12]),
                _logro(diego, T.HOLE_IN_ONE, "grupo-1", holes=[8]),
            ]
        )
        await db_session.commit()

        eventos = await _eventos(repository, diego)
        assert eventos[(T.EAGLE_OR_BETTER, "grupo-1")].visible_to_friends is True
        assert eventos[(T.HOLE_IN_ONE, "grupo-1")].visible_to_friends is False

    async def test_a_record_hidden_comes_back_hidden_whatever_its_number(self, db_session):
        """3.5: sin hoyos, como hasta ahora."""
        diego = await _user(db_session)
        repository = SQLAlchemyActivityEventRepository(db_session)
        await repository.add_many(
            [_logro(diego, T.PERSONAL_BEST, "grupo-1", visible=False, differential="12.4")]
        )
        await repository.delete_for_competition("torneo-1", [T.PERSONAL_BEST])
        await db_session.commit()

        await repository.add_many([_logro(diego, T.PERSONAL_BEST, "grupo-1", differential="11.0")])
        await db_session.commit()

        eventos = await _eventos(repository, diego)
        assert eventos[(T.PERSONAL_BEST, "grupo-1")].visible_to_friends is False
