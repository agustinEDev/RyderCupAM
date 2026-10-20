"""
Aceptación de los Términos en el agregado User.

La versión vigente vive en el dominio (`terms_of_service.CURRENT_TERMS_VERSION`):
quien no tiene aceptada ESA versión no ha aceptado los Términos, aunque
aceptara una anterior. Cambiarla obliga a todos a aceptar de nuevo.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.modules.user.domain.entities.user import User
from src.modules.user.domain.services import terms_of_service


def _usuario() -> User:
    return User.create(
        first_name="Ana",
        last_name="Lopez",
        email_str="ana@example.com",
        plain_password="V@l1dP@ss123!",
    )


def _usuario_de_google() -> User:
    return User.create_from_oauth(first_name="Ana", last_name="Lopez", email_str="ana@gmail.com")


class TestVersionVigente:
    def test_current_terms_version_returns_the_constant(self, monkeypatch):
        """
        Given: Una versión vigente cualquiera
        When: Se pregunta por la vigente
        Then: Se lee la constante en el momento, no una copia de cuando se importó
        """
        monkeypatch.setattr(terms_of_service, "CURRENT_TERMS_VERSION", "2099-01-01")

        assert terms_of_service.current_terms_version() == "2099-01-01"

    def test_current_terms_version_is_a_short_non_empty_string(self):
        """
        Given: La constante del backend
        When: Se mira
        Then: Es una cadena no vacía que cabe en la columna (20 caracteres)
        """
        version = terms_of_service.current_terms_version()

        assert isinstance(version, str)
        assert 0 < len(version) <= terms_of_service.TERMS_VERSION_MAX_LENGTH


class TestUsuarioNuevo:
    def test_create_starts_without_acceptance(self):
        """
        Given: Un usuario creado por la factoría de registro
        When: Aún no ha aceptado nada
        Then: No tiene fecha ni versión, y no consta como aceptado
        """
        user = _usuario()

        assert user.terms_accepted_at is None
        assert user.terms_version is None
        assert user.terms_accepted is False

    def test_create_from_oauth_starts_without_acceptance(self):
        """
        Given: Un usuario dado de alta con Google (B3)
        When: Se crea
        Then: Sin fecha ni versión: tendrá que aceptar al entrar
        """
        user = _usuario_de_google()

        assert user.terms_accepted_at is None
        assert user.terms_version is None
        assert user.terms_accepted is False


class TestAceptar:
    def test_accept_terms_stores_version_and_utc_now(self):
        """
        Given: Un usuario sin aceptación
        When: Acepta la versión vigente
        Then: Guarda esa versión y la fecha de ahora, en UTC
        """
        user = _usuario()
        antes = datetime.now(UTC)

        cambiado = user.accept_terms(terms_of_service.current_terms_version())

        despues = datetime.now(UTC)
        assert cambiado is True
        assert user.terms_version == terms_of_service.current_terms_version()
        assert user.terms_accepted_at is not None
        assert user.terms_accepted_at.tzinfo is not None
        assert user.terms_accepted_at.utcoffset() == timedelta(0)
        assert antes <= user.terms_accepted_at <= despues
        assert user.terms_accepted is True

    def test_accept_terms_twice_same_version_keeps_the_first_date(self):
        """
        Given: Un usuario que ya aceptó la versión vigente
        When: Vuelve a aceptarla
        Then: No cambia nada: ni la fecha ni la versión (idempotente)
        """
        user = _usuario()
        user.accept_terms(terms_of_service.current_terms_version())
        primera = user.terms_accepted_at

        cambiado = user.accept_terms(terms_of_service.current_terms_version())

        assert cambiado is False
        assert user.terms_accepted_at == primera

    def test_accept_terms_new_version_updates_date_and_version(self):
        """
        Given: Un usuario que aceptó una versión anterior
        When: Acepta otra
        Then: Se guardan la nueva versión y una fecha nueva
        """
        user = _usuario()
        user.accept_terms("2000-01-01")
        primera = user.terms_accepted_at

        cambiado = user.accept_terms("2000-02-02")

        assert cambiado is True
        assert user.terms_version == "2000-02-02"
        assert user.terms_accepted_at is not None
        assert primera is not None
        assert user.terms_accepted_at >= primera

    @pytest.mark.parametrize("version", ["", "   ", "x" * 21])
    def test_accept_terms_rejects_an_invalid_version(self, version):
        """
        Given: Una versión vacía o más larga que la columna
        When: Se intenta aceptar
        Then: ValueError, y el usuario sigue sin aceptación
        """
        user = _usuario()

        with pytest.raises(ValueError):
            user.accept_terms(version)

        assert user.terms_version is None
        assert user.terms_accepted_at is None


class TestCambioDeVersion:
    def test_terms_accepted_false_when_current_version_changes(self, monkeypatch):
        """
        Given: Un usuario que aceptó la versión vigente (B7)
        When: El backend pasa a otra versión
        Then: Deja de constar como aceptado, sin tocar lo que aceptó
        """
        user = _usuario()
        user.accept_terms(terms_of_service.current_terms_version())
        aceptada = user.terms_version

        monkeypatch.setattr(terms_of_service, "CURRENT_TERMS_VERSION", "2099-01-01")

        assert user.terms_accepted is False
        assert user.terms_version == aceptada

    def test_terms_version_required_follows_the_constant(self, monkeypatch):
        """
        Given: Cualquier usuario
        When: Cambia la versión vigente
        Then: La versión exigida es la nueva
        """
        user = _usuario()

        monkeypatch.setattr(terms_of_service, "CURRENT_TERMS_VERSION", "2099-01-01")

        assert user.terms_version_required == "2099-01-01"
