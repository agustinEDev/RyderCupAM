"""
Validate Reset Token Use Case

Caso de uso OPCIONAL para validar un token de reseteo antes de mostrar el formulario.
Mejora la UX al detectar tokens expirados/inválidos antes de que el usuario complete el formulario.

Este endpoint es público y NO requiere autenticación.
"""

from src.modules.user.application.dto.user_dto import (
    ValidateResetTokenRequestDTO,
    ValidateResetTokenResponseDTO,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)


class ValidateResetTokenUseCase:
    """
    Caso de uso para validar un token de reseteo ANTES de mostrar el formulario.

    Responsabilidades:
    - Buscar usuario por token de reseteo
    - Validar token (coincidencia + expiración)
    - Retornar si el token es válido o no

    UX Benefits:
    - Detecta token expirado ANTES de que el usuario escriba nueva contraseña
    - Redirige a /forgot-password si el token es inválido
    - Muestra formulario solo si el token es válido

    Security:
    - NO requiere autenticación (endpoint público)
    - NO revela información sobre el usuario (solo retorna valid: bool)
    - Rate limiting: 10 intentos/hora por IP (configurado en SlowAPI)
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        """
        Inicializa el caso de uso.

        Args:
            uow: Unit of Work para acceso a repositorio de usuarios
        """
        self._uow = uow

    async def execute(self, request: ValidateResetTokenRequestDTO) -> ValidateResetTokenResponseDTO:
        """
        Ejecuta el caso de uso de validación de token.

        Args:
            request: DTO con el token a validar

        Returns:
            ValidateResetTokenResponseDTO con valid=True/False y mensaje

        Example:
            >>> request = ValidateResetTokenRequestDTO(token="abc123...")
            >>> response = await use_case.execute(request)
            >>> if response.valid:
            ...     # Mostrar formulario de nueva contraseña
            >>> else:
            ...     # Redirigir a /forgot-password con mensaje de error
        """
        # Buscar usuario por token de reseteo
        user = await self._uow.users.find_by_password_reset_token(request.token)

        # CASO 1: Token no encontrado
        if not user:
            return ValidateResetTokenResponseDTO(
                valid=False,
                message="Token de reseteo inválido o expirado. Solicita un nuevo enlace.",
            )

        # CASO 2: Token encontrado → Validar expiración
        try:
            is_valid = user.can_reset_password(request.token)
        except ValueError:
            # No hay token de reseteo activo (caso edge)
            return ValidateResetTokenResponseDTO(
                valid=False,
                message="Token de reseteo inválido o expirado. Solicita un nuevo enlace.",
            )

        if is_valid:
            return ValidateResetTokenResponseDTO(
                valid=True, message="Token válido. Puedes proceder con el reseteo de tu contraseña."
            )
        # Token expirado (> 24 horas)
        return ValidateResetTokenResponseDTO(
            valid=False,
            message="Token de reseteo expirado. Los tokens son válidos por 24 horas. Solicita un nuevo enlace.",
        )
