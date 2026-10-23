"""
Tests de la marca con la que se mide un record (decision de Agustin, 23 oct
2026): solo cuentan las vueltas de dias ANTERIORES a la que se juzga. Un record
del 12 oct no puede «mejorar su 35.6» si ese 35.6 es del 15 oct.
"""

from datetime import date, timedelta
from decimal import Decimal

from src.modules.social.domain.services.achievement_detector import RoundContext
from src.modules.social.domain.services.personal_best import (
    DatedDifferential,
    record_context,
)

D12 = date(2026, 10, 12)


def _vuelta(dia: date, diferencial: str, origen: str = "otra", torneo: str | None = None):
    return DatedDifferential(
        played_on=dia,
        differential=Decimal(diferencial),
        source_id=origen,
        competition_id=torneo,
    )


def _de_la_partida(vuelta: DatedDifferential) -> bool:
    return vuelta.source_id == "esta"


def _del_torneo(vuelta: DatedDifferential) -> bool:
    return vuelta.competition_id == "torneo"


class TestOnlyEarlierDays:
    def test_a_later_round_is_not_the_mark_it_beats(self):
        """El caso del probador: el 35.6 es del 15 oct y el record del 12 oct."""
        rondas = [
            _vuelta(D12 + timedelta(days=3), "35.6"),
            _vuelta(D12, "36.0", "esta"),
            _vuelta(D12 - timedelta(days=5), "38.2"),
        ]

        contexto = record_context(rondas, _de_la_partida)

        assert contexto == RoundContext(
            previous_best_differential=Decimal("38.2"), differential=Decimal("36.0")
        )

    def test_a_round_the_same_day_is_not_earlier(self):
        """4.5: el mismo dia no cuenta como anterior (las estadisticas no guardan la hora)."""
        rondas = [
            _vuelta(D12, "30.0"),
            _vuelta(D12, "36.0", "esta"),
            _vuelta(D12 - timedelta(days=1), "38.2"),
        ]

        contexto = record_context(rondas, _de_la_partida)

        assert contexto.previous_best_differential == Decimal("38.2")

    def test_without_earlier_rounds_there_is_no_mark(self):
        rondas = [_vuelta(D12, "36.0", "esta"), _vuelta(D12 + timedelta(days=1), "40.0")]

        contexto = record_context(rondas, _de_la_partida)

        assert contexto.previous_best_differential is None
        assert contexto.differential == Decimal("36.0")

    def test_without_its_own_round_there_is_nothing_to_judge(self):
        """La vuelta no es computable (incompleta, sin tee): ni record ni marca."""
        rondas = [_vuelta(D12 - timedelta(days=1), "38.2")]

        assert record_context(rondas, _de_la_partida) == RoundContext()

    def test_the_order_they_come_in_does_not_matter(self):
        rondas = [
            _vuelta(D12 - timedelta(days=9), "37.0"),
            _vuelta(D12, "36.0", "esta"),
            _vuelta(D12 - timedelta(days=1), "39.0"),
            _vuelta(D12 + timedelta(days=2), "20.0"),
        ]

        contexto = record_context(list(reversed(rondas)), _de_la_partida)

        assert contexto.previous_best_differential == Decimal("37.0")


class TestTheRecordWindow:
    def test_the_mark_is_the_best_of_the_twenty_most_recent_earlier_rounds(self):
        """La misma ventana del WHS que las estadisticas, contada hacia atras desde ese dia."""
        antiguas = [_vuelta(D12 - timedelta(days=30), "10.0")]
        recientes = [_vuelta(D12 - timedelta(days=d), "30.0") for d in range(1, 21)]
        rondas = [*antiguas, *recientes, _vuelta(D12, "25.0", "esta")]

        contexto = record_context(rondas, _de_la_partida)

        assert contexto.previous_best_differential == Decimal("30.0")

    def test_later_rounds_do_not_push_earlier_ones_out_of_the_window(self):
        despues = [_vuelta(D12 + timedelta(days=d), "40.0") for d in range(1, 25)]
        rondas = [*despues, _vuelta(D12 - timedelta(days=1), "31.0"), _vuelta(D12, "25.0", "esta")]

        contexto = record_context(rondas, _de_la_partida)

        assert contexto.previous_best_differential == Decimal("31.0")


class TestATournament:
    def test_its_best_round_against_what_was_played_before_its_first_day(self):
        rondas = [
            _vuelta(D12, "33.0", "g1", "torneo"),
            _vuelta(D12 + timedelta(days=1), "31.5", "g2", "torneo"),
            # Durante el torneo: no es anterior a el
            _vuelta(D12 + timedelta(days=1), "20.0"),
            _vuelta(D12 - timedelta(days=2), "34.0"),
        ]

        contexto = record_context(rondas, _del_torneo)

        assert contexto == RoundContext(
            previous_best_differential=Decimal("34.0"), differential=Decimal("31.5")
        )
