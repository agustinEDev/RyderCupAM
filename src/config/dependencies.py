from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from src.config.database import async_session_maker
from fastapi import Depends
from src.modules.user.application.use_cases.register_user import RegisterUserUseCase
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork,
)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Proveedor de sesión de base de datos para la inyección de dependencias de FastAPI.

    Esta función es un generador asíncrono que:
    1. Crea una nueva sesión de SQLAlchemy para una petición entrante.
    2. Proporciona (yields) esta sesión al endpoint.
    3. Se asegura de que la sesión se cierre siempre al final,
       liberando la conexión a la base de datos.
    """
    async with async_session_maker() as session:
        yield session

def get_uow(
    session: AsyncSession = Depends(get_db_session),
) -> UserUnitOfWorkInterface:
    """
    Proveedor de la Unit of Work para la inyección de dependencias.

    Esta función:
    1. Depende de `get_db_session` para obtener una sesión de BD.
    2. Crea una instancia de `SQLAlchemyUnitOfWork` con esa sesión.
    3. Devuelve la instancia, cumpliendo con la interfaz `UserUnitOfWorkInterface`.
    """
    return SQLAlchemyUnitOfWork(session)

def get_register_user_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> RegisterUserUseCase:
    """
    Proveedor del caso de uso RegisterUserUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Crea una instancia de `RegisterUserUseCase` con esa UoW.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return RegisterUserUseCase(uow)