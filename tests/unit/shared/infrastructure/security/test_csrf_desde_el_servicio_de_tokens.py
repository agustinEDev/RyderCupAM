"""
El servicio de tokens firma el CSRF de la sesión (auditoría de arquitectura del 9 nov 2026).

Los casos de uso de login, Google y refresco lo generaban importando
`src.config.csrf_config`; ahora lo piden al servicio de tokens que ya reciben, y
este delega en la firma de siempre.
"""

from src.config.csrf_config import csrf_token_belongs_to
from src.shared.infrastructure.security.jwt_handler import JWTTokenService

USUARIO = "3f2b8c1e-9d4a-4e7b-8a2f-1c5d6e7f8a9b"
OTRO = "7c9e6679-7425-40de-944b-e07fc1f90ae7"


def test_el_csrf_del_servicio_va_firmado_para_ese_usuario():
    """
    Given: el servicio de tokens JWT
    When: genera el CSRF de un usuario
    Then: la firma es de ese usuario y no vale para otro
    """
    token = JWTTokenService().create_csrf_token(USUARIO)

    assert csrf_token_belongs_to(token, USUARIO)
    assert not csrf_token_belongs_to(token, OTRO)


def test_cada_csrf_es_distinto():
    """
    Given: el servicio de tokens JWT
    When: genera dos CSRF para el mismo usuario
    Then: no se repiten (llevan su parte aleatoria)
    """
    servicio = JWTTokenService()

    assert servicio.create_csrf_token(USUARIO) != servicio.create_csrf_token(USUARIO)
