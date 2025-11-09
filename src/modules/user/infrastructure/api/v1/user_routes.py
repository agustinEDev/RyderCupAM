from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from src.config.dependencies import get_find_user_use_case, get_current_user
from src.modules.user.application.dto.user_dto import FindUserRequestDTO, FindUserResponseDTO, UserResponseDTO
from src.modules.user.application.use_cases.find_user_use_case import FindUserUseCase
from src.modules.user.domain.errors.user_errors import UserNotFoundError

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