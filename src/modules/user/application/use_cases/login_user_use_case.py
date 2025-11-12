"""
Login User Use Case

Caso de uso para autenticar un usuario y generar un token JWT.
"""

from typing import Optional

from src.modules.user.application.dto.user_dto import (
    LoginRequestDTO,
    LoginResponseDTO,
    UserResponseDTO,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.email import Email
from src.shared.infrastructure.security.jwt_handler import create_access_token


class LoginUserUseCase:
    """
    Caso de uso para login de usuario.

    Responsabilidades:
    - Buscar usuario por email
    - Verificar contraseña
    - Generar token JWT
    - Devolver token y datos de usuario
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        """
        Inicializa el caso de uso.

        Args:
            uow: Unit of Work para acceso a repositorio de usuarios
        """
        self._uow = uow

    async def execute(self, request: LoginRequestDTO) -> Optional[LoginResponseDTO]:
        """
        Ejecuta el caso de uso de login.

        Args:
            request: DTO con email y password

        Returns:
            LoginResponseDTO con token y datos de usuario si credenciales válidas
            None si el usuario no existe o las credenciales son inválidas

        Example:
            >>> request = LoginRequestDTO(email="user@example.com", password="secret123")
            >>> response = await use_case.execute(request)
            >>> if response:
            >>>     print(response.access_token)
        """
        # Buscar usuario por email
        email = Email(request.email)
        user = await self._uow.users.find_by_email(email)

        if not user:
            return None

        # Verificar contraseña
        if not user.verify_password(request.password):
            return None

        # Registrar evento de login exitoso (Clean Architecture)
        from datetime import datetime
        login_time = datetime.now()
        user.record_login(
            logged_in_at=login_time,
            # ip_address y user_agent se pueden agregar cuando el controlador los pase
            # session_id se podría generar aquí si fuera necesario
        )

        # Persistir el evento usando Unit of Work
        async with self._uow:
            await self._uow.users.save(user)

        # Generar token JWT con user_id en el subject
        access_token = create_access_token(
            data={"sub": str(user.id.value)}
        )

        # Crear respuesta con token y datos de usuario
        user_dto = UserResponseDTO.model_validate(user)

        return LoginResponseDTO(
            access_token=access_token,
            token_type="bearer",
            user=user_dto,
            email_verification_required=not user.is_email_verified()
        )
