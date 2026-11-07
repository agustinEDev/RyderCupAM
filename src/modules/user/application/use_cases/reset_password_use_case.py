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

import logging

from src.modules.user.application.dto.user_dto import (
    ResetPasswordRequestDTO,
    ResetPasswordResponseDTO,
)
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.ports.security_audit_interface import ISecurityAuditLogger
from src.modules.user.application.services.cierra_lo_que_no_se_probo import (
    avisa_de_la_toma,
    cierra_lo_que_no_se_probo,
)
from src.modules.user.application.services.registra_sin_romper import registra_sin_romper
from src.modules.user.domain.entities.password_history import PasswordHistory
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.exceptions.invalid_reset_token_error import InvalidResetTokenError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.password import Password
from src.shared.application.concurrencia.bcrypt_executor import run_bcrypt

logger = logging.getLogger(__name__)


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
        email_service: IEmailService,
        *,
        security_audit: ISecurityAuditLogger,
    ):
        """
        Inicializa el caso de uso.

        Args:
            uow: Unit of Work para acceso a repositorios (users + refresh_tokens)
            email_service: Servicio para envío de emails (Mailgun)
        """
        self._security_audit = security_audit
        self._uow = uow
        self._email_service = email_service

    def _apunta_la_toma(
        self,
        user: User,
        cerrado: tuple[int, int, int],
        ip_address: str,
        user_agent: str,
    ) -> None:
        """La toma, al log de seguridad, ya guardada: si el log falla, vale igual."""
        registra_sin_romper(
            "Account claim",
            lambda: self._security_audit.log_unverified_account_claimed(
                user_id=str(user.id.value),
                devices_revoked=cerrado[0],
                tokens_revoked=cerrado[1],
                google_unlinked=cerrado[2],
                via="password_reset",
                ip_address=ip_address,
                user_agent=user_agent,
            ),
        )

    async def execute(self, request: ResetPasswordRequestDTO) -> ResetPasswordResponseDTO:
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
        security_logger = self._security_audit

        # Valores por defecto para security logging
        ip_address = request.ip_address or "unknown"
        user_agent = request.user_agent or "unknown"

        # Buscar usuario por token de reseteo, en su propia transacción: cerrada antes
        # del bcrypt (BE #283)
        async with self._uow:
            user = await self._uow.users.find_by_password_reset_token(request.token)

        if not user:
            # Security Logging: Token inválido (usuario no encontrado)
            registra_sin_romper(
                "Reset password",
                lambda: security_logger.log_password_reset_completed(
                    user_id=None,
                    email="unknown",
                    success=False,
                    failure_reason="Invalid or expired token",
                    ip_address=ip_address,
                    user_agent=user_agent,
                ),
            )
            raise InvalidResetTokenError()

        # Lo barato antes del bcrypt y sin transacción (BE #283): un enlace que no vale
        # responde sin calcular nada; luego la política y el hash de la nueva
        try:
            if not user.can_reset_password(request.token):
                raise InvalidResetTokenError()
            nueva = await run_bcrypt(Password.from_plain_text, request.new_password)
        except ValueError as e:
            fallo = str(e)
            registra_sin_romper(
                "Reset password",
                lambda: security_logger.log_password_reset_completed(
                    user_id=str(user.id.value),
                    email=str(user.email.value),
                    success=False,
                    failure_reason=fallo,
                    ip_address=ip_address,
                    user_agent=user_agent,
                ),
            )
            raise

        # Todo con la fila bloqueada (revisión de #749): una toma por Google a la vez
        # borra el token, y entonces el enlace ya no vale; sin el bloqueo, el
        # restablecimiento seguía con la lectura de antes y deshacía la toma
        async with self._uow:
            bloqueada = await self._uow.users.find_by_id_for_update(user.id)
            # El token se vuelve a validar sobre la fila bloqueada, en reset_password
            if bloqueada is None:
                registra_sin_romper(
                    "Reset password",
                    lambda: security_logger.log_password_reset_completed(
                        user_id=str(user.id.value),
                        email=str(user.email.value),
                        success=False,
                        failure_reason="Account deleted during reset",
                        ip_address=ip_address,
                        user_agent=user_agent,
                    ),
                )
                raise InvalidResetTokenError()
            user = bloqueada

            # Sin verificar: quien usa el enlace de su buzón demuestra que el correo
            # es suyo, y se queda la cuenta (#749, pre-captura)
            sin_verificar = not user.email_verified

            # Validar token y expiración usando lógica de dominio
            try:
                # reset_password() internamente llama a can_reset_password()
                # Si el token es inválido/expirado, lanza ValueError
                # El token, otra vez sobre la fila bloqueada (otro pudo gastarlo
                # entretanto); la contraseña ya va calculada, sin bcrypt aquí
                user.reset_password(
                    token=request.token,
                    new_password=nueva,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
            except ValueError as e:
                # Security Logging: Reseteo fallido (token inválido, expirado o password inválido)
                fallo = str(e)
                registra_sin_romper(
                    "Reset password",
                    lambda: security_logger.log_password_reset_completed(
                        user_id=str(user.id.value),
                        email=str(user.email.value),
                        success=False,
                        failure_reason=fallo,
                        ip_address=ip_address,
                        user_agent=user_agent,
                    ),
                )
                raise  # Re-lanzar la excepción para que el API layer la maneje

            # Guardar el nuevo hash en el historial de contraseñas, revocar las
            # sesiones y guardar el usuario, en la MISMA transacción
            total_history_count = await self._uow.password_history.count_by_user(user.id) + 1
            password_history = PasswordHistory.create(
                user_id=user.id,
                password_hash=user.password.hashed_value,
                total_history_count=total_history_count,
            )
            await self._uow.password_history.save(password_history)

            if sin_verificar:
                # Lo que dejó quien la creó o le cambió el correo, fuera: dispositivos,
                # sesiones y su Google
                user.confirm_email_ownership()
                cerrado = await cierra_lo_que_no_se_probo(self._uow, user.id)
            else:
                # Sesiones, dispositivos Y su Google: un acceso robado no sigue valiendo
                # hasta que caduque (OWASP A07; tabla de caminos de #749), ni un Google
                # que vinculó quien entró en la cuenta (BE #753, Agustín). Quien lo tenga
                # de verdad lo vuelve a vincular. No es una toma: ni su log ni su aviso
                await cierra_lo_que_no_se_probo(self._uow, user.id)
                cerrado = None

            # Y un cambio de correo pendiente, fuera: quizá lo pidió quien entró en
            # la cuenta (revisión de #749)
            user.cancel_email_change()

            # Guardar usuario con nueva contraseña y token invalidado
            await self._uow.users.save(user)
            # Commit automático al salir del contexto (todas las operaciones atomicas)

        if cerrado is not None:
            self._apunta_la_toma(user, cerrado, ip_address, user_agent)

        # Enviar email de confirmación. Si se la quedó, el de cuenta asegurada, que ya
        # dice cuál es la contraseña (BE #753)
        if cerrado is not None:
            await avisa_de_la_toma(self._email_service, user, "reset")
        else:
            await self._email_service.send_password_changed_notification(
                to_email=str(user.email.value), user_name=user.get_full_name()
            )

        # Security Logging: Reseteo exitoso
        registra_sin_romper(
            "Reset password",
            lambda: security_logger.log_password_reset_completed(
                user_id=str(user.id.value),
                email=str(user.email.value),
                success=True,
                failure_reason=None,
                ip_address=ip_address,
                user_agent=user_agent,
            ),
        )

        # Retornar mensaje de confirmación
        return ResetPasswordResponseDTO(
            message="Contraseña reseteada exitosamente. Todas tus sesiones activas han sido cerradas por seguridad.",
            email=str(user.email.value),
        )
