"""
Cuando cuenta una partida rapida en lo social (tabla aprobada el 22 oct 2026, A).

| Caso                                                     | Cuentan                       |
|----------------------------------------------------------|-------------------------------|
| Todos con los 18                                         | Todos                         |
| Dos con los mismos 9 (exactos)                           | Los dos                       |
| La referencia es 8                                       | Nadie                         |
| 18 y 17                                                  | Solo el de 18                 |
| 1-9 frente a 10-18 (mismo numero, distintos hoyos)       | Nadie (decision conservadora) |
| 1-9, 1-9 y 1-8                                           | Los dos de 1-9                |
| Nadie anoto                                              | Nadie                         |
| Match play decidido antes de tiempo                      | Cuenta, tenga lo que tenga    |
| Match play con los mismos 9 por bando                    | Cuenta                        |
| Match play con 8, o bandos con hoyos distintos           | No cuenta                     |
"""

from src.modules.social.domain.services.counted_round import (
    MIN_COUNTED_HOLES,
    counting_units,
    holes_by_side,
    match_play_counts,
)
from src.shared.domain.value_objects.match_format import MatchFormat

TODOS = range(1, 19)
IDA = range(1, 10)
VUELTA = range(10, 19)


class TestCountingUnits:
    def test_el_minimo_son_nueve_hoyos(self):
        assert MIN_COUNTED_HOLES == 9

    def test_todos_con_los_18_cuentan_todos(self):
        assert counting_units({"ana": TODOS, "eva": TODOS}) == {"ana", "eva"}

    def test_nueve_hoyos_exactos_cuentan(self):
        assert counting_units({"ana": IDA, "eva": IDA}) == {"ana", "eva"}

    def test_con_ocho_de_referencia_no_cuenta_nadie(self):
        assert counting_units({"ana": range(1, 9), "eva": range(1, 9)}) == frozenset()

    def test_quien_tiene_menos_que_la_referencia_no_cuenta(self):
        assert counting_units({"ana": TODOS, "eva": range(1, 18)}) == {"ana"}

    def test_mismo_numero_de_hoyos_pero_distintos_no_cuenta_nadie(self):
        """1-9 frente a 10-18: no hay una referencia, no se compara lo que no se jugo igual."""
        assert counting_units({"ana": IDA, "eva": VUELTA}) == frozenset()

    def test_cuentan_los_que_tienen_exactamente_la_referencia(self):
        assert counting_units({"ana": IDA, "eva": IDA, "luz": range(1, 9)}) == {"ana", "eva"}

    def test_el_mismo_numero_con_un_hoyo_cambiado_no_es_la_referencia(self):
        """Ana y Eva 1-9; Luz 1-8 y el 10: nueve hoyos, pero no los mismos."""
        luz = [*range(1, 9), 10]
        assert counting_units({"ana": IDA, "eva": IDA, "luz": luz}) == frozenset()

    def test_solo_uno_con_la_vuelta_entera(self):
        assert counting_units({"ana": TODOS}) == {"ana"}

    def test_sin_hoyos_no_cuenta_nadie(self):
        assert counting_units({}) == frozenset()
        assert counting_units({"ana": []}) == frozenset()


class TestMatchPlayCounts:
    def test_decidido_antes_de_tiempo_cuenta_siempre(self):
        assert match_play_counts(range(1, 17), range(1, 15), decided_early=True)

    def test_los_mismos_nueve_hoyos_por_bando_cuentan(self):
        assert match_play_counts(IDA, IDA, decided_early=False)

    def test_con_ocho_no_cuenta(self):
        assert not match_play_counts(range(1, 9), range(1, 9), decided_early=False)

    def test_un_solo_hoyo_no_cuenta(self):
        """El caso que se corrige: un hoyo anotado ya no es «Ganaste 1UP»."""
        assert not match_play_counts([1], [1], decided_early=False)

    def test_un_bando_con_menos_hoyos_no_cuenta(self):
        assert not match_play_counts(TODOS, range(1, 18), decided_early=False)

    def test_bandos_con_hoyos_distintos_no_cuenta(self):
        assert not match_play_counts(IDA, VUELTA, decided_early=False)


class TestHolesBySide:
    """
    Los hoyos que entrego un bando. En fourball, con la bola de los dos: como la
    pantalla de la partida y los torneos (Agustin, 24 oct 2026, deshace la
    bola de uno del 22 oct).
    """

    def test_singles_los_del_jugador(self):
        scores = {"ana": {1: 4, 2: 5}, "eva": {3: 4}}

        assert holes_by_side(scores, {"ana"}, MatchFormat.SINGLES) == {1, 2}

    def test_fourball_hacen_falta_los_dos(self):
        scores = {"ana": {1: 4, 2: 5, 3: 4}, "pepa": {2: None, 3: 6}, "eva": {4: 4}}

        assert holes_by_side(scores, {"ana", "pepa"}, MatchFormat.FOURBALL) == {2, 3}

    def test_fourball_con_uno_sin_nada_no_entrega_ninguno(self):
        scores = {"ana": {1: 4, 2: 5}}

        assert holes_by_side(scores, {"ana", "pepa"}, MatchFormat.FOURBALL) == frozenset()

    def test_foursomes_basta_la_bola_del_bando(self):
        """Una bola por bando, guardada a nombre de uno."""
        scores = {"ana": {1: 4, 2: None}, "eva": {4: 4}}

        assert holes_by_side(scores, {"ana", "pepa"}, MatchFormat.FOURSOMES) == {1, 2}

    def test_bando_sin_nada(self):
        assert holes_by_side({"eva": {1: 4}}, {"ana", "pepa"}, MatchFormat.FOURSOMES) == frozenset()
