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


# Los avisos de BE-2 (tabla aprobada el 21 oct 2026)
SOLO_EL_AUTOR = [
    ActivityEventType.ENROLLMENT_APPROVED,
    ActivityEventType.INVITED_TO_TOURNAMENT,
    ActivityEventType.ENROLLMENT_REQUEST_CLOSED,
    ActivityEventType.ENROLLMENT_REJECTED,
    ActivityEventType.TOURNAMENT_MATCH_RESULT,
    # Tabla del 22 oct 2026, C: «ya estás inscrito», solo tuyo
    ActivityEventType.ENROLLMENT_CONFIRMED,
    # G6: tu salida o tu partido, solo tuyo
    ActivityEventType.TEE_TIME_ASSIGNED,
    # N1 (release social 2): «el organizador te ha quitado», solo tuyo
    ActivityEventType.ENROLLMENT_REMOVED,
]


class TestPublicoDeLosAvisos:
    @pytest.mark.parametrize("tipo", SOLO_EL_AUTOR)
    def test_los_avisos_de_inscripcion_y_resultados_son_solo_tuyos(self, tipo):
        """A y C. Given un aviso de inscripcion o de resultado / Then SELF."""
        assert audience_of(tipo) is ActivityAudience.SELF

    def test_la_posicion_final_la_ven_tambien_sus_amigos(self):
        """Tabla del 27 oct 2026, fila 10. Given su puesto final en un torneo / Then BOTH."""
        assert audience_of(ActivityEventType.TOURNAMENT_FINAL_STANDING) is ActivityAudience.BOTH

    def test_el_amigo_apuntado_lo_ven_solo_sus_amigos(self):
        """B. Given «X se ha apuntado a Y» / Then FRIENDS: el autor tiene su propio aviso."""
        assert audience_of(ActivityEventType.ENROLLED_IN_TOURNAMENT) is ActivityAudience.FRIENDS

    def test_la_partida_rapida_la_vemos_tu_y_tus_amigos(self):
        """D. Given una partida rapida terminada / Then BOTH."""
        assert audience_of(ActivityEventType.QUICK_MATCH_FINISHED) is ActivityAudience.BOTH


class TestTiposVisibles:
    def test_con_el_mapa_real_autor_y_amigos_ven_lo_suyo(self):
        assert types_seen_by_author() == frozenset(
            [
                *LOGROS,
                *SOLO_EL_AUTOR,
                ActivityEventType.QUICK_MATCH_FINISHED,
                ActivityEventType.TOURNAMENT_FINAL_STANDING,
            ]
        )
        assert types_seen_by_friends() == frozenset(
            [
                *LOGROS,
                ActivityEventType.ENROLLED_IN_TOURNAMENT,
                ActivityEventType.QUICK_MATCH_FINISHED,
                ActivityEventType.TOURNAMENT_FINAL_STANDING,
            ]
        )

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
