"""
La composición da al reseteo de contraseña la URL del frontend (auditoría 9 nov 2026).

El caso de uso leía `FRONTEND_URL` instanciando `src.config.settings.Settings`;
ahora la recibe por constructor, y quien se la da es `src.config.dependencies`. Si no
se la diera bien, los enlaces de los correos apuntarían a otro sitio.
"""

from unittest.mock import AsyncMock

import pytest

from src.config import dependencies as d
from src.config.aviso_en_segundo_plano import espera_los_avisos_pendientes
from src.modules.user.application.dto.user_dto import RequestPasswordResetRequestDTO
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio


async def test_el_enlace_de_reseteo_usa_el_frontend_url_de_la_configuracion(monkeypatch):
    """
    Given: FRONTEND_URL configurado como https://front.ejemplo.test
    When: el proveedor de src.config.dependencies construye el caso de uso y se pide un reseteo
    Then: el enlace del correo apunta a ese frontend
    """
    monkeypatch.setattr(d.settings, "FRONTEND_URL", "https://front.ejemplo.test")
    uow = InMemoryUnitOfWork()
    email_service = AsyncMock()
    usuario = User.create(
        first_name="Ana",
        last_name="Garcia",
        email_str="enlace@test.com",
        plain_password="CurrentPassword123!",
    )
    async with uow:
        await uow.users.save(usuario)
    caso_de_uso = d.get_request_password_reset_use_case(
        uow=uow, email_service=email_service, security_audit=d.get_security_audit_logger()
    )

    await caso_de_uso.execute(RequestPasswordResetRequestDTO(email="enlace@test.com"))
    # El correo sale en segundo plano (fase 3, B-2)
    await espera_los_avisos_pendientes(tope_s=5)

    enlace = email_service.send_password_reset_email.call_args.kwargs["reset_link"]
    assert enlace.startswith("https://front.ejemplo.test/reset-password/")
