import logging
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.database import async_session_maker
from src.config.settings import settings
from src.modules.competition.application.ports.invitation_email_service_interface import (
    IInvitationEmailService,
)
from src.modules.competition.application.use_cases.activate_competition_use_case import (
    ActivateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.add_golf_course_use_case import (
    AddGolfCourseToCompetitionUseCase,
)
from src.modules.competition.application.use_cases.assign_teams_use_case import (
    AssignTeamsUseCase,
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
from src.modules.competition.application.use_cases.concede_match_use_case import (
    ConcedeMatchUseCase,
)
from src.modules.competition.application.use_cases.configure_schedule_use_case import (
    ConfigureScheduleUseCase,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.create_round_use_case import (
    CreateRoundUseCase,
)
from src.modules.competition.application.use_cases.declare_walkover_use_case import (
    DeclareWalkoverUseCase,
)
from src.modules.competition.application.use_cases.delete_competition_use_case import (
    DeleteCompetitionUseCase,
)
from src.modules.competition.application.use_cases.delete_round_use_case import (
    DeleteRoundUseCase,
)
from src.modules.competition.application.use_cases.direct_enroll_player_use_case import (
    DirectEnrollPlayerUseCase,
)
from src.modules.competition.application.use_cases.generate_matches_use_case import (
    GenerateMatchesUseCase,
)
from src.modules.competition.application.use_cases.get_competition_use_case import (
    GetCompetitionUseCase,
)
from src.modules.competition.application.use_cases.get_leaderboard_use_case import (
    GetLeaderboardUseCase,
)
from src.modules.competition.application.use_cases.get_match_detail_use_case import (
    GetMatchDetailUseCase,
)
from src.modules.competition.application.use_cases.get_schedule_use_case import (
    GetScheduleUseCase,
)
from src.modules.competition.application.use_cases.get_scoring_view_use_case import (
    GetScoringViewUseCase,
)
from src.modules.competition.application.use_cases.handle_enrollment_use_case import (
    HandleEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.list_competition_invitations_use_case import (
    ListCompetitionInvitationsUseCase,
)
from src.modules.competition.application.use_cases.list_competitions_use_case import (
    ListCompetitionsUseCase,
)
from src.modules.competition.application.use_cases.list_enrollments_use_case import (
    ListEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.list_my_invitations_use_case import (
    ListMyInvitationsUseCase,
)
from src.modules.competition.application.use_cases.reassign_match_players_use_case import (
    ReassignMatchPlayersUseCase,
)
from src.modules.competition.application.use_cases.remove_golf_course_use_case import (
    RemoveGolfCourseFromCompetitionUseCase,
)
from src.modules.competition.application.use_cases.reorder_golf_courses_use_case import (
    ReorderGolfCoursesUseCase,
)
from src.modules.competition.application.use_cases.request_enrollment_use_case import (
    RequestEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.respond_to_invitation_use_case import (
    RespondToInvitationUseCase,
)
from src.modules.competition.application.use_cases.send_invitation_by_email_use_case import (
    SendInvitationByEmailUseCase,
)
from src.modules.competition.application.use_cases.send_invitation_by_user_id_use_case import (
    SendInvitationByUserIdUseCase,
)
from src.modules.competition.application.use_cases.set_custom_handicap_use_case import (
    SetCustomHandicapUseCase,
)
from src.modules.competition.application.use_cases.start_competition_use_case import (
    StartCompetitionUseCase,
)
from src.modules.competition.application.use_cases.submit_hole_score_use_case import (
    SubmitHoleScoreUseCase,
)
from src.modules.competition.application.use_cases.submit_scorecard_use_case import (
    SubmitScorecardUseCase,
)
from src.modules.competition.application.use_cases.update_competition_use_case import (
    UpdateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.update_match_status_use_case import (
    UpdateMatchStatusUseCase,
)
from src.modules.competition.application.use_cases.update_round_use_case import (
    UpdateRoundUseCase,
)
from src.modules.competition.application.use_cases.withdraw_enrollment_use_case import (
    WithdrawEnrollmentUseCase,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.playing_handicap_calculator import (
    PlayingHandicapCalculator,
)
from src.modules.competition.domain.services.schedule_format_service import (
    ScheduleFormatService,
)
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.services.snake_draft_service import (
    SnakeDraftService,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_unit_of_work import (
    SQLAlchemyCompetitionUnitOfWork,
)
from src.modules.golf_course.application.use_cases.approve_golf_course_use_case import (
    ApproveGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.approve_update_golf_course_use_case import (
    ApproveUpdateGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.create_direct_golf_course_use_case import (
    CreateDirectGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.get_golf_course_by_id_use_case import (
    GetGolfCourseByIdUseCase,
)
from src.modules.golf_course.application.use_cases.list_approved_golf_courses_use_case import (
    ListApprovedGolfCoursesUseCase,
)
from src.modules.golf_course.application.use_cases.list_pending_golf_courses_use_case import (
    ListPendingGolfCoursesUseCase,
)
from src.modules.golf_course.application.use_cases.reject_golf_course_use_case import (
    RejectGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.reject_update_golf_course_use_case import (
    RejectUpdateGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.request_golf_course_use_case import (
    RequestGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.update_golf_course_use_case import (
    UpdateGolfCourseUseCase,
)
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.infrastructure.persistence.sqlalchemy.golf_course_unit_of_work import (
    SQLAlchemyGolfCourseUnitOfWork,
)
from src.modules.support.application.use_cases.submit_contact_use_case import (
    SubmitContactUseCase,
)
from src.modules.support.infrastructure.services.github_issue_service import (
    GitHubIssueService,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.ports.google_oauth_service_interface import (
    IGoogleOAuthService,
)
from src.modules.user.application.ports.token_service_interface import ITokenService
from src.modules.user.application.use_cases.find_user_use_case import FindUserUseCase
from src.modules.user.application.use_cases.get_current_user_use_case import (
    GetCurrentUserUseCase,
)
from src.modules.user.application.use_cases.google_login_use_case import (
    GoogleLoginUseCase,
)
from src.modules.user.application.use_cases.link_google_account_use_case import (
    LinkGoogleAccountUseCase,
)
from src.modules.user.application.use_cases.list_user_devices_use_case import (
    ListUserDevicesUseCase,
)
from src.modules.user.application.use_cases.login_user_use_case import LoginUserUseCase
from src.modules.user.application.use_cases.logout_user_use_case import (
    LogoutUserUseCase,
)
from src.modules.user.application.use_cases.refresh_access_token_use_case import (
    RefreshAccessTokenUseCase,
)
from src.modules.user.application.use_cases.register_device_use_case import (
    RegisterDeviceUseCase,
)
from src.modules.user.application.use_cases.register_user_use_case import (
    RegisterUserUseCase,
)
from src.modules.user.application.use_cases.request_password_reset_use_case import (
    RequestPasswordResetUseCase,
)
from src.modules.user.application.use_cases.resend_verification_email_use_case import (
    ResendVerificationEmailUseCase,
)
from src.modules.user.application.use_cases.reset_password_use_case import (
    ResetPasswordUseCase,
)
from src.modules.user.application.use_cases.revoke_device_use_case import (
    RevokeDeviceUseCase,
)
from src.modules.user.application.use_cases.unlink_google_account_use_case import (
    UnlinkGoogleAccountUseCase,
)
from src.modules.user.application.use_cases.unlock_account_use_case import (
    UnlockAccountUseCase,
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
from src.modules.user.application.use_cases.validate_reset_token_use_case import (
    ValidateResetTokenUseCase,
)
from src.modules.user.application.use_cases.verify_email_use_case import (
    VerifyEmailUseCase,
)
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.handicap_service import HandicapService
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.external.google_oauth_service import (
    GoogleOAuthService,
)
from src.modules.user.infrastructure.external.rfeg_handicap_service import (
    RFEGHandicapService,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.user_device_mapper import (
    user_devices_table,
)
from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)
from src.shared.infrastructure.email.email_service import EmailService
from src.shared.infrastructure.http.http_context_validator import get_trusted_client_ip
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
    email_service: IEmailService = Depends(get_email_service),
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
        email_service=email_service,
    )


def get_find_user_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
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
    handicap_service: HandicapService = Depends(get_handicap_service),
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
    handicap_service: HandicapService = Depends(get_handicap_service),
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


def get_register_device_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> RegisterDeviceUseCase:
    """
    Proveedor del caso de uso RegisterDeviceUseCase (v1.13.0 - Device Fingerprinting).

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work (user_devices repository).
    2. Crea una instancia de `RegisterDeviceUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada internamente por Login y RefreshToken.

    Note:
        Este use case NO tiene endpoint directo. Se llama internamente desde:
        - LoginUserUseCase (auto-registro en login exitoso)
        - RefreshAccessTokenUseCase (auto-registro en refresh exitoso)
    """
    return RegisterDeviceUseCase(uow)


def get_login_user_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    token_service: ITokenService = Depends(get_token_service),
    register_device_use_case: RegisterDeviceUseCase = Depends(get_register_device_use_case),
) -> LoginUserUseCase:
    """
    Proveedor del caso de uso LoginUserUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_token_service` para generación de tokens JWT.
    3. Depende de `get_register_device_use_case` para device fingerprinting (v1.13.0).
    4. Crea una instancia de `LoginUserUseCase` con esas dependencias.
    5. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return LoginUserUseCase(uow, token_service, register_device_use_case)


def get_logout_user_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
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
    token_service: ITokenService = Depends(get_token_service),
    register_device_use_case: RegisterDeviceUseCase = Depends(get_register_device_use_case),
) -> RefreshAccessTokenUseCase:
    """
    Proveedor del caso de uso RefreshAccessTokenUseCase (Session Timeout - v1.8.0).

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work (users + refresh_tokens + user_devices).
    2. Depende de `get_token_service` para generación de tokens JWT.
    3. Depende de `get_register_device_use_case` para device fingerprinting (v1.13.0).
    4. Crea una instancia de `RefreshAccessTokenUseCase` con esas dependencias.
    5. Devuelve la instancia lista para ser usada por el endpoint /refresh-token.
    """
    return RefreshAccessTokenUseCase(uow, token_service, register_device_use_case)


def get_update_profile_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    country_repository: CountryRepositoryInterface = Depends(get_country_repository),
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
    email_service: IEmailService = Depends(get_email_service),
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

    # Device Fingerprinting Security Check (v1.13.0):
    # Verificar que el dispositivo actual NO esté revocado
    # Si el dispositivo fue revocado, el token es inválido aunque técnicamente sea válido
    logger = logging.getLogger(__name__)

    user_agent = request.headers.get("User-Agent", "unknown")

    # Extraer IP real del cliente (usa shared helper con soporte Cloudflare + proxies)
    ip_address = get_trusted_client_ip(
        request, settings.TRUSTED_PROXIES, settings.TRUST_CLOUDFLARE_HEADERS
    )

    if user_agent != "unknown" and ip_address:
        try:
            # Crear fingerprint del dispositivo actual
            current_fingerprint = DeviceFingerprint.create(
                user_agent=user_agent, ip_address=ip_address
            )

            # Buscar dispositivo por fingerprint (usando nueva transacción)
            # IMPORTANTE: NO usamos find_by_user_and_fingerprint porque filtra por is_active=True
            # Necesitamos encontrar el dispositivo AUNQUE esté revocado para bloquearlo
            user_id_vo = UserId(user_id_str)
            async with uow:
                # Query directo sin filtrar por is_active
                statement = (
                    select(UserDevice)
                    .where(UserDevice.user_id == user_id_vo)  # type: ignore[arg-type]
                    .where(UserDevice.fingerprint_hash == current_fingerprint.fingerprint_hash)  # type: ignore[arg-type]
                    # NO filtramos por is_active para encontrar dispositivos revocados
                    # Ordenamos por is_active DESC para que si hay múltiples, tome el activo primero
                    .order_by(user_devices_table.c.is_active.desc())
                    .limit(1)
                )
                result = await uow._session.execute(statement)
                device = result.scalar_one_or_none()

                # Si el dispositivo existe pero está revocado, denegar acceso
                if device and not device.is_active:
                    logger.warning(
                        f"Access denied: Revoked device {device.id} attempted access for user {user_id_str}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Dispositivo revocado. Por favor, inicia sesión nuevamente.",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
        except HTTPException:
            # Re-lanzar HTTPException para que FastAPI la maneje
            raise
        except Exception as e:
            # Si hay error al crear fingerprint o consultar BD, continuar (no bloquear por errores técnicos)
            # Esto previene que un error en device fingerprinting bloquee a todos los usuarios
            logger.error(
                f"Error during device validation for user {user_id_str}: {type(e).__name__}: {e}"
            )
            pass

    return user


def get_verify_email_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
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
    email_service: IEmailService = Depends(get_email_service),
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
    email_service: IEmailService = Depends(get_email_service),
):
    """
    Proveedor del caso de uso RequestPasswordResetUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_email_service` para envío de emails de reseteo.
    3. Crea una instancia de `RequestPasswordResetUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return RequestPasswordResetUseCase(uow, email_service)


def get_reset_password_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IEmailService = Depends(get_email_service),
):
    """
    Proveedor del caso de uso ResetPasswordUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_email_service` para envío de email de confirmación.
    3. Crea una instancia de `ResetPasswordUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return ResetPasswordUseCase(uow, email_service)


def get_validate_reset_token_use_case(uow: UserUnitOfWorkInterface = Depends(get_uow)):
    """
    Proveedor del caso de uso ValidateResetTokenUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Crea una instancia de `ValidateResetTokenUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
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


def get_golf_course_uow(
    session: AsyncSession = Depends(get_db_session),
) -> GolfCourseUnitOfWorkInterface:
    """
    Proveedor de la Unit of Work para el módulo Golf Course.

    Esta función:
    1. Depende de `get_db_session` para obtener una sesión de BD.
    2. Crea una instancia de `SQLAlchemyGolfCourseUnitOfWork` con esa sesión.
    3. Devuelve la instancia, cumpliendo con la interfaz `GolfCourseUnitOfWorkInterface`.

    La UoW de Golf Course coordina 2 repositorios:
    - golf_courses: Repositorio de campos de golf
    - countries: Repositorio de países (shared domain)
    """
    return SQLAlchemyGolfCourseUnitOfWork(session)


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


def get_add_golf_course_to_competition_use_case(
    competition_uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> AddGolfCourseToCompetitionUseCase:
    """
    Proveedor del caso de uso AddGolfCourseToCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` y `get_golf_course_uow`.
    2. Crea una instancia de `AddGolfCourseToCompetitionUseCase` con ambas dependencias.
    3. El golf_course_repository se obtiene desde golf_course_uow.golf_courses.
    """
    return AddGolfCourseToCompetitionUseCase(
        uow=competition_uow,
        golf_course_repository=golf_course_uow.golf_courses,
    )


def get_remove_golf_course_from_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> RemoveGolfCourseFromCompetitionUseCase:
    """
    Proveedor del caso de uso RemoveGolfCourseFromCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `RemoveGolfCourseFromCompetitionUseCase` con esa dependencia.
    """
    return RemoveGolfCourseFromCompetitionUseCase(uow)


def get_reorder_golf_courses_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> ReorderGolfCoursesUseCase:
    """
    Proveedor del caso de uso ReorderGolfCoursesUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `ReorderGolfCoursesUseCase` con esa dependencia.
    """
    return ReorderGolfCoursesUseCase(uow)


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


# ======================================================================================
# ROUND, MATCH & TEAM ASSIGNMENT USE CASE PROVIDERS (Sprint 2 - Block 7)
# ======================================================================================


def get_create_round_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> CreateRoundUseCase:
    """Proveedor del caso de uso CreateRoundUseCase."""
    return CreateRoundUseCase(uow)


def get_update_round_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> UpdateRoundUseCase:
    """Proveedor del caso de uso UpdateRoundUseCase."""
    return UpdateRoundUseCase(uow)


def get_delete_round_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> DeleteRoundUseCase:
    """Proveedor del caso de uso DeleteRoundUseCase."""
    return DeleteRoundUseCase(uow)


def get_get_schedule_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> GetScheduleUseCase:
    """Proveedor del caso de uso GetScheduleUseCase."""
    return GetScheduleUseCase(uow)


def get_get_match_detail_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> GetMatchDetailUseCase:
    """Proveedor del caso de uso GetMatchDetailUseCase."""
    return GetMatchDetailUseCase(uow)


def get_update_match_status_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> UpdateMatchStatusUseCase:
    """Proveedor del caso de uso UpdateMatchStatusUseCase."""
    return UpdateMatchStatusUseCase(uow)


def get_declare_walkover_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> DeclareWalkoverUseCase:
    """Proveedor del caso de uso DeclareWalkoverUseCase."""
    return DeclareWalkoverUseCase(uow)


def get_configure_schedule_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> ConfigureScheduleUseCase:
    """Proveedor del caso de uso ConfigureScheduleUseCase."""
    return ConfigureScheduleUseCase(uow, schedule_format_service=ScheduleFormatService())


def get_assign_teams_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> AssignTeamsUseCase:
    """Proveedor del caso de uso AssignTeamsUseCase (cross-module: Competition + User)."""
    return AssignTeamsUseCase(
        uow=uow,
        user_repository=user_uow.users,
        snake_draft_service=SnakeDraftService(),
    )


def get_scoring_service() -> ScoringService:
    """Proveedor del servicio de dominio ScoringService."""
    return ScoringService()


def get_generate_matches_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
) -> GenerateMatchesUseCase:
    """Proveedor del caso de uso GenerateMatchesUseCase (cross-module: Competition + GolfCourse + User)."""
    return GenerateMatchesUseCase(
        uow=uow,
        golf_course_repository=gc_uow.golf_courses,
        user_repository=user_uow.users,
        handicap_calculator=PlayingHandicapCalculator(),
        scoring_service=scoring_service,
    )


def get_reassign_match_players_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> ReassignMatchPlayersUseCase:
    """Proveedor del caso de uso ReassignMatchPlayersUseCase (cross-module: Competition + GolfCourse + User)."""
    return ReassignMatchPlayersUseCase(
        uow=uow,
        golf_course_repository=gc_uow.golf_courses,
        user_repository=user_uow.users,
        handicap_calculator=PlayingHandicapCalculator(),
    )


# ======================================================================================
# INVITATION USE CASE PROVIDERS (Sprint 3 - Block 2)
# ======================================================================================


def get_invitation_email_service() -> IInvitationEmailService:
    """Proveedor del servicio de email para invitaciones."""
    return EmailService()


def get_send_invitation_by_user_id_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IInvitationEmailService = Depends(get_invitation_email_service),
) -> SendInvitationByUserIdUseCase:
    """Proveedor del caso de uso SendInvitationByUserIdUseCase."""
    return SendInvitationByUserIdUseCase(uow, user_uow, email_service)


def get_send_invitation_by_email_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IInvitationEmailService = Depends(get_invitation_email_service),
) -> SendInvitationByEmailUseCase:
    """Proveedor del caso de uso SendInvitationByEmailUseCase."""
    return SendInvitationByEmailUseCase(uow, user_uow, email_service)


def get_list_my_invitations_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> ListMyInvitationsUseCase:
    """Proveedor del caso de uso ListMyInvitationsUseCase."""
    return ListMyInvitationsUseCase(uow, user_uow)


def get_respond_to_invitation_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> RespondToInvitationUseCase:
    """Proveedor del caso de uso RespondToInvitationUseCase."""
    return RespondToInvitationUseCase(uow, user_uow)


def get_list_competition_invitations_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> ListCompetitionInvitationsUseCase:
    """Proveedor del caso de uso ListCompetitionInvitationsUseCase."""
    return ListCompetitionInvitationsUseCase(uow, user_uow)


# ======================================================================================
# SCORING USE CASE PROVIDERS (Sprint 4 - Live Scoring)
# ======================================================================================


def get_get_scoring_view_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
) -> GetScoringViewUseCase:
    """Proveedor del caso de uso GetScoringViewUseCase (cross-module: Competition + GolfCourse + User)."""
    return GetScoringViewUseCase(uow, user_uow.users, scoring_service, gc_uow.golf_courses)


def get_submit_hole_score_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
) -> SubmitHoleScoreUseCase:
    """Proveedor del caso de uso SubmitHoleScoreUseCase (cross-module: Competition + GolfCourse + User)."""
    return SubmitHoleScoreUseCase(uow, user_uow.users, scoring_service, gc_uow.golf_courses)


def get_submit_scorecard_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
) -> SubmitScorecardUseCase:
    """Proveedor del caso de uso SubmitScorecardUseCase."""
    return SubmitScorecardUseCase(uow, scoring_service)


def get_get_leaderboard_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
) -> GetLeaderboardUseCase:
    """Proveedor del caso de uso GetLeaderboardUseCase."""
    return GetLeaderboardUseCase(uow, user_uow.users, scoring_service)


def get_concede_match_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
) -> ConcedeMatchUseCase:
    """Proveedor del caso de uso ConcedeMatchUseCase."""
    return ConcedeMatchUseCase(uow, scoring_service)


# ============================================================================
# Account Lockout Use Cases (v1.13.0)
# ============================================================================


def get_unlock_account_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> UnlockAccountUseCase:
    """Proveedor del caso de uso UnlockAccountUseCase (v1.13.0 - Account Lockout)."""
    return UnlockAccountUseCase(uow)


# ============================================================================
# SUPPORT MODULE - Dependency Injection
# ============================================================================


def get_github_issue_service():
    """Proveedor del servicio de GitHub Issues."""
    return GitHubIssueService()


def get_submit_contact_use_case(
    github_issue_service=Depends(get_github_issue_service),
):
    """Proveedor del caso de uso SubmitContactUseCase."""
    return SubmitContactUseCase(github_issue_service)


# ============================================================================
# GOLF COURSE MODULE - Dependency Injection
# ============================================================================


def get_request_golf_course_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> RequestGolfCourseUseCase:
    """Proveedor del caso de uso RequestGolfCourseUseCase."""
    return RequestGolfCourseUseCase(uow)


def get_get_golf_course_by_id_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> GetGolfCourseByIdUseCase:
    """Proveedor del caso de uso GetGolfCourseByIdUseCase."""
    return GetGolfCourseByIdUseCase(uow)


def get_list_approved_golf_courses_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ListApprovedGolfCoursesUseCase:
    """Proveedor del caso de uso ListApprovedGolfCoursesUseCase."""
    return ListApprovedGolfCoursesUseCase(uow)


def get_list_pending_golf_courses_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ListPendingGolfCoursesUseCase:
    """Proveedor del caso de uso ListPendingGolfCoursesUseCase."""
    return ListPendingGolfCoursesUseCase(uow)


def get_approve_golf_course_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ApproveGolfCourseUseCase:
    """Proveedor del caso de uso ApproveGolfCourseUseCase."""
    return ApproveGolfCourseUseCase(uow)


def get_reject_golf_course_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> RejectGolfCourseUseCase:
    """Proveedor del caso de uso RejectGolfCourseUseCase."""
    return RejectGolfCourseUseCase(uow)


def get_create_direct_golf_course_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> CreateDirectGolfCourseUseCase:
    """Proveedor del caso de uso CreateDirectGolfCourseUseCase."""
    return CreateDirectGolfCourseUseCase(uow)


def get_update_golf_course_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> UpdateGolfCourseUseCase:
    """Proveedor del caso de uso UpdateGolfCourseUseCase."""
    return UpdateGolfCourseUseCase(uow)


def get_approve_update_golf_course_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ApproveUpdateGolfCourseUseCase:
    """Proveedor del caso de uso ApproveUpdateGolfCourseUseCase."""
    return ApproveUpdateGolfCourseUseCase(uow)


def get_reject_update_golf_course_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> RejectUpdateGolfCourseUseCase:
    """Proveedor del caso de uso RejectUpdateGolfCourseUseCase."""
    return RejectUpdateGolfCourseUseCase(uow)


# ============================================================================
# Device Fingerprinting Use Cases (v1.13.0)
# ============================================================================


def get_list_user_devices_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> ListUserDevicesUseCase:
    """
    Proveedor del caso de uso ListUserDevicesUseCase (v1.13.0 - Device Fingerprinting).

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work (user_devices repository).
    2. Crea una instancia de `ListUserDevicesUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint GET /users/me/devices.
    """
    return ListUserDevicesUseCase(uow)


def get_revoke_device_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> RevokeDeviceUseCase:
    """
    Proveedor del caso de uso RevokeDeviceUseCase (v1.13.0 - Device Fingerprinting).

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work (user_devices repository).
    2. Crea una instancia de `RevokeDeviceUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint DELETE /users/me/devices/{id}.
    """
    return RevokeDeviceUseCase(uow)


# ============================================================================
# Google OAuth Use Cases (Sprint 3)
# ============================================================================


def get_google_oauth_service() -> IGoogleOAuthService:
    """Proveedor del servicio de Google OAuth."""
    return GoogleOAuthService()


def get_google_login_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    token_service: ITokenService = Depends(get_token_service),
    google_oauth_service: IGoogleOAuthService = Depends(get_google_oauth_service),
    register_device_use_case: RegisterDeviceUseCase = Depends(get_register_device_use_case),
) -> GoogleLoginUseCase:
    """Proveedor del caso de uso GoogleLoginUseCase."""
    return GoogleLoginUseCase(uow, token_service, google_oauth_service, register_device_use_case)


def get_link_google_account_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    google_oauth_service: IGoogleOAuthService = Depends(get_google_oauth_service),
) -> LinkGoogleAccountUseCase:
    """Proveedor del caso de uso LinkGoogleAccountUseCase."""
    return LinkGoogleAccountUseCase(uow, google_oauth_service)


def get_unlink_google_account_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> UnlinkGoogleAccountUseCase:
    """Proveedor del caso de uso UnlinkGoogleAccountUseCase."""
    return UnlinkGoogleAccountUseCase(uow)
