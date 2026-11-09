"""
Lo que llega DE VERDAD a Sentry de un evento de seguridad mandado dentro de una
petición (revisión de la fase 2, 9 nov 2026).

La integración de FastAPI adjunta el cuerpo de la petición a cualquier evento que se
capture dentro de ella: el de un cambio de correo o de un login llevaba el correo
tecleado. Y la IP iba en el contexto, que el filtro de cabeceras no mira (BE #466).
Ahora el evento de seguridad sale con el método y la ruta de la petición, nada más, y
sin IP: el id del usuario basta, y la IP queda en el log (stdout).

Se prueba en un proceso aparte, con un transporte falso: iniciar Sentry en el proceso
de los tests engancharía sus integraciones a los demás.
"""

import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[5]

_PROGRAMA = r"""
import json
import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.transport import Transport

from src.config import sentry_config
from src.shared.domain.events.security_events import PasswordChangedEvent
from src.shared.infrastructure.logging.security_logger import avisa_a_sentry

eventos = []


class Falso(Transport):
    def capture_envelope(self, sobre):
        eventos.extend(i.payload.json for i in sobre.items if i.type == "event")


sentry_sdk.init(
    dsn="https://p@o0.ingest.sentry.io/0",
    transport=Falso(),
    send_default_pii=False,
    integrations=[FastApiIntegration()],
    before_send=sentry_config.before_send,
    include_local_variables=False,
)
app = FastAPI()


@app.patch("/api/v1/users/security")
async def seguridad(request: Request, body: dict):
    avisa_a_sentry(
        PasswordChangedEvent(user_id="u-1", ip_address="203.0.113.7", user_agent="ua")
    )
    return {}


TestClient(app).patch(
    "/api/v1/users/security?x=1",
    json={"new_email": "victima@example.com", "current_password": "hunter2"},
    headers={"X-Forwarded-For": "203.0.113.7", "Cookie": "a=b"},
)
sentry_sdk.flush()
print(json.dumps(eventos))
"""


def _eventos_enviados() -> list[dict]:
    """Ejecuta el programa y devuelve los eventos que habrían llegado a Sentry."""
    salida = subprocess.run(
        [sys.executable, "-c", _PROGRAMA],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(salida.stdout.strip().splitlines()[-1])


def test_a_security_event_reaches_sentry_without_body_ip_or_email():
    """
    Given: Sentry con la integración de FastAPI y el before_send de la app
    When: Se manda un evento de seguridad dentro de una petición con correo en el cuerpo
    Then: Llega uno, con el método y la ruta de la petición y nada más de ella, sin IP
          en el contexto ni en el usuario, y sin el correo en ningún sitio
    """
    [evento] = _eventos_enviados()

    assert evento["level"] == "warning"
    assert set(evento["request"]) <= {"method", "url"}
    assert evento["request"]["method"] == "PATCH"
    assert evento["request"]["url"].endswith("/api/v1/users/security")
    assert "ip_address" not in evento["contexts"]["security_event"]
    assert "ip_address" not in evento.get("user", {})
    assert evento["contexts"]["security_event"]["user_id"] == "u-1"
    texto = json.dumps(evento)
    assert "victima@example.com" not in texto
    assert "203.0.113.7" not in texto
