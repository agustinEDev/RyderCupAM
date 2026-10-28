"""
El alta de un dispositivo que otro inicio de sesión dio de alta entre medias,
contra Postgres (BE #692, 28 oct 2026): el índice único parcial rechaza el
segundo, se deshace solo su SAVEPOINT y se devuelve el que ya estaba.
"""

import pytest

from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.infrastructure.persistence.sqlalchemy.user_device_repository import (
    SQLAlchemyUserDeviceRepository,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

AGENTE = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0"


async def test_el_segundo_alta_devuelve_el_primero_y_la_transaccion_sigue(db_session):
    usuario = User.create(
        first_name="Dos",
        last_name="Logins",
        email_str="dos_logins@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    await SQLAlchemyUserRepository(db_session).save(usuario)
    await db_session.flush()
    huella = DeviceFingerprint.create(user_agent=AGENTE, ip_address="192.168.1.100")
    repo = SQLAlchemyUserDeviceRepository(db_session)
    primero = UserDevice.create(user_id=usuario.id, fingerprint=huella)
    segundo = UserDevice.create(user_id=usuario.id, fingerprint=huella)

    guardado_1 = await repo.add_unless_registered(primero)
    # El de otro login, como si su lectura no hubiera visto el primero
    guardado_2 = await repo.add_unless_registered(segundo)
    await db_session.commit()

    assert guardado_1 is primero
    assert guardado_2.id == primero.id
    assert [d.id for d in await repo.find_active_by_user(usuario.id)] == [primero.id]
