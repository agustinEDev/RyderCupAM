
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from src.config.dependencies import (
    get_current_user,
    get_find_user_use_case,
    get_update_profile_use_case,
    get_update_security_use_case,
)
from src.modules.user.application.dto.user_dto import (
    FindUserRequestDTO,
    FindUserResponseDTO,
    UpdateProfileRequestDTO,
    UpdateProfileResponseDTO,
    UpdateSecurityRequestDTO,
    UpdateSecurityResponseDTO,
    UserResponseDTO,
)
from src.modules.user.application.use_cases.find_user_use_case import FindUserUseCase
from src.modules.user.application.use_cases.update_profile_use_case import UpdateProfileUseCase
from src.modules.user.application.use_cases.update_security_use_case import UpdateSecurityUseCase
from src.modules.user.domain.errors.user_errors import (
    DuplicateEmailError,
    InvalidCredentialsError,
    UserNotFoundError,
)

router = APIRouter()


# ============================================================================
# HELPER FUNCTIONS - Security Context Extraction
# ============================================================================

def get_client_ip(request: Request) -> str:
    """
    Extrae la dirección IP del cliente del request.

    Args:
        request: Request de FastAPI

    Returns:
        Dirección IP del cliente o "unknown"
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def get_user_agent(request: Request) -> str:
    """
    Extrae el User-Agent del cliente del request.

    Args:
        request: Request de FastAPI

    Returns:
        User-Agent del navegador o "unknown"
    """
    user_agent = request.headers.get("User-Agent")
    return user_agent if user_agent else "unknown"

@router.get(
    "/search",
    response_model=FindUserResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Buscar usuario",
    description="Busca un usuario por email o nombre completo y devuelve su ID y datos básicos.",
    tags=["Users"],
)
async def find_user(
    email: str | None = Query(None, description="Email del usuario a buscar"),
    full_name: str | None = Query(None, description="Nombre completo del usuario a buscar"),
    use_case: FindUserUseCase = Depends(get_find_user_use_case),
    current_user: UserResponseDTO = Depends(get_current_user)
):
    """
    Endpoint para buscar un usuario por email o nombre completo.

    Permite encontrar usuarios utilizando:
    - Email: Búsqueda exacta por dirección de correo electrónico
    - Nombre completo: Búsqueda por nombre y apellidos

    Al menos uno de los dos parámetros debe ser proporcionado.
    """
    try:
        # Validar que al menos un parámetro sea proporcionado
        if not email and not full_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe proporcionar al menos 'email' o 'full_name' para la búsqueda."
            )

        # Crear el DTO de request
        request = FindUserRequestDTO(
            email=email,
            full_name=full_name
        )

        # Ejecutar el caso de uso
        return await use_case.execute(request)
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.patch(
    "/profile",
    response_model=UpdateProfileResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar perfil del usuario",
    description="Actualiza la información personal del usuario autenticado (nombre, apellidos y/o país).",
    tags=["Users"],
)
async def update_profile(
    request: UpdateProfileRequestDTO,
    use_case: UpdateProfileUseCase = Depends(get_update_profile_use_case),
    current_user: UserResponseDTO = Depends(get_current_user)
):
    """
    Endpoint para actualizar información personal del usuario.

    Permite al usuario autenticado actualizar:
    - Nombre (first_name)
    - Apellidos (last_name)
    - Código de país (country_code) - ISO 3166-1 alpha-2

    Al menos uno de los campos debe ser proporcionado.
    NO requiere contraseña actual (solo autenticación JWT).
    """
    try:
        # Ejecutar el caso de uso con el user_id del token JWT
        user_id = str(current_user.id)
        response = await use_case.execute(user_id, request)
        return response

    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.patch(
    "/security",
    response_model=UpdateSecurityResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar datos de seguridad",
    description="Actualiza el email y/o password del usuario autenticado. Requiere contraseña actual.",
    tags=["Users"],
)
async def update_security(
    http_request: Request,
    request: UpdateSecurityRequestDTO,
    use_case: UpdateSecurityUseCase = Depends(get_update_security_use_case),
    current_user: UserResponseDTO = Depends(get_current_user)
):
    """
    Endpoint para actualizar datos de seguridad del usuario.

    Permite al usuario autenticado actualizar:
    - Email (new_email)
    - Password (new_password + confirm_password)

    REQUIERE:
    - current_password: Contraseña actual para verificación
    - Al menos uno de: new_email o new_password

    Si se cambia password, se debe proporcionar confirm_password.

    Security Logging (v1.8.0):
    - Registra cambios de contraseña (severity HIGH)
    - Registra cambios de email (severity HIGH)
    - Revoca refresh tokens si cambia contraseña
    """
    try:
        # Security Logging (v1.8.0): Extraer contexto HTTP para audit trail
        request.ip_address = get_client_ip(http_request)
        request.user_agent = get_user_agent(http_request)

        # Ejecutar el caso de uso con el user_id del token JWT
        user_id = str(current_user.id)
        response = await use_case.execute(user_id, request)
        return response

    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
    except DuplicateEmailError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
