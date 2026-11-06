"""
Diez contraseñas malas A LA VEZ, cada una en su conexión, bloquean la cuenta (BE #282).

Sin la fila bloqueada, todas leían el contador a 0 y escribían 1: la cuenta seguía
abierta tras diez intentos. Con la relectura bloqueada, cada intento espera al
anterior y suma sobre lo que este dejó.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.freno_del_login import FrenoDelLoginEnMemoria
from src.config.rate_limit import limiter
from src.modules.user.application.dto.user_dto import LoginRequestDTO
from src.modules.user.application.use_cases.login_user_use_case import LoginUserUseCase
from src.modules.user.domain.entities.user import MAX_FAILED_ATTEMPTS, User
from src.modules.user.domain.exceptions import AccountLockedException
from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)
from src.shared.infrastructure.security.jwt_handler import JWTTokenService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

EMAIL = "diez_a_la_vez@test.com"


async def test_login_ten_concurrent_failures_counts_ten_and_locks(db_session, monkeypatch):
    """
    Given: Una cuenta con el contador a 0
    When: Llegan 10 contraseñas malas a la vez, cada una en su conexión
    Then: El contador queda en 10 y la cuenta bloqueada
    """
    # Aquí se prueba el respaldo de la BD con concurrencia, no el techo de fallos de
    # la red (30/min), que desde BE #732 aplica el caso de uso y cortaría la ráfaga
    monkeypatch.setattr(limiter, "enabled", False)
    usuario = User.create(
        first_name="Diez",
        last_name="Intentos",
        email_str=EMAIL,
        plain_password="V@l1dP@ss123!",
    )
    await SQLAlchemyUserRepository(db_session).save(usuario)
    await db_session.commit()
    sesiones = async_sessionmaker(db_session.bind, class_=AsyncSession, expire_on_commit=False)

    async def un_intento():
        """Ayudante del test: un intento."""
        async with sesiones() as sesion:
            # Un freno propio por intento: aquí se prueba el respaldo de la BD, no
            # el freno por red, que cortaría la ráfaga en el quinto (BE #732)
            login = LoginUserUseCase(
                SQLAlchemyUnitOfWork(sesion),
                JWTTokenService(),
                AsyncMock(),
                AsyncMock(),
                FrenoDelLoginEnMemoria(),
                AsyncMock(),
            )
            return await login.execute(LoginRequestDTO(email=EMAIL, password="Mala-Pass-1!"))

    resultados = await asyncio.gather(
        *(un_intento() for _ in range(MAX_FAILED_ATTEMPTS)), return_exceptions=True
    )

    # Ninguno entra; el que llega a 10 avisa del bloqueo
    assert all(r is None or isinstance(r, AccountLockedException) for r in resultados), resultados
    async with sesiones() as sesion:
        final = await SQLAlchemyUserRepository(sesion).find_by_id(usuario.id)
        # Si se perdiera una suma, no llegaría a 50 y no se bloquearía
        assert final.is_locked()
        assert final.failed_login_attempts == MAX_FAILED_ATTEMPTS
    assert sum(isinstance(r, AccountLockedException) for r in resultados) >= 1
