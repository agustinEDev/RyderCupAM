"""
El historial de aceptaciones de los Términos (decisión de Agustín, 20 oct 2026).

Cada aceptación real deja una fila con la versión, cuándo, desde qué IP y con
qué navegador. Las columnas del usuario son solo el estado actual.
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.modules.user.domain.entities.terms_acceptance import (
    IP_ADDRESS_MAX_LENGTH,
    USER_AGENT_MAX_LENGTH,
    TermsAcceptance,
)
from src.modules.user.domain.services.terms_of_service import (
    TERMS_ACCEPTANCE_RETENTION_YEARS,
    terms_acceptance_purge_cutoff,
)
from src.modules.user.domain.value_objects.terms_acceptance_id import TermsAcceptanceId
from src.modules.user.domain.value_objects.user_id import UserId

AHORA = datetime(2026, 10, 20, 9, 30, tzinfo=UTC)


def _registro(**cambios) -> TermsAcceptance:
    datos = {
        "user_id": UserId.generate(),
        "user_email": "ana@example.com",
        "terms_version": "2026-10-20",
        "accepted_at": AHORA,
        "ip_address": "203.0.113.7",
        "user_agent": "Mozilla/5.0 (iPhone) Safari",
    }
    datos.update(cambios)
    return TermsAcceptance.record(**datos)


class TestRegistrar:
    def test_record_keeps_every_field(self):
        """
        Given: Una aceptación con versión, fecha, IP y navegador
        When: Se registra
        Then: Tiene un id nuevo y guarda todo tal cual
        """
        user_id = UserId.generate()

        fila = _registro(user_id=user_id)

        assert isinstance(fila.id, TermsAcceptanceId)
        assert fila.user_id == user_id
        assert fila.terms_version == "2026-10-20"
        assert fila.accepted_at == AHORA
        assert fila.ip_address == "203.0.113.7"
        assert fila.user_agent == "Mozilla/5.0 (iPhone) Safari"
        assert fila.user_email == "ana@example.com"
        assert fila.user_deleted_at is None

    def test_two_records_have_different_ids(self):
        """
        Given: Dos aceptaciones
        When: Se registran
        Then: Cada una tiene su id
        """
        assert _registro().id != _registro().id

    def test_record_without_ip_or_user_agent(self):
        """
        Given: Una aceptación sin IP ni navegador conocidos
        When: Se registra
        Then: Se guardan como None
        """
        fila = _registro(ip_address=None, user_agent=None)

        assert fila.ip_address is None
        assert fila.user_agent is None

    def test_long_user_agent_is_cut_to_the_column(self):
        """
        Given: Un navegador más largo que la columna
        When: Se registra
        Then: Se recorta a USER_AGENT_MAX_LENGTH
        """
        fila = _registro(user_agent="x" * (USER_AGENT_MAX_LENGTH + 50))

        assert fila.user_agent == "x" * USER_AGENT_MAX_LENGTH

    def test_ip_longer_than_the_column_is_dropped(self):
        """
        Given: Una "IP" más larga que cualquier IPv6
        When: Se registra
        Then: No se guarda (None): recortarla daría una IP falsa
        """
        fila = _registro(ip_address="1" * (IP_ADDRESS_MAX_LENGTH + 1))

        assert fila.ip_address is None

    def test_naive_date_is_rejected(self):
        """
        Given: Una fecha sin zona horaria
        When: Se registra
        Then: ValueError: el historial va en UTC
        """
        with pytest.raises(ValueError):
            _registro(accepted_at=datetime(2026, 10, 20, 9, 30))

    @pytest.mark.parametrize("version", ["", "  ", "x" * 21])
    def test_invalid_version_is_rejected(self, version):
        """
        Given: Una versión vacía o más larga que la columna
        When: Se registra
        Then: ValueError
        """
        with pytest.raises(ValueError):
            _registro(terms_version=version)

    def test_non_utc_date_is_rejected(self):
        """
        Given: Una fecha con zona pero no UTC
        When: Se registra
        Then: ValueError: todo el historial en UTC
        """
        madrid = timezone(timedelta(hours=2))

        with pytest.raises(ValueError):
            _registro(accepted_at=datetime(2026, 10, 20, 11, 30, tzinfo=madrid))

    @pytest.mark.parametrize("email", ["", "   ", "a" * 250 + "@x.com"])
    def test_invalid_email_snapshot_is_rejected(self, email):
        """
        Given: Un email vacío o más largo que la columna (255)
        When: Se registra
        Then: ValueError: sin email la fila no prueba nada tras borrar la cuenta
        """
        with pytest.raises(ValueError):
            _registro(user_email=email)


class TestBorradoDeLaCuenta:
    def test_detach_from_deleted_user_keeps_the_proof(self):
        """
        Given: Una aceptación de un usuario
        When: Se borra su cuenta
        Then: La fila deja de apuntar al usuario, guarda cuándo se borró y
            conserva email, versión, fecha, IP y navegador
        """
        fila = _registro()
        borrado = datetime(2027, 1, 1, tzinfo=UTC)

        fila.detach_from_deleted_user(borrado)

        assert fila.user_id is None
        assert fila.user_deleted_at == borrado
        assert fila.user_email == "ana@example.com"
        assert fila.terms_version == "2026-10-20"
        assert fila.accepted_at == AHORA
        assert (fila.ip_address, fila.user_agent) == ("203.0.113.7", "Mozilla/5.0 (iPhone) Safari")

    def test_detach_requires_a_utc_date(self):
        """
        Given: Una fecha de borrado sin zona
        When: Se desvincula
        Then: ValueError
        """
        with pytest.raises(ValueError):
            _registro().detach_from_deleted_user(datetime(2027, 1, 1))


class TestRetencion:
    def test_retention_is_three_years(self):
        """
        Given: La constante del dominio
        When: Se mira
        Then: Tres años (decisión de Agustín, 20 oct 2026)
        """
        assert TERMS_ACCEPTANCE_RETENTION_YEARS == 3

    @pytest.mark.parametrize(
        ("ahora", "corte"),
        [
            (datetime(2029, 10, 20, 12, tzinfo=UTC), datetime(2026, 10, 20, 12, tzinfo=UTC)),
            (datetime(2028, 2, 29, 8, tzinfo=UTC), datetime(2025, 2, 28, 8, tzinfo=UTC)),
        ],
    )
    def test_purge_cutoff_is_three_calendar_years_back(self, ahora, corte):
        """
        Given: Una fecha (también un 29 de febrero)
        When: Se calcula el corte de la purga
        Then: Tres años naturales antes (el 29-F cae en el 28-F)
        """
        assert terms_acceptance_purge_cutoff(ahora) == corte

    def test_purge_cutoff_requires_a_utc_date(self):
        """
        Given: Una fecha sin zona
        When: Se calcula el corte
        Then: ValueError
        """
        with pytest.raises(ValueError):
            terms_acceptance_purge_cutoff(datetime(2029, 10, 20))

    @pytest.mark.parametrize(
        ("borrado", "purgable"),
        [
            (None, False),
            (datetime(2026, 10, 19, 23, 59, tzinfo=UTC), True),
            (datetime(2026, 10, 20, 12, tzinfo=UTC), False),
            (datetime(2027, 6, 1, tzinfo=UTC), False),
        ],
    )
    def test_is_purgeable_only_after_three_years_from_deletion(self, borrado, purgable):
        """
        Given: Una fila de un usuario vivo, o borrado hace más o menos de 3 años
        When: Se pregunta si se puede purgar el 20 oct 2029 a las 12:00
        Then: Solo si se borró ANTES del corte (justo en el corte, aún no)
        """
        fila = _registro()
        if borrado is not None:
            fila.detach_from_deleted_user(borrado)

        assert fila.is_purgeable(datetime(2029, 10, 20, 12, tzinfo=UTC)) is purgable
