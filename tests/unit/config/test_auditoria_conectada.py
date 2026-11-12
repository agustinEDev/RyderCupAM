"""
La composición conecta el log de auditoría de verdad (#750, 7 nov 2026).

Los ocho casos de uso reciben el log por su puerto, obligatorio: si `src.config.dependencies` no
se lo diera, fallaría al construirlos; y si le diera otra cosa, la auditoría se perdería
en silencio. Este guardián comprueba que es el adaptador de verdad.
"""

import inspect
from unittest.mock import MagicMock

import pytest

from src.config import dependencies as d
from src.modules.user.infrastructure.security.security_audit_logger import SecurityAuditLogger

CASOS = [
    d.get_login_user_use_case,
    d.get_logout_user_use_case,
    d.get_refresh_access_token_use_case,
    d.get_confirm_email_change_use_case,
    d.get_update_security_use_case,
    d.get_request_password_reset_use_case,
    d.get_reset_password_use_case,
    d.get_google_login_use_case,
    d.get_link_google_account_use_case,
]


@pytest.mark.parametrize("proveedor", CASOS, ids=[c.__name__ for c in CASOS])
def test_each_use_case_gets_the_real_audit_logger(proveedor):
    """
    Given: El proveedor de cada caso de uso de src.config.dependencies
    When: Se construye con lo que FastAPI le inyecta
    Then: El log de auditoría es el de `get_security_audit_logger`, y es el de verdad
    """
    parametros = inspect.signature(proveedor).parameters
    assert parametros["security_audit"].default.dependency is d.get_security_audit_logger

    logger = d.get_security_audit_logger()
    assert isinstance(logger, SecurityAuditLogger)
    otros = {n: MagicMock() for n in parametros if n != "security_audit"}

    assert proveedor(**otros, security_audit=logger)._security_audit is logger
