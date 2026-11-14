"""
Proveedores del módulo de usuarios: registro, sesión, contraseña, perfil, dispositivos,
Google, avatar.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.aviso_en_segundo_plano import (
    AvisoDeFallosEnSegundoPlano,
    AvisoDeSesionCerradaEnSegundoPlano,
    AvisoEnSegundoPlano,
    CorreoEnSegundoPlano,
    ReenvioEnSegundoPlano,
)
from src.config.cupo_de_avisos import cupo_de_avisos
from src.config.dependencies.comun import (
    get_competition_uow,
    get_country_repository,
    get_email_service,
    get_fabrica_de_sesiones,
    get_golf_course_uow,
    get_handicap_service,
    get_image_processor,
    get_quick_match_uow,
    get_social_uow,
    get_uow,
)
from src.config.freno_del_login import freno_del_login
from src.config.settings import settings
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.infrastructure.adapters.bloqueos_adapter import BloqueosAdapter
from src.modules.user.application.ports.avatar_preset_provider_interface import (
    IAvatarPresetProvider,
)
from src.modules.user.application.ports.aviso_de_fallos_port import IAvisoDeFallos
from src.modules.user.application.ports.aviso_de_nuevo_inicio_port import IAvisoDeNuevoInicio
from src.modules.user.application.ports.aviso_de_sesion_cerrada_port import (
    IAvisoDeSesionCerrada,
)
from src.modules.user.application.ports.bloqueos_interface import BloqueosInterface
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.ports.freno_del_login_port import IFrenoDelLogin
from src.modules.user.application.ports.google_oauth_service_interface import (
    IGoogleOAuthService,
)
from src.modules.user.application.ports.image_processor_interface import IImageProcessor
from src.modules.user.application.ports.reenvio_de_verificacion_port import (
    IReenvioDeVerificacion,
)
from src.modules.user.application.ports.security_audit_interface import ISecurityAuditLogger
from src.modules.user.application.ports.token_service_interface import ITokenService
from src.modules.user.application.use_cases.accept_terms_use_case import AcceptTermsUseCase
from src.modules.user.application.use_cases.activate_uploaded_avatar_use_case import (
    ActivateUploadedAvatarUseCase,
)
from src.modules.user.application.use_cases.admin_delete_user_use_case import (
    AdminDeleteUserUseCase,
)
from src.modules.user.application.use_cases.admin_list_users_use_case import (
    AdminListUsersUseCase,
)
from src.modules.user.application.use_cases.admin_set_user_active_use_case import (
    AdminSetUserActiveUseCase,
)
from src.modules.user.application.use_cases.admin_update_user_use_case import (
    AdminUpdateUserUseCase,
)
from src.modules.user.application.use_cases.cancel_email_change_use_case import (
    CancelEmailChangeUseCase,
)
from src.modules.user.application.use_cases.confirm_email_change_use_case import (
    ConfirmEmailChangeUseCase,
)
from src.modules.user.application.use_cases.find_user_use_case import FindUserUseCase
from src.modules.user.application.use_cases.get_admin_stats_use_case import (
    GetAdminStatsUseCase,
)
from src.modules.user.application.use_cases.get_avatar_image_use_case import (
    GetAvatarImageUseCase,
)
from src.modules.user.application.use_cases.get_avatar_preset_image_use_case import (
    GetAvatarPresetImageUseCase,
)
from src.modules.user.application.use_cases.get_my_avatar_upload_image_use_case import (
    GetMyAvatarUploadImageUseCase,
)
from src.modules.user.application.use_cases.get_recent_matches_use_case import (
    GetRecentMatchesUseCase,
)
from src.modules.user.application.use_cases.google_login_use_case import (
    GoogleLoginUseCase,
)
from src.modules.user.application.use_cases.link_google_account_use_case import (
    LinkGoogleAccountUseCase,
)
from src.modules.user.application.use_cases.list_avatar_presets_use_case import (
    ListAvatarPresetsUseCase,
)
from src.modules.user.application.use_cases.list_my_avatar_uploads_use_case import (
    ListMyAvatarUploadsUseCase,
)
from src.modules.user.application.use_cases.list_user_devices_use_case import (
    ListUserDevicesUseCase,
)
from src.modules.user.application.use_cases.login_user_use_case import LoginUserUseCase
from src.modules.user.application.use_cases.logout_user_use_case import (
    LogoutUserUseCase,
)
from src.modules.user.application.use_cases.reauthenticate_use_case import (
    ReauthenticateUseCase,
)
from src.modules.user.application.use_cases.refresh_access_token_use_case import (
    RefreshAccessTokenUseCase,
)
from src.modules.user.application.use_cases.refresh_own_handicap_use_case import (
    RefreshOwnHandicapUseCase,
)
from src.modules.user.application.use_cases.register_device_use_case import (
    RegisterDeviceUseCase,
)
from src.modules.user.application.use_cases.register_user_use_case import (
    RegisterUserUseCase,
)
from src.modules.user.application.use_cases.remove_avatar_use_case import RemoveAvatarUseCase
from src.modules.user.application.use_cases.request_password_reset_use_case import (
    RequestPasswordResetUseCase,
)
from src.modules.user.application.use_cases.resend_verification_email_use_case import (
    ResendVerificationEmailUseCase,
    ResendVerificationFromLinkUseCase,
)
from src.modules.user.application.use_cases.reset_password_use_case import (
    ResetPasswordUseCase,
)
from src.modules.user.application.use_cases.revoke_device_use_case import (
    RevokeDeviceUseCase,
)
from src.modules.user.application.use_cases.search_users_use_case import SearchUsersUseCase
from src.modules.user.application.use_cases.set_avatar_preset_use_case import (
    SetAvatarPresetUseCase,
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
from src.modules.user.application.use_cases.upload_avatar_use_case import UploadAvatarUseCase
from src.modules.user.application.use_cases.validate_reset_token_use_case import (
    ValidateResetTokenUseCase,
)
from src.modules.user.application.use_cases.verify_email_use_case import (
    VerifyEmailUseCase,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.handicap_service import HandicapService
from src.modules.user.infrastructure.external.filesystem_avatar_preset_provider import (
    FileSystemAvatarPresetProvider,
)
from src.modules.user.infrastructure.external.google_oauth_service import (
    GoogleOAuthService,
)
from src.modules.user.infrastructure.security.security_audit_logger import SecurityAuditLogger
from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)
from src.shared.infrastructure.security.jwt_handler import (
    JWTTokenService,
)


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


def get_security_audit_logger() -> ISecurityAuditLogger:
    """Proveedor del puerto de auditoría de seguridad (el SecurityLogger compartido)."""
    return SecurityAuditLogger()


def get_register_user_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    country_repository: CountryRepositoryInterface = Depends(get_country_repository),
    handicap_service: HandicapService = Depends(get_handicap_service),
    email_service: IEmailService = Depends(get_email_service),
    security_audit: ISecurityAuditLogger = Depends(get_security_audit_logger),
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
        security_audit=security_audit,
        # Los correos del registro, sin que la respuesta los espere (fase 3)
        correo_en_segundo_plano=CorreoEnSegundoPlano(),
    )


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


def get_refresh_own_handicap_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    handicap_service: HandicapService = Depends(get_handicap_service),
) -> RefreshOwnHandicapUseCase:
    """
    Proveedor del caso de uso RefreshOwnHandicapUseCase (RyderCupAM#340).

    El refresco del hándicap que antes hacía el login, ahora aparte para que el
    login no espere a la RFEG.
    """
    return RefreshOwnHandicapUseCase(uow, handicap_service)


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


def get_aviso_de_nuevo_inicio_de_sesion(
    email_service: IEmailService = Depends(get_email_service),
    fabrica: async_sessionmaker[AsyncSession] = Depends(get_fabrica_de_sesiones),
) -> IAvisoDeNuevoInicio:
    """El correo de «nuevo inicio de sesión» al propio usuario, en segundo plano (BE #737)."""
    return AvisoEnSegundoPlano(fabrica, email_service)


def get_aviso_de_sesion_cerrada(
    email_service: IEmailService = Depends(get_email_service),
    fabrica: async_sessionmaker[AsyncSession] = Depends(get_fabrica_de_sesiones),
) -> IAvisoDeSesionCerrada:
    """El correo de «sesión cerrada por seguridad» al propio usuario, en segundo plano (F-02),
    con el tope global de avisos."""
    return AvisoDeSesionCerradaEnSegundoPlano(fabrica, email_service, cupo_de_avisos)


def get_freno_del_login() -> IFrenoDelLogin:
    """El freno del login por correo y origen, uno para todo el proceso (BE #732)."""
    return freno_del_login


def get_aviso_de_fallos(
    email_service: IEmailService = Depends(get_email_service),
    fabrica: async_sessionmaker[AsyncSession] = Depends(get_fabrica_de_sesiones),
) -> IAvisoDeFallos:
    """El correo de «intentos fallidos» al dueño, en segundo plano, con su tope global (BE #732)."""
    return AvisoDeFallosEnSegundoPlano(fabrica, email_service, cupo_de_avisos)


def get_login_user_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    token_service: ITokenService = Depends(get_token_service),
    register_device_use_case: RegisterDeviceUseCase = Depends(get_register_device_use_case),
    aviso: IAvisoDeNuevoInicio = Depends(get_aviso_de_nuevo_inicio_de_sesion),
    freno: IFrenoDelLogin = Depends(get_freno_del_login),
    aviso_de_fallos: IAvisoDeFallos = Depends(get_aviso_de_fallos),
    security_audit: ISecurityAuditLogger = Depends(get_security_audit_logger),
) -> LoginUserUseCase:
    """
    Proveedor del caso de uso LoginUserUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_token_service` para generación de tokens JWT.
    3. Depende de `get_register_device_use_case` para device fingerprinting (v1.13.0).
    4. Crea una instancia de `LoginUserUseCase` con esas dependencias.
    5. Devuelve la instancia lista para ser usada por el endpoint de la API.

    Ya no recibe el servicio de hándicap: el login no espera a la RFEG
    (RyderCupAM#340); eso lo hace `get_refresh_own_handicap_use_case`.
    """
    return LoginUserUseCase(
        uow,
        token_service,
        register_device_use_case,
        aviso,
        freno,
        aviso_de_fallos,
        security_audit=security_audit,
    )


def get_logout_user_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    security_audit: ISecurityAuditLogger = Depends(get_security_audit_logger),
) -> LogoutUserUseCase:
    """
    Proveedor del caso de uso LogoutUserUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Crea una instancia de `LogoutUserUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return LogoutUserUseCase(uow, security_audit=security_audit)


def get_refresh_access_token_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    token_service: ITokenService = Depends(get_token_service),
    security_audit: ISecurityAuditLogger = Depends(get_security_audit_logger),
    aviso_de_cierre: IAvisoDeSesionCerrada = Depends(get_aviso_de_sesion_cerrada),
) -> RefreshAccessTokenUseCase:
    """
    Proveedor del caso de uso RefreshAccessTokenUseCase (Session Timeout - v1.8.0).

    Con la Unit of Work (users + refresh_tokens + user_devices) y el servicio de
    tokens. Ya no registra dispositivos: usa el de su token (BE #738). Rota el refresh
    token y, si detecta un robo, avisa al usuario en segundo plano (F-02).
    """
    return RefreshAccessTokenUseCase(
        uow, token_service, security_audit=security_audit, aviso_de_cierre=aviso_de_cierre
    )


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


def get_confirm_email_change_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    security_audit: ISecurityAuditLogger = Depends(get_security_audit_logger),
    email_service: IEmailService = Depends(get_email_service),
) -> ConfirmEmailChangeUseCase:
    """Proveedor del caso de uso que confirma el correo nuevo pendiente (#749)."""
    return ConfirmEmailChangeUseCase(
        uow, security_audit=security_audit, email_service=email_service
    )


def get_cancel_email_change_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> CancelEmailChangeUseCase:
    """Proveedor del caso de uso que anula el correo nuevo pendiente (#749)."""
    return CancelEmailChangeUseCase(uow)


def get_update_security_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IEmailService = Depends(get_email_service),
    security_audit: ISecurityAuditLogger = Depends(get_security_audit_logger),
    token_service: ITokenService = Depends(get_token_service),
) -> UpdateSecurityUseCase:
    """
    Proveedor del caso de uso UpdateSecurityUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_email_service` para envío de emails de verificación.
    3. Crea una instancia de `UpdateSecurityUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    # Con el servicio de tokens: quien cambia la contraseña sigue dentro con una
    # sesión nueva (auditoría de la fase 6, B-05)
    return UpdateSecurityUseCase(
        uow, email_service, security_audit=security_audit, token_service=token_service
    )


def get_avatar_preset_provider() -> IAvatarPresetProvider:
    """Proveedor del catálogo de presets de avatar (assets estáticos en disco)."""
    return FileSystemAvatarPresetProvider()


def get_set_avatar_preset_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> SetAvatarPresetUseCase:
    """Proveedor del caso de uso SetAvatarPresetUseCase."""
    return SetAvatarPresetUseCase(uow)


def get_upload_avatar_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    image_processor: IImageProcessor = Depends(get_image_processor),
) -> UploadAvatarUseCase:
    """Proveedor del caso de uso UploadAvatarUseCase."""
    return UploadAvatarUseCase(uow, image_processor)


def get_activate_uploaded_avatar_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> ActivateUploadedAvatarUseCase:
    """Proveedor del caso de uso ActivateUploadedAvatarUseCase."""
    return ActivateUploadedAvatarUseCase(uow)


def get_list_my_avatar_uploads_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> ListMyAvatarUploadsUseCase:
    """Proveedor del caso de uso ListMyAvatarUploadsUseCase."""
    return ListMyAvatarUploadsUseCase(uow)


def get_accept_terms_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    security_audit: ISecurityAuditLogger = Depends(get_security_audit_logger),
) -> AcceptTermsUseCase:
    """Proveedor del caso de uso AcceptTermsUseCase."""
    return AcceptTermsUseCase(uow, security_audit)


def get_remove_avatar_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> RemoveAvatarUseCase:
    """Proveedor del caso de uso RemoveAvatarUseCase."""
    return RemoveAvatarUseCase(uow)


def get_my_avatar_upload_image_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> GetMyAvatarUploadImageUseCase:
    """Proveedor del caso de uso GetMyAvatarUploadImageUseCase."""
    return GetMyAvatarUploadImageUseCase(uow)


def get_list_avatar_presets_use_case() -> ListAvatarPresetsUseCase:
    """Proveedor del caso de uso ListAvatarPresetsUseCase."""
    return ListAvatarPresetsUseCase()


def get_avatar_preset_image_use_case(
    preset_provider: IAvatarPresetProvider = Depends(get_avatar_preset_provider),
) -> GetAvatarPresetImageUseCase:
    """Proveedor del caso de uso GetAvatarPresetImageUseCase."""
    return GetAvatarPresetImageUseCase(preset_provider)


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


def get_reenvio_de_verificacion(
    email_service: IEmailService = Depends(get_email_service),
    fabrica: async_sessionmaker[AsyncSession] = Depends(get_fabrica_de_sesiones),
) -> IReenvioDeVerificacion:
    """El reenvío del enlace de verificación: envía y después guarda, en segundo plano."""
    return ReenvioEnSegundoPlano(fabrica, email_service)


def get_resend_verification_email_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IEmailService = Depends(get_email_service),
    reenvio: IReenvioDeVerificacion = Depends(get_reenvio_de_verificacion),
) -> ResendVerificationEmailUseCase:
    """El reenvío por correo, el de la cuenta con sesión (fase 3, revisión)."""
    return ResendVerificationEmailUseCase(uow, email_service, reenvio=reenvio)


def get_resend_verification_from_link_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IEmailService = Depends(get_email_service),
    reenvio: IReenvioDeVerificacion = Depends(get_reenvio_de_verificacion),
) -> ResendVerificationFromLinkUseCase:
    """El reenvío sin sesión, con el enlace caducado como prueba (fase 3, revisión)."""
    return ResendVerificationFromLinkUseCase(uow, email_service, reenvio=reenvio)


def get_request_password_reset_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IEmailService = Depends(get_email_service),
    security_audit: ISecurityAuditLogger = Depends(get_security_audit_logger),
):
    """
    Proveedor del caso de uso RequestPasswordResetUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_email_service` para envío de emails de reseteo.
    3. Crea una instancia de `RequestPasswordResetUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return RequestPasswordResetUseCase(
        uow,
        email_service,
        frontend_url=settings.FRONTEND_URL,
        security_audit=security_audit,
        # El correo, sin que la respuesta lo espere (fase 3, B-2)
        correo_en_segundo_plano=CorreoEnSegundoPlano(),
    )


def get_reset_password_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IEmailService = Depends(get_email_service),
    security_audit: ISecurityAuditLogger = Depends(get_security_audit_logger),
):
    """
    Proveedor del caso de uso ResetPasswordUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_email_service` para envío de email de confirmación.
    3. Crea una instancia de `ResetPasswordUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return ResetPasswordUseCase(uow, email_service, security_audit=security_audit)


def get_validate_reset_token_use_case(uow: UserUnitOfWorkInterface = Depends(get_uow)):
    """
    Proveedor del caso de uso ValidateResetTokenUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Crea una instancia de `ValidateResetTokenUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return ValidateResetTokenUseCase(uow)


def get_bloqueos(
    social_uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
) -> BloqueosInterface:
    """Quién bloqueó a quién, del módulo social, para `user` (F-09)."""
    return BloqueosAdapter(social_uow)


def get_avatar_image_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    preset_provider: IAvatarPresetProvider = Depends(get_avatar_preset_provider),
    bloqueos: BloqueosInterface = Depends(get_bloqueos),
) -> GetAvatarImageUseCase:
    """Proveedor del caso de uso GetAvatarImageUseCase; con los bloqueos (F-09)."""
    return GetAvatarImageUseCase(uow, preset_provider, bloqueos)


def get_find_user_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    bloqueos: BloqueosInterface = Depends(get_bloqueos),
) -> FindUserUseCase:
    """Proveedor del caso de uso FindUserUseCase; sin quien me bloqueó (F-09)."""
    return FindUserUseCase(uow, bloqueos)


def get_search_users_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    bloqueos: BloqueosInterface = Depends(get_bloqueos),
) -> SearchUsersUseCase:
    """Proveedor del caso de uso SearchUsersUseCase; sin quien me bloqueó (F-09)."""
    return SearchUsersUseCase(uow=uow, bloqueos=bloqueos)


def get_admin_list_users_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> AdminListUsersUseCase:
    """Proveedor del caso de uso AdminListUsersUseCase."""
    return AdminListUsersUseCase(uow)


def get_admin_update_user_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IEmailService = Depends(get_email_service),
    security_audit: ISecurityAuditLogger = Depends(get_security_audit_logger),
) -> AdminUpdateUserUseCase:
    """Proveedor de AdminUpdateUserUseCase (con su log de seguridad desde F-20)."""
    return AdminUpdateUserUseCase(uow, email_service=email_service, security_audit=security_audit)


def get_admin_set_user_active_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    security_audit: ISecurityAuditLogger = Depends(get_security_audit_logger),
) -> AdminSetUserActiveUseCase:
    """Proveedor de AdminSetUserActiveUseCase (con su log de seguridad desde BE #744)."""
    return AdminSetUserActiveUseCase(uow, security_audit)


def get_admin_delete_user_use_case(
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    competition_uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    quick_match_uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    security_audit: ISecurityAuditLogger = Depends(get_security_audit_logger),
) -> AdminDeleteUserUseCase:
    """Proveedor de AdminDeleteUserUseCase (con su log de seguridad desde F-20)."""
    return AdminDeleteUserUseCase(
        user_uow,
        competition_uow,
        quick_match_uow,
        golf_course_uow,
        security_audit=security_audit,
    )


def get_get_admin_stats_use_case(
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    competition_uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    quick_match_uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> GetAdminStatsUseCase:
    """Proveedor del caso de uso GetAdminStatsUseCase."""
    return GetAdminStatsUseCase(user_uow, competition_uow, quick_match_uow, golf_course_uow)


def get_get_recent_matches_use_case(
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    competition_uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    quick_match_uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> GetRecentMatchesUseCase:
    """Proveedor del caso de uso GetRecentMatchesUseCase."""
    return GetRecentMatchesUseCase(user_uow, competition_uow, quick_match_uow, golf_course_uow)


def get_unlock_account_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    freno: IFrenoDelLogin = Depends(get_freno_del_login),
    security_audit: ISecurityAuditLogger = Depends(get_security_audit_logger),
) -> UnlockAccountUseCase:
    """Proveedor de UnlockAccountUseCase (v1.13.0; log desde 2.50.1, por red desde BE #732)."""
    return UnlockAccountUseCase(uow, freno, security_audit)


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
    security_audit: ISecurityAuditLogger = Depends(get_security_audit_logger),
) -> RevokeDeviceUseCase:
    """
    Proveedor del caso de uso RevokeDeviceUseCase (v1.13.0 - Device Fingerprinting).

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work (user_devices repository).
    2. Crea una instancia de `RevokeDeviceUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint DELETE /users/me/devices/{id}.
    """
    return RevokeDeviceUseCase(uow, security_audit)


def get_google_oauth_service() -> IGoogleOAuthService:
    """Proveedor del servicio de Google OAuth."""
    return GoogleOAuthService()


def get_google_login_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    token_service: ITokenService = Depends(get_token_service),
    google_oauth_service: IGoogleOAuthService = Depends(get_google_oauth_service),
    register_device_use_case: RegisterDeviceUseCase = Depends(get_register_device_use_case),
    aviso: IAvisoDeNuevoInicio = Depends(get_aviso_de_nuevo_inicio_de_sesion),
    security_audit: ISecurityAuditLogger = Depends(get_security_audit_logger),
    email_service: IEmailService = Depends(get_email_service),
) -> GoogleLoginUseCase:
    """Proveedor del caso de uso GoogleLoginUseCase."""
    return GoogleLoginUseCase(
        uow,
        token_service,
        google_oauth_service,
        register_device_use_case,
        aviso,
        security_audit=security_audit,
        email_service=email_service,
    )


def get_link_google_account_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    google_oauth_service: IGoogleOAuthService = Depends(get_google_oauth_service),
    security_audit: ISecurityAuditLogger = Depends(get_security_audit_logger),
    email_service: IEmailService = Depends(get_email_service),
) -> LinkGoogleAccountUseCase:
    """Proveedor del caso de uso LinkGoogleAccountUseCase."""
    return LinkGoogleAccountUseCase(
        uow, google_oauth_service, security_audit=security_audit, email_service=email_service
    )


def get_reauthenticate_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    security_audit: ISecurityAuditLogger = Depends(get_security_audit_logger),
) -> ReauthenticateUseCase:
    """Proveedor del caso de uso que comprueba la contraseña actual (BE #753)."""
    return ReauthenticateUseCase(uow, security_audit=security_audit)


def get_unlink_google_account_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IEmailService = Depends(get_email_service),
    security_audit: ISecurityAuditLogger = Depends(get_security_audit_logger),
) -> UnlinkGoogleAccountUseCase:
    """Proveedor del caso de uso UnlinkGoogleAccountUseCase."""
    return UnlinkGoogleAccountUseCase(
        uow, email_service=email_service, security_audit=security_audit
    )
