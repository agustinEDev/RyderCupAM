"""
La composición conecta el log de auditoría de verdad (#750, 7 nov 2026).

Los ocho casos de uso reciben el log por su puerto, obligatorio: si `dependencies.py` no
se lo diera, fallaría al construirlos; y si le diera otra cosa, la auditoría se perdería
en silencio. Este guardián comprueba que es el adaptador de verdad.
"""

from unittest.mock import MagicMock

import pytest

from src.config import dependencies as d
from src.modules.user.infrastructure.security.security_audit_logger import SecurityAuditLogger

CASOS = [
    ("login", lambda: d.get_login_user_use_case(*(MagicMock() for _ in range(6)))),
    ("logout", lambda: d.get_logout_user_use_case(MagicMock())),
    ("refresco", lambda: d.get_refresh_access_token_use_case(MagicMock(), MagicMock())),
    ("confirmar correo", lambda: d.get_confirm_email_change_use_case(MagicMock())),
    ("seguridad", lambda: d.get_update_security_use_case(MagicMock(), MagicMock())),
    ("pedir restablecer", lambda: d.get_request_password_reset_use_case(MagicMock(), MagicMock())),
    ("restablecer", lambda: d.get_reset_password_use_case(MagicMock(), MagicMock())),
    ("google", lambda: d.get_google_login_use_case(*(MagicMock() for _ in range(5)))),
    ("vincular google", lambda: d.get_link_google_account_use_case(MagicMock(), MagicMock())),
]


@pytest.mark.parametrize(("nombre", "crea"), CASOS, ids=[c[0] for c in CASOS])
def test_each_use_case_gets_the_real_audit_logger(nombre, crea):
    """
    Given: El proveedor de cada caso de uso de dependencies.py
    When: Se construye
    Then: Su log de auditoría es el adaptador de verdad
    """
    assert isinstance(crea()._security_audit, SecurityAuditLogger), nombre
