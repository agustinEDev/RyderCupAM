"""
La consulta de «hay una sesión más nueva en el navegador», en Postgres (BE #734).

El navegador guarda un dispositivo por cuenta: la consulta mira todos los que se le pasan,
sin depender de su orden (/code-review: un mutante que solo miraba el primero sobrevivía
según el orden de los UUID).
"""

from datetime import datetime, timedelta

import pytest

from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.infrastructure.persistence.sqlalchemy.refresh_token_repository import (
    SQLAlchemyRefreshTokenRepository,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.user_device_repository import (
    SQLAlchemyUserDeviceRepository,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

AGENTE = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0"


async def _dispositivo(db_session, nombre: str) -> UserDevice:
    usuario = User.create(
        first_name=nombre,
        last_name="Navegador",
        email_str=f"{nombre.lower()}_navegador@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    await SQLAlchemyUserRepository(db_session).save(usuario)
    dispositivo = UserDevice.create(
        user_id=usuario.id, fingerprint=DeviceFingerprint.create(AGENTE, "192.168.1.100")
    )
    await SQLAlchemyUserDeviceRepository(db_session).save(dispositivo)
    await db_session.commit()
    return dispositivo


@pytest.mark.parametrize("vivo_primero", [True, False])
async def test_any_of_the_browser_devices_counts_whatever_the_order(db_session, vivo_primero):
    """
    Given: Dos dispositivos del navegador; solo uno con un token vivo y reciente
    When: Se pregunta con los dos, en un orden y en el otro
    Then: Sí, en los dos órdenes
    """
    sin_sesion = await _dispositivo(db_session, "Ana")
    con_sesion = await _dispositivo(db_session, "Bea")
    repo = SQLAlchemyRefreshTokenRepository(db_session)
    await repo.save(
        RefreshToken.create(user_id=con_sesion.user_id, token="nuevo", device_id=con_sesion.id)
    )
    await db_session.commit()
    orden = [con_sesion.id, sin_sesion.id] if vivo_primero else [sin_sesion.id, con_sesion.id]
    ahora = datetime.now()

    assert await repo.hay_uno_vivo_mas_nuevo(orden, ahora - timedelta(minutes=5), ahora) is True


async def test_no_devices_means_no_newer_session(db_session):
    """Sin dispositivos no hay nada que mirar: no (y sin consulta inválida)."""
    ahora = datetime.now()
    repo = SQLAlchemyRefreshTokenRepository(db_session)

    assert await repo.hay_uno_vivo_mas_nuevo([], ahora - timedelta(minutes=5), ahora) is False
