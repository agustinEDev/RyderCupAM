"""
Las reglas del cara a cara (BE-3, tabla aprobada el 22 oct 2026).

| Caso                                              | Resultado                       |
|---------------------------------------------------|---------------------------------|
| Stableford: mas puntos / menos / iguales          | Gana / pierde / empata          |
| Stableford con menos golpes netos pero menos pts  | Pierde: van los puntos          |
| Medal: menos netos / mas / iguales                | Gana / pierde / empata          |
| Medal con mas golpes brutos pero menos netos      | Gana: nunca en bruto            |
| Tarjeta a medias, de uno u otro (caso 10)         | No cuenta (None)                |
| Sin tarjeta de uno de los dos                     | No cuenta                       |
| Match play: gana mi bando / el otro / empate      | Gana / pierde / empata          |
| Match play sin resultado o con uno raro (caso 7)  | No cuenta                       |
| Mismo bando / bandos distintos                    | Con él / contra él              |
| Suma por apartado                                 | Cada uno lo suyo                |
| Sin resultado no suma (caso 7)                    | Fuera                           |
| Sin nada que contar (caso 8)                      | None, no 0-0-0                  |
| Solo contra él                                    | «Con él» en None                |
"""

from decimal import Decimal

import pytest

from src.modules.social.domain.services.head_to_head import (
    CardResult,
    HeadToHead,
    Outcome,
    Record,
    Relation,
    relation_between,
    stroke_play_outcome,
    tally,
    team_outcome,
)
from src.shared.domain.value_objects.scoring_format import ScoringFormat

STABLEFORD = ScoringFormat.STABLEFORD
MEDAL = ScoringFormat.MEDAL


def _card(
    points: int = 36, net_to_par: int = 0, complete: bool = True, handicap=10.0
) -> CardResult:
    return CardResult(complete=complete, points=points, net_to_par=net_to_par, handicap=handicap)


class TestStableford:
    def test_mas_puntos_gana(self):
        assert stroke_play_outcome(_card(points=37), _card(points=36), STABLEFORD) == Outcome.WON

    def test_menos_puntos_pierde(self):
        assert stroke_play_outcome(_card(points=35), _card(points=36), STABLEFORD) == Outcome.LOST

    def test_mismos_puntos_empata(self):
        assert stroke_play_outcome(_card(points=36), _card(points=36), STABLEFORD) == Outcome.HALVED

    def test_van_los_puntos_y_no_los_golpes(self):
        """Menos golpes netos pero menos puntos: en Stableford pierde."""
        mia = _card(points=30, net_to_par=-3)
        suya = _card(points=31, net_to_par=5)

        assert stroke_play_outcome(mia, suya, STABLEFORD) == Outcome.LOST


class TestMedal:
    def test_menos_netos_gana(self):
        assert stroke_play_outcome(_card(net_to_par=2), _card(net_to_par=3), MEDAL) == Outcome.WON

    def test_mas_netos_pierde(self):
        assert stroke_play_outcome(_card(net_to_par=4), _card(net_to_par=3), MEDAL) == Outcome.LOST

    def test_mismos_netos_empata(self):
        assert (
            stroke_play_outcome(_card(net_to_par=1), _card(net_to_par=1), MEDAL) == Outcome.HALVED
        )

    def test_van_los_netos_y_no_los_puntos(self):
        """Mas puntos pero mas golpes netos: en Medal pierde."""
        mia = _card(points=40, net_to_par=1)
        suya = _card(points=20, net_to_par=0)

        assert stroke_play_outcome(mia, suya, MEDAL) == Outcome.LOST


class TestDesempatePorHandicap:
    """
    Tabla del 22 oct 2026, H: el cara a cara deshace el empate como el aviso y
    la clasificación, con el menor índice exacto; sin hándicap cuenta como 0.
    """

    @pytest.mark.parametrize("formato", [STABLEFORD, MEDAL])
    def test_a_igual_valor_gana_el_de_menos_handicap(self, formato):
        assert stroke_play_outcome(_card(handicap=12.4), _card(handicap=19.0), formato) == (
            Outcome.WON
        )
        assert stroke_play_outcome(_card(handicap=19.0), _card(handicap=12.4), formato) == (
            Outcome.LOST
        )

    def test_con_el_mismo_indice_exacto_empata(self):
        mia, suya = _card(handicap=12.4), _card(handicap=Decimal("12.40"))

        assert stroke_play_outcome(mia, suya, STABLEFORD) == Outcome.HALVED

    def test_sin_handicap_cuenta_como_cero(self):
        assert stroke_play_outcome(_card(handicap=None), _card(handicap=19.0), STABLEFORD) == (
            Outcome.WON
        )
        assert stroke_play_outcome(_card(handicap=None), _card(handicap=0.0), STABLEFORD) == (
            Outcome.HALVED
        )
        assert stroke_play_outcome(_card(handicap=None), _card(handicap=-1.0), STABLEFORD) == (
            Outcome.LOST
        )

    def test_el_handicap_no_cambia_lo_que_no_esta_empatado(self):
        mia, suya = _card(points=37, handicap=30.0), _card(points=36, handicap=0.0)

        assert stroke_play_outcome(mia, suya, STABLEFORD) == Outcome.WON


class TestFormatoDesconocido:
    def test_un_formato_que_no_es_stableford_ni_medal_no_cuenta(self):
        """Solo se juzga en las dos modalidades conocidas; lo demás no se adivina."""
        assert stroke_play_outcome(_card(net_to_par=1), _card(net_to_par=3), "SCRATCH") is None
        assert stroke_play_outcome(_card(), _card(), None) is None


class TestTarjetasQueNoCuentan:
    def test_mi_tarjeta_a_medias_no_cuenta(self):
        assert stroke_play_outcome(_card(complete=False), _card(), STABLEFORD) is None

    def test_su_tarjeta_a_medias_no_cuenta(self):
        assert stroke_play_outcome(_card(), _card(complete=False), MEDAL) is None

    def test_sin_mi_tarjeta_no_cuenta(self):
        assert stroke_play_outcome(None, _card(), STABLEFORD) is None

    def test_sin_su_tarjeta_no_cuenta(self):
        assert stroke_play_outcome(_card(), None, MEDAL) is None


class TestMatchPlay:
    def test_gana_mi_bando(self):
        assert team_outcome("A", "A") == Outcome.WON
        assert team_outcome("B", "B") == Outcome.WON

    def test_gana_el_otro_bando(self):
        assert team_outcome("B", "A") == Outcome.LOST
        assert team_outcome("A", "B") == Outcome.LOST

    def test_empate(self):
        assert team_outcome("HALVED", "A") == Outcome.HALVED
        assert team_outcome("HALVED", "B") == Outcome.HALVED

    def test_sin_resultado_no_cuenta(self):
        assert team_outcome(None, "A") is None

    def test_un_ganador_desconocido_no_cuenta(self):
        assert team_outcome("X", "A") is None

    def test_mismo_bando_es_con_el(self):
        assert relation_between("A", "A") == Relation.WITH
        assert relation_between("B", "B") == Relation.WITH

    def test_bandos_distintos_es_contra_el(self):
        assert relation_between("A", "B") == Relation.AGAINST
        assert relation_between("B", "A") == Relation.AGAINST


class TestSuma:
    def test_cada_apartado_suma_lo_suyo(self):
        resultados = [
            (Relation.AGAINST, Outcome.WON),
            (Relation.AGAINST, Outcome.WON),
            (Relation.AGAINST, Outcome.HALVED),
            (Relation.AGAINST, Outcome.LOST),
            (Relation.WITH, Outcome.LOST),
            (Relation.WITH, Outcome.HALVED),
            (Relation.WITH, Outcome.HALVED),
        ]

        assert tally(resultados) == HeadToHead(
            against=Record(won=2, halved=1, lost=1),
            alongside=Record(won=0, halved=2, lost=1),
        )

    def test_lo_que_no_tiene_resultado_no_suma(self):
        resultados = [(Relation.AGAINST, Outcome.WON), (Relation.AGAINST, None)]

        assert tally(resultados) == HeadToHead(
            against=Record(won=1, halved=0, lost=0), alongside=None
        )

    def test_sin_nada_que_contar_no_hay_cara_a_cara(self):
        assert tally([]) is None

    def test_solo_partidas_sin_resultado_tampoco(self):
        assert tally([(Relation.AGAINST, None), (Relation.WITH, None)]) is None

    def test_solo_con_el(self):
        assert tally([(Relation.WITH, Outcome.WON)]) == HeadToHead(
            against=None, alongside=Record(won=1, halved=0, lost=0)
        )
