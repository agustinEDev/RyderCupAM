from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.database import async_session_maker
from src.modules.competition.application.use_cases.activate_competition_use_case import (
    ActivateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.cancel_competition_use_case import (
    CancelCompetitionUseCase,
)
from src.modules.competition.application.use_cases.cancel_enrollment_use_case import (
    CancelEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.close_enrollments_use_case import (
    CloseEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.complete_competition_use_case import (
    CompleteCompetitionUseCase,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.delete_competition_use_case import (
    DeleteCompetitionUseCase,
)
from src.modules.competition.application.use_cases.direct_enroll_player_use_case import (
    DirectEnrollPlayerUseCase,
)
from src.modules.competition.application.use_cases.get_competition_use_case import (
    GetCompetitionUseCase,
)
from src.modules.competition.application.use_cases.handle_enrollment_use_case import (
    HandleEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.list_competitions_use_case import (
    ListCompetitionsUseCase,
)
from src.modules.competition.application.use_cases.list_enrollments_use_case import (
    ListEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.request_enrollment_use_case import (
    RequestEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.set_custom_handicap_use_case import (
    SetCustomHandicapUseCase,
)
from src.modules.competition.application.use_cases.start_competition_use_case import (
    StartCompetitionUseCase,
)
from src.modules.competition.application.use_cases.update_competition_use_case import (
    UpdateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.withdraw_enrollment_use_case import (
    WithdrawEnrollmentUseCase,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_unit_of_work import (
    SQLAlchemyCompetitionUnitOfWork,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.ports.token_service_interface import ITokenService
from src.modules.user.application.use_cases.find_user_use_case import FindUserUseCase
from src.modules.user.application.use_cases.get_current_user_use_case import (
    GetCurrentUserUseCase,
)
from src.modules.user.application.use_cases.login_user_use_case import LoginUserUseCase
from src.modules.user.application.use_cases.logout_user_use_case import (
    LogoutUserUseCase,
)
from src.modules.user.application.use_cases.refresh_access_token_use_case import (
    RefreshAccessTokenUseCase,
)
from src.modules.user.application.use_cases.register_user_use_case import (
    RegisterUserUseCase,
)
from src.modules.user.application.use_cases.resend_verification_email_use_case import (
    ResendVerificationEmailUseCase,
)
from src.modules.user.application.use_cases.update_multiple_handicaps_use_case import (
    UpdateMultipleHandicapsUseCase,
)
from src.modules.user.application.use_cases.update_profile_use_case import (
    UpdateProfileUseCase,
)
from src.modules.user.application.use_cases.update_security_use_case import (
    UpdateSecurityUseCase,
)
from src.modules.user.application.use_cases.update_user_handicap_manually_use_case import (
    UpdateUserHandicapManuallyUseCase,
)
from src.modules.user.application.use_cases.update_user_handicap_use_case import (
    UpdateUserHandicapUseCase,
)
from src.modules.user.application.use_cases.verify_email_use_case import (
    VerifyEmailUseCase,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.handicap_service import HandicapService
from src.modules.user.infrastructure.external.rfeg_handicap_service import (
    RFEGHandicapService,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork,
)
from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)
from src.shared.infrastructure.email.email_service import EmailService
from src.shared.infrastructure.persistence.sqlalchemy.country_repository import (
    SQLAlchemyCountryRepository,
)
from src.shared.infrastructure.security.cookie_handler import get_cookie_name
from src.shared.infrastructure.security.jwt_handler import (
    JWTTokenService,
    verify_access_token,
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

def get_country_repository(
    session: AsyncSession = Depends(get_db_session),
) -> CountryRepositoryInterface:
    """
    Proveedor del repositorio de países.

    Esta función:
    1. Depende de `get_db_session` para obtener una sesión de BD.
    2. Crea una instancia de `SQLAlchemyCountryRepository`.
    3. Devuelve la instancia que implementa CountryRepositoryInterface.

    Returns:
        Implementación concreta del repositorio de países (SQLAlchemy)
    """
    return SQLAlchemyCountryRepository(session)

def get_register_user_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    country_repository: CountryRepositoryInterface = Depends(get_country_repository),
    handicap_service: HandicapService = Depends(get_handicap_service),
    email_service: IEmailService = Depends(get_email_service)
) -> RegisterUserUseCase:
    """
    Proveedor del caso de uso RegisterUserUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_country_repository` para validar códigos de país.
    3. Depende de `get_handicap_service` para buscar hándicaps.
    4. Depende de `get_email_service` para envío de emails de verificación.
    5. Crea una instancia de `RegisterUserUseCase` con esas dependencias.
    6. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return RegisterUserUseCase(
        uow=uow,
        country_repository=country_repository,
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

def get_refresh_access_token_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    token_service: ITokenService = Depends(get_token_service)
) -> RefreshAccessTokenUseCase:
    """
    Proveedor del caso de uso RefreshAccessTokenUseCase (Session Timeout - v1.8.0).

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work (users + refresh_tokens).
    2. Depende de `get_token_service` para generación de tokens JWT.
    3. Crea una instancia de `RefreshAccessTokenUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint /refresh-token.
    """
    return RefreshAccessTokenUseCase(uow, token_service)

def get_update_profile_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    country_repository: CountryRepositoryInterface = Depends(get_country_repository)
) -> UpdateProfileUseCase:
    """
    Proveedor del caso de uso UpdateProfileUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_country_repository` para validar códigos de país.
    3. Crea una instancia de `UpdateProfileUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return UpdateProfileUseCase(uow, country_repository)

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
# IMPORTANTE: auto_error=False permite que el endpoint no falle si no hay header Authorization
# Esto es necesario para el middleware dual (cookies + headers)
security = HTTPBearer(auto_error=False)

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> UserResponseDTO:
    """
    Dependencia para obtener el usuario actual desde el token JWT.

    FASE TRANSITORIA (v1.8.0 - v2.0.0):
    Soporta autenticación dual para migración gradual del frontend:

    1. **httpOnly Cookie** (PRIORIDAD 1 - Recomendado):
       - Intenta leer JWT desde cookie "access_token"
       - Protección contra XSS (JavaScript no puede leerla)

    2. **Authorization Header** (PRIORIDAD 2 - LEGACY - Fallback):
       - Si no hay cookie, lee desde header "Authorization: Bearer <token>"
       - Permite compatibilidad con frontend actual (localStorage)
       - TODO (v2.0.0): Eliminar soporte para headers cuando frontend migre

    Flujo de Autenticación:
    1. Extrae token desde cookie O header (prioridad a cookie)
    2. Verifica y decodifica el token JWT
    3. Busca el usuario en la base de datos
    4. Retorna el usuario autenticado

    Security Improvements (OWASP A01/A02):
    - httpOnly cookie: JavaScript NO puede leer el token (previene XSS)
    - Fallback a headers: Compatibilidad backward sin breaking changes

    Args:
        request: Request de FastAPI (para leer cookies)
        credentials: Credenciales del header Authorization (opcional ahora)
        uow: Unit of Work para acceso a datos

    Raises:
        HTTPException 401: Si no hay token, es inválido, o el usuario no existe

    Returns:
        Usuario autenticado

    Example:
        @router.get("/protected")
        async def protected_route(current_user: UserResponseDTO = Depends(get_current_user)):
            return {"message": f"Hello {current_user.email}"}
    """
    token: str | None = None

    # PRIORIDAD 1: Intentar leer JWT desde httpOnly cookie (NUEVO - v1.8.0)
    cookie_name = get_cookie_name()
    token = request.cookies.get(cookie_name)

    # PRIORIDAD 2 (Fallback): Si no hay cookie, leer desde header Authorization (LEGACY)
    if not token and credentials:
        token = credentials.credentials

    # Si no hay token en ninguno de los dos lugares, rechazar autenticación
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales de autenticación no proporcionadas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verificar y decodificar token (mismo código que antes)
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


def get_request_password_reset_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IEmailService = Depends(get_email_service)
):
    """
    Proveedor del caso de uso RequestPasswordResetUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_email_service` para envío de emails de reseteo.
    3. Crea una instancia de `RequestPasswordResetUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    from src.modules.user.application.use_cases.request_password_reset_use_case import (
        RequestPasswordResetUseCase,
    )
    return RequestPasswordResetUseCase(uow, email_service)


def get_reset_password_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IEmailService = Depends(get_email_service)
):
    """
    Proveedor del caso de uso ResetPasswordUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_email_service` para envío de email de confirmación.
    3. Crea una instancia de `ResetPasswordUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    from src.modules.user.application.use_cases.reset_password_use_case import (
        ResetPasswordUseCase,
    )
    return ResetPasswordUseCase(uow, email_service)


def get_validate_reset_token_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow)
):
    """
    Proveedor del caso de uso ValidateResetTokenUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Crea una instancia de `ValidateResetTokenUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    from src.modules.user.application.use_cases.validate_reset_token_use_case import (
        ValidateResetTokenUseCase,
    )
    return ValidateResetTokenUseCase(uow)


# ============================================================================
# COMPETITION MODULE - Dependency Injection
# ============================================================================


# Enrollment Use Cases


def get_competition_uow(
    session: AsyncSession = Depends(get_db_session),
) -> CompetitionUnitOfWorkInterface:
    """
    Proveedor de la Unit of Work para el módulo Competition.

    Esta función:
    1. Depende de `get_db_session` para obtener una sesión de BD.
    2. Crea una instancia de `SQLAlchemyCompetitionUnitOfWork` con esa sesión.
    3. Devuelve la instancia, cumpliendo con la interfaz `CompetitionUnitOfWorkInterface`.

    La UoW de Competition coordina 3 repositorios:
    - competitions: Repositorio de competiciones
    - enrollments: Repositorio de inscripciones
    - countries: Repositorio de países (shared domain)
    """
    return SQLAlchemyCompetitionUnitOfWork(session)


def get_create_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> CreateCompetitionUseCase:
    """
    Proveedor del caso de uso CreateCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `CreateCompetitionUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return CreateCompetitionUseCase(uow)


def get_list_competitions_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> ListCompetitionsUseCase:
    """
    Proveedor del caso de uso ListCompetitionsUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `ListCompetitionsUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return ListCompetitionsUseCase(uow)


def get_update_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> UpdateCompetitionUseCase:
    """
    Proveedor del caso de uso UpdateCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `UpdateCompetitionUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return UpdateCompetitionUseCase(uow)


def get_get_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> GetCompetitionUseCase:
    """
    Proveedor del caso de uso GetCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `GetCompetitionUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return GetCompetitionUseCase(uow)


def get_delete_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> DeleteCompetitionUseCase:
    """
    Proveedor del caso de uso DeleteCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `DeleteCompetitionUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return DeleteCompetitionUseCase(uow)


def get_activate_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> ActivateCompetitionUseCase:
    """
    Proveedor del caso de uso ActivateCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `ActivateCompetitionUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return ActivateCompetitionUseCase(uow)


def get_close_enrollments_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> CloseEnrollmentsUseCase:
    """
    Proveedor del caso de uso CloseEnrollmentsUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `CloseEnrollmentsUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return CloseEnrollmentsUseCase(uow)


def get_start_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> StartCompetitionUseCase:
    """
    Proveedor del caso de uso StartCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `StartCompetitionUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return StartCompetitionUseCase(uow)


def get_complete_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> CompleteCompetitionUseCase:
    """
    Proveedor del caso de uso CompleteCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `CompleteCompetitionUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return CompleteCompetitionUseCase(uow)


def get_cancel_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> CancelCompetitionUseCase:
    """
    Proveedor del caso de uso CancelCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `CancelCompetitionUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return CancelCompetitionUseCase(uow)


# ======================================================================================
# ENROLLMENT USE CASE PROVIDERS
# ======================================================================================

def get_request_enrollment_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> RequestEnrollmentUseCase:
    """Proveedor del caso de uso RequestEnrollmentUseCase."""
    return RequestEnrollmentUseCase(uow)


def get_direct_enroll_player_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> DirectEnrollPlayerUseCase:
    """Proveedor del caso de uso DirectEnrollPlayerUseCase."""
    return DirectEnrollPlayerUseCase(uow)


def get_handle_enrollment_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> HandleEnrollmentUseCase:
    """Proveedor del caso de uso HandleEnrollmentUseCase."""
    return HandleEnrollmentUseCase(uow)


def get_cancel_enrollment_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> CancelEnrollmentUseCase:
    """Proveedor del caso de uso CancelEnrollmentUseCase."""
    return CancelEnrollmentUseCase(uow)


def get_withdraw_enrollment_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> WithdrawEnrollmentUseCase:
    """Proveedor del caso de uso WithdrawEnrollmentUseCase."""
    return WithdrawEnrollmentUseCase(uow)


def get_set_custom_handicap_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> SetCustomHandicapUseCase:
    """Proveedor del caso de uso SetCustomHandicapUseCase."""
    return SetCustomHandicapUseCase(uow)


def get_list_enrollments_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> ListEnrollmentsUseCase:
    """Proveedor del caso de uso ListEnrollmentsUseCase."""
    return ListEnrollmentsUseCase(uow)
