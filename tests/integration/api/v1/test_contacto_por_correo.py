"""
La ruta del formulario de contacto, que ahora manda un correo a admin@ (6 nov 2026).
"""

import pytest
from httpx import AsyncClient

from main import app
from src.config.cupo_de_contacto import cupo_de_contacto
from src.config.dependencies import get_contact_mailer
from src.config.settings import settings

pytestmark = pytest.mark.asyncio

MENSAJE = {
    "name": "Ana López",
    "email": "ana@example.com",
    "category": "QUESTION",
    "subject": "Duda con el hándicap",
    "message": "¿Cómo se calcula el hándicap de juego en un fourball?",
}


class _Buzon:
    def __init__(self, acepta=True):
        self.acepta = acepta
        self.enviados = []

    async def send(self, subject, text, reply_to):
        self.enviados.append({"subject": subject, "text": text, "reply_to": reply_to})
        return self.acepta


@pytest.fixture
def buzon():
    buzon = _Buzon()
    app.dependency_overrides[get_contact_mailer] = lambda: buzon
    cupo_de_contacto.reinicia()
    yield buzon
    app.dependency_overrides.pop(get_contact_mailer, None)
    cupo_de_contacto.reinicia()


async def test_c1_the_message_goes_by_email(client: AsyncClient, buzon):
    """
    Given: Un mensaje válido
    When: Se envía el formulario
    Then: 200 y un correo con su asunto y «responder a» quien escribe
    """
    r = await client.post("/api/v1/support/contact", json=MENSAJE)

    assert r.status_code == 200
    assert len(buzon.enviados) == 1
    enviado = buzon.enviados[0]
    assert enviado["subject"] == "[Contacto · Pregunta] Duda con el hándicap"
    assert enviado["reply_to"] == "ana@example.com"
    for dato in ("Ana López", "ana@example.com", "Pregunta", MENSAJE["message"]):
        assert dato in enviado["text"]


async def test_c4_a_full_daily_quota_answers_429_with_its_code(client: AsyncClient, buzon):
    """
    Given: El tope diario lleno
    When: Se envía otro mensaje
    Then: 429 con CONTACT_QUOTA_EXCEEDED y el texto que manda a admin@; no sale correo
    """
    while cupo_de_contacto.reserva():
        pass

    r = await client.post("/api/v1/support/contact", json=MENSAJE)

    assert r.status_code == 429
    assert r.json()["error_code"] == "CONTACT_QUOTA_EXCEEDED"
    assert settings.CONTACT_EMAIL in r.json()["detail"]
    assert buzon.enviados == []


async def test_c5_a_refused_email_answers_502(client: AsyncClient, buzon):
    """
    Given: Mailgun no acepta el correo
    When: Se envía el formulario
    Then: 502 con el mismo texto de siempre
    """
    buzon.acepta = False

    r = await client.post("/api/v1/support/contact", json=MENSAJE)

    assert r.status_code == 502
    assert r.json()["detail"] == "Unable to process your request. Please try again later."
    # El hueco del tope, devuelto: no salió
    assert cupo_de_contacto.reserva() is True and len(cupo_de_contacto._enviados) == 1


async def test_the_quota_text_names_the_configured_mailbox(client: AsyncClient, buzon, monkeypatch):
    """Si se cambia CONTACT_EMAIL, el 429 manda a escribir a ese buzón, no a otro."""
    monkeypatch.setattr(settings, "CONTACT_EMAIL", "otro.buzon@example.com")
    while cupo_de_contacto.reserva():
        pass

    r = await client.post("/api/v1/support/contact", json=MENSAJE)

    assert "otro.buzon@example.com" in r.json()["detail"]


async def test_one_network_sends_at_most_three_a_day(client: AsyncClient, buzon):
    """
    Given: Una red que ya mandó 3 mensajes hoy
    When: Manda el cuarto
    Then: 429 del límite por red (no el del tope de la app), y solo salieron 3: una red
          sola ya no cierra el formulario a todos (auditoría OWASP)
    """
    cabecera = {"X-Test-Client-ID": "contacto-una-red"}
    respuestas = [
        await client.post("/api/v1/support/contact", json=MENSAJE, headers=cabecera)
        for _ in range(4)
    ]

    assert [r.status_code for r in respuestas] == [200, 200, 200, 429]
    assert respuestas[3].json().get("error_code") != "CONTACT_QUOTA_EXCEEDED"
    assert len(buzon.enviados) == 3
