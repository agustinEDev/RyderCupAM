"""
El log de seguridad sigue saliendo por stdout aunque no pueda abrir su fichero
(revisión de la fase 2, 9 nov 2026).

En el Kind, `COPY . .` metía en la imagen el `logs/security_audit.log` local, de root,
y el usuario 10001 no podía abrirlo: el SecurityLogger no se creaba y, como stdout
colgaba del mismo arranque, el log se perdía entero sin avisar. Ahora `logs/` no entra
en la imagen, y si el fichero falla, stdout sigue y se avisa.
"""

import json
import logging
from pathlib import Path

from src.shared.domain.events.security_events import LogoutEvent
from src.shared.infrastructure.logging.security_logger import SecurityLogger

RAIZ = Path(__file__).resolve().parents[5]


def test_stdout_keeps_working_when_the_file_cannot_be_opened(tmp_path, capsys, caplog):
    """
    Given: Una carpeta de logs que no se puede crear (en su sitio hay un fichero)
    When: Se crea el SecurityLogger y se registra un evento
    Then: No lanza, el evento sale por stdout y queda un aviso de que falta el fichero
    """
    bloqueo = tmp_path / "logs"
    bloqueo.write_text("no soy una carpeta", encoding="utf-8")
    capsys.readouterr()

    with caplog.at_level(logging.WARNING):
        audit = SecurityLogger(log_dir=bloqueo, log_file="audit.log")
    audit.log_security_event(LogoutEvent(user_id="u-1", ip_address="1.2.3.4", user_agent="ua"))

    lineas = [json.loads(fila) for fila in capsys.readouterr().out.splitlines() if fila.strip()]
    assert any(
        fila.get("extra", {}).get("security_event", {}).get("event_type") == "LogoutEvent"
        for fila in lineas
    )
    assert any("stdout only" in r.getMessage() for r in caplog.records)


def test_the_local_logs_folder_does_not_go_into_the_image():
    """
    Given: El .dockerignore del repositorio
    When: Se buscan sus exclusiones
    Then: Excluye logs/: el fichero de root del equipo no entra en la imagen
    """
    lineas = (RAIZ / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert "logs/" in [linea.strip() for linea in lineas]
