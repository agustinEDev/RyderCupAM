import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials

from src.config.dependencies import (
    get_current_user,
    get_login_user_use_case,
    get_logout_user_use_case,
    get_refresh_access_token_use_case,
    get_register_user_use_case,
    get_resend_verification_email_use_case,
    get_verify_email_use_case,
    security,
)
from src.config.rate_limit import limiter
from src.modules.user.application.dto.user_dto import (
    LoginRequestDTO,
    LoginResponseDTO,
    LogoutRequestDTO,
    LogoutResponseDTO,
    RefreshAccessTokenRequestDTO,
    RefreshAccessTokenResponseDTO,
    RegisterUserRequestDTO,
    ResendVerificationEmailRequestDTO,
    ResendVerificationEmailResponseDTO,
    UserResponseDTO,
    VerifyEmailRequestDTO,
)
from src.modules.user.application.use_cases.login_user_use_case import LoginUserUseCase
from src.modules.user.application.use_cases.logout_user_use_case import LogoutUserUseCase
from src.modules.user.application.use_cases.refresh_access_token_use_case import (
    RefreshAccessTokenUseCase,
)
from src.modules.user.application.use_cases.register_user_use_case import RegisterUserUseCase
from src.modules.user.application.use_cases.resend_verification_email_use_case import (
    ResendVerificationEmailUseCase,
)
from src.modules.user.application.use_cases.verify_email_use_case import VerifyEmailUseCase
from src.modules.user.domain.errors.user_errors import UserAlreadyExistsError
from src.shared.infrastructure.security.cookie_handler import (
    delete_auth_cookie,
    delete_refresh_token_cookie,
    get_cookie_name,
    get_refresh_cookie_name,
    set_auth_cookie,
    set_refresh_token_cookie,
)
from src.shared.infrastructure.security.jwt_handler import (
    create_access_token,
    create_refresh_token,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# HELPER FUNCTIONS - Security Context Extraction
# ============================================================================

def get_client_ip(request: Request) -> str:
    """
    Extrae la dirección IP del cliente del request.

    Prioriza headers de proxy (X-Forwarded-For, X-Real-IP) para detectar
    IP real detrás de proxies/load balancers.

    Args:
        request: Request de FastAPI

    Returns:
        Dirección IP del cliente o "unknown" si no se puede determinar
    """
    # Prioridad 1: X-Forwarded-For (proxies, load balancers)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For puede contener múltiples IPs: "client, proxy1, proxy2"
        # La primera es la IP real del cliente
        return forwarded_for.split(",")[0].strip()

    # Prioridad 2: X-Real-IP (Nginx, otros proxies)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Prioridad 3: client.host (conexión directa)
    if request.client and request.client.host:
        return request.client.host

    # Fallback: IP desconocida
    return "unknown"


def get_user_agent(request: Request) -> str:
    """
    Extrae el User-Agent del cliente del request.

    Args:
        request: Request de FastAPI

    Returns:
        User-Agent del navegador o "unknown" si no está presente
    """
    user_agent = request.headers.get("User-Agent")
    return user_agent if user_agent else "unknown"

@router.post(
    "/register",
    response_model=UserResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo usuario",
    description="Crea un nuevo usuario en el sistema con email, contraseña, nombre, apellidos y opcionalmente código de país (ISO 3166-1 alpha-2).",
    tags=["Authentication"],
)
@limiter.limit("3/hour")  # Anti-spam: máximo 3 registros por hora desde la misma IP
async def register_user(
    request: Request,  # Requerido por SlowAPI limiter (no renombrar)
    register_data: RegisterUserRequestDTO,
    use_case: RegisterUserUseCase = Depends(get_register_user_use_case),
):
    """
    Endpoint para registrar un nuevo usuario.
    """
    try:
        user_response = await use_case.execute(register_data)
        return user_response
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
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
@limiter.limit("5/minute")  # Anti brute-force: máximo 5 intentos de login por minuto
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
    login_data.ip_address = get_client_ip(request)
    login_data.user_agent = get_user_agent(request)

    login_response = await use_case.execute(login_data)

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
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
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
       - Marca todos los refresh tokens del usuario como revocados
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

    # Obtener token: prioridad cookie, luego header (mismo orden que get_current_user)
    token = None
    cookie_name = get_cookie_name()
    token = request.cookies.get(cookie_name)

    if not token and credentials:
        token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no encontrado",
        )

    # Security Logging (v1.8.0): Extraer contexto HTTP para audit trail
    logout_request.ip_address = get_client_ip(request)
    logout_request.user_agent = get_user_agent(request)

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

    return logout_response


@router.post(
    "/refresh-token",
    response_model=RefreshAccessTokenResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Renovar access token",
    description="Genera un nuevo access token usando un refresh token válido (httpOnly cookie).",
    tags=["Authentication"],
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

    Raises:
        HTTPException 401: Si refresh token es inválido, expirado o revocado
    """
    # Leer refresh token desde cookie httpOnly
    refresh_cookie_name = get_refresh_cookie_name()
    refresh_token_jwt = request.cookies.get(refresh_cookie_name)

    if not refresh_token_jwt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token no proporcionado. Por favor, inicia sesión nuevamente.",
        )

    # Security Logging (v1.8.0): Extraer contexto HTTP para audit trail
    refresh_request = RefreshAccessTokenRequestDTO(
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request)
    )
    refresh_response = await use_case.execute(refresh_request, refresh_token_jwt)

    if not refresh_response:
        # Refresh token inválido, expirado o revocado
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado. Por favor, inicia sesión nuevamente.",
        )

    # ✅ Establecer nuevo access token en cookie httpOnly (15 min)
    set_auth_cookie(response, refresh_response.access_token)

    # ⚠️ LEGACY: Retornar access token en response body para compatibilidad
    # TODO (v2.0.0): BREAKING CHANGE - Eliminar campo access_token del response body
    return refresh_response


from src.shared.infrastructure.security.jwt_handler import create_access_token


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
async def verify_email(
    request: VerifyEmailRequestDTO,
    response: Response,
    use_case: VerifyEmailUseCase = Depends(get_verify_email_use_case),
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
        request: DTO con el token de verificación
        response: Response de FastAPI (para establecer cookies)
        use_case: Caso de uso de verificación de email

    Returns:
        LoginResponseDTO con token y datos del usuario

    Raises:
        HTTPException 400: Si el token es inválido (mensaje genérico)
    """
    TOKEN_PREVIEW_LENGTH = 8
    token_preview = f"{request.token[:TOKEN_PREVIEW_LENGTH]}..." if len(request.token) > TOKEN_PREVIEW_LENGTH else "***"
    logger.info(f"Email verification attempt with token: {token_preview}")

    try:
        user = await use_case.execute(request.token)
        logger.info(f"Email verification successful for token: {token_preview}")

        # Generar access token (15 min) + refresh token (7 días) - Session Timeout v1.8.0
        access_token = create_access_token({"sub": str(user.id.value)})
        refresh_token = create_refresh_token({"sub": str(user.id.value)})

        # ✅ NUEVO (v1.8.0): Establecer ambas cookies httpOnly
        set_auth_cookie(response, access_token)
        set_refresh_token_cookie(response, refresh_token)

        # Mapear a DTO
        user_dto = UserResponseDTO.model_validate(user)

        # ⚠️ LEGACY: Retornar tokens en response body para compatibilidad
        # TODO (v2.0.0): BREAKING CHANGE - Eliminar campos de tokens del response body
        return LoginResponseDTO(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user=user_dto,
            email_verification_required=False
        )
    except ValueError as e:
        logger.warning(
            f"Email verification failed (expected): {type(e).__name__} - token: {token_preview}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to verify email. Please check your verification link or request a new one.",
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error in email verification: {type(e).__name__}",
            exc_info=True
        )
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
@limiter.limit("3/hour")  # Anti-spam de emails: máximo 3 reenvíos por hora
async def resend_verification_email(
    request: Request,  # Requerido por SlowAPI limiter (no renombrar)
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
            exc_info=True
        )
        # Aún así procedemos con respuesta genérica

    # Siempre retornamos el mismo mensaje genérico
    return ResendVerificationEmailResponseDTO(
        message="If the email address exists in our system, a verification email has been sent.",
        email=resend_data.email
    )
