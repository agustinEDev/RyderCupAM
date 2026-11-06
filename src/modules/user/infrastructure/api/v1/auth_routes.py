import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError

from src.config.csrf_config import generate_csrf_token
from src.config.dependencies import (
    get_current_user,
    get_login_user_use_case,
    get_logout_user_use_case,
    get_open_session_use_case,
    get_refresh_access_token_use_case,
    get_register_user_use_case,
    get_request_password_reset_use_case,
    get_resend_verification_email_use_case,
    get_reset_password_use_case,
    get_unlock_account_use_case,
    get_validate_reset_token_use_case,
    get_verify_email_use_case,
    security,
)
from src.config.rate_limit import (
    EMAIL_SENDING_LIMIT,
    EMAIL_SENDING_PER_EMAIL_LIMIT,
    LOGIN_ATTEMPTS_LIMIT,
    REFRESH_TOKEN_LIMIT,
    REGISTER_LIMIT,
    RESET_PASSWORD_LIMIT,
    VALIDATE_RESET_TOKEN_LIMIT,
    VERIFY_EMAIL_LIMIT,
    count_or_refuse,
    email_rate_limit_key,
    get_client_identifier,
    limiter,
    refresh_token_rate_limit_key,
    skip_refresh_limit_without_valid_cookie,
    too_many_failed_logins_from_network,
    too_many_login_attempts,
)
from src.config.settings import settings
from src.modules.user.application.dto.device_dto import OpenSessionRequestDTO
from src.modules.user.application.dto.user_dto import (
    LoginRequestDTO,
    LoginResponseDTO,
    LogoutRequestDTO,
    LogoutResponseDTO,
    RefreshAccessTokenRequestDTO,
    RefreshAccessTokenResponseDTO,
    RegisterUserRequestDTO,
    RequestPasswordResetRequestDTO,
    RequestPasswordResetResponseDTO,
    ResendVerificationEmailRequestDTO,
    ResendVerificationEmailResponseDTO,
    ResetPasswordRequestDTO,
    ResetPasswordResponseDTO,
    UnlockAccountRequestDTO,
    UnlockAccountResponseDTO,
    UserResponseDTO,
    ValidateResetTokenRequestDTO,
    ValidateResetTokenResponseDTO,
    VerifyEmailRequestDTO,
)
from src.modules.user.application.use_cases.login_user_use_case import LoginUserUseCase
from src.modules.user.application.use_cases.logout_user_use_case import (
    LogoutUserUseCase,
)
from src.modules.user.application.use_cases.open_session_use_case import OpenSessionUseCase
from src.modules.user.application.use_cases.refresh_access_token_use_case import (
    SESSION_ENDED,
    SESSION_REJECTED,
    RefreshAccessTokenUseCase,
    RefreshRejectedError,
    RefreshRejection,
    codigo_publico,
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
from src.modules.user.application.use_cases.unlock_account_use_case import (
    UnlockAccountUseCase,
)
from src.modules.user.application.use_cases.validate_reset_token_use_case import (
    ValidateResetTokenUseCase,
)
from src.modules.user.application.use_cases.verify_email_use_case import (
    VerifyEmailUseCase,
)
from src.modules.user.domain.errors.user_errors import (
    TermsAcceptanceRequiredError,
    UserAlreadyExistsError,
)
from src.modules.user.domain.exceptions import (
    AccountDeactivatedException,
    AccountLockedException,
    LoginAttemptsExceededException,
)
from src.modules.user.domain.exceptions.invalid_reset_token_error import InvalidResetTokenError
from src.modules.user.domain.value_objects.password import InvalidPasswordError
from src.modules.user.infrastructure.api.v1.cookie_de_dispositivo import (
    es_la_app_instalada,
    ids_validos_de_la_cookie,
    pon_la_cookie_de_dispositivo,
)
from src.modules.user.infrastructure.api.v1.password_errors import coded_bad_request
from src.shared.infrastructure.api.respuesta_con_codigo import respuesta_con_codigo
from src.shared.infrastructure.http.http_context_validator import (
    cloudflare_client_country,
    get_trusted_client_ip,
    get_user_agent,
)
from src.shared.infrastructure.logging.security_logger import get_security_logger
from src.shared.infrastructure.security.authorization import require_admin
from src.shared.infrastructure.security.cookie_handler import (
    delete_auth_cookie,
    delete_csrf_cookie,
    delete_refresh_token_cookie,
    get_device_id_cookie_name,
    get_refresh_cookie_name,
    read_access_token,
    set_auth_cookie,
    set_csrf_cookie,
    set_refresh_token_cookie,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


# ============================================================================
# HELPER FUNCTIONS - Removed (v1.13.1)
# ============================================================================
# NOTA: get_client_ip() y get_user_agent() movidas a helper centralizado
# src/shared/infrastructure/http/http_context_validator.py
# Ahora se usa get_trusted_client_ip() para prevenir IP spoofing
# ============================================================================


@router.post(
    "/register",
    response_model=UserResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo usuario",
    description="Crea un nuevo usuario en el sistema con email, contraseña, nombre, apellidos y opcionalmente código de país (ISO 3166-1 alpha-2).",
    tags=["Authentication"],
)
@limiter.limit(REGISTER_LIMIT, key_func=get_client_identifier)  # Anti-spam, por red
async def register_user(
    request: Request,
    register_data: RegisterUserRequestDTO,
    use_case: RegisterUserUseCase = Depends(get_register_user_use_case),
):
    """
    Endpoint para registrar un nuevo usuario.
    """
    # La IP y el navegador van al historial de aceptaciones de los Términos.
    # Los pone la API, nunca el cliente (como en el login)
    register_data.ip_address = get_trusted_client_ip(
        request, settings.TRUSTED_PROXIES, settings.TRUST_CLOUDFLARE_HEADERS
    )
    register_data.user_agent = get_user_agent(request)
    try:
        user_response = await use_case.execute(register_data)
        return user_response
    except TermsAcceptanceRequiredError as e:
        # La validación del DTO ya da 422; esto es por si llegara sin validar
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        ) from e
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except InvalidPasswordError as e:
        # Con el código de la regla, para traducirlo (BE #519)
        return coded_bad_request(e)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/login",
    response_model=LoginResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Login de usuario",
    description="Autentica un usuario y devuelve access + refresh tokens (httpOnly cookies + response body).",
    tags=["Authentication"],
)
@limiter.limit(
    LOGIN_ATTEMPTS_LIMIT, key_func=get_client_identifier
)  # Techo por red; el email y los fallos van dentro
async def login_user(
    request: Request,
    response: Response,
    login_data: LoginRequestDTO,
    use_case: LoginUserUseCase = Depends(get_login_user_use_case),
):
    """
    Endpoint para login de usuario.

    Session Timeout (v1.8.0):
    Retorna dos tokens JWT con diferentes duraciones:

    1. **Access Token (15 minutos)**:
       - httpOnly cookie: access_token
       - Response body: access_token (LEGACY - compatibilidad)
       - Usado para acceder a recursos protegidos
       - Corta duración para máxima seguridad

    2. **Refresh Token (7 días)**:
       - httpOnly cookie: refresh_token
       - Response body: refresh_token (LEGACY - compatibilidad)
       - Usado solo en endpoint /refresh-token
       - Larga duración para mejor UX (sin re-login)

    Security Improvements (OWASP A01/A02/A07):
    - httpOnly=True: Previene robo de token vía XSS
    - secure=True (producción): Cookies solo viajan por HTTPS
    - samesite="lax": Protección contra CSRF
    - Refresh token hasheado en BD (no texto plano)
    - Access token de corta duración (15 min)

    Migration Path:
    - v1.8.0 (actual): Dual support (cookies + body)
    - v1.9.0: Deprecation warning en docs
    - v2.0.0: BREAKING CHANGE - Solo cookies

    Args:
        request: Request de FastAPI (requerido por SlowAPI rate limiting)
        response: Response de FastAPI (para establecer cookies)
        login_data: Credenciales de login (email + password)
        use_case: Caso de uso de login

    Returns:
        LoginResponseDTO con access_token, refresh_token y datos del usuario

    Raises:
        HTTPException 401: Si las credenciales son incorrectas
    """
    # Security Logging (v1.8.0): Extraer contexto HTTP para audit trail
    # SEGURIDAD: Usa get_trusted_client_ip() para prevenir IP spoofing
    login_data.ip_address = get_trusted_client_ip(
        request, settings.TRUSTED_PROXIES, settings.TRUST_CLOUDFLARE_HEADERS
    )
    login_data.user_agent = get_user_agent(request)

    # Device Fingerprinting (v2.0.4): Leer y validar device_id desde cookie httpOnly
    # SECURITY: Validar UUID para evitar ValidationError si cookie es malformada
    device_id_cookie_name = get_device_id_cookie_name()
    login_data.device_id_from_cookie = ids_validos_de_la_cookie(
        request.cookies.get(device_id_cookie_name)
    )
    login_data.installed_app = es_la_app_instalada(request)
    login_data.country_code = cloudflare_client_country(request)
    # La red del intento: el freno del correo cuenta por correo + red (BE #732)
    # Recortada al tamaño del DTO: fuera de producción la elige X-Test-Client-ID
    login_data.red = get_client_identifier(request)[:100]

    try:
        login_response = await use_case.execute(login_data)
    except LoginAttemptsExceededException as e:
        # 5 por minuto por correo + red (o dispositivo fiable), o el techo de fallos
        # de la red (#273): el mismo 429 que cualquier límite, exista el correo o no.
        # Los fallos, y el techo, los cuenta el caso de uso (BE #732)
        if e.techo_de_red:
            raise too_many_failed_logins_from_network() from e
        raise too_many_login_attempts() from e
    except AccountLockedException as e:
        # Account Lockout (v1.13.0): Cuenta bloqueada por intentos fallidos
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked until {e.locked_until.isoformat()}. Too many failed login attempts.",
        ) from e
    except AccountDeactivatedException as e:
        # Admin Panel (v2.4.0): Cuenta desactivada por un administrador
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Contact an administrator.",
        ) from e

    if not login_response:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ✅ NUEVO (v1.8.0): Establecer cookies httpOnly con ambos tokens
    # Access Token: 15 minutos
    set_auth_cookie(response, login_response.access_token)

    # Refresh Token: 7 días (Session Timeout)
    set_refresh_token_cookie(response, login_response.refresh_token)

    # ✅ NUEVO (v1.13.0): Establecer cookie CSRF (NO httpOnly para double-submit)
    # CSRF Token: 15 minutos (sincronizado con access token)
    set_csrf_cookie(response, login_response.csrf_token)

    # La cookie del dispositivo, siempre: renovarla la mantiene viva (Safari
    # recorta a 7 días las de una API en otra dirección) y deja este delante (BE #737)
    pon_la_cookie_de_dispositivo(response, login_response.device_id, request)

    # ⚠️ LEGACY: Retornar tokens en response body para compatibilidad
    # TODO (v2.0.0): BREAKING CHANGE - Eliminar campos de tokens del response body
    return login_response


@router.get(
    "/current-user",
    response_model=UserResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Obtener usuario actual",
    description="Devuelve información del usuario autenticado.",
    tags=["Authentication"],
)
async def get_current_user_endpoint(
    current_user: UserResponseDTO = Depends(get_current_user),
):
    """
    Endpoint para obtener información del usuario actual.

    Requiere autenticación mediante token JWT en el header:
    Authorization: Bearer <token>
    """
    return current_user


@router.post(
    "/logout",
    response_model=LogoutResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Logout de usuario",
    description="Cierra la sesión del usuario autenticado (elimina cookies httpOnly + revoca refresh tokens en BD).",
    tags=["Authentication"],
)
async def logout_user(
    request: Request,
    logout_request: LogoutRequestDTO,
    response: Response,
    current_user: UserResponseDTO = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: ARG001 - declara el esquema Bearer en OpenAPI
    use_case: LogoutUserUseCase = Depends(get_logout_user_use_case),
):
    """
    Endpoint para logout de usuario.

    Session Timeout (v1.8.0):
    El logout ahora realiza una invalidación completa de la sesión:

    1. **Eliminar cookies httpOnly** (NUEVO - v1.8.0):
       - access_token cookie (15 min)
       - refresh_token cookie (7 días)
       - Logout inmediato en el cliente

    2. **Revocar refresh tokens en BD** (NUEVO - v1.8.0):
       - Revoca los refresh tokens de ESTE dispositivo; los demás siguen (BE #376)
       - Previene renovación de access tokens después del logout
       - OWASP A01: Broken Access Control

    3. **Domain Event** (Existente):
       - Registra el evento de logout en el dominio
       - Auditoría y trazabilidad

    Security Improvements (OWASP A01/A07):
    - delete_auth_cookie(): Elimina access token del navegador
    - delete_refresh_token_cookie(): Elimina refresh token del navegador
    - LogoutUserUseCase: Revoca refresh tokens en BD
    - Previene reuso de refresh tokens después de logout

    Nota sobre access tokens:
    - Access token sigue técnicamente válido hasta expiración (15 min)
    - Pero sin refresh token, usuario debe re-login cuando expire
    - Esto es aceptable por la corta duración (15 min)

    Args:
        request: Request de FastAPI (para leer cookies)
        logout_request: DTO de logout (renombrado de 'request' para evitar conflicto)
        response: Response de FastAPI (para eliminar cookies)
        current_user: Usuario autenticado obtenido del token
        credentials: Credenciales con el token JWT (opcional con cookies)
        use_case: Caso de uso de logout

    Returns:
        LogoutResponseDTO con confirmación y timestamp
    """
    user_id = str(current_user.id)

    # Obtener token: prioridad cookie, luego header (la regla de get_current_user)
    token = read_access_token(request)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no encontrado",
        )

    # Security Logging (v1.8.0): Extraer contexto HTTP para audit trail
    # SEGURIDAD: Usa get_trusted_client_ip() para prevenir IP spoofing
    logout_request.ip_address = get_trusted_client_ip(
        request, settings.TRUSTED_PROXIES, settings.TRUST_CLOUDFLARE_HEADERS
    )
    logout_request.user_agent = get_user_agent(request)
    # Solo se cierra la sesión de este dispositivo (BE #376): su token de
    # refresco sale de su cookie httpOnly, nunca de lo que mande el cliente
    logout_request.refresh_token = request.cookies.get(get_refresh_cookie_name())

    logout_response = await use_case.execute(logout_request, user_id, token)

    if not logout_response:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
        )

    # ✅ NUEVO (v1.8.0): Eliminar ambas cookies httpOnly del navegador
    # Access Token (15 min)
    delete_auth_cookie(response)

    # Refresh Token (7 días) - Session Timeout
    delete_refresh_token_cookie(response)

    # ✅ NUEVO (v1.13.0): Eliminar cookie CSRF
    delete_csrf_cookie(response)

    # La cookie del dispositivo NO se borra (BE #737): no da acceso a nada, y
    # borrarla hacía que el siguiente login en el mismo navegador estrenara otro
    # dispositivo. El dispositivo se revoca desde /users/me/devices

    return logout_response


# El texto del 401 del refresco: el mismo para los dos códigos públicos (BE #733),
# para no decir con el texto lo que el código ya no dice
_TEXTOS_DEL_REFRESCO = dict.fromkeys(
    (SESSION_ENDED, SESSION_REJECTED),
    "Refresh token inválido o expirado. Por favor, inicia sesión nuevamente.",
)


def _refresco_rechazado(
    motivo: RefreshRejection,
    contexto: tuple[str | None, str | None] = (None, None),
    user_id: str | None = None,
) -> JSONResponse:
    """
    El 401 del refresco: texto fijo y en `error_code` solo SESSION_ENDED (el final
    normal) o SESSION_REJECTED (BE #733). El motivo exacto va al log de seguridad:
    al cliente le decía si la cuenta se borró o si cambió la contraseña.

    Borra la cookie de refresh si llegó una: un token que ya no vale no se vuelve a
    mandar, y el siguiente intento es un REFRESH_TOKEN_MISSING, el final normal, en vez
    de un REVOKED que alertaría en cada visita (/code-review, 5 nov).
    """
    codigo = codigo_publico(motivo)
    if motivo is not RefreshRejection.REFRESH_TOKEN_MISSING:
        # Sin cookie es cualquier visitante anónimo: no se apunta, solo haría ruido.
        # El log nunca cambia la respuesta: un fallo suyo daría un 500 en vez del 401
        # que borra la cookie (/code-review)
        ip_address, user_agent = contexto
        try:
            get_security_logger().log_refresh_rejected(
                ip_address=ip_address or "unknown",
                user_agent=user_agent or "unknown",
                reason=motivo.value,
                rejected=codigo == SESSION_REJECTED,
                user_id=user_id,
            )
        except Exception as error:
            logger.error("Refresh rejection audit event failed: %s", type(error).__name__)
    respuesta = respuesta_con_codigo(status.HTTP_401_UNAUTHORIZED, _TEXTOS_DEL_REFRESCO, codigo)
    # Sin cookie no hay nada que borrar, y borrarla igualmente dejaría a cualquier
    # web cerrar la sesión de quien la visite: un formulario suyo llega sin la
    # cookie (SameSite=Lax) y el Set-Cookie sí se aplica (auditoría OWASP, 5 nov)
    if motivo is not RefreshRejection.REFRESH_TOKEN_MISSING:
        delete_refresh_token_cookie(respuesta)
    return respuesta


@router.post(
    "/refresh-token",
    response_model=RefreshAccessTokenResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Renovar access token",
    description="Genera un nuevo access token usando un refresh token válido (httpOnly cookie).",
    tags=["Authentication"],
    responses={
        401: {
            "description": (
                "La sesión no se renueva. `error_code`: SESSION_ENDED, el final normal "
                "(sin sesión, caducada o 24 h sin uso), o SESSION_REJECTED, un rechazo "
                "(sin decir por qué). Borra la cookie de refresh."
            ),
        }
    },
)
# Por el usuario del refresh: llega con el acceso caducado (BE #467). Sin cookie
# válida no cuenta: va a dar 401
@limiter.limit(
    REFRESH_TOKEN_LIMIT,
    key_func=refresh_token_rate_limit_key,
    exempt_when=skip_refresh_limit_without_valid_cookie,
)
async def refresh_access_token(
    request: Request,
    response: Response,
    use_case: RefreshAccessTokenUseCase = Depends(get_refresh_access_token_use_case),
):
    """
    Endpoint para renovar el access token usando un refresh token válido.

    Session Timeout (v1.8.0):
    Este endpoint permite mantener al usuario autenticado sin necesidad de
    re-login cuando su access token (15 min) expira, siempre que tenga un
    refresh token válido (7 días).

    Flujo:
    1. Frontend detecta que access token expiró (HTTP 401 en request)
    2. Frontend llama a /refresh-token (cookie refresh_token enviada automáticamente)
    3. Backend valida refresh token (JWT + BD)
    4. Backend genera nuevo access token (15 min)
    5. Backend retorna nuevo access token (httpOnly cookie + body)
    6. Frontend reintenta request original con nuevo access token

    Security (OWASP A01/A02/A07):
    - Refresh token leído desde httpOnly cookie (previene XSS)
    - Refresh token validado contra BD (previene reuso después de logout)
    - Refresh token hasheado en BD (previene robo en DB leak)
    - Access token de corta duración (15 min)
    - Refresh token NO se renueva (debe durar hasta expiración o logout)

    NO requiere autenticación previa:
    - NO lleva header Authorization
    - Solo requiere cookie refresh_token válida

    Args:
        request: Request de FastAPI (para leer cookie refresh_token)
        response: Response de FastAPI (para establecer nuevo access_token)
        use_case: Caso de uso de refresh token

    Returns:
        RefreshAccessTokenResponseDTO con nuevo access_token y datos del usuario

    Returns (401):
        `detail` fijo y `error_code` SESSION_ENDED o SESSION_REJECTED; borra la cookie
    """
    # Leer refresh token desde cookie httpOnly
    refresh_cookie_name = get_refresh_cookie_name()
    refresh_token_jwt = request.cookies.get(refresh_cookie_name)

    if not refresh_token_jwt:
        return _refresco_rechazado(RefreshRejection.REFRESH_TOKEN_MISSING)

    # Security Logging (v1.8.0): Extraer contexto HTTP para audit trail
    # SEGURIDAD: Usa get_trusted_client_ip() para prevenir IP spoofing
    # El dispositivo es el del refresh token (BE #737, #738)
    refresh_request = RefreshAccessTokenRequestDTO(
        ip_address=get_trusted_client_ip(
            request, settings.TRUSTED_PROXIES, settings.TRUST_CLOUDFLARE_HEADERS
        ),
        user_agent=get_user_agent(request),
        installed_app=es_la_app_instalada(request),
        country_code=cloudflare_client_country(request),
    )
    try:
        refresh_response = await use_case.execute(refresh_request, refresh_token_jwt)
    except RefreshRejectedError as rechazo:
        # El mismo texto, y el código público para que el front distinga el final
        # normal de un rechazo (BE #733); el motivo exacto, al log de seguridad
        return _refresco_rechazado(
            rechazo.motivo,
            (refresh_request.ip_address, refresh_request.user_agent),
            rechazo.user_id,
        )

    # ✅ Establecer nuevo access token en cookie httpOnly (15 min)
    set_auth_cookie(response, refresh_response.access_token)

    # ✅ NUEVO (v1.13.0): Establecer nuevo token CSRF (15 min)
    set_csrf_cookie(response, refresh_response.csrf_token)

    # La cookie del dispositivo se renueva en cada refresco (BE #737): sin esto
    # caducaba a los 7 días en Safari y la app creía que el dispositivo estaba revocado
    pon_la_cookie_de_dispositivo(response, refresh_response.device_id, request)

    # ⚠️ LEGACY: Retornar access token en response body para compatibilidad
    # TODO (v2.0.0): BREAKING CHANGE - Eliminar campo access_token del response body
    return refresh_response


@router.post(
    "/verify-email",
    response_model=LoginResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Verificar email y autenticar usuario",
    description=(
        "Verifica el email del usuario usando el token recibido por correo. "
        "Si la verificación es exitosa, retorna un JWT de acceso (httpOnly cookie + response body) "
        "y la información del usuario autenticado en el mismo formato que el login. "
        "Esto permite que el usuario quede autenticado automáticamente tras verificar su email. "
        "\n\n"
        "Respuesta: LoginResponseDTO (access_token, token_type, user, email_verification_required)."
    ),
    tags=["Authentication"],
)
@limiter.limit(VERIFY_EMAIL_LIMIT, key_func=get_client_identifier)  # Por red
async def verify_email(
    request: Request,
    verify_data: VerifyEmailRequestDTO,
    response: Response,
    use_case: VerifyEmailUseCase = Depends(get_verify_email_use_case),
    open_session: OpenSessionUseCase = Depends(get_open_session_use_case),
):
    """
    Endpoint para verificar el email del usuario y autenticarlo automáticamente.

    FASE TRANSITORIA (v1.8.0 - v2.0.0):
    Al igual que /login, este endpoint retorna el JWT de dos formas:

    1. **httpOnly Cookie** (NUEVO - Recomendado):
       - Establecida automáticamente en el navegador
       - Protección contra XSS

    2. **Response Body** (LEGACY - Deprecated):
       - Campo `access_token` en LoginResponseDTO
       - TODO (v2.0.0): Eliminar este campo en breaking change

    El usuario recibe un email con un link que contiene un token.
    Este endpoint valida el token, marca el email como verificado y retorna un JWT.

    Security Notes:
    - Usa mensajes de error genéricos para prevenir user enumeration
    - No revela información sobre el estado de la cuenta
    - httpOnly cookie previene robo de token vía XSS

    Args:
        request: La petición (la necesita el límite por red)
        verify_data: DTO con el token de verificación
        response: Response de FastAPI (para establecer cookies)
        use_case: Caso de uso de verificación de email

    Returns:
        LoginResponseDTO con token y datos del usuario

    Raises:
        HTTPException 400: Si el token es inválido (mensaje genérico)
    """
    # Ni el token ni su principio en el log: con LoggingIntegration a INFO iban a
    # las migas de Sentry (auditoría OWASP, A09, 5 nov 2026)
    logger.info("Email verification attempt")

    try:
        user = await use_case.execute(verify_data.token)
        logger.info("Email verification successful")

        # La sesión, como en el login (BE #737): dispositivo, tokens con su id y el
        # refresco GUARDADO. Antes no se guardaba, y a los 15 minutos el refresco daba
        # REFRESH_TOKEN_NOT_FOUND: a cada usuario nuevo le echaban
        try:
            sesion = await open_session.execute(
                OpenSessionRequestDTO(
                    user_id=str(user.id.value),
                    user_agent=get_user_agent(request),
                    ip_address=get_trusted_client_ip(
                        request, settings.TRUSTED_PROXIES, settings.TRUST_CLOUDFLARE_HEADERS
                    ),
                    device_id_from_cookie=ids_validos_de_la_cookie(
                        request.cookies.get(get_device_id_cookie_name())
                    ),
                    installed_app=es_la_app_instalada(request),
                    country_code=cloudflare_client_country(request),
                )
            )
        except AccountDeactivatedException as e:
            # Una cuenta desactivada verifica su correo, pero no entra (BE #744): la
            # misma respuesta que el login
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account has been deactivated. Contact an administrator.",
            ) from e
        except Exception as e:
            # El correo YA está verificado y el enlace gastado: decir que el enlace no
            # vale le dejaba sin forma de entrar. Que entre con su contraseña
            # (/code-review, BE #737)
            logger.error(
                f"Session could not be opened after verifying the email: {type(e).__name__}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email verified. Please sign in to continue.",
            ) from e
        access_token = sesion.access_token
        refresh_token = sesion.refresh_token
        pon_la_cookie_de_dispositivo(response, sesion.device_id, request)

        # ✅ NUEVO (v1.13.0): Generar token CSRF - CSRF Protection
        csrf_token = generate_csrf_token(str(user.id.value))

        # ✅ NUEVO (v1.8.0): Establecer ambas cookies httpOnly
        set_auth_cookie(response, access_token)
        set_refresh_token_cookie(response, refresh_token)

        # ✅ NUEVO (v1.13.0): Establecer cookie CSRF (NO httpOnly para double-submit)
        # CSRF Token: 15 minutos (sincronizado con access token)
        set_csrf_cookie(response, csrf_token)

        # Mapear a DTO
        user_dto = UserResponseDTO.model_validate(user)

        # ⚠️ LEGACY: Retornar tokens en response body para compatibilidad
        # TODO (v2.0.0): BREAKING CHANGE - Eliminar campos de tokens del response body
        return LoginResponseDTO(
            access_token=access_token,
            refresh_token=refresh_token,
            csrf_token=csrf_token,
            token_type="bearer",  # nosec B106 - Not a password, it's OAuth2 token type
            user=user_dto,
            email_verification_required=False,
            # La sesión que abre verificar el correo también tiene su dispositivo
            device_id=sesion.device_id,
        )
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Email verification failed (expected): {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to verify email. Please check your verification link or request a new one.",
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error in email verification: {type(e).__name__}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to verify email. Please check your verification link or request a new one.",
        ) from e


@router.post(
    "/resend-verification",
    response_model=ResendVerificationEmailResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Reenviar email de verificación",
    description="Genera un nuevo token de verificación y reenvía el email al usuario.",
    tags=["Authentication"],
)
@limiter.limit(EMAIL_SENDING_LIMIT, key_func=get_client_identifier)  # Por red; el email va dentro
async def resend_verification_email(
    request: Request,  # noqa: ARG001 - Requerido por SlowAPI limiter
    resend_data: ResendVerificationEmailRequestDTO,
    use_case: ResendVerificationEmailUseCase = Depends(get_resend_verification_email_use_case),
):
    """
    Endpoint para reenviar el email de verificación.

    Este endpoint permite al usuario solicitar un nuevo email de verificación
    si no recibió el original o si expiró.

    Security Note:
    - Siempre retorna 200 OK con mensaje genérico (independiente del resultado)
    - No revela si el email existe en el sistema (previene user enumeration)
    - No revela si el email ya está verificado

    Args:
        request: DTO con el email del usuario
        use_case: Caso de uso de reenvío de email de verificación

    Returns:
        ResendVerificationEmailResponseDTO con mensaje genérico

    Note:
        Por razones de seguridad, este endpoint siempre retorna éxito,
        independientemente de si el email existe o está verificado.
    """
    # Rate limit por email (#273), desde cualquier red y exista o no el email
    count_or_refuse(
        EMAIL_SENDING_PER_EMAIL_LIMIT,
        "resend-verification-email",
        email_rate_limit_key(resend_data.email),
    )

    # Log intento de reenvío (parcialmente ofuscado para proteger privacidad)
    email_preview = f"{resend_data.email[:3]}***@{resend_data.email.split('@')[1] if '@' in resend_data.email else '***'}"
    logger.info(f"Verification email resend requested for: {email_preview}")

    try:
        await use_case.execute(resend_data.email)
        logger.info(f"Verification email resend successful for: {email_preview}")
    except ValueError as e:
        # Log para monitoreo de seguridad sin exponer en respuesta
        logger.info(
            f"Verification email resend failed (expected): {type(e).__name__} - email: {email_preview}"
        )
        # Silenciosamente ignoramos errores para prevenir user enumeration
        # Casos posibles:
        # - Email no existe
        # - Email ya verificado
        # - Error al enviar email
    except Exception as e:
        # Log errores inesperados para monitoreo del sistema
        logger.error(
            f"Unexpected error in resend verification: {type(e).__name__}",
            exc_info=True,
        )
        # Aún así procedemos con respuesta genérica

    # Siempre retornamos el mismo mensaje genérico
    return ResendVerificationEmailResponseDTO(
        message="If the email address exists in our system, a verification email has been sent.",
        email=resend_data.email,
    )


# ============================================================================
# PASSWORD RESET ENDPOINTS
# ============================================================================


@router.post(
    "/forgot-password",
    response_model=RequestPasswordResetResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Solicitar reseteo de contraseña",
    description="""
    Endpoint público para solicitar el reseteo de contraseña (flujo "Olvidé mi contraseña").

    Security Features:
    - Rate limiting: 3 intentos/hora por email
    - Timing attack prevention: Mensaje genérico sin revelar si el email existe
    - Email injection prevention: Validación con Pydantic EmailStr
    - Security logging: Todos los intentos registrados (exitosos y fallidos)

    Flow:
    1. Usuario ingresa email en formulario /forgot-password
    2. Backend valida email (mensaje genérico si no existe)
    3. Si existe: Genera token (24h) y envía email con enlace
    4. Si no existe: Delay artificial + mensaje genérico (previene enumeración)

    Response:
    - SIEMPRE retorna 200 OK con mensaje genérico
    - NUNCA revela si el email existe (previene user enumeration)
    """,
    tags=["Authentication"],
)
@limiter.limit(EMAIL_SENDING_LIMIT, key_func=get_client_identifier)  # Por red; el email va dentro
async def forgot_password(
    request: Request,
    reset_data: RequestPasswordResetRequestDTO,
    use_case: RequestPasswordResetUseCase = Depends(get_request_password_reset_use_case),
) -> RequestPasswordResetResponseDTO:
    """
    Solicita el reseteo de contraseña enviando un email con token único.

    Args:
        request: Request de FastAPI (para extraer IP, User-Agent)
        reset_data: DTO con email del usuario
        use_case: Caso de uso inyectado por FastAPI

    Returns:
        RequestPasswordResetResponseDTO con mensaje genérico

    Note:
        - Siempre retorna 200 OK (nunca 404)
        - Mensaje genérico previene enumeración de usuarios
        - Timing attack prevention con delay artificial
    """
    # Rate limit por email (#273), desde cualquier red y exista o no el email
    count_or_refuse(
        EMAIL_SENDING_PER_EMAIL_LIMIT,
        "forgot-password-email",
        email_rate_limit_key(reset_data.email),
    )

    # Extraer contexto de seguridad
    # SEGURIDAD: Usa get_trusted_client_ip() para prevenir IP spoofing
    ip_address = get_trusted_client_ip(
        request, settings.TRUSTED_PROXIES, settings.TRUST_CLOUDFLARE_HEADERS
    )
    user_agent = get_user_agent(request)

    # Añadir contexto al request DTO
    reset_data.ip_address = ip_address
    reset_data.user_agent = user_agent

    # Ejecutar use case (maneja toda la lógica)
    response = await use_case.execute(reset_data)

    return response


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Completar reseteo de contraseña",
    description="""
    Endpoint público para completar el reseteo de contraseña usando el token del email.

    Security Features:
    - Token de un solo uso (se invalida después del primer uso exitoso)
    - Validación estricta de expiración (24 horas)
    - Password policy enforcement (OWASP ASVS V2.1: 12+ chars, complejidad completa)
    - Invalidación automática de TODAS las sesiones activas (logout forzado)
    - Email de confirmación enviado al usuario
    - Security logging completo

    Flow:
    1. Usuario hace clic en enlace del email → accede a /reset-password/:token
    2. Frontend muestra formulario de nueva contraseña
    3. Usuario envía nueva contraseña + token
    4. Backend valida token, cambia password, invalida sesiones
    5. Email de confirmación enviado
    6. Usuario debe hacer login nuevamente

    Errors:
    - 400: Token inválido/expirado
    - 400: Password no cumple política
    - 429: Rate limit excedido
    """,
    tags=["Authentication"],
)
@limiter.limit(RESET_PASSWORD_LIMIT, key_func=get_client_identifier)  # Por red
async def reset_password(
    request: Request,
    reset_data: ResetPasswordRequestDTO,
    use_case: ResetPasswordUseCase = Depends(get_reset_password_use_case),
) -> ResetPasswordResponseDTO | JSONResponse:
    """
    Completa el reseteo de contraseña usando el token del email.

    Args:
        request: Request de FastAPI (para extraer IP, User-Agent)
        reset_data: DTO con token y nueva contraseña
        use_case: Caso de uso inyectado por FastAPI

    Returns:
        ResetPasswordResponseDTO con mensaje de confirmación

    Raises:
        HTTPException 400: Si el token es inválido/expirado o password inválido

    Post-Conditions:
        - Token invalidado (uso único)
        - Todas las sesiones activas invalidadas
        - Email de confirmación enviado
    """
    # Extraer contexto de seguridad
    # SEGURIDAD: Usa get_trusted_client_ip() para prevenir IP spoofing
    ip_address = get_trusted_client_ip(
        request, settings.TRUSTED_PROXIES, settings.TRUST_CLOUDFLARE_HEADERS
    )
    user_agent = get_user_agent(request)

    # Añadir contexto al request DTO
    reset_data.ip_address = ip_address
    reset_data.user_agent = user_agent

    try:
        # Ejecutar use case (maneja toda la lógica)
        response = await use_case.execute(reset_data)
        return response
    except (InvalidPasswordError, InvalidResetTokenError) as e:
        # Con su código, para traducirlo (BE #519), y al log como los demás fallos
        logger.warning(f"Password reset failed: {e!s}")
        return coded_bad_request(e)
    except ValueError as e:
        # Token inválido/expirado o password inválido
        logger.warning(f"Password reset failed: {e!s}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None


@router.get(
    "/validate-reset-token/{token}",
    response_model=ValidateResetTokenResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Validar token de reseteo (OPCIONAL)",
    description="""
    Endpoint público OPCIONAL para validar un token ANTES de mostrar el formulario.

    UX Benefits:
    - Detecta token expirado ANTES de que el usuario escriba nueva contraseña
    - Redirige a /forgot-password si el token es inválido (mejor experiencia)
    - Muestra formulario solo si el token es válido

    Security:
    - NO requiere autenticación (endpoint público)
    - NO revela información sobre el usuario (solo retorna valid: bool)
    - Rate limiting: 10 intentos/hora por IP

    Flow sin validación previa:
    1. Usuario hace clic → Formulario → Envía → "Token expirado" (mala UX)

    Flow con validación previa:
    1. Usuario hace clic → Validación → Si expirado: Redirige con mensaje
    2. Si válido: Muestra formulario → Envía → SUCCESS
    """,
    tags=["Authentication"],
)
@limiter.limit(VALIDATE_RESET_TOKEN_LIMIT, key_func=get_client_identifier)  # Por red
async def validate_reset_token(
    request: Request,  # noqa: ARG001 - Requerido por SlowAPI limiter
    token: str,
    use_case: ValidateResetTokenUseCase = Depends(get_validate_reset_token_use_case),
) -> ValidateResetTokenResponseDTO:
    """
    Valida un token de reseteo antes de mostrar el formulario.

    Args:
        token: Token de reseteo a validar (path parameter)
        use_case: Caso de uso inyectado por FastAPI

    Returns:
        ValidateResetTokenResponseDTO con valid=True/False y mensaje

    Note:
        - SIEMPRE retorna 200 OK (nunca 404)
        - NO incluye email del usuario por seguridad
    """
    # Un token con una longitud imposible es un token inválido más: la ruta
    # promete 200 con valid=False, no un 500 (BE #453). Mismo mensaje que el
    # caso de uso, para que la longitud no revele nada distinto
    try:
        request_dto = ValidateResetTokenRequestDTO(token=token)
    except ValidationError:
        return ValidateResetTokenResponseDTO(
            valid=False,
            message="Token de reseteo inválido o expirado. Solicita un nuevo enlace.",
        )

    # Ejecutar use case
    response = await use_case.execute(request_dto)

    return response


# ============================================================================
# ACCOUNT LOCKOUT ENDPOINT (v1.13.0)
# ============================================================================


@router.post(
    "/unlock-account",
    response_model=UnlockAccountResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Desbloquear cuenta manualmente (Admin)",
    description="Permite a un administrador desbloquear una cuenta bloqueada por intentos fallidos antes de la expiración de 30 minutos.",
    tags=["Authentication", "Admin"],
)
async def unlock_account(
    request: Request,
    unlock_data: UnlockAccountRequestDTO,
    use_case: UnlockAccountUseCase = Depends(get_unlock_account_use_case),
    current_user: UserResponseDTO = Depends(get_current_user),
):
    """
    Desbloquea manualmente una cuenta bloqueada (solo Admin).

    Account Lockout (v1.13.0):
    - Permite desbloquear cuentas antes de expiración automática (30 min)
    - Resetea failed_login_attempts a 0
    - Elimina locked_until (None)
    - Deja el desbloqueo en el log de seguridad (y el intento sin permiso)

    Security (OWASP A01, A09):
    - Solo Admin puede ejecutar este endpoint (403 al resto, hotfix 2.50.1)
    - Requiere autenticación JWT válida

    Args:
        request: Request de FastAPI
        unlock_data: DTO con user_id (a desbloquear) y unlocked_by_user_id (admin)
        use_case: Caso de uso de desbloqueo
        current_user: Usuario autenticado (de JWT)

    Returns:
        UnlockAccountResponseDTO con resultado de la operación

    Raises:
        HTTPException 401: Si no está autenticado
        HTTPException 403: Si no es Admin
        HTTPException 400: Si el usuario no existe o la cuenta no está bloqueada
    """
    ip_address = get_trusted_client_ip(
        request, settings.TRUSTED_PROXIES, settings.TRUST_CLOUDFLARE_HEADERS
    )
    user_agent = get_user_agent(request)

    # Solo administradores (hotfix 2.50.1): con solo pedir sesión, cualquiera podía
    # quitar el bloqueo de otra cuenta y seguir probando contraseñas (OWASP A01/A07).
    # Antes de buscar la cuenta: un 403 no dice si el id existe. El intento, al log
    try:
        require_admin(current_user)
    except HTTPException:
        # El log, sin tumbar el 403: si falla, solo el tipo del error
        try:
            get_security_logger().log_access_denied(
                user_id=str(current_user.id),
                ip_address=ip_address or "unknown",
                user_agent=user_agent or "unknown",
                resource_type="account_lock",
                resource_id=unlock_data.user_id,
                action_attempted="unlock",
                denial_reason="not_admin",
            )
        except Exception as log_error:
            logger.error("Access denied audit event failed: %s", type(log_error).__name__)
        raise

    # Quién y desde dónde, del usuario autenticado y de la petición: nunca del cuerpo
    unlock_data.unlocked_by_user_id = str(current_user.id)
    unlock_data.ip_address = ip_address
    unlock_data.user_agent = user_agent

    try:
        response = await use_case.execute(unlock_data)
        return response
    except ValueError as e:
        # Usuario no existe o cuenta no está bloqueada
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
