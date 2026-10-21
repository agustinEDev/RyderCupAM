"""Tests del publico de cada tipo de evento: quien lo ve."""

import pytest

from src.modules.social.domain.value_objects.activity_audience import (
    AUDIENCE_BY_TYPE,
    ActivityAudience,
    audience_of,
    types_seen_by_author,
    types_seen_by_friends,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType

LOGROS = [
    ActivityEventType.HOLE_IN_ONE,
    ActivityEventType.EAGLE_OR_BETTER,
    ActivityEventType.BIRDIE,
    ActivityEventType.NEW_COURSE,
    ActivityEventType.PERSONAL_BEST,
    ActivityEventType.FIRST_TOURNAMENT,
]


class TestPublico:
    @pytest.mark.parametrize(
        ("audience", "autor", "amigos"),
        [
            (ActivityAudience.SELF, True, False),
            (ActivityAudience.FRIENDS, False, True),
            (ActivityAudience.BOTH, True, True),
        ],
    )
    def test_quien_ve_cada_publico(self, audience, autor, amigos):
        """Given un publico / When se pregunta quien lo ve / Then autor y amigos segun cual."""
        assert audience.seen_by_author is autor
        assert audience.seen_by_friends is amigos

    def test_todo_tipo_tiene_publico(self):
        """
        Given la lista de tipos / When se mira el mapa / Then ninguno falta: un
        tipo nuevo sin publico no se veria en ningun sitio.
        """
        assert set(AUDIENCE_BY_TYPE) == set(ActivityEventType)

    @pytest.mark.parametrize("tipo", LOGROS)
    def test_d22_los_logros_los_ven_el_autor_y_sus_amigos(self, tipo):
        """
        D22. Given los seis logros de siempre / When se mira su publico / Then
        BOTH: uno se ve a si mismo en su feed y sus amigos tambien lo ven.
        """
        assert audience_of(tipo) is ActivityAudience.BOTH


class TestTiposVisibles:
    def test_con_el_mapa_real_autor_y_amigos_ven_los_seis(self):
        assert types_seen_by_author() == frozenset(LOGROS)
        assert types_seen_by_friends() == frozenset(LOGROS)

    def test_se_calculan_desde_el_mapa(self, monkeypatch):
        """
        Given un mapa con un tipo de cada publico / When se piden los tipos
        visibles / Then el autor ve SELF y BOTH, y los amigos FRIENDS y BOTH.
        """
        monkeypatch.setitem(AUDIENCE_BY_TYPE, ActivityEventType.BIRDIE, ActivityAudience.SELF)
        monkeypatch.setitem(
            AUDIENCE_BY_TYPE, ActivityEventType.EAGLE_OR_BETTER, ActivityAudience.FRIENDS
        )

        autor = types_seen_by_author()
        amigos = types_seen_by_friends()

        assert ActivityEventType.BIRDIE in autor
        assert ActivityEventType.BIRDIE not in amigos
        assert ActivityEventType.EAGLE_OR_BETTER in amigos
        assert ActivityEventType.EAGLE_OR_BETTER not in autor
        assert ActivityEventType.HOLE_IN_ONE in autor
        assert ActivityEventType.HOLE_IN_ONE in amigos
