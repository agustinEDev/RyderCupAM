"""
Application Ports - Interfaces para servicios externos.

Este módulo define las interfaces (ports) que la capa de aplicación necesita
para interactuar con servicios externos. Siguiendo el patrón Port/Adapter
(Hexagonal Architecture), estos puertos definen los contratos que deben
cumplir las implementaciones de infraestructura.
"""

from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.ports.token_service_interface import ITokenService

__all__ = [
    "IEmailService",
    "ITokenService",
]
