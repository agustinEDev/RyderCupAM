"""
La ruta del formulario de contacto, que ahora manda un correo a admin@ (6 nov 2026).
"""

import pytest
from httpx import AsyncClient

from main import app
from src.config.cupo_de_contacto import cupo_de_contacto
from src.config.dependencies import get_contact_mailer

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
    assert buzon.enviados == [
        {
            "subject": "[Contacto · Pregunta] Duda con el hándicap",
            "text": buzon.enviados[0]["text"],
            "reply_to": "ana@example.com",
        }
    ]


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
    assert "admin@rydercupfriends.com" in r.json()["detail"]
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
