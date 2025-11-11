from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from src.config.dependencies import (
    get_find_user_use_case,
    get_update_profile_use_case,
    get_update_security_use_case,
    get_current_user
)
from src.modules.user.application.dto.user_dto import (
    FindUserRequestDTO,
    FindUserResponseDTO,
    UserResponseDTO,
    UpdateProfileRequestDTO,
    UpdateProfileResponseDTO,
    UpdateSecurityRequestDTO,
    UpdateSecurityResponseDTO
)
from src.modules.user.application.use_cases.find_user_use_case import FindUserUseCase
from src.modules.user.application.use_cases.update_profile_use_case import UpdateProfileUseCase
from src.modules.user.application.use_cases.update_security_use_case import UpdateSecurityUseCase
from src.modules.user.domain.errors.user_errors import (
    UserNotFoundError,
    InvalidCredentialsError,
    DuplicateEmailError
)

router = APIRouter()

@router.get(
    "/search",
    response_model=FindUserResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Buscar usuario",
    description="Busca un usuario por email o nombre completo y devuelve su ID y datos básicos.",
    tags=["Users"],
)
async def find_user(
    email: Optional[str] = Query(None, description="Email del usuario a buscar"),
    full_name: Optional[str] = Query(None, description="Nombre completo del usuario a buscar"),
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
        user_response = await use_case.execute(request)
        return user_response
        
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch(
    "/profile",
    response_model=UpdateProfileResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar perfil del usuario",
    description="Actualiza la información personal del usuario autenticado (nombre y/o apellidos).",
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
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch(
    "/security",
    response_model=UpdateSecurityResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar datos de seguridad",
    description="Actualiza el email y/o password del usuario autenticado. Requiere contraseña actual.",
    tags=["Users"],
)
async def update_security(
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
        )
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except DuplicateEmailError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )