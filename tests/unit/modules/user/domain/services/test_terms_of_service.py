"""
Las validaciones de los Términos, en un solo sitio (terms_of_service).

`require_utc` y `validate_terms_version` las usan el DTO de la purga, el corte
de la purga, TermsAcceptance.record y User.accept_terms.
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.modules.user.domain.services.terms_of_service import (
    TERMS_VERSION_MAX_LENGTH,
    require_utc,
    validate_terms_version,
)


class TestRequireUtc:
    def test_utc_date_is_returned_as_is(self):
        """
        Given: Una fecha en UTC
        When: Se valida
        Then: Se devuelve la misma
        """
        fecha = datetime(2026, 10, 20, 9, tzinfo=UTC)

        assert require_utc(fecha, "fecha") is fecha

    @pytest.mark.parametrize(
        "fecha",
        [
            datetime(2026, 10, 20, 9),
            datetime(2026, 10, 20, 9, tzinfo=timezone(timedelta(hours=2))),
        ],
    )
    def test_naive_or_non_utc_date_is_rejected_with_its_name(self, fecha):
        """
        Given: Una fecha sin zona o con otra zona
        When: Se valida
        Then: ValueError que nombra el campo
        """
        with pytest.raises(ValueError, match="accepted_at"):
            require_utc(fecha, "accepted_at")


class TestValidateTermsVersion:
    def test_valid_version_is_returned(self):
        """
        Given: Una versión normal
        When: Se valida
        Then: Se devuelve tal cual
        """
        assert validate_terms_version("2026-10-20") == "2026-10-20"

    def test_version_of_max_length_is_valid(self):
        """
        Given: Una versión del largo justo de la columna
        When: Se valida
        Then: Vale
        """
        version = "x" * TERMS_VERSION_MAX_LENGTH

        assert validate_terms_version(version) == version

    @pytest.mark.parametrize("version", ["", "   ", "x" * (TERMS_VERSION_MAX_LENGTH + 1)])
    def test_empty_or_too_long_version_is_rejected(self, version):
        """
        Given: Una versión vacía, en blanco o más larga que la columna
        When: Se valida
        Then: ValueError
        """
        with pytest.raises(ValueError):
            validate_terms_version(version)
