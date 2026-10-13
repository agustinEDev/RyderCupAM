"""Tests para CompetitionName Value Object."""

import pytest

from src.modules.competition.domain.value_objects.competition_name import (
    CompetitionName,
    InvalidCompetitionNameError,
)


class TestCompetitionNameCreation:
    """Tests para la creación de objetos CompetitionName."""

    def test_create_valid_name(self):
        """Debe crear un CompetitionName con nombre válido."""
        name = CompetitionName("Ryder Cup 2025")
        assert name.value == "Ryder Cup 2025"

    @pytest.mark.parametrize(
        "escrito",
        ["QA Medal qcf15", "RCG El Prat", "Copa McGregor", "ryder cup amateur"],
    )
    def test_keeps_the_name_as_written(self, escrito):
        """Las mayúsculas del organizador se respetan (#540): nada de title()."""
        assert CompetitionName(escrito).value == escrito

    def test_create_name_with_spaces(self):
        """Debe remover espacios al inicio y final."""
        name = CompetitionName("  Ryder Cup 2025  ")
        assert name.value == "Ryder Cup 2025"

    @pytest.mark.parametrize(
        ("escrito", "guardado"),
        [
            ("<script>alert('x')</script>Ryder Cup", "alert('x')Ryder Cup"),
            ("Copa <b>de</b> Otoño", "Copa de Otoño"),
            ("Copa & Amigos", "Copa & Amigos"),
            ("Copa\x00 de\x07 Otoño", "Copa de Otoño"),
            # Anidadas: una pasada sola dejaba un <script> de verdad (/code-review)
            ("<<script>script>alert(1)<</script>/script>", "alert(1)"),
            ("<scr<b>ipt>Copa</scr</b>ipt>", "Copa"),
            # Invisibles y de dirección: fuera (/code-review)
            ("Copa\u200b de\u202e Otoño\ufeff", "Copa de Otoño"),
            # No son etiquetas: se quedan (revisor)
            ("Hcp < 10 y > 5", "Hcp < 10 y > 5"),
            ("Copa <3 amigos>", "Copa <3 amigos>"),
        ],
    )
    def test_strips_html_tags_and_control_characters(self, escrito, guardado):
        """Sin title(), las etiquetas se quitan de verdad (#540; antes salía «<Script>»)."""
        assert CompetitionName(escrito).value == guardado

    @pytest.mark.parametrize("escrito", ["<b></b>", "<b>ab</b>", " a\x00b ", "\u200b\u200b\u200b"])
    def test_too_short_once_cleaned(self, escrito):
        """El mínimo de 3 se mira después de limpiar: antes daba un 500 (revisor)."""
        with pytest.raises(InvalidCompetitionNameError):
            CompetitionName(escrito)

    def test_the_error_is_a_value_error(self):
        """Así las rutas lo devuelven como 400 y no como 500."""
        assert issubclass(InvalidCompetitionNameError, ValueError)

    def test_collapses_inner_whitespace(self):
        """Espacios de más dentro del nombre: uno solo (#540)."""
        assert CompetitionName("Copa  de\tOtoño   2026").value == "Copa de Otoño 2026"


class TestCompetitionNameValidation:
    """Tests para la validación de nombres."""

    def test_empty_name_raises_error(self):
        """Nombre vacío debe lanzar InvalidCompetitionNameError."""
        with pytest.raises(
            InvalidCompetitionNameError,
            match="El nombre de la competición no puede estar vacío",
        ):
            CompetitionName("")

    def test_whitespace_only_name_raises_error(self):
        """Nombre con solo espacios debe lanzar error."""
        with pytest.raises(
            InvalidCompetitionNameError,
            match="El nombre de la competición no puede estar vacío",
        ):
            CompetitionName("   ")

    def test_name_exceeds_max_length_raises_error(self):
        """Nombre mayor a 100 caracteres debe lanzar error."""
        long_name = "A" * 101
        with pytest.raises(InvalidCompetitionNameError, match="no puede exceder 100 caracteres"):
            CompetitionName(long_name)

    def test_name_exactly_100_chars_is_valid(self):
        """Nombre de exactamente 100 caracteres es válido."""
        name_100 = "A" * 100
        name = CompetitionName(name_100)
        # Title case capitaliza la primera letra
        assert len(name.value) == 100

    def test_non_string_raises_error(self):
        """Tipo no string debe lanzar error."""
        with pytest.raises(InvalidCompetitionNameError, match="El nombre debe ser un string"):
            CompetitionName(123)


class TestCompetitionNameEquality:
    """Tests para comparación de nombres."""

    def test_same_names_are_equal(self):
        """Nombres iguales deben ser iguales."""
        name1 = CompetitionName("Ryder Cup 2025")
        name2 = CompetitionName("Ryder Cup 2025")
        assert name1 == name2

    def test_different_names_are_not_equal(self):
        """Nombres diferentes no son iguales."""
        name1 = CompetitionName("Ryder Cup 2025")
        name2 = CompetitionName("Masters 2025")
        assert name1 != name2

    def test_names_differing_only_in_case_share_the_key(self):
        """Son valores distintos, pero la misma clave para no repetir nombre (#540)."""
        name1 = CompetitionName("ryder cup")
        name2 = CompetitionName("RYDER  CUP")
        assert name1 != name2
        assert name1.clave == name2.clave

    def test_hash_is_consistent(self):
        """Hash debe ser consistente para nombres iguales."""
        name1 = CompetitionName("Ryder Cup 2025")
        name2 = CompetitionName("Ryder Cup 2025")
        assert hash(name1) == hash(name2)

    def test_can_use_in_set(self):
        """Debe poder usarse en sets."""
        name1 = CompetitionName("Ryder Cup 2025")
        name2 = CompetitionName("Ryder Cup 2025")
        name3 = CompetitionName("Masters 2025")

        names_set = {name1, name2, name3}
        assert len(names_set) == 2  # name1 y name2 son iguales


class TestCompetitionNameStringRepresentation:
    """Tests para representación string."""

    def test_str_returns_value(self):
        """__str__ debe retornar el valor."""
        name = CompetitionName("Ryder Cup 2025")
        assert str(name) == "Ryder Cup 2025"


class TestLoYaGuardado:
    def test_a_stored_name_loads_as_it_is(self):
        """Lo guardado con las reglas de antes no se vuelve a validar al leer (/code-review)."""
        assert CompetitionName.guardado("A").value == "A"
        assert CompetitionName.guardado("<B>X</B>").value == "<B>X</B>"
        assert CompetitionName.guardado("Copa") == CompetitionName("Copa")
