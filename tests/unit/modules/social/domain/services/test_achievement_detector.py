"""
Tests del AchievementDetector (BE #175).

La regla que protegen estos tests no es de cálculo, es de producto: **solo se
publican logros**. Si alguna vez sale de aquí algo que delate una vuelta mala,
el feed empezará a desincentivar que la gente anote sus tarjetas — que es el
sesgo que ya arrastran las estadísticas (BE #173).
"""

from decimal import Decimal

import pytest

from src.modules.social.domain.services.achievement_detector import (
    AchievementDetector,
    PlayedHole,
    RoundContext,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType


@pytest.fixture
def detector():
    return AchievementDetector()


def hoyos(*specs):
    """(par, golpes) por hoyo, numerados desde el 1."""
    return [PlayedHole(number=i + 1, par=p, strokes=s) for i, (p, s) in enumerate(specs)]


class TestLogrosPorHoyo:
    def test_un_birdie_se_publica(self, detector):
        [logro] = detector.detect(hoyos((4, 3)))

        assert logro.type == ActivityEventType.BIRDIE
        assert logro.count == 1
        assert logro.holes == (1,)

    def test_los_birdies_de_una_vuelta_van_juntos(self, detector):
        """
        Cuatro birdies son una entrada que dice cuatro, no cuatro entradas
        empujandose unas a otras en el feed de los amigos.
        """
        [logro] = detector.detect(hoyos((4, 3), (4, 4), (3, 2), (5, 4), (4, 3)))

        assert logro.type == ActivityEventType.BIRDIE
        assert logro.count == 4
        assert logro.holes == (1, 3, 4, 5)

    def test_un_eagle_no_cuenta_ademas_como_birdie(self, detector):
        [logro] = detector.detect(hoyos((5, 3)))

        assert logro.type == ActivityEventType.EAGLE_OR_BETTER
        assert logro.count == 1

    def test_un_hoyo_en_uno_no_cuenta_ademas_como_eagle(self, detector):
        """En un par 3, un hoyo en uno es tambien un eagle. Se cuenta una vez."""
        logros = detector.detect(hoyos((3, 1)))

        assert [logro.type for logro in logros] == [ActivityEventType.HOLE_IN_ONE]

    def test_un_hoyo_en_uno_en_par_4_tampoco_se_duplica(self, detector):
        logros = detector.detect(hoyos((4, 1)))

        assert [logro.type for logro in logros] == [ActivityEventType.HOLE_IN_ONE]

    def test_se_ordenan_del_mas_raro_al_mas_comun(self, detector):
        logros = detector.detect(hoyos((4, 3), (5, 3), (3, 1)))

        assert [logro.type for logro in logros] == [
            ActivityEventType.HOLE_IN_ONE,
            ActivityEventType.EAGLE_OR_BETTER,
            ActivityEventType.BIRDIE,
        ]

    def test_una_vuelta_normal_no_publica_nada(self, detector):
        """Jugar al par no es noticia."""
        assert detector.detect(hoyos((4, 4), (3, 3), (5, 5))) == []

    def test_una_vuelta_mala_no_publica_nada(self, detector):
        """
        Lo mas importante del feed: jugar mal no genera ninguna entrada. Nadie
        deberia pensarselo dos veces antes de anotar una tarjeta.
        """
        assert detector.detect(hoyos((4, 8), (3, 7), (5, 10))) == []

    def test_ignora_hoyos_sin_datos(self, detector):
        assert detector.detect(hoyos((4, 0), (0, 3))) == []


class TestLogrosDeVuelta:
    def test_estrenar_campo_se_publica(self, detector):
        logros = detector.detect(hoyos((4, 4)), RoundContext(is_first_round_on_course=True))

        assert [logro.type for logro in logros] == [ActivityEventType.NEW_COURSE]

    def test_el_primer_torneo_se_publica(self, detector):
        logros = detector.detect(hoyos((4, 4)), RoundContext(is_first_tournament=True))

        assert [logro.type for logro in logros] == [ActivityEventType.FIRST_TOURNAMENT]

    def test_batir_la_mejor_vuelta_se_publica(self, detector):
        logros = detector.detect(
            hoyos((4, 4)),
            RoundContext(differential=Decimal("12.1"), previous_best_differential=Decimal("14.3")),
        )

        [logro] = logros
        assert logro.type == ActivityEventType.PERSONAL_BEST
        assert logro.detail["differential"] == "12.1"
        assert logro.detail["previous_best"] == "14.3"

    def test_no_batir_el_record_no_publica_nada(self, detector):
        logros = detector.detect(
            hoyos((4, 4)),
            RoundContext(differential=Decimal("15.0"), previous_best_differential=Decimal("14.3")),
        )

        assert logros == []

    def test_igualar_el_record_no_es_batirlo(self, detector):
        logros = detector.detect(
            hoyos((4, 4)),
            RoundContext(differential=Decimal("14.3"), previous_best_differential=Decimal("14.3")),
        )

        assert logros == []

    def test_la_primera_vuelta_con_diferencial_no_es_un_record(self, detector):
        """
        Sin nada anterior con lo que compararla no hay record que anunciar: es
        el punto de partida, y publicarlo seria un anuncio vacio.
        """
        logros = detector.detect(
            hoyos((4, 4)),
            RoundContext(differential=Decimal("12.1"), previous_best_differential=None),
        )

        assert logros == []

    def test_una_vuelta_puede_traer_varios_logros(self, detector):
        logros = detector.detect(
            hoyos((4, 3), (5, 3)),
            RoundContext(
                is_first_round_on_course=True,
                differential=Decimal("10.0"),
                previous_best_differential=Decimal("12.0"),
            ),
        )

        assert {logro.type for logro in logros} == {
            ActivityEventType.EAGLE_OR_BETTER,
            ActivityEventType.BIRDIE,
            ActivityEventType.NEW_COURSE,
            ActivityEventType.PERSONAL_BEST,
        }
