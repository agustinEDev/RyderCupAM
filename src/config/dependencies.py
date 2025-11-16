from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from src.config.database import async_session_maker
from fastapi import Depends
from src.modules.user.application.use_cases.register_user_use_case import RegisterUserUseCase
from src.modules.user.application.use_cases.login_user_use_case import LoginUserUseCase
from src.modules.user.application.use_cases.logout_user_use_case import LogoutUserUseCase
from src.modules.user.application.use_cases.get_current_user_use_case import GetCurrentUserUseCase
from src.modules.user.application.use_cases.find_user_use_case import FindUserUseCase
from src.modules.user.application.use_cases.update_user_handicap_use_case import UpdateUserHandicapUseCase
from src.modules.user.application.use_cases.update_multiple_handicaps_use_case import UpdateMultipleHandicapsUseCase
from src.modules.user.application.use_cases.update_user_handicap_manually_use_case import UpdateUserHandicapManuallyUseCase
from src.modules.user.application.use_cases.update_profile_use_case import UpdateProfileUseCase
from src.modules.user.application.use_cases.update_security_use_case import UpdateSecurityUseCase
from src.modules.user.application.use_cases.verify_email_use_case import VerifyEmailUseCase
from src.modules.user.application.use_cases.resend_verification_email_use_case import ResendVerificationEmailUseCase
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.handicap_service import HandicapService
from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork,
)
from src.modules.user.infrastructure.external.rfeg_handicap_service import RFEGHandicapService
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.ports.token_service_interface import ITokenService
from src.shared.infrastructure.email.email_service import EmailService
from src.shared.infrastructure.security.jwt_handler import JWTTokenService, verify_access_token
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

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

def get_email_service() -> IEmailService:
    """
    Proveedor del servicio de email.

    Esta función:
    1. Crea una instancia de EmailService (Mailgun).
    2. Devuelve la instancia que implementa IEmailService.

    Returns:
        Implementación concreta del servicio de email (Mailgun)
    """
    return EmailService()

def get_token_service() -> ITokenService:
    """
    Proveedor del servicio de tokens.

    Esta función:
    1. Crea una instancia de JWTTokenService.
    2. Devuelve la instancia que implementa ITokenService.

    Returns:
        Implementación concreta del servicio de tokens (JWT)
    """
    return JWTTokenService()

def get_register_user_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    handicap_service: HandicapService = Depends(get_handicap_service),
    email_service: IEmailService = Depends(get_email_service)
) -> RegisterUserUseCase:
    """
    Proveedor del caso de uso RegisterUserUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_handicap_service` para buscar hándicaps.
    3. Depende de `get_email_service` para envío de emails de verificación.
    4. Crea una instancia de `RegisterUserUseCase` con esas dependencias.
    5. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return RegisterUserUseCase(
        uow=uow,
        handicap_service=handicap_service,
        email_service=email_service
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

def get_login_user_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    token_service: ITokenService = Depends(get_token_service)
) -> LoginUserUseCase:
    """
    Proveedor del caso de uso LoginUserUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_token_service` para generación de tokens JWT.
    3. Crea una instancia de `LoginUserUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return LoginUserUseCase(uow, token_service)

def get_logout_user_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow)
) -> LogoutUserUseCase:
    """
    Proveedor del caso de uso LogoutUserUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Crea una instancia de `LogoutUserUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return LogoutUserUseCase(uow)

def get_update_profile_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow)
) -> UpdateProfileUseCase:
    """
    Proveedor del caso de uso UpdateProfileUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Crea una instancia de `UpdateProfileUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return UpdateProfileUseCase(uow)

def get_update_security_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IEmailService = Depends(get_email_service)
) -> UpdateSecurityUseCase:
    """
    Proveedor del caso de uso UpdateSecurityUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_email_service` para envío de emails de verificación.
    3. Crea una instancia de `UpdateSecurityUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return UpdateSecurityUseCase(uow, email_service)

# Esquema de seguridad HTTP Bearer para Swagger
security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> UserResponseDTO:
    """
    Dependencia para obtener el usuario actual desde el token JWT.

    Esta función:
    1. Extrae el token del header Authorization: Bearer <token>
    2. Verifica y decodifica el token JWT
    3. Busca el usuario en la base de datos
    4. Retorna el usuario autenticado

    Raises:
        HTTPException 401: Si el token es inválido o el usuario no existe

    Returns:
        Usuario autenticado

    Example:
        @router.get("/protected")
        async def protected_route(current_user: UserResponseDTO = Depends(get_current_user)):
            return {"message": f"Hello {current_user.email}"}
    """
    token = credentials.credentials

    # Verificar y decodificar token
    payload = verify_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extraer user_id del payload
    user_id_str: str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: falta subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Buscar usuario
    use_case = GetCurrentUserUseCase(uow)
    user = await use_case.execute(user_id_str)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

def get_verify_email_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow)
) -> VerifyEmailUseCase:
    """
    Proveedor del caso de uso VerifyEmailUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Crea una instancia de `VerifyEmailUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return VerifyEmailUseCase(uow)

def get_resend_verification_email_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IEmailService = Depends(get_email_service)
) -> ResendVerificationEmailUseCase:
    """
    Proveedor del caso de uso ResendVerificationEmailUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_email_service` para envío de emails de verificación.
    3. Crea una instancia de `ResendVerificationEmailUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return ResendVerificationEmailUseCase(uow, email_service)