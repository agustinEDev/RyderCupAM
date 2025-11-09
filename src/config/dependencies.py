from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from src.config.database import async_session_maker
from fastapi import Depends
from src.modules.user.application.use_cases.register_user_use_case import RegisterUserUseCase
from src.modules.user.application.use_cases.find_user_use_case import FindUserUseCase
from src.modules.user.application.use_cases.update_user_handicap_use_case import UpdateUserHandicapUseCase
from src.modules.user.application.use_cases.update_multiple_handicaps_use_case import UpdateMultipleHandicapsUseCase
from src.modules.user.application.use_cases.update_user_handicap_manually_use_case import UpdateUserHandicapManuallyUseCase
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.handicap_service import HandicapService
from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork,
)
from src.modules.user.infrastructure.external.rfeg_handicap_service import RFEGHandicapService

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

def get_handicap_service() -> HandicapService:
    """
    Proveedor del servicio de hándicap.

    Esta función:
    1. Crea una instancia de RFEGHandicapService.
    2. Configura el timeout apropiado.
    3. Devuelve la instancia que implementa HandicapService.

    Returns:
        Implementación concreta del servicio de hándicap (RFEG)
    """
    return RFEGHandicapService(timeout=10)

def get_register_user_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    handicap_service: HandicapService = Depends(get_handicap_service)
) -> RegisterUserUseCase:
    """
    Proveedor del caso de uso RegisterUserUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_handicap_service` para buscar hándicaps.
    3. Crea una instancia de `RegisterUserUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return RegisterUserUseCase(
        uow=uow, 
        handicap_service=handicap_service
    )

def get_find_user_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow)
) -> FindUserUseCase:
    """
    Proveedor del caso de uso FindUserUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Crea una instancia de `FindUserUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return FindUserUseCase(uow)

def get_update_handicap_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    handicap_service: HandicapService = Depends(get_handicap_service)
) -> UpdateUserHandicapUseCase:
    """
    Proveedor del caso de uso UpdateUserHandicapUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_handicap_service` para buscar hándicaps.
    3. Crea una instancia de `UpdateUserHandicapUseCase`.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return UpdateUserHandicapUseCase(uow, handicap_service)

def get_update_multiple_handicaps_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    handicap_service: HandicapService = Depends(get_handicap_service)
) -> UpdateMultipleHandicapsUseCase:
    """
    Proveedor del caso de uso UpdateMultipleHandicapsUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_handicap_service` para buscar hándicaps.
    3. Crea una instancia de `UpdateMultipleHandicapsUseCase`.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return UpdateMultipleHandicapsUseCase(uow, handicap_service)

def get_update_handicap_manually_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> UpdateUserHandicapManuallyUseCase:
    """
    Proveedor del caso de uso UpdateUserHandicapManuallyUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Crea una instancia de `UpdateUserHandicapManuallyUseCase`.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    
    Nota: Este caso de uso NO depende del HandicapService porque actualiza
    manualmente sin consultar servicios externos como RFEG.
    """
    return UpdateUserHandicapManuallyUseCase(uow)