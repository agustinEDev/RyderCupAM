"""
Dos avisos de «intentos fallidos» a la vez mandan UN correo (BE #732).

El aviso se reserva con la fila del usuario bloqueada antes de enviarlo. Sin eso,
dos tareas leían «sin aviso en la última hora» a la vez y mandaban dos correos
(revisor de la PR y auditoría OWASP). Con dos sesiones de BD de verdad.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.cupo_de_avisos import CupoDeAvisosEnMemoria
from src.modules.user.application.dto.user_dto import AvisoDeFallosRequestDTO
from src.modules.user.application.services.aviso_de_fallos_de_login import AvisoDeFallosDeLogin
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)
from src.shared.infrastructure.persistence.sqlalchemy.country_repository import (
    SQLAlchemyCountryRepository,
)

pytestmark = pytest.mark.asyncio


async def test_dos_avisos_a_la_vez_mandan_un_correo(db_session):
    """
    Given: Ana, con el correo confirmado y sin avisos
    When: Dos avisos de fallos llegan a la vez, cada uno con su sesión
    Then: Sale un solo correo, y Ana queda apuntada
    """
    ana = User.create(
        first_name="Ana",
        last_name="C",
        email_str="ana.conc@example.com",
        plain_password="V@l1dP@ss123!",
    )
    ana.verify_email_from_oauth()
    await SQLAlchemyUserRepository(db_session).save(ana)
    await db_session.commit()
    sesiones = async_sessionmaker(db_session.bind, class_=AsyncSession, expire_on_commit=False)
    correo = AsyncMock()

    async def lento(**_kw):
        await asyncio.sleep(0.2)  # mientras, la otra tarea intenta reservar
        return True

    correo.send_failed_logins_notification = AsyncMock(side_effect=lento)
    cupo = CupoDeAvisosEnMemoria()
    pide = AvisoDeFallosRequestDTO(
        user_id=str(ana.id.value),
        email="ana.conc@example.com",
        nombre="Ana",
        verificado=True,
        motivo="red",
    )

    async def un_aviso():
        async with sesiones() as sesion:
            aviso = AvisoDeFallosDeLogin(
                SQLAlchemyUnitOfWork(sesion), correo, SQLAlchemyCountryRepository(sesion), cupo
            )
            await aviso.avisa(pide)

    await asyncio.gather(un_aviso(), un_aviso())

    assert correo.send_failed_logins_notification.await_count == 1
    async with sesiones() as sesion:
        releida = await SQLAlchemyUserRepository(sesion).find_by_id(ana.id)
    assert releida.failed_login_notice_at is not None
