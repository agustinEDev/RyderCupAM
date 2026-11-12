"""
Proveedores del módulo de soporte.
"""

from fastapi import Depends

from src.config.cupo_de_contacto import cupo_de_contacto
from src.modules.support.application.ports.contact_mailer import IContactMailer
from src.modules.support.application.use_cases.submit_contact_use_case import (
    SubmitContactUseCase,
)
from src.modules.support.infrastructure.services.contact_mailer import (
    ContactMailer,
)

# ============================================================================
# SUPPORT MODULE - Dependency Injection
# ============================================================================


def get_contact_mailer() -> IContactMailer:
    """El envío por correo de los mensajes de contacto (la pieza común de envío)."""
    return ContactMailer()


def get_submit_contact_use_case(
    mailer: IContactMailer = Depends(get_contact_mailer),
) -> SubmitContactUseCase:
    """Proveedor del caso de uso SubmitContactUseCase, con el tope diario de la app."""
    return SubmitContactUseCase(mailer, cupo_de_contacto)
