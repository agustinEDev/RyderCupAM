from fastapi import APIRouter, Depends, HTTPException, status
from src.config.dependencies import get_register_user_use_case
from src.modules.user.application.dto.user_dto import RegisterUserRequestDTO, UserResponseDTO
from src.modules.user.application.use_cases.register_user import RegisterUserUseCase
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