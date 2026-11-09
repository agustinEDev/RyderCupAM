"""
El correo tecleado no se guarda en claro en el log de seguridad (revisión de la fase 2,
decidido por Agustín el 9 nov 2026).

Un login fallido o un restablecimiento llevan el correo que alguien escribió: en el
fichero y en stdout (que Render guarda) va enmascarado, `j***@example.com`, más un hash
con clave (HMAC-SHA256 con una clave derivada de SECRET_KEY con su propia etiqueta,
como la del CSRF) para relacionar los intentos sobre el mismo correo sin guardarlo.
La IP y el navegador se quedan.
"""

import hashlib
import hmac
import json

import pytest

from src.shared.domain.events.security_events import LoginAttemptEvent
from src.shared.infrastructure.logging import security_logger as modulo
from src.shared.infrastructure.logging.security_logger import (
    SecurityLogger,
    enmascara_el_correo,
    huella_del_correo,
)

CORREO = "Jugador.Uno@Example.com"
IP = "203.0.113.7"
UA = "Mozilla/5.0 (prueba)"


@pytest.fixture
def audit(tmp_path, monkeypatch):
    """Un SecurityLogger en una carpeta temporal, sin mandar nada a Sentry."""
    monkeypatch.setattr(modulo.sentry_sdk, "capture_message", lambda *_a, **_k: None)
    return SecurityLogger(log_dir=tmp_path, log_file="audit.log")


def _fallo(email: str = CORREO) -> LoginAttemptEvent:
    """Un login fallido con el correo dado."""
    return LoginAttemptEvent(
        user_id=None,
        email=email,
        success=False,
        failure_reason="Invalid credentials",
        ip_address=IP,
        user_agent=UA,
    )


def _evento_en_stdout(salida: str) -> dict:
    """El evento de seguridad de la única línea JSON de stdout que lo lleva."""
    [linea] = [
        json.loads(fila)
        for fila in salida.splitlines()
        if fila.strip() and "security_event" in fila
    ]
    return linea


def test_the_typed_email_is_masked_with_its_keyed_hash_in_stdout_and_file(audit, tmp_path, capsys):
    """
    Given: Un login fallido con un correo
    When: Se registra
    Then: En stdout y en el fichero va `j***@example.com` y su hash, nunca el correo;
          la IP y el navegador se quedan
    """
    capsys.readouterr()

    audit.log_security_event(_fallo())
    audit.vacia()  # lo escribe el hilo del log

    linea = _evento_en_stdout(capsys.readouterr().out)
    evento = linea["extra"]["security_event"]
    assert evento["email"] == "j***@example.com"
    assert evento["email_hash"] == huella_del_correo(CORREO)
    assert (evento["ip_address"], evento["user_agent"]) == (IP, UA)
    assert "j***@example.com" in linea["message"]
    fichero = (tmp_path / "audit.log").read_text(encoding="utf-8")
    for texto in (json.dumps(linea), fichero):
        assert CORREO not in texto
        assert CORREO.lower() not in texto
        assert "jugador.uno" not in texto.lower()


def test_the_same_email_gives_the_same_hash_whatever_its_case():
    """
    Given: El mismo correo con otras mayúsculas y espacios, y otro correo
    When: Se calcula su hash
    Then: El mismo para el mismo correo, distinto para el otro
    """
    assert huella_del_correo(CORREO) == huella_del_correo("  jugador.uno@example.com ")
    assert huella_del_correo(CORREO) != huella_del_correo("jugador.dos@example.com")


def test_the_hash_is_an_hmac_with_a_key_derived_from_secret_key(monkeypatch):
    """
    Given: La SECRET_KEY de la app
    When: Se calcula el hash de un correo
    Then: Es HMAC-SHA256 con una clave DERIVADA (con su etiqueta, no SECRET_KEY a
          secas), recortado a 32 cifras; y cambia si cambia SECRET_KEY
    """
    clave = hmac.new(
        modulo.settings.SECRET_KEY.encode(), modulo._ETIQUETA_DE_LA_CLAVE_DEL_CORREO, hashlib.sha256
    ).digest()
    esperado = hmac.new(clave, b"jugador.uno@example.com", hashlib.sha256).hexdigest()[:32]
    sin_derivar = hmac.new(
        modulo.settings.SECRET_KEY.encode(), b"jugador.uno@example.com", hashlib.sha256
    ).hexdigest()[:32]

    assert huella_del_correo(CORREO) == esperado != sin_derivar
    antes = huella_del_correo(CORREO)
    monkeypatch.setattr(modulo.settings, "SECRET_KEY", "otra-clave-de-prueba-de-32-bytes!!")
    modulo._clave_del_correo.cache_clear()
    try:
        assert huella_del_correo(CORREO) != antes
    finally:
        monkeypatch.undo()
        modulo._clave_del_correo.cache_clear()


@pytest.mark.parametrize(
    ("correo", "mascara"),
    [
        ("ana@gmail.com", "a***@gmail.com"),
        ("A@x.es", "a***@x.es"),
        ("@dominio.com", "***@dominio.com"),
        ("sin-arroba", "***"),
        ("", ""),
    ],
)
def test_the_mask_keeps_only_the_first_letter_and_the_domain(correo, mascara):
    """
    Given: Correos de varias formas (también mal escritos)
    When: Se enmascaran
    Then: Primera letra, *** y el dominio; sin arroba, solo ***
    """
    assert enmascara_el_correo(correo) == mascara
