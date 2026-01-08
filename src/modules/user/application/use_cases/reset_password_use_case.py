"""
Reset Password Use Case

Caso de uso para completar el reseteo de contraseña (después de hacer clic en el enlace del email).
Este endpoint es público y NO requiere autenticación.

Security Features:
- Token de un solo uso (se invalida después del primer uso exitoso)
- Validación estricta de expiración (24 horas)
- Password policy enforcement (OWASP ASVS V2.1: 12+ chars, complejidad completa)
- Invalidación automática de TODAS las sesiones activas (refresh tokens revocados)
- Security logging completo

Post-Conditions:
- Token invalidado (password_reset_token = None)
- Password cambiado (hasheado con bcrypt 12 rounds)
- Todas las sesiones activas cerradas (refresh tokens revocados)
- Email de confirmación enviado al usuario
"""

from src.modules.user.application.dto.user_dto import (
    ResetPasswordRequestDTO,
    ResetPasswordResponseDTO,
)
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.shared.infrastructure.logging.security_logger import get_security_logger


class ResetPasswordUseCase:
    """
    Caso de uso para completar el reseteo de contraseña.

    Responsabilidades:
    - Buscar usuario por token de reseteo
    - Validar token (coincidencia + expiración)
    - Cambiar contraseña (aplicando política de seguridad)
    - Invalidar token (uso único)
    - Revocar TODAS las sesiones activas del usuario
    - Enviar email de confirmación
    - Registrar evento de dominio para auditoría

    Security (OWASP A01, A02, A07):
    - Usuario no autenticado (endpoint público)
    - Token de un solo uso (se invalida después del primer uso)
    - Validación estricta de expiración (< 24 horas)
    - Password policy: 12+ chars, complejidad completa, no en blacklist
    - Logout forzado en todos los dispositivos
    """

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        email_service: IEmailService
    ):
        """
        Inicializa el caso de uso.

        Args:
            uow: Unit of Work para acceso a repositorios (users + refresh_tokens)
            email_service: Servicio para envío de emails (Mailgun)
        """
        self._uow = uow
        self._email_service = email_service

    async def execute(
        self,
        request: ResetPasswordRequestDTO
    ) -> ResetPasswordResponseDTO:
        """
        Ejecuta el caso de uso de reseteo de contraseña.

        Args:
            request: DTO con token, nueva contraseña y contexto de seguridad

        Returns:
            ResetPasswordResponseDTO con mensaje de confirmación

        Raises:
            ValueError: Si el token es inválido, expirado, o la contraseña no cumple la política

        Security Flow:
            1. Busca usuario por token de reseteo
            2. Valida token (can_reset_password)
            3. Cambia contraseña (Password VO aplica política)
            4. Invalida token (uso único)
            5. Revoca TODOS los refresh tokens del usuario
            6. Envía email de confirmación
            7. Registra evento de dominio (PasswordResetCompletedEvent)

        Example:
            >>> request = ResetPasswordRequestDTO(
            ...     token="abc123...",
            ...     new_password="NewSecure123!",
            ...     ip_address="192.168.1.1"
            ... )
            >>> response = await use_case.execute(request)
            >>> print(response.message)
            "Contraseña reseteada exitosamente. Todas tus sesiones activas han sido cerradas..."
        """
        # Obtener security logger
        security_logger = get_security_logger()

        # Valores por defecto para security logging
        ip_address = request.ip_address or "unknown"
        user_agent = request.user_agent or "unknown"

        # Buscar usuario por token de reseteo
        user = await self._uow.users.find_by_password_reset_token(request.token)

        if not user:
            # Security Logging: Token inválido (usuario no encontrado)
            security_logger.log_password_reset_completed(
                user_id=None,
                email="unknown",
                success=False,
                failure_reason="Invalid or expired token",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise ValueError("Token de reseteo inválido o expirado")

        # Validar token y expiración usando lógica de dominio
        try:
            # reset_password() internamente llama a can_reset_password()
            # Si el token es inválido/expirado, lanza ValueError
            user.reset_password(
                token=request.token,
                new_password=request.new_password,
                ip_address=ip_address,
                user_agent=user_agent
            )
        except ValueError as e:
            # Security Logging: Reseteo fallido (token inválido, expirado o password inválido)
            security_logger.log_password_reset_completed(
                user_id=str(user.id.value),
                email=str(user.email.value),
                success=False,
                failure_reason=str(e),
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise  # Re-lanzar la excepción para que el API layer la maneje

        # Guardar usuario con nueva contraseña, historial y revocar todos los refresh tokens
        # Todas las operaciones se ejecutan en la MISMA transacción para garantizar atomicidad
        async with self._uow:
            from src.modules.user.domain.entities.password_history import PasswordHistory

            # Guardar el nuevo hash en el historial de contraseñas
            total_history_count = await self._uow.password_history.count_by_user(user.id) + 1
            password_history = PasswordHistory.create(
                user_id=user.id,
                password_hash=user.password.hashed_value,
                total_history_count=total_history_count
            )
            await self._uow.password_history.save(password_history)

            # Revocar TODOS los refresh tokens del usuario (logout forzado)
            # Esto asegura que todas las sesiones activas se cierren
            await self._uow.refresh_tokens.revoke_all_for_user(user.id)

            # Guardar usuario con nueva contraseña y token invalidado
            await self._uow.users.save(user)
            # Commit automático al salir del contexto (todas las operaciones atomicas)

        # Enviar email de confirmación
        await self._email_service.send_password_changed_notification(
            to_email=str(user.email.value),
            user_name=user.get_full_name()
        )

        # Security Logging: Reseteo exitoso
        security_logger.log_password_reset_completed(
            user_id=str(user.id.value),
            email=str(user.email.value),
            success=True,
            failure_reason=None,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Retornar mensaje de confirmación
        return ResetPasswordResponseDTO(
            message="Contraseña reseteada exitosamente. Todas tus sesiones activas han sido cerradas por seguridad.",
            email=str(user.email.value)
        )
