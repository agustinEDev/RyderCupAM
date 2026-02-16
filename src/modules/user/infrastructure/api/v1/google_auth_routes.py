"""
Google Auth Routes - Infrastructure Layer

Endpoints para autenticación con Google OAuth:
- POST /google: Login/registro con Google (público)
- POST /google/link: Vincular cuenta Google (auth requerida)
- DELETE /google/unlink: Desvincular cuenta Google (auth requerida)
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from src.config.dependencies import (
    get_current_user,
    get_google_login_use_case,
    get_link_google_account_use_case,
    get_unlink_google_account_use_case,
)
from src.config.rate_limit import limiter
from src.config.settings import settings
from src.modules.user.application.dto.oauth_dto import (
    GoogleLoginRequestDTO,
    GoogleLoginResponseDTO,
    LinkGoogleAccountRequestDTO,
    LinkGoogleAccountResponseDTO,
    UnlinkGoogleAccountResponseDTO,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.application.use_cases.google_login_use_case import (
    GoogleLoginUseCase,
)
from src.modules.user.application.use_cases.link_google_account_use_case import (
    LinkGoogleAccountUseCase,
)
from src.modules.user.application.use_cases.unlink_google_account_use_case import (
    UnlinkGoogleAccountUseCase,
)
from src.modules.user.domain.exceptions import AccountLockedException
from src.shared.infrastructure.http.http_context_validator import (
    get_trusted_client_ip,
    get_user_agent,
)
from src.shared.infrastructure.security.cookie_handler import (
    get_device_id_cookie_name,
    set_auth_cookie,
    set_csrf_cookie,
    set_device_id_cookie,
    set_refresh_token_cookie,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _validate_device_id_cookie(cookie_value: str | None) -> str | None:
    """Valida que el device_id cookie sea un UUID válido."""
    if not cookie_value:
        return None
    try:
        validated = uuid.UUID(cookie_value)
        return str(validated)
    except (ValueError, AttributeError):
        return None


@router.post(
    "/google",
    response_model=GoogleLoginResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Login/registro con Google",
    description="Autentica o registra un usuario usando Google OAuth. Público.",
    tags=["Authentication"],
)
@limiter.limit("5/minute")
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
    login_data.device_id_from_cookie = _validate_device_id_cookie(
        request.cookies.get(device_id_cookie_name)
    )

    try:
        login_response = await use_case.execute(login_data)
    except AccountLockedException as e:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account temporarily locked. Please try again later.",
        ) from e
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

    if login_response.should_set_device_cookie and login_response.device_id:
        set_device_id_cookie(response, login_response.device_id)

    return login_response


@router.post(
    "/google/link",
    response_model=LinkGoogleAccountResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Vincular cuenta Google",
    description="Vincula una cuenta de Google al usuario autenticado.",
    tags=["Authentication"],
)
async def link_google_account(
    request: Request,  # noqa: ARG001
    link_data: LinkGoogleAccountRequestDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: LinkGoogleAccountUseCase = Depends(get_link_google_account_use_case),
):
    """Vincula cuenta Google a usuario autenticado."""
    try:
        return await use_case.execute(link_data, str(current_user.id))
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
