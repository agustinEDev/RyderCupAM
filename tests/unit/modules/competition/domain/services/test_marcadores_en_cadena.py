"""
Los marcadores de una partida de stroke play (#251, PR 4; D12 decidida el 9 oct 2026).

Por defecto, en cadena: cada jugador marca al siguiente y el último al primero.
El organizador puede cambiarla, pero nadie se marca a sí mismo.

| Caso                                        | Resultado                     |
|---------------------------------------------|-------------------------------|
| Partida vacía o de 1                        | Sin marcadores                |
| De 2                                        | Se marcan el uno al otro      |
| De 3 / de 4                                 | A→B→C(→D)→A                   |
| Validar la cadena                           | Vale                          |
| Validar dos parejas (A↔B, C↔D)              | Vale                          |
| Alguien se marca a sí mismo                 | Error                         |
| Alguien se queda sin marcar a nadie         | Error                         |
| Alguien marca a uno de otra partida         | Error                         |
| Dos marcan al mismo                         | Error                         |
| Marca alguien que no está en la partida     | Error                         |
| Partida de 1 sin marcadores / con él mismo  | Vale / Error                  |
"""

import pytest

from src.modules.competition.domain.services.marcadores_en_cadena import (
    MarcadoresEnCadena,
    MarcadoresInvalidosError,
)
from src.modules.user.domain.value_objects.user_id import UserId

A, B, C, D, FUERA = (UserId.generate() for _ in range(5))


class TestDe:
    @pytest.mark.parametrize("jugadores", [[], [A]])
    def test_without_a_partner_nobody_marks(self, jugadores):
        assert MarcadoresEnCadena.de(jugadores) == {}

    def test_two_mark_each_other(self):
        assert MarcadoresEnCadena.de([A, B]) == {A: B, B: A}

    def test_three_go_round_in_a_chain(self):
        assert MarcadoresEnCadena.de([A, B, C]) == {A: B, B: C, C: A}

    def test_four_go_round_in_a_chain(self):
        assert MarcadoresEnCadena.de([A, B, C, D]) == {A: B, B: C, C: D, D: A}


class TestValidar:
    def test_the_default_chain_is_valid(self):
        MarcadoresEnCadena.validar([A, B, C, D], MarcadoresEnCadena.de([A, B, C, D]))

    def test_two_pairs_are_valid(self):
        MarcadoresEnCadena.validar([A, B, C, D], {A: B, B: A, C: D, D: C})

    def test_a_partida_of_one_without_markers_is_valid(self):
        MarcadoresEnCadena.validar([A], {})

    @pytest.mark.parametrize(
        ("jugadores", "marcadores"),
        [
            pytest.param([A, B, C], {A: A, B: C, C: B}, id="se marca a sí mismo"),
            pytest.param([A, B, C], {A: B, B: A}, id="uno no marca a nadie"),
            pytest.param([A, B, C], {A: B, B: C, C: FUERA}, id="marca a uno de fuera"),
            pytest.param([A, B, C], {A: B, B: A, C: A}, id="dos marcan al mismo"),
            pytest.param([A, B], {A: B, B: A, FUERA: A}, id="marca uno que no está"),
            pytest.param([A], {A: A}, id="partida de 1 consigo mismo"),
        ],
    )
    def test_anything_else_is_refused(self, jugadores, marcadores):
        with pytest.raises(MarcadoresInvalidosError):
            MarcadoresEnCadena.validar(jugadores, marcadores)
