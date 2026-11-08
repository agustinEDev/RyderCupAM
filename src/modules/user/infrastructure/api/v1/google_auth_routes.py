"""
Google Auth Routes - Infrastructure Layer

Endpoints para autenticación con Google OAuth:
- POST /google: Login/registro con Google (público)
- POST /google/link: Vincular cuenta Google (auth requerida)
- DELETE /google/unlink: Desvincular cuenta Google (auth requerida)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from src.config.dependencies import (
    get_current_user,
    get_google_login_use_case,
    get_link_google_account_use_case,
    get_reauthenticate_use_case,
    get_unlink_google_account_use_case,
)
from src.config.rate_limit import GOOGLE_LOGIN_LIMIT, get_client_identifier, limiter
from src.config.settings import settings
from src.modules.user.application.dto.oauth_dto import (
    GoogleLoginRequestDTO,
    GoogleLoginResponseDTO,
    LinkGoogleAccountRequestDTO,
    LinkGoogleAccountResponseDTO,
    ReauthenticateRequestDTO,
    ReauthenticateResponseDTO,
    UnlinkGoogleAccountResponseDTO,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.application.use_cases.google_login_use_case import (
    GoogleEmailNotVerifiedError,
    GoogleLoginUseCase,
)
from src.modules.user.application.use_cases.link_google_account_use_case import (
    GoogleLinkNeedsVerifiedEmailError,
    LinkGoogleAccountUseCase,
    ReauthenticationRequiredError,
)
from src.modules.user.application.use_cases.reauthenticate_use_case import (
    AccountWithoutPasswordError,
    ReauthenticateUseCase,
)
from src.modules.user.application.use_cases.unlink_google_account_use_case import (
    UnlinkGoogleAccountUseCase,
)
from src.modules.user.domain.errors.user_errors import InvalidCredentialsError
from src.modules.user.domain.exceptions import AccountDeactivatedException
from src.modules.user.infrastructure.api.v1.codigos_de_cuenta import (
    CURRENT_PASSWORD_INCORRECT,
    TEXTOS as TEXTOS_DE_CUENTA,
)
from src.modules.user.infrastructure.api.v1.cookie_de_dispositivo import (
    es_la_app_instalada,
    ids_validos_de_la_cookie,
    pon_la_cookie_de_dispositivo,
)
from src.modules.user.infrastructure.api.v1.cuenta_desactivada import (
    ACCOUNT_DEACTIVATED,
    TEXTO as TEXTO_DE_CUENTA_DESACTIVADA,
)
from src.modules.user.infrastructure.api.v1.limite_de_seguridad import (
    DEMASIADOS_CAMBIOS,
    cabe_otro_cambio,
    demasiados,
)
from src.modules.user.infrastructure.security import reautenticacion
from src.shared.infrastructure.api.respuesta_con_codigo import respuesta_con_codigo
from src.shared.infrastructure.http.http_context_validator import (
    cloudflare_client_country,
    get_trusted_client_ip,
    get_user_agent,
)
from src.shared.infrastructure.security.cookie_handler import (
    get_device_id_cookie_name,
    set_auth_cookie,
    set_csrf_cookie,
    set_refresh_token_cookie,
)

logger = logging.getLogger(__name__)
GOOGLE_EMAIL_NOT_VERIFIED = "GOOGLE_EMAIL_NOT_VERIFIED"
GOOGLE_LINK_NEEDS_VERIFIED_EMAIL = "GOOGLE_LINK_NEEDS_VERIFIED_EMAIL"
_TEXTOS_DE_GOOGLE = {
    GOOGLE_LINK_NEEDS_VERIFIED_EMAIL: "Verify your email before linking a Google account.",
    ACCOUNT_DEACTIVATED: TEXTO_DE_CUENTA_DESACTIVADA,
    GOOGLE_EMAIL_NOT_VERIFIED: (
        "Your Google account email is not verified. Verify it with Google, or sign up "
        "with your email and a password."
    ),
}

router = APIRouter()


@router.post(
    "/google",
    response_model=GoogleLoginResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Login/registro con Google",
    description="Autentica o registra un usuario usando Google OAuth. Público.",
    tags=["Authentication"],
    # Sus dos códigos, en el esquema (#750 punto 1)
    responses={
        400: {"description": "error_code GOOGLE_EMAIL_NOT_VERIFIED: Google no verificó el correo"},
        403: {"description": "error_code ACCOUNT_DEACTIVATED: cuenta desactivada"},
    },
)
@limiter.limit(GOOGLE_LOGIN_LIMIT, key_func=get_client_identifier)
async def google_login(
    request: Request,
    response: Response,
    login_data: GoogleLoginRequestDTO,
    use_case: GoogleLoginUseCase = Depends(get_google_login_use_case),
):
    """Login o registro con Google OAuth."""
    # Inyectar contexto HTTP
    login_data.ip_address = get_trusted_client_ip(
        request, settings.TRUSTED_PROXIES, settings.TRUST_CLOUDFLARE_HEADERS
    )
    login_data.user_agent = get_user_agent(request)

    device_id_cookie_name = get_device_id_cookie_name()
    login_data.device_id_from_cookie = ids_validos_de_la_cookie(
        request.cookies.get(device_id_cookie_name)
    )
    login_data.installed_app = es_la_app_instalada(request)
    login_data.country_code = cloudflare_client_country(request)

    # Sin 423: el bloqueo por fallos de contraseña no frena a Google (BE #732)
    try:
        login_response = await use_case.execute(login_data)
    except GoogleEmailNotVerifiedError:
        # Sin el correo verificado por Google, ni alta ni vínculo: con su código, para
        # que la app diga qué hacer en su idioma
        return respuesta_con_codigo(
            status.HTTP_400_BAD_REQUEST,
            _TEXTOS_DE_GOOGLE,
            GOOGLE_EMAIL_NOT_VERIFIED,
        )
    except AccountDeactivatedException:
        # El mismo texto que el login con contraseña (BE #744), con su código: la app
        # dice que está desactivada en vez de invitar a reintentar
        return respuesta_con_codigo(
            status.HTTP_403_FORBIDDEN, _TEXTOS_DE_GOOGLE, ACCOUNT_DEACTIVATED
        )
    except ValueError as e:
        error_msg = str(e)
        # Map known errors to safe client-facing messages
        safe_messages = {
            "Invalid or expired Google authorization code": "Invalid or expired Google authorization code",
            "Google did not return an access token": "Google authentication failed",
            "Failed to retrieve user information from Google": "Google authentication failed",
            "Google user info is missing required fields (sub, email)": "Google authentication failed",
        }
        detail = safe_messages.get(error_msg, "Google authentication failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from e

    # Set cookies (same as email login)
    set_auth_cookie(response, login_response.access_token)
    set_refresh_token_cookie(response, login_response.refresh_token)
    set_csrf_cookie(response, login_response.csrf_token)

    # Siempre: la renueva y deja este dispositivo delante (BE #737)
    pon_la_cookie_de_dispositivo(response, login_response.device_id, request)

    return login_response


# Los errores de la marca de reautenticación (BE #753), con su código para traducirlos
ACCOUNT_WITHOUT_PASSWORD = "ACCOUNT_WITHOUT_PASSWORD"  # nosec B105 - an error code, not a password
REAUTHENTICATION_REQUIRED = "REAUTHENTICATION_REQUIRED"
_TEXTOS_DE_LA_REAUTENTICACION = {
    CURRENT_PASSWORD_INCORRECT: TEXTOS_DE_CUENTA[CURRENT_PASSWORD_INCORRECT],
    ACCOUNT_WITHOUT_PASSWORD: "This account has no password.",
    REAUTHENTICATION_REQUIRED: "Enter your current password first.",
}


@router.post(
    "/reauthenticate",
    response_model=ReauthenticateResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Confirmar la contraseña actual",
    description=(
        "Con la contraseña actual, deja una marca de 5 minutos (cookie httpOnly) que pide "
        "/auth/google/link (BE #753). Los intentos cuentan en el límite de seguridad del "
        "usuario (429 TOO_MANY_SECURITY_CHANGES)."
    ),
    tags=["Authentication"],
    responses={
        401: {"description": "`error_code` CURRENT_PASSWORD_INCORRECT."},
        409: {"description": "`error_code` ACCOUNT_WITHOUT_PASSWORD: la cuenta es solo Google."},
        429: {"description": "`error_code` TOO_MANY_SECURITY_CHANGES."},
    },
)
async def reauthenticate(
    request: Request,
    datos: ReauthenticateRequestDTO,
    response: Response,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ReauthenticateUseCase = Depends(get_reauthenticate_use_case),
):
    """Comprueba la contraseña actual y deja la marca para vincular Google."""
    user_id = str(current_user.id)
    # Cada intento prueba una contraseña: el mismo límite que Seguridad
    if not cabe_otro_cambio(user_id):
        return demasiados(DEMASIADOS_CAMBIOS)
    try:
        # La red, siempre desde la petición: lo que mande el cliente no cuenta
        datos.ip_address = get_trusted_client_ip(
            request, settings.TRUSTED_PROXIES, settings.TRUST_CLOUDFLARE_HEADERS
        )
        datos.user_agent = get_user_agent(request)
        await use_case.execute(datos, user_id)
    except InvalidCredentialsError:
        return respuesta_con_codigo(
            status.HTTP_401_UNAUTHORIZED,
            _TEXTOS_DE_LA_REAUTENTICACION,
            CURRENT_PASSWORD_INCORRECT,
        )
    except AccountWithoutPasswordError:
        return respuesta_con_codigo(
            status.HTTP_409_CONFLICT, _TEXTOS_DE_LA_REAUTENTICACION, ACCOUNT_WITHOUT_PASSWORD
        )
    reautenticacion.pon_la_cookie(response, reautenticacion.emite(user_id))
    return ReauthenticateResponseDTO(expires_in=int(reautenticacion.DURACION.total_seconds()))


@router.post(
    "/google/link",
    response_model=LinkGoogleAccountResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Vincular cuenta Google",
    description="Vincula una cuenta de Google al usuario autenticado.",
    tags=["Authentication"],
    responses={
        400: {"description": "Código de Google inválido, o ya vinculada (a él o a otra cuenta)."},
        403: {
            "description": (
                "`error_code` REAUTHENTICATION_REQUIRED (falta la marca de "
                "/auth/reauthenticate en una cuenta con contraseña) o "
                "GOOGLE_LINK_NEEDS_VERIFIED_EMAIL (el correo de la cuenta sin verificar)."
            )
        },
    },
)
async def link_google_account(
    request: Request,
    response: Response,
    link_data: LinkGoogleAccountRequestDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: LinkGoogleAccountUseCase = Depends(get_link_google_account_use_case),
):
    """Vincula cuenta Google a usuario autenticado."""
    user_id = str(current_user.id)
    marca = request.cookies.get(reautenticacion.COOKIE)
    try:
        # El caso de uso lo deja en el log de seguridad, con la red (#750 punto 3).
        # Siempre desde la petición: lo que mande el cliente no cuenta
        link_data.ip_address = get_trusted_client_ip(
            request, settings.TRUSTED_PROXIES, settings.TRUST_CLOUDFLARE_HEADERS
        )
        link_data.user_agent = get_user_agent(request)
        # Gastada al empezar, de una vez: una sola vez, aunque el navegador no borrara
        # la cookie, y sin que dos vínculos a la vez pasen los dos
        reautenticado = reautenticacion.gasta_si_vale(marca, user_id)
        vinculado = await use_case.execute(link_data, user_id, reautenticado=reautenticado)
        reautenticacion.borra_la_cookie(response)
        return vinculado
    except ReauthenticationRequiredError:
        return respuesta_con_codigo(
            status.HTTP_403_FORBIDDEN, _TEXTOS_DE_LA_REAUTENTICACION, REAUTHENTICATION_REQUIRED
        )
    except GoogleLinkNeedsVerifiedEmailError:
        # Sin el correo verificado, sin Google: con su código, para que la app diga
        # qué hacer en su idioma
        return respuesta_con_codigo(
            status.HTTP_403_FORBIDDEN, _TEXTOS_DE_GOOGLE, GOOGLE_LINK_NEEDS_VERIFIED_EMAIL
        )
    except ValueError as e:
        error_msg = str(e)
        safe_messages = {
            "This Google account is already linked to another user": error_msg,
            "You already have a Google account linked": error_msg,
            "Invalid or expired Google authorization code": "Invalid or expired Google authorization code",
        }
        detail = safe_messages.get(error_msg, "Failed to link Google account")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from e


@router.delete(
    "/google/unlink",
    response_model=UnlinkGoogleAccountResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Desvincular cuenta Google",
    description="Desvincula la cuenta de Google del usuario autenticado.",
    tags=["Authentication"],
    responses={
        400: {
            "description": "No hay Google vinculado, o es el único método para entrar "
            "(antes hay que poner una contraseña), u otro fallo."
        },
        403: {
            "description": "`error_code` TERMS_NOT_ACCEPTED: faltan los Términos vigentes "
            "(o falla el CSRF)."
        },
    },
)
async def unlink_google_account(
    request: Request,  # noqa: ARG001
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: UnlinkGoogleAccountUseCase = Depends(get_unlink_google_account_use_case),
):
    """Desvincula cuenta Google de usuario autenticado."""
    try:
        return await use_case.execute(str(current_user.id))
    except ValueError as e:
        error_msg = str(e)
        safe_messages = {
            "No Google account linked to this user": error_msg,
            "Cannot unlink Google account: it is your only authentication method. Set a password first.": error_msg,
        }
        detail = safe_messages.get(error_msg, "Failed to unlink Google account")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from e
