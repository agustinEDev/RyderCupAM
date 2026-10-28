"""
Dos inicios de sesión a la vez de verdad: dos conexiones (BE #692, revisor 28 oct).

La segunda se queda esperando en el índice único hasta que la primera confirma, y
entonces su alta choca: deshace solo su SAVEPOINT y se queda con la de la primera.
"""

import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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


async def test_la_segunda_conexion_espera_y_se_queda_con_el_de_la_primera(db_session):
    usuario = User.create(
        first_name="Dos",
        last_name="Conexiones",
        email_str="dos_conexiones@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    await SQLAlchemyUserRepository(db_session).save(usuario)
    await db_session.commit()
    sesiones = async_sessionmaker(db_session.bind, class_=AsyncSession, expire_on_commit=False)
    huella = DeviceFingerprint.create(user_agent=AGENTE, ip_address="192.168.1.100")
    primero = UserDevice.create(user_id=usuario.id, fingerprint=huella)
    segundo = UserDevice.create(user_id=usuario.id, fingerprint=huella)
    dada_de_alta = asyncio.Event()

    async def login_1():
        async with sesiones() as sesion:
            guardado = await SQLAlchemyUserDeviceRepository(sesion).add_unless_registered(primero)
            dada_de_alta.set()
            # La otra conexión ya está bloqueada en el índice: confirmar la libera
            await asyncio.sleep(0.3)
            await sesion.commit()
            return guardado

    async def login_2():
        await dada_de_alta.wait()
        async with sesiones() as sesion:
            guardado = await SQLAlchemyUserDeviceRepository(sesion).add_unless_registered(segundo)
            await sesion.commit()
            return guardado

    uno, dos = await asyncio.gather(login_1(), login_2())

    assert uno.id == primero.id
    assert dos.id == primero.id
    activos = await SQLAlchemyUserDeviceRepository(db_session).find_active_by_user(usuario.id)
    assert [d.id for d in activos] == [primero.id]
