import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config.rate_limit import limiter
from src.shared.infrastructure.security.cookie_handler import delete_auth_cookie, set_auth_cookie
from src.config.dependencies import (
    get_current_user,
    get_login_user_use_case,
    get_logout_user_use_case,
    get_register_user_use_case,
    get_resend_verification_email_use_case,
    get_verify_email_use_case,
    security,
)
from src.modules.user.application.dto.user_dto import (
    LoginRequestDTO,
    LoginResponseDTO,
    LogoutRequestDTO,
    LogoutResponseDTO,
    RegisterUserRequestDTO,
    ResendVerificationEmailRequestDTO,
    ResendVerificationEmailResponseDTO,
    UserResponseDTO,
    VerifyEmailRequestDTO,
)
from src.modules.user.application.use_cases.login_user_use_case import LoginUserUseCase
from src.modules.user.application.use_cases.logout_user_use_case import LogoutUserUseCase
from src.modules.user.application.use_cases.register_user_use_case import RegisterUserUseCase
from src.modules.user.application.use_cases.resend_verification_email_use_case import (
    ResendVerificationEmailUseCase,
)
from src.modules.user.application.use_cases.verify_email_use_case import VerifyEmailUseCase
from src.modules.user.domain.errors.user_errors import UserAlreadyExistsError

logger = logging.getLogger(__name__)
router = APIRouter()

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
    request: Request,
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
    description="Autentica un usuario y devuelve un token JWT (httpOnly cookie + response body para compatibilidad).",
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

    FASE TRANSITORIA (v1.8.0 - v2.0.0):
    Retorna el JWT de dos formas para permitir migración gradual del frontend:

    1. **httpOnly Cookie** (NUEVO - Recomendado):
       - Establecida automáticamente en el navegador
       - JavaScript NO puede leerla (protección XSS)
       - Se envía automáticamente en requests subsecuentes

    2. **Response Body** (LEGACY - Deprecated):
       - Campo `access_token` en LoginResponseDTO
       - Permite compatibilidad con frontend actual (localStorage)
       - TODO (v2.0.0): Eliminar este campo en breaking change

    Security Improvements (OWASP A01/A02):
    - httpOnly=True: Previene robo de token vía XSS
    - secure=True (producción): Cookie solo viaja por HTTPS
    - samesite="lax": Protección contra CSRF

    Migration Path:
    - v1.8.0 (actual): Dual support (cookie + body)
    - v1.9.0: Deprecation warning en docs
    - v2.0.0: BREAKING CHANGE - Solo cookies, eliminar campo access_token

    Args:
        request: Request de FastAPI (requerido por SlowAPI rate limiting)
        response: Response de FastAPI (para establecer cookies)
        login_data: Credenciales de login (email + password)
        use_case: Caso de uso de login

    Returns:
        LoginResponseDTO con token y datos del usuario

    Raises:
        HTTPException 401: Si las credenciales son incorrectas
    """
    login_response = await use_case.execute(login_data)

    if not login_response:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ✅ NUEVO (v1.8.0): Establecer cookie httpOnly con el JWT
    # Protección contra XSS: JavaScript NO puede leer esta cookie
    set_auth_cookie(response, login_response.access_token)

    # ⚠️ LEGACY: Retornar token en response body para compatibilidad
    # TODO (v2.0.0): BREAKING CHANGE - Eliminar campo access_token del response body
    # cuando frontend migre completamente a cookies httpOnly
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
    description="Cierra la sesión del usuario autenticado (elimina cookie httpOnly + domain event).",
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

    FASE TRANSITORIA (v1.8.0 - v2.0.0):
    El logout ahora elimina la cookie httpOnly del navegador:

    1. **Eliminar cookie httpOnly** (NUEVO - v1.8.0):
       - Invalida la cookie en el navegador (logout inmediato)
       - Protege contra reutilización accidental de sesiones

    2. **Domain Event** (Existente):
       - Registra el evento de logout en el dominio
       - Preparado para blacklist de tokens en Fase 2

    Nota sobre invalidación de tokens:
    - Fase 1 (v1.8.0): Cookie eliminada del navegador, pero JWT técnicamente válido hasta expiración
    - Fase 2 (v1.9.0+): Blacklist de tokens para invalidación completa en backend

    Security Improvements:
    - delete_auth_cookie(): Elimina cookie httpOnly del navegador
    - Frontend no puede acceder a la cookie (httpOnly=true)
    - Logout inmediato sin intervención de JavaScript

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
    from src.shared.infrastructure.security.cookie_handler import get_cookie_name
    
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

    logout_response = await use_case.execute(logout_request, user_id, token)

    if not logout_response:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
        )

    # ✅ NUEVO (v1.8.0): Eliminar cookie httpOnly del navegador
    # Logout inmediato en el cliente (cookie invalidada)
    delete_auth_cookie(response)

    return logout_response



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
    token_preview = f"{request.token[:8]}..." if len(request.token) > 8 else "***"
    logger.info(f"Email verification attempt with token: {token_preview}")

    try:
        user = await use_case.execute(request.token)
        logger.info(f"Email verification successful for token: {token_preview}")

        # Generar JWT
        access_token = create_access_token({"sub": str(user.id.value)})

        # ✅ NUEVO (v1.8.0): Establecer cookie httpOnly con el JWT
        # Protección contra XSS: JavaScript NO puede leer esta cookie
        set_auth_cookie(response, access_token)

        # Mapear a DTO
        from src.modules.user.application.dto.user_dto import LoginResponseDTO, UserResponseDTO
        user_dto = UserResponseDTO.model_validate(user)

        # ⚠️ LEGACY: Retornar token en response body para compatibilidad
        # TODO (v2.0.0): BREAKING CHANGE - Eliminar campo access_token del response body
        return LoginResponseDTO(
            access_token=access_token,
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
    request: Request,
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
