"""
Tests del apunte de un logro retirado (decisiones de Agustin del 23 oct 2026):
la fecha del mismo logro, lo oculto por hoyo y la suma de dos apuntes.
"""

from datetime import datetime

from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.services.withdrawn_achievement import (
    WithdrawnAchievement,
    cards_keep_their_date,
    exclusive_scope,
    scope_of,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.user.domain.value_objects.user_id import UserId

T = ActivityEventType
DIEGO = UserId.generate()
PRIMERA = datetime(2026, 10, 20, 9, 0)
DESPUES = datetime(2026, 10, 23, 9, 0)


def _logro(
    tipo=T.BIRDIE, *, visible=True, publicado=DESPUES, origen="grupo-1", **payload
) -> ActivityEvent:
    return ActivityEvent.create(
        user_id=DIEGO,
        type=tipo,
        occurred_at=PRIMERA,
        source_match_id=origen,
        published_at=publicado,
        payload=payload,
        visible_to_friends=visible,
    )


def _apunte(evento: ActivityEvent) -> WithdrawnAchievement:
    return WithdrawnAchievement.of(
        evento.type, evento.published_at, evento.visible_to_friends, evento.payload
    )


class TestWhatIsNoted:
    def test_a_visible_one_notes_only_its_date(self):
        assert _apunte(_logro(publicado=PRIMERA, holes=[3])) == WithdrawnAchievement(
            published_at=PRIMERA, hidden=False
        )

    def test_a_hidden_per_hole_one_notes_its_holes(self):
        apunte = _apunte(_logro(visible=False, holes=[7, 3, 3]))

        assert apunte.hidden is True
        assert apunte.hidden_holes == (3, 7)

    def test_a_hidden_record_hides_it_whole(self):
        apunte = _apunte(_logro(T.PERSONAL_BEST, visible=False, holes=[3]))

        assert apunte.hidden_holes is None

    def test_a_new_course_notes_its_course(self):
        assert _apunte(_logro(T.NEW_COURSE, golf_course_id="c-1")).golf_course_id == "c-1"
        assert _apunte(_logro(T.BIRDIE, golf_course_id="c-1")).golf_course_id is None


class TestApplyingIt:
    def test_the_same_achievement_keeps_its_date(self):
        evento = _logro()

        WithdrawnAchievement(published_at=PRIMERA, hidden=False).apply_to(evento)

        assert evento.published_at == PRIMERA
        assert evento.visible_to_friends is True

    def test_a_note_from_before_without_date_leaves_it_new(self):
        evento = _logro()

        WithdrawnAchievement(published_at=None, hidden=True).apply_to(evento)

        assert evento.published_at == DESPUES
        assert evento.visible_to_friends is False

    def test_only_a_hidden_hole_coming_back_hides_it(self):
        oculto_el_3 = WithdrawnAchievement(published_at=PRIMERA, hidden=True, hidden_holes=(3,))
        otro, mismo, los_dos, sin_hoyos = (
            _logro(holes=[7]),
            _logro(holes=[3]),
            _logro(holes=[3, 7]),
            _logro(),
        )

        for evento in (otro, mismo, los_dos, sin_hoyos):
            oculto_el_3.apply_to(evento)

        assert [e.visible_to_friends for e in (otro, mismo, los_dos, sin_hoyos)] == [
            True,
            False,
            False,
            False,
        ]


class TestAddingTwoNotes:
    def test_the_first_date_and_the_hidden_holes_of_both(self):
        primero = WithdrawnAchievement(published_at=DESPUES, hidden=True, hidden_holes=(3,))
        segundo = WithdrawnAchievement(published_at=PRIMERA, hidden=True, hidden_holes=(5, 3))

        assert primero.merged_with(segundo) == WithdrawnAchievement(
            published_at=PRIMERA, hidden=True, hidden_holes=(3, 5)
        )

    def test_a_visible_one_does_not_uncover_a_hidden_one(self):
        oculto = WithdrawnAchievement(published_at=PRIMERA, hidden=True, hidden_holes=(3,))
        visible = WithdrawnAchievement(published_at=DESPUES, hidden=False)

        assert oculto.merged_with(visible) == oculto
        assert visible.merged_with(oculto) == oculto

    def test_one_hiding_every_hole_hides_every_hole(self):
        todos = WithdrawnAchievement(published_at=None, hidden=True)
        el_3 = WithdrawnAchievement(published_at=PRIMERA, hidden=True, hidden_holes=(3,))

        assert todos.merged_with(el_3).hidden_holes is None
        assert el_3.merged_with(todos).hidden_holes is None

    def test_the_course_is_kept(self):
        con_campo = WithdrawnAchievement(published_at=PRIMERA, hidden=True, golf_course_id="c-1")
        sin_campo = WithdrawnAchievement(published_at=DESPUES, hidden=False)

        assert con_campo.merged_with(sin_campo).golf_course_id == "c-1"


class TestTheScopeOfTheExclusiveOnes:
    def test_a_new_course_by_course_and_a_first_tournament_by_player(self):
        assert scope_of(_logro(T.NEW_COURSE, golf_course_id="c-1")) == exclusive_scope(
            DIEGO, T.NEW_COURSE, "c-1"
        )
        assert scope_of(_logro(T.FIRST_TOURNAMENT, golf_course_id="c-1")) == exclusive_scope(
            DIEGO, T.FIRST_TOURNAMENT, None
        )


class TestTheCardKeepsItsDate:
    """
    Hallazgo 2 del revisor (Agustin, 23 oct 2026): los logros de una vuelta son
    una tarjeta en el feed, y una tarjeta no se parte.
    """

    def test_a_new_one_of_a_card_that_kept_its_date_takes_that_date(self):
        """2.1: el birdie conserva el 20 oct y el eagle nuevo entra en su tarjeta."""
        birdie, eagle = _logro(publicado=PRIMERA), _logro(T.EAGLE_OR_BETTER)

        cards_keep_their_date([birdie, eagle], {})

        assert (birdie.published_at, eagle.published_at) == (PRIMERA, PRIMERA)

    def test_the_oldest_date_of_the_card_wins(self):
        """2.2."""
        antes = datetime(2026, 10, 18, 9, 0)
        birdie, eagle = _logro(publicado=PRIMERA), _logro(T.EAGLE_OR_BETTER, publicado=antes)

        cards_keep_their_date([birdie, eagle], {})

        assert (birdie.published_at, eagle.published_at) == (antes, antes)

    def test_a_card_already_published_keeps_its_date(self):
        """2.8: el «campo nuevo» heredado entra en la tarjeta que ya estaba."""
        campo = _logro(T.NEW_COURSE)

        cards_keep_their_date([campo], {campo.card_key: PRIMERA})

        assert campo.published_at == PRIMERA

    def test_what_is_already_published_wins_so_the_card_never_splits(self):
        """Lo publicado no se mueve: lo que llega se pone con ello, aunque sea anterior."""
        antes = datetime(2026, 10, 18, 9, 0)
        birdie = _logro(publicado=antes)

        cards_keep_their_date([birdie], {birdie.card_key: PRIMERA})

        assert birdie.published_at == PRIMERA

    def test_a_new_card_keeps_its_date(self):
        """2.3."""
        birdie, eagle = _logro(), _logro(T.EAGLE_OR_BETTER)

        cards_keep_their_date([birdie, eagle], {})

        assert (birdie.published_at, eagle.published_at) == (DESPUES, DESPUES)

    def test_each_card_on_its_own(self):
        """2.7."""
        uno, otro = _logro(publicado=PRIMERA), _logro(T.EAGLE_OR_BETTER, origen="grupo-2")

        cards_keep_their_date([uno, otro], {})

        assert (uno.published_at, otro.published_at) == (PRIMERA, DESPUES)

    def test_a_notice_is_its_own_card(self):
        """2.4."""
        aviso = ActivityEvent.create(
            user_id=DIEGO,
            type=T.QUICK_MATCH_FINISHED,
            occurred_at=PRIMERA,
            source_match_id="grupo-1",
            published_at=DESPUES,
            payload={},
            visible_to_friends=True,
        )
        birdie = _logro(publicado=PRIMERA)

        cards_keep_their_date([aviso, birdie], {})

        assert aviso.published_at == DESPUES

    def test_it_only_moves_the_date(self):
        """2.5."""
        oculto = _logro(T.EAGLE_OR_BETTER, visible=False)

        cards_keep_their_date([_logro(publicado=PRIMERA), oculto], {})

        assert oculto.visible_to_friends is False
