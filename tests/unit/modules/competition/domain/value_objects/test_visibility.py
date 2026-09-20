"""Quien puede ver una competicion y pedir sitio en ella (BE #318).

Hoy no existe la distincion: la pantalla de explorar ensena la Ryder de unos
amigos a cualquiera —su nombre, sus fechas y su campo—, y cualquiera puede
pedir plaza en ella. Eso no es una brecha, porque el organizador aprueba, pero
es justo lo que un torneo privado existe para evitar.

Es un enum y no un booleano porque los clubes vienen detras (FE #652): un
tercer caso, «solo para quien sigue al club», no deberia obligar a cambiar el
tipo de la columna.
"""

import pytest

from src.modules.competition.domain.value_objects.visibility import Visibility


class TestVisibility:
    def test_the_two_cases_that_hay(self):
        assert Visibility.PRIVATE == "PRIVATE"
        assert Visibility.PUBLIC == "PUBLIC"

    def test_a_private_one_is_not_announced(self):
        assert Visibility.PRIVATE.is_discoverable() is False

    def test_a_public_one_is(self):
        assert Visibility.PUBLIC.is_discoverable() is True

    def test_only_a_public_one_takes_requests(self):
        """En una privada se entra porque te invitan, no porque lo pidas."""
        assert Visibility.PUBLIC.accepts_enrollment_requests() is True
        assert Visibility.PRIVATE.accepts_enrollment_requests() is False

    def test_it_reads_from_its_name(self):
        assert Visibility("PRIVATE") is Visibility.PRIVATE

    def test_anything_else_is_refused(self):
        with pytest.raises(ValueError):
            Visibility("SEMI_PRIVADA")
