"""
Tests for Support Module - Contact Form

Tests for ContactCategory, ContactRequestDTO, ContactResponseDTO, and SubmitContactUseCase
(the form arrives by email to admin@, 6 Nov 2026).
"""

from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from src.modules.support.application.dto.contact_dto import (
    ContactRequestDTO,
    ContactResponseDTO,
)
from src.modules.support.application.use_cases.submit_contact_use_case import (
    ContactDeliveryError,
    ContactQuotaExceededError,
    SubmitContactUseCase,
)
from src.modules.support.domain.value_objects.contact_category import ContactCategory

# =============================================================================
# ContactCategory Tests
# =============================================================================


class TestContactCategory:
    """Tests for ContactCategory enum."""

    def test_all_categories_exist(self):
        """All expected categories should be defined."""
        assert ContactCategory.BUG.value == "BUG"
        assert ContactCategory.FEATURE.value == "FEATURE"
        assert ContactCategory.QUESTION.value == "QUESTION"
        assert ContactCategory.OTHER.value == "OTHER"

    def test_category_is_string_enum(self):
        """ContactCategory should be a string enum for Pydantic compatibility."""
        assert isinstance(ContactCategory.BUG, str)
        assert ContactCategory.BUG == "BUG"


# =============================================================================
# ContactRequestDTO Tests
# =============================================================================


class TestContactRequestDTO:
    """Tests for ContactRequestDTO validation."""

    def _valid_data(self, **overrides):
        """Helper to build valid DTO data with optional overrides."""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "category": "BUG",
            "subject": "Something is broken",
            "message": "When I click the button, nothing happens. Please fix.",
        }
        data.update(overrides)
        return data

    def test_valid_request(self):
        """Should create DTO with valid data."""
        dto = ContactRequestDTO(**self._valid_data())
        assert dto.name == "John Doe"
        assert str(dto.email) == "john@example.com"
        assert dto.category == ContactCategory.BUG
        assert dto.subject == "Something is broken"

    def test_all_categories_accepted(self):
        """Should accept all valid category values."""
        for category in ["BUG", "FEATURE", "QUESTION", "OTHER"]:
            dto = ContactRequestDTO(**self._valid_data(category=category))
            assert dto.category.value == category

    def test_name_too_short(self):
        """Should reject name shorter than 2 characters."""
        with pytest.raises(ValidationError):
            ContactRequestDTO(**self._valid_data(name="A"))

    def test_name_too_long(self):
        """Should reject name longer than 100 characters."""
        with pytest.raises(ValidationError):
            ContactRequestDTO(**self._valid_data(name="A" * 101))

    def test_invalid_email(self):
        """Should reject invalid email format."""
        with pytest.raises(ValidationError):
            ContactRequestDTO(**self._valid_data(email="not-an-email"))

    def test_invalid_category(self):
        """Should reject invalid category value."""
        with pytest.raises(ValidationError):
            ContactRequestDTO(**self._valid_data(category="INVALID"))

    def test_subject_too_short(self):
        """Should reject subject shorter than 3 characters."""
        with pytest.raises(ValidationError):
            ContactRequestDTO(**self._valid_data(subject="AB"))

    def test_subject_too_long(self):
        """Should reject subject longer than 200 characters."""
        with pytest.raises(ValidationError):
            ContactRequestDTO(**self._valid_data(subject="A" * 201))

    def test_message_too_short(self):
        """Should reject message shorter than 10 characters."""
        with pytest.raises(ValidationError):
            ContactRequestDTO(**self._valid_data(message="Short"))

    def test_message_too_long(self):
        """Should reject message longer than 5000 characters."""
        with pytest.raises(ValidationError):
            ContactRequestDTO(**self._valid_data(message="A" * 5001))

    def test_missing_required_fields(self):
        """Should reject request with missing fields."""
        with pytest.raises(ValidationError):
            ContactRequestDTO()


# =============================================================================
# ContactResponseDTO Tests
# =============================================================================


class TestContactResponseDTO:
    """Tests for ContactResponseDTO."""

    def test_valid_response(self):
        """Should create response DTO with message."""
        dto = ContactResponseDTO(message="Success")
        assert dto.message == "Success"


# =============================================================================
# SubmitContactUseCase Tests
# =============================================================================


class TestSubmitContactUseCase:
    """
    El formulario de contacto llega por correo a admin@ (6 nov 2026). Antes abría
    una issue en un repositorio público de GitHub, con el nombre y el correo.

      #   Caso                                   | Resultado
      ----|----------------------------------------|-----------------------------------
      C1  un mensaje                             | [Contacto · <categoría>] <asunto>, responder a quien escribe
      C2  saltos de línea y control en el asunto | se quitan; el cuerpo, texto plano con todo
      C4  el tope diario lleno                   | ContactQuotaExceededError, sin enviar
      C5  el envío falla                         | ContactDeliveryError y el hueco del tope se devuelve
    """

    def _caso(self, envia=True, cabe=True):
        mailer = AsyncMock()
        mailer.send.return_value = envia
        cupo = Mock()
        cupo.reserva.return_value = cabe
        return SubmitContactUseCase(mailer, cupo), mailer, cupo

    def _peticion(self, **cambios):
        datos = {
            "name": "Ana López",
            "email": "ana@example.com",
            "category": ContactCategory.QUESTION,
            "subject": "Duda con el hándicap",
            "message": "¿Cómo se calcula el hándicap de juego en un fourball?",
        }
        datos.update(cambios)
        return ContactRequestDTO(**datos)

    async def test_c1_it_emails_admin_with_reply_to_the_sender(self):
        """
        Given: Un mensaje de contacto
        When: Se envía
        Then: Un correo con el asunto [Contacto · Pregunta] y «responder a» quien escribe
        """
        caso, mailer, _cupo = self._caso()

        respuesta = await caso.execute(self._peticion())

        assert isinstance(respuesta, ContactResponseDTO)
        mailer.send.assert_awaited_once()
        kw = mailer.send.call_args.kwargs
        assert kw["subject"] == "[Contacto · Pregunta] Duda con el hándicap"
        assert kw["reply_to"] == "ana@example.com"

    @pytest.mark.parametrize(
        ("categoria", "nombre"),
        [
            (ContactCategory.BUG, "Error"),
            (ContactCategory.FEATURE, "Sugerencia"),
            (ContactCategory.QUESTION, "Pregunta"),
            (ContactCategory.OTHER, "Otro"),
        ],
    )
    async def test_c1_every_category_has_its_name(self, categoria, nombre):
        """Cada categoría sale con su nombre en el asunto."""
        caso, mailer, _cupo = self._caso()

        await caso.execute(self._peticion(category=categoria))

        assert mailer.send.call_args.kwargs["subject"].startswith(f"[Contacto · {nombre}] ")

    async def test_c2_the_subject_cannot_carry_line_breaks(self):
        """
        Given: Un asunto y un nombre con saltos de línea y caracteres de control
        When: Se envía
        Then: Quedan en una línea: no se pueden colar cabeceras ni líneas falsas
        """
        caso, mailer, _cupo = self._caso()

        await caso.execute(self._peticion(subject="Hola\r\nBcc: x@y.z\x00 fin", name="Ana\nLópez"))

        kw = mailer.send.call_args.kwargs
        assert kw["subject"] == "[Contacto · Pregunta] Hola Bcc: x@y.z fin"
        assert "Nombre: Ana López\n" in kw["text"]

    async def test_c2_the_body_is_plain_text_with_everything(self):
        """
        Given: Un mensaje con < y & y varias líneas
        When: Se envía
        Then: Texto plano, tal cual (sin &lt;): nombre, correo, categoría y mensaje
        """
        caso, mailer, _cupo = self._caso()
        mensaje = "Primera línea <b>negrita</b> & más\nSegunda línea"

        await caso.execute(self._peticion(message=mensaje))

        kw = mailer.send.call_args.kwargs
        assert "Nombre: Ana López" in kw["text"]
        assert "Correo: ana@example.com" in kw["text"]
        assert "Categoría: Pregunta" in kw["text"]
        assert mensaje in kw["text"]
        assert set(kw) == {"subject", "text", "reply_to"}

    async def test_c4_a_full_daily_quota_sends_nothing(self):
        """
        Given: El tope diario de mensajes, lleno
        When: Llega otro
        Then: ContactQuotaExceededError y no se envía: el cupo de correos es de todos
        """
        caso, mailer, _cupo = self._caso(cabe=False)

        with pytest.raises(ContactQuotaExceededError):
            await caso.execute(self._peticion())

        mailer.send.assert_not_awaited()

    async def test_c5_a_failed_delivery_gives_the_slot_back(self):
        """
        Given: Mailgun no acepta el correo
        When: Se envía
        Then: ContactDeliveryError, y el hueco del tope se devuelve (no salió)
        """
        caso, _mailer, cupo = self._caso(envia=False)

        with pytest.raises(ContactDeliveryError):
            await caso.execute(self._peticion())

        cupo.devuelve.assert_called_once()

    async def test_c5_a_sent_message_keeps_its_slot(self):
        """Enviado, el hueco se queda gastado."""
        caso, _mailer, cupo = self._caso()

        await caso.execute(self._peticion())

        cupo.reserva.assert_called_once()
        cupo.devuelve.assert_not_called()


class TestSubmitContactUseCaseRevision:
    """Lo que pidieron las revisiones del cambio a correo (revisor y auditoría OWASP)."""

    def _caso(self, envia=True):
        mailer = AsyncMock()
        mailer.send.return_value = envia
        cupo = Mock()
        cupo.reserva.return_value = True
        return SubmitContactUseCase(mailer, cupo), mailer, cupo

    def _peticion(self, **cambios):
        datos = {
            "name": "Ana López",
            "email": "ana@example.com",
            "category": ContactCategory.BUG,
            "subject": "Algo falla",
            "message": "La tarjeta no guarda el golpe del hoyo 7.",
        }
        datos.update(cambios)
        return ContactRequestDTO(**datos)

    async def test_an_exception_while_sending_gives_the_slot_back(self):
        """
        Given: El envío lanza una excepción inesperada
        When: Se envía
        Then: ContactDeliveryError y el hueco se devuelve: veinte fallos así no
              cierran el formulario un día
        """
        caso, mailer, cupo = self._caso()
        mailer.send.side_effect = RuntimeError("fallo raro")

        with pytest.raises(ContactDeliveryError):
            await caso.execute(self._peticion())

        cupo.devuelve.assert_called_once()

    async def test_control_characters_leave_the_body(self):
        """El cuerpo pierde los caracteres de control, salvo saltos y tabuladores."""
        caso, mailer, _cupo = self._caso()

        await caso.execute(self._peticion(message="Hola\x00 que\x1b tal\n\tbien"))

        assert "Hola que tal\n\tbien" in mailer.send.call_args.kwargs["text"]

    async def test_invisible_and_bidi_characters_leave_the_subject_and_name(self):
        """
        Given: Asunto y nombre con caracteres invisibles o que dan la vuelta al texto
        When: Se envía
        Then: Salen limpios: no se puede disfrazar el asunto en el buzón
        """
        caso, mailer, _cupo = self._caso()

        await caso.execute(
            self._peticion(subject="Pago\u202e pendiente\u200b ya", name="Ana\u200d López")
        )

        kw = mailer.send.call_args.kwargs
        assert kw["subject"] == "[Contacto · Error] Pago pendiente ya"
        assert "Nombre: Ana López\n" in kw["text"]

    async def test_a_subject_of_only_invisible_characters_says_so(self):
        """Un asunto que se queda vacío al limpiarlo sale como «(sin asunto)»."""
        caso, mailer, _cupo = self._caso()

        await caso.execute(self._peticion(subject="\u200b\u200b\u200b\u200b"))

        assert mailer.send.call_args.kwargs["subject"] == "[Contacto · Error] (sin asunto)"

    async def test_the_body_warns_that_the_address_is_unverified(self):
        """
        Given: Un mensaje
        When: Llega al buzón
        Then: Bajo el correo, que no está verificado: no responder a ciegas a un tercero
        """
        caso, mailer, _cupo = self._caso()

        await caso.execute(self._peticion())

        assert (
            "Correo: ana@example.com\n(sin verificar: lo escribió quien envía el formulario)\n"
            in mailer.send.call_args.kwargs["text"]
        )
