"""
Tests del desglose de golpes (BE #168).

Las métricas anteriores dicen cuánto juega de bien un jugador; estas dicen
dónde pierde los golpes, así que lo que se prueba aquí es que cada hoyo cae
donde le toca y que las medias hablan todas en la misma unidad.
"""

from src.modules.user.domain.services.scoring_breakdown_calculator import (
    RoundOutcome,
    ScoringBreakdownCalculator,
)
from src.shared.domain.value_objects.hole_outcome import HoleOutcome


def hoyo(number: int, par: int, adjusted_gross: int, strokes_received: int = 0) -> HoleOutcome:
    return HoleOutcome(
        number=number,
        par=par,
        adjusted_gross=adjusted_gross,
        strokes_received=strokes_received,
    )


def vuelta_de_par(pares: list[int], golpes: list[int], **kwargs) -> RoundOutcome:
    """Una vuelta con tantos hoyos como pares se den, numerados desde el 1."""
    return RoundOutcome(
        golf_course_id=kwargs.get("golf_course_id"),
        golf_course_name=kwargs.get("golf_course_name"),
        holes=[
            hoyo(i + 1, par, golpe, kwargs.get("strokes_received", 0))
            for i, (par, golpe) in enumerate(zip(pares, golpes, strict=True))
        ],
    )


class TestSinDatos:
    def test_sin_vueltas_devuelve_el_desglose_vacio(self):
        """Una cuenta nueva es un caso normal, no un error."""
        resultado = ScoringBreakdownCalculator().compute([])

        assert resultado.holes_counted == 0
        assert resultado.rounds_counted == 0
        assert resultado.by_par == []
        assert resultado.by_course == []
        assert resultado.front_nine is None
        assert resultado.back_nine is None

    def test_una_vuelta_sin_hoyos_no_cuenta_como_vuelta_jugada(self):
        vacia = RoundOutcome(golf_course_id="c1", golf_course_name="Campo", holes=[])

        resultado = ScoringBreakdownCalculator().compute([vacia])

        assert resultado.holes_counted == 0
        assert resultado.by_course == []


class TestDistribucion:
    def test_reparte_cada_hoyo_en_su_cesta(self):
        # birdie, par, bogey, doble, triple
        vuelta = vuelta_de_par([4, 4, 4, 4, 4], [3, 4, 5, 6, 7])

        bruto = ScoringBreakdownCalculator().compute([vuelta]).gross_distribution

        assert bruto.birdie_or_better == 1
        assert bruto.par == 1
        assert bruto.bogey == 1
        # El triple entra en la misma cesta que el doble
        assert bruto.double_or_worse == 2
        assert bruto.holes == 5

    def test_un_eagle_cuenta_como_birdie_o_mejor(self):
        vuelta = vuelta_de_par([5], [3])

        bruto = ScoringBreakdownCalculator().compute([vuelta]).gross_distribution

        assert bruto.birdie_or_better == 1

    def test_bruto_y_neto_difieren_cuando_el_jugador_recibe_golpes(self):
        """
        El mismo hoyo: bogey en bruto, par en neto. Es justo lo que hace útil
        dar las dos, y por lo que un hándicap alto no ve solo bogeys.
        """
        vuelta = vuelta_de_par([4], [5], strokes_received=1)

        resultado = ScoringBreakdownCalculator().compute([vuelta])

        assert resultado.gross_distribution.bogey == 1
        assert resultado.gross_distribution.par == 0
        assert resultado.net_distribution.par == 1
        assert resultado.net_distribution.bogey == 0

    def test_sin_golpes_recibidos_bruto_y_neto_coinciden(self):
        vuelta = vuelta_de_par([4, 3, 5], [5, 3, 6])

        resultado = ScoringBreakdownCalculator().compute([vuelta])

        assert resultado.gross_distribution == resultado.net_distribution


class TestRendimientoPorPar:
    def test_separa_la_media_por_cada_par(self):
        # par 3 en bogey, par 4 en par, par 5 en birdie
        vuelta = vuelta_de_par([3, 4, 5], [4, 4, 4])

        por_par = {p.par: p for p in ScoringBreakdownCalculator().compute([vuelta]).by_par}

        assert por_par[3].average_to_par == 1.0
        assert por_par[4].average_to_par == 0.0
        assert por_par[5].average_to_par == -1.0
        assert por_par[3].holes == 1

    # La issue solo hablaba de par 3, 4 y 5, pero el par 6 existe: La Marquesa
    # tiene uno en el hoyo 9, en sus ocho barras
    def test_incluye_el_par_6_en_vez_de_perderlo(self):
        vuelta = vuelta_de_par([4, 6], [4, 7])

        pares = [p.par for p in ScoringBreakdownCalculator().compute([vuelta]).by_par]

        assert pares == [4, 6]

    def test_no_inventa_pares_que_no_se_jugaron(self):
        """Un pitch & putt es todo par 3, y su desglose no debe tener huecos."""
        vuelta = vuelta_de_par([3, 3, 3], [3, 4, 3])

        por_par = ScoringBreakdownCalculator().compute([vuelta]).by_par

        assert len(por_par) == 1
        assert por_par[0].par == 3

    def test_la_media_por_par_es_por_hoyo_y_no_por_vuelta(self):
        """
        Dos par 3, uno en par y otro en doble: la media es +1 por hoyo. Si se
        escalara a la vuelta daría un número sin sentido para un par 3.
        """
        vuelta = vuelta_de_par([3, 3], [3, 5])

        assert ScoringBreakdownCalculator().compute([vuelta]).by_par[0].average_to_par == 1.0


class TestNueves:
    def test_separa_la_ida_de_la_vuelta(self):
        holes = [hoyo(n, 4, 4) for n in range(1, 10)] + [hoyo(n, 4, 5) for n in range(10, 19)]
        vuelta = RoundOutcome(golf_course_id="c1", golf_course_name="Campo", holes=holes)

        resultado = ScoringBreakdownCalculator().compute([vuelta])

        assert resultado.front_nine.average_to_par == 0.0
        assert resultado.back_nine.average_to_par == 1.0
        assert resultado.front_nine.holes == 9

    def test_el_hoyo_9_es_ida_y_el_10_es_vuelta(self):
        vuelta = RoundOutcome(
            golf_course_id=None,
            golf_course_name=None,
            holes=[hoyo(9, 4, 5), hoyo(10, 4, 4)],
        )

        resultado = ScoringBreakdownCalculator().compute([vuelta])

        assert resultado.front_nine.holes == 1
        assert resultado.front_nine.average_to_par == 1.0
        assert resultado.back_nine.average_to_par == 0.0

    def test_quien_solo_juega_la_ida_no_tiene_media_de_vuelta(self):
        """None, no cero: no haber jugado no es haber jugado en par."""
        vuelta = RoundOutcome(
            golf_course_id=None, golf_course_name=None, holes=[hoyo(1, 4, 4)]
        )

        assert ScoringBreakdownCalculator().compute([vuelta]).back_nine is None


class TestPorCampo:
    def test_ordena_los_campos_de_mejor_a_peor(self):
        facil = vuelta_de_par([4] * 18, [4] * 18, golf_course_id="c1", golf_course_name="Fácil")
        dificil = vuelta_de_par(
            [4] * 18, [6] * 18, golf_course_id="c2", golf_course_name="Difícil"
        )

        por_campo = ScoringBreakdownCalculator().compute([dificil, facil]).by_course

        assert [c.golf_course_name for c in por_campo] == ["Fácil", "Difícil"]
        assert por_campo[0].average_to_par == 0.0
        assert por_campo[1].average_to_par == 36.0

    def test_agrupa_varias_vueltas_del_mismo_campo(self):
        buena = vuelta_de_par([4] * 18, [4] * 18, golf_course_id="c1", golf_course_name="Campo")
        mala = vuelta_de_par([4] * 18, [5] * 18, golf_course_id="c1", golf_course_name="Campo")

        por_campo = ScoringBreakdownCalculator().compute([buena, mala]).by_course

        assert len(por_campo) == 1
        assert por_campo[0].rounds == 2
        assert por_campo[0].average_to_par == 9.0

    # Media vuelta se escala a 18, igual que hace `scoring_avg`: sin eso, jugar
    # nueve hoyos parecería jugar la mitad de mal
    def test_lleva_la_media_vuelta_a_la_escala_de_18(self):
        nueve = vuelta_de_par([4] * 9, [5] * 9, golf_course_id="c1", golf_course_name="Campo")

        assert ScoringBreakdownCalculator().compute([nueve]).by_course[0].average_to_par == 18.0

    def test_deja_fuera_las_vueltas_sin_campo_conocido(self):
        """Sin campo no hay nada con lo que comparar; agruparlas mentiría."""
        sin_campo = vuelta_de_par([4] * 18, [5] * 18)

        assert ScoringBreakdownCalculator().compute([sin_campo]).by_course == []

    def test_esas_vueltas_si_cuentan_para_el_resto_del_desglose(self):
        sin_campo = vuelta_de_par([4, 3], [5, 3])

        resultado = ScoringBreakdownCalculator().compute([sin_campo])

        assert resultado.holes_counted == 2
        assert resultado.by_par != []
