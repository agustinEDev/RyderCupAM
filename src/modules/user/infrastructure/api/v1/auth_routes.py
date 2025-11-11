from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from src.config.dependencies import (
    get_register_user_use_case,
    get_login_user_use_case,
    get_current_user,
    get_logout_user_use_case,
)
from src.modules.user.application.dto.user_dto import (
    RegisterUserRequestDTO,
    UserResponseDTO,
    LoginRequestDTO,
    LoginResponseDTO,
    LogoutRequestDTO,
    LogoutResponseDTO,
)
from src.modules.user.application.use_cases.register_user_use_case import RegisterUserUseCase
from src.modules.user.application.use_cases.login_user_use_case import LoginUserUseCase
from src.modules.user.application.use_cases.logout_user_use_case import LogoutUserUseCase
from src.modules.user.domain.errors.user_errors import UserAlreadyExistsError

router = APIRouter()

@router.post(
    "/register",
    response_model=UserResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo usuario",
    description="Crea un nuevo usuario en el sistema y devuelve su información.",
    tags=["Authentication"],
)
async def register_user(
    request: RegisterUserRequestDTO,
    use_case: RegisterUserUseCase = Depends(get_register_user_use_case),
):
    """
    Endpoint para registrar un nuevo usuario.
    """
    try:
        user_response = await use_case.execute(request)
        return user_response
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.post(
    "/login",
    response_model=LoginResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Login de usuario",
    description="Autentica un usuario y devuelve un token JWT de acceso.",
    tags=["Authentication"],
)
async def login_user(
    request: LoginRequestDTO,
    use_case: LoginUserUseCase = Depends(get_login_user_use_case),
):
    """
    Endpoint para login de usuario.

    Autentica las credenciales y retorna un token JWT que debe ser usado
    en requests subsecuentes en el header Authorization: Bearer <token>
    """
    response = await use_case.execute(request)

    if not response:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return response


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


# Esquema de seguridad HTTP Bearer para obtener el token
security = HTTPBearer()

@router.post(
    "/logout",
    response_model=LogoutResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Logout de usuario",
    description="Cierra la sesión del usuario autenticado. En Fase 1, el token sigue técnicamente válido hasta su expiración.",
    tags=["Authentication"],
)
async def logout_user(
    request: LogoutRequestDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    use_case: LogoutUserUseCase = Depends(get_logout_user_use_case),
):
    """
    Endpoint para logout de usuario.

    Requiere autenticación mediante token JWT en el header:
    Authorization: Bearer <token>

    Nota sobre Fase 1 vs Fase 2:
    - Fase 1 (Actual): El token sigue siendo técnicamente válido hasta su expiración.
      El logout es principalmente del lado cliente (borrar el token del storage).
    - Fase 2 (Futura): El token se agregará a una blacklist para invalidación inmediata.

    Args:
        request: DTO de logout (preparado para extensiones futuras)
        current_user: Usuario autenticado obtenido del token
        credentials: Credenciales con el token JWT
        use_case: Caso de uso de logout

    Returns:
        LogoutResponseDTO con confirmación y timestamp
    """
    user_id = str(current_user.id)
    token = credentials.credentials

    response = await use_case.execute(request, user_id, token)

    if not response:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
        )

    return response