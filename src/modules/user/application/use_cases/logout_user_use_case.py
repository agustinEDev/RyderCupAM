"""
Logout User Use Case

Caso de uso para cerrar sesión de un usuario.
Cierra la sesión de ESTE dispositivo, no las demás (BE #376).
Security Logging (v1.8.0): Registra logout con cantidad de tokens revocados.
"""

from datetime import UTC, datetime

from src.modules.user.application.dto.user_dto import (
    LogoutRequestDTO,
    LogoutResponseDTO,
)
from src.modules.user.application.ports.security_audit_interface import ISecurityAuditLogger
from src.modules.user.application.services.registra_sin_romper import registra_sin_romper
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId


class LogoutUserUseCase:
    """
    Caso de uso para logout de usuario.

    Responsabilidades:
    - Validar que el usuario existe (del token JWT)
    - Revocar los refresh tokens de ESTE dispositivo (BE #376)
    - Registrar el evento de logout para auditoría
    - Retornar confirmación

    Solo este dispositivo (BE #376):
    - Revoca el refresh token con el que se sale y los demás de su dispositivo
    - Los demás dispositivos siguen dentro: salir en el ordenador de casa no
      puede echar a nadie del móvil en el campo, sin cobertura para volver a
      entrar. «Salir de todos» es revocar dispositivos desde su gestión
    - El access token sigue técnicamente válido hasta expiración (15 min)
    - Frontend debe eliminar cookies httpOnly de access y refresh tokens
    - OWASP A01: Previene reuso de refresh tokens después de logout
    """

    def __init__(self, uow: UserUnitOfWorkInterface, *, security_audit: ISecurityAuditLogger):
        """
        Inicializa el caso de uso.

        Args:
            uow: Unit of Work para acceso a repositorios (users + refresh_tokens)
        """
        self._security_audit = security_audit
        self._uow = uow

    async def execute(
        self, request: LogoutRequestDTO, user_id: str, token: str | None = None
    ) -> LogoutResponseDTO | None:
        """
        Ejecuta el caso de uso de logout.

        Args:
            request: DTO de logout con contexto de seguridad (IP, User-Agent)
            user_id: ID del usuario obtenido del token JWT
            token: Token JWT original (actualmente no usado)

        Returns:
            LogoutResponseDTO con confirmación y timestamp
            None si el usuario no existe

        Security Logging (v1.8.0):
            - Registra logout con cantidad de refresh tokens revocados
            - Registra revocación de tokens por logout
            - Severity LOW (acción normal)

        Example:
            >>> request = LogoutRequestDTO(
            ...     ip_address="192.168.1.1",
            ...     user_agent="Mozilla/5.0..."
            ... )
            >>> response = await use_case.execute(request, "user-123", "jwt-token")
            >>> print(response.message)  # "Logout exitoso"
        """
        # Obtener security logger
        security_logger = self._security_audit

        # Valores por defecto para security logging
        ip_address = request.ip_address or "unknown"
        user_agent = request.user_agent or "unknown"

        # 1. Verificar que el usuario existe
        user_id_vo = UserId(user_id)
        user = await self._uow.users.find_by_id(user_id_vo)

        if not user:
            return None

        # 2. Registrar evento de logout para auditoría (dominio)
        logout_time = datetime.now()
        user.record_logout(logout_time, token)

        # 3. y 4. Los refresh tokens de ESTE dispositivo (BE #376), en la misma
        # transacción que el usuario: el que llega en la petición y todos los de su
        # dispositivo (logins anteriores y la cadena de la rotación, F-02). Uno de otra
        # persona no se toca, y sin token no hay sesión que cerrar aquí
        async with self._uow:
            tokens_revoked_count = await self._cierra_este_dispositivo(
                user_id_vo, request.refresh_token
            )
            # Y su acceso, al momento: tras revocar (y bloquear) los refrescos, así que
            # uno que terminara antes dejó un acceso emitido antes de esta hora (B-05)
            await self._cierra_las_sesiones_del_dispositivo(user_id_vo, request.device_id)

            # Guardar usuario dentro de la misma transacción
            await self._uow.users.save(user)
            # Commit automático al salir del contexto (atomicidad garantizada)

        # 5. Security Logging: Logout exitoso
        registra_sin_romper(
            "Logout user",
            lambda: security_logger.log_logout(
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                refresh_tokens_revoked=tokens_revoked_count,
            ),
        )

        # 6. Security Logging: Revocación de refresh tokens
        if tokens_revoked_count > 0:
            registra_sin_romper(
                "Logout user",
                lambda: security_logger.log_refresh_token_revoked(
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    tokens_revoked_count=tokens_revoked_count,
                    reason="logout",
                ),
            )

        return LogoutResponseDTO(message="Logout exitoso", logged_out_at=logout_time)

    async def _cierra_las_sesiones_del_dispositivo(
        self, user_id: UserId, device_id: str | None
    ) -> None:
        """Los accesos de este dispositivo emitidos hasta ahora dejan de valer (B-05)."""
        if not device_id:
            return
        try:
            id_del_dispositivo = UserDeviceId.from_string(device_id)
        except (ValueError, TypeError):
            return
        dispositivo = await self._uow.user_devices.find_by_id_and_user(
            device_id=id_del_dispositivo, user_id=user_id
        )
        if dispositivo is None:
            return
        dispositivo.cierra_las_sesiones(datetime.now(UTC))
        await self._uow.user_devices.save(dispositivo)

    async def _cierra_este_dispositivo(self, user_id: UserId, refresh_token_jwt: str | None) -> int:
        """
        Revoca en bloque los tokens del dispositivo del token que llega, tras bloquear
        el dispositivo como hacen los refrescos (F-02): un refresco a la vez espera, o
        termina antes y su sucesor también se revoca. Devuelve cuántos. (La fila del
        usuario no se toca: cerrar sesión solo apunta un evento, y no choca con un
        cambio de contraseña.)
        """
        if not refresh_token_jwt:
            return 0
        actual = await self._uow.refresh_tokens.find_by_token_hash(refresh_token_jwt)
        if actual is None or actual.user_id != user_id:
            return 0
        if actual.device_id is None:
            if actual.revoked:
                return 0
            actual.revoke()
            await self._uow.refresh_tokens.save(actual)
            return 1
        await self._uow.user_devices.find_by_id_for_update(actual.device_id)
        return await self._uow.refresh_tokens.revoke_all_for_device(actual.device_id)
