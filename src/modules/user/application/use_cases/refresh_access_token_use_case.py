"""
Refresh Access Token Use Case

Caso de uso para renovar el access token usando un refresh token válido.
Implementa el patrón Session Timeout (OWASP A01/A02 - v1.8.0).
Security Logging (v1.8.0): Registra uso de refresh tokens.
CSRF Protection (v1.13.0): Genera nuevo token CSRF al renovar access token.
Dispositivos (BE #737, #738): usa y actualiza el dispositivo de su refresh token.
Rotación (F-02): cada refresco sustituye el refresh token y detecta su reutilización.
"""

import logging
from datetime import datetime, timedelta
from enum import StrEnum

from src.modules.user.application.dto.device_dto import (
    UNRESOLVED_IP_PLACEHOLDER,
    AvisoDeSesionCerradaRequestDTO,
)
from src.modules.user.application.dto.user_dto import (
    RefreshAccessTokenRequestDTO,
    RefreshAccessTokenResponseDTO,
    UserResponseDTO,
)
from src.modules.user.application.ports.aviso_de_sesion_cerrada_port import (
    IAvisoDeSesionCerrada,
)
from src.modules.user.application.ports.security_audit_interface import ISecurityAuditLogger
from src.modules.user.application.ports.token_service_interface import ITokenService
from src.modules.user.application.services.datos_del_acceso import datos_del_acceso
from src.modules.user.application.services.registra_sin_romper import registra_sin_romper
from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.rotacion_del_refresco import (
    PasoDelRefresco,
    paso_del_refresco,
)
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import InvalidUserIdError, UserId


class RefreshRejection(StrEnum):
    """
    Por qué no se renueva la sesión: el motivo exacto, para el log de seguridad.

    Al cliente solo le llega su código público (`codigo_publico`, BE #733).
    """

    # El final normal
    REFRESH_TOKEN_MISSING = "REFRESH_TOKEN_MISSING"  # nosec B105 - an error code
    REFRESH_TOKEN_EXPIRED = "REFRESH_TOKEN_EXPIRED"  # nosec B105 - an error code
    SESSION_IDLE = "SESSION_IDLE"
    # Lo raro
    REFRESH_TOKEN_INVALID = "REFRESH_TOKEN_INVALID"  # nosec B105 - an error code
    REFRESH_TOKEN_NOT_FOUND = "REFRESH_TOKEN_NOT_FOUND"  # nosec B105 - an error code
    REFRESH_TOKEN_REVOKED = "REFRESH_TOKEN_REVOKED"  # nosec B105 - an error code
    USER_NOT_FOUND = "USER_NOT_FOUND"
    USER_INACTIVE = "USER_INACTIVE"  # desactivada por un administrador (BE #744)
    # Un token ya sustituido, fuera del margen, cuyo sustituto ya se usó: dos sitios
    # tienen la misma sesión (F-02, robo)
    REFRESH_TOKEN_REUSED = "REFRESH_TOKEN_REUSED"  # nosec B105 - an error code
    # Un token ya sustituido con el navegador en un login más nuevo (F-02 con BE #734):
    # no se emite nada de la sesión vieja. Conserva siempre la cookie, así que el
    # cliente recibe SESSION_REPLACED; en el log cuenta como rechazo, como el
    # revocado de BE #734
    NEWER_SESSION_IN_BROWSER = "NEWER_SESSION_IN_BROWSER"


_FINAL_NORMAL = frozenset(
    {
        RefreshRejection.REFRESH_TOKEN_MISSING,
        RefreshRejection.REFRESH_TOKEN_EXPIRED,
        RefreshRejection.SESSION_IDLE,
    }
)
SESSION_ENDED = "SESSION_ENDED"
SESSION_REJECTED = "SESSION_REJECTED"
# Un 401 tardío de la cookie vieja con el navegador ya en una sesión nueva (BE #734):
# no es un fin de sesión, y el front no cierra la sesión: reintenta con la cookie nueva
SESSION_REPLACED = "SESSION_REPLACED"


def codigo_publico(motivo: RefreshRejection) -> str:
    """
    El código que ve el cliente (BE #733): SESSION_ENDED o SESSION_REJECTED.

    El motivo exacto le decía a quien tuviera una cookie de refresco robada si la
    cuenta se borró, si cambió la contraseña o si cerró sesión (OWASP A01/A04). Al
    front le basta separar el final normal de un rechazo; el motivo se queda en el
    log de seguridad.
    """
    return SESSION_ENDED if motivo in _FINAL_NORMAL else SESSION_REJECTED


logger = logging.getLogger(__name__)

# Una sesión nueva más vieja que esto ya no es la de una petición tardía (BE #734)
VENTANA_DE_LA_SESION_NUEVA = timedelta(minutes=5)


class RefreshRejectedError(Exception):
    """La sesión no se renueva, con su motivo. La ruta responde 401."""

    def __init__(self, motivo: RefreshRejection, user_id: str | None = None):
        super().__init__(motivo.value)
        self.motivo = motivo
        # Para el log de seguridad (BE #733), nunca para el cliente
        self.user_id = user_id
        # Si la ruta no debe borrar la cookie: el navegador ya tiene una sesión más
        # nueva, y su cookie es la de esa (BE #734)
        self.conserva_la_cookie = False
        # Solo un token SUSTITUIDO (revocado al cerrar sesión, o caducado) puede tener
        # una sesión que lo reemplace; nunca una cuenta desactivada, un dispositivo
        # revocado o 24 h sin uso (/code-review). Con su dispositivo y su fecha
        self.sustituido: tuple[UserDeviceId | None, datetime] | None = None


class RefreshAccessTokenUseCase:
    """
    Caso de uso para renovar el access token usando un refresh token.

    Flujo:
    1. Validar que el refresh token sea válido (vía ITokenService)
    2. Verificar que el refresh token NO esté revocado en BD
    3. Verificar que el usuario sigue existiendo y activo
    4. Generar nuevo access token (15 min)
    5. Retornar nuevo access token + datos de usuario

    Responsabilidades:
    - Validar refresh token (JWT + base de datos)
    - Verificar que el usuario existe
    - Generar nuevo access token
    - Rotar el refresh token y detectar su reutilización (F-02): ver `_paso` y la
      regla del dominio `paso_del_refresco`

    OWASP Coverage:
    - A01: Broken Access Control - Tokens de corta duración
    - A02: Cryptographic Failures - Refresh tokens en BD con hash
    - A07: Identification and Authentication Failures - Renovación segura
    """

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        token_service: ITokenService,
        *,
        security_audit: ISecurityAuditLogger,
        aviso_de_cierre: IAvisoDeSesionCerrada,
    ):
        """
        Inicializa el caso de uso.

        Args:
            uow: Unit of Work para acceso a repositorios (users, refresh_tokens, user_devices)
            token_service: Servicio para validación y generación de tokens JWT
            security_audit: El log de auditoría de seguridad
            aviso_de_cierre: El correo al usuario cuando se cierra una sesión por robo
        """
        self._security_audit = security_audit
        self._aviso_de_cierre = aviso_de_cierre
        self._uow = uow
        self._token_service = token_service

    async def execute(
        self, request: RefreshAccessTokenRequestDTO, refresh_token_jwt: str
    ) -> RefreshAccessTokenResponseDTO:
        """
        Ejecuta el caso de uso de renovación de access token.

        Args:
            request: DTO de entrada con contexto de seguridad (IP, User-Agent)
            refresh_token_jwt: Refresh token JWT obtenido de la cookie httpOnly

        Returns:
            RefreshAccessTokenResponseDTO con nuevo access token si el refresh token es válido

        Raises:
            RefreshRejectedError: con el motivo, si la sesión no se renueva (FE #1042)

        Security Logging (v1.8.0):
            - Registra uso exitoso de refresh token
            - Severity LOW (acción normal de renovación)

        Example:
            >>> request = RefreshAccessTokenRequestDTO(
            ...     ip_address="192.168.1.1",
            ...     user_agent="Mozilla/5.0..."
            ... )
            >>> response = await use_case.execute(request, "eyJ...")  # o RefreshRejectedError
            >>> print(response.access_token)  # Nuevo token válido por 15 min
        """
        # 1. Verificar que el refresh token JWT sea válido (firma + expiración)
        payload = self._token_service.verify_refresh_token(refresh_token_jwt)

        if not payload:
            # Caducado con la firma buena es el final normal; si no, inválido
            if self._token_service.refresh_token_expired(refresh_token_jwt):
                caducado = RefreshRejectedError(RefreshRejection.REFRESH_TOKEN_EXPIRED)
                # También el caducado: se identifica en la BD igual (BE #734, Agustín)
                caducado.sustituido = await self._del_token(refresh_token_jwt)
                caducado.conserva_la_cookie = await self._hay_una_sesion_mas_nueva(
                    caducado, request
                )
                raise caducado
            raise RefreshRejectedError(RefreshRejection.REFRESH_TOKEN_INVALID)

        # 2. Extraer user_id del payload
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise RefreshRejectedError(RefreshRejection.REFRESH_TOKEN_INVALID)

        try:
            user_id = UserId(user_id_str)
        except (ValueError, TypeError, InvalidUserIdError) as error:
            raise RefreshRejectedError(RefreshRejection.REFRESH_TOKEN_INVALID) from error

        # 3. Verificar que el refresh token NO esté revocado en base de datos
        # Nota: find_by_token_hash espera el JWT token original, NO el hash
        # El repositorio se encarga de hashear internamente
        try:
            return await self._renueva(request, refresh_token_jwt, user_id)
        except RefreshRejectedError as rechazo:
            # Los rechazos pueden dejar abierta la transacción con los FOR UPDATE de la
            # cuenta, el dispositivo y el token: se sueltan ya, no al cerrar la sesión
            await self._suelta_los_bloqueos()
            # Con el usuario del token, para el log de seguridad (revisor de la PR)
            rechazo.user_id = rechazo.user_id or user_id_str
            # Si ya se sabe que la conserva (un sustituido con un login más nuevo, F-02),
            # no se vuelve a mirar
            rechazo.conserva_la_cookie = rechazo.conserva_la_cookie or (
                await self._hay_una_sesion_mas_nueva(rechazo, request)
            )
            raise

    async def _suelta_los_bloqueos(self) -> None:
        """Rollback de lo que quede abierto (lo que había que guardar ya se confirmó)."""
        try:
            await self._uow.rollback()
        except Exception as error:
            logger.error("Refresh rollback failed: %s", type(error).__name__)

    async def _del_token(
        self, refresh_token_jwt: str
    ) -> tuple[UserDeviceId | None, datetime] | None:
        """El dispositivo y la fecha de un token caducado, si está en la BD."""
        try:
            async with self._uow:
                token = await self._uow.refresh_tokens.find_by_token_hash(refresh_token_jwt)
        except Exception as error:
            logger.error("Newer session check failed: %s", type(error).__name__)
            return None
        return (token.device_id, token.created_at) if token is not None else None

    async def _hay_una_sesion_mas_nueva(
        self, rechazo: RefreshRejectedError, request: RefreshAccessTokenRequestDTO
    ) -> bool:
        """
        Si el navegador tiene ya una sesión más nueva, viva y reciente (BE #734).

        Entonces el rechazo es de una petición tardía con la cookie vieja, y el navegador
        ya tiene la nueva: borrarla le echaría de la sesión a los 15 minutos. Se miran
        el dispositivo del token y los de la cookie de dispositivo del navegador (cada
        cuenta tiene el suyo: así vale también si otra cuenta entró en ese navegador).
        Solo para un token sustituido; si algo falla, se borra como siempre.
        """
        if rechazo.sustituido is None:
            return False
        dispositivo, creado = rechazo.sustituido
        try:
            async with self._uow:
                return await self._sesion_mas_nueva(dispositivo, creado, request)
        except Exception as error:
            # Si falla, se borra como siempre y el rechazo es el mismo (#750 punto 2)
            logger.error("Newer session check failed: %s", type(error).__name__)
            return False

    async def _sesion_mas_nueva(
        self,
        dispositivo: UserDeviceId | None,
        creado: datetime,
        request: RefreshAccessTokenRequestDTO,
    ) -> bool:
        """
        La consulta de `_hay_una_sesion_mas_nueva`, dentro de la transacción del que
        llama: la rotación la hace con la fila del token bloqueada (F-02), y abrir y
        cerrar otra la soltaría. `creado` es el inicio de la sesión del token: los
        sucesores lo heredan, así que la propia cadena nunca es «más nueva».
        """
        dispositivos = {d for d in [dispositivo] if d is not None}
        for crudo in request.dispositivos_del_navegador:
            try:
                dispositivos.add(UserDeviceId.from_string(crudo))
            except (ValueError, TypeError):
                continue
        if not dispositivos:
            return False
        # Un dispositivo revocado no se sustituye, aunque otra cuenta de la cookie
        # del navegador tenga una sesión más nueva (revisor de seguridad)
        if dispositivo is not None:
            propio = await self._uow.user_devices.find_by_id(dispositivo)
            if propio is not None and not propio.is_active:
                return False
        ahora = datetime.now()
        # Solo una sesión reciente: la petición tardía llega segundos después del
        # nuevo login. Más vieja, se borra (sin cookies muertas de días, Agustín)
        desde = max(creado, ahora - VENTANA_DE_LA_SESION_NUEVA)
        return await self._uow.refresh_tokens.hay_uno_vivo_mas_nuevo(
            sorted(dispositivos, key=lambda d: str(d.value)), desde, ahora
        )

    async def _renueva(
        self,
        request: RefreshAccessTokenRequestDTO,
        refresh_token_jwt: str,
        user_id: UserId,
    ) -> RefreshAccessTokenResponseDTO:
        """Del token en la BD en adelante: la cuenta, el token, el dispositivo y el acceso."""
        security_logger = self._security_audit
        user_id_str = str(user_id.value)
        ip_address = request.ip_address or "unknown"
        user_agent = request.user_agent or "unknown"
        refresh_token_entity = await self._bloquea(user_id, refresh_token_jwt)
        if not refresh_token_entity:
            # Refresh token no existe en BD (nunca fue creado o ya fue eliminado)
            raise RefreshRejectedError(RefreshRejection.REFRESH_TOKEN_NOT_FOUND)

        # 4. La cuenta, antes que el token: una desactivada tiene sus tokens revocados,
        # y el motivo del log tiene que ser ese y no «revocado» (revisor de la PR)
        user = await self._uow.users.find_by_id(user_id)
        if not user:
            # Usuario fue eliminado
            raise RefreshRejectedError(RefreshRejection.USER_NOT_FOUND)
        if not user.is_active:
            # Desactivada (BE #744): este token, revocado si se coló, para que no
            # vuelva a valer al reactivarla (auditoría OWASP)
            if not refresh_token_entity.revoked:
                async with self._uow:
                    refresh_token_entity.revoke()
                    await self._uow.refresh_tokens.save(refresh_token_entity)
            raise RefreshRejectedError(RefreshRejection.USER_INACTIVE)

        ahora = datetime.now()
        await self._robo_si_vuelve_un_anulado(refresh_token_entity, user, request, ahora)
        await self._rechaza_si_no_vale(refresh_token_entity)

        # 5. Toda sesión tiene dispositivo desde BE #737. Un token sin él es de antes
        # y ya no queda ninguno vivo (BE #738): no se ata a ninguno, se rechaza
        dispositivo = await self._dispositivo_del_token(refresh_token_entity)
        if dispositivo is None:
            raise RefreshRejectedError(RefreshRejection.REFRESH_TOKEN_INVALID)
        if not dispositivo.is_active:
            # Un token que se coló sin revocar (una carrera con la revocación): no da
            # acceso a un dispositivo revocado; se revoca (/code-review)
            async with self._uow:
                refresh_token_entity.revoke()
                await self._uow.refresh_tokens.save(refresh_token_entity)
            # Con su motivo: en el log se distingue de reusar un token ya revocado
            registra_sin_romper(
                "Refresh revocation",
                lambda: security_logger.log_refresh_token_revoked(
                    user_id=user_id_str,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    tokens_revoked_count=1,
                    reason="refresh_on_revoked_device",
                    device_id=str(dispositivo.id.value),
                ),
            )
            raise RefreshRejectedError(RefreshRejection.REFRESH_TOKEN_REVOKED)
        # La sesión de este dispositivo caduca tras 24 h sin usarse (BE #376, OWASP
        # A07). Se revoca: el token no vuelve a servir aunque llegue de otra forma
        if dispositivo.is_idle():
            async with self._uow:
                refresh_token_entity.revoke()
                await self._uow.refresh_tokens.save(refresh_token_entity)
            # Que quede constancia: «la app me echó» tiene que poder explicarse
            registra_sin_romper(
                "Refresh revocation",
                lambda: security_logger.log_refresh_token_revoked(
                    user_id=user_id_str,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    tokens_revoked_count=1,
                    reason="idle",
                    device_id=str(dispositivo.id.value),
                ),
            )
            raise RefreshRejectedError(RefreshRejection.SESSION_IDLE)
        # Qué toca con este token: rotar, reanudar o solo el acceso (F-02). Puede
        # rechazar: un robo, o un sustituido con el navegador ya en un login más nuevo
        paso, sustituto = await self._paso(refresh_token_entity, dispositivo, user, request, ahora)

        nuevo_refresco: tuple[str, int] | None = None
        async with self._uow:
            if paso is PasoDelRefresco.REANUDA and sustituto is not None:
                # El sustituto que nunca llegó al navegador no debe valer; si vuelve,
                # es un robo (A3)
                sustituto.anula(ahora)
                await self._uow.refresh_tokens.save(sustituto)
            if paso is not PasoDelRefresco.SOLO_ACCESO:
                nuevo_refresco = await self._rota(refresh_token_entity, user_id_str, ahora)
            # Refrescar es usar ESTE dispositivo, el del token (ver el método)
            device_id = await self._usa_el_dispositivo(request, dispositivo)

        # 6. Generar nuevo access token (15 minutos)
        # Con el id de su dispositivo: revocarlo se comprueba por id (BE #737)
        new_access_token = self._token_service.create_access_token(
            data=datos_del_acceso(str(user.id.value), device_id)
        )

        # 7. Generar nuevo token CSRF (256 bits; vale lo que el refresh token más 1 h, y su
        # cookie dura 15 minutos)
        csrf_token = self._token_service.create_csrf_token(str(user.id.value))

        # 8. Security Logging: Uso exitoso de refresh token
        registra_sin_romper(
            "Refresh",
            lambda: security_logger.log_refresh_token_used(
                user_id=str(user.id.value),
                ip_address=ip_address,
                user_agent=user_agent,
                refresh_token_id=str(refresh_token_entity.id.value),
                new_access_token_created=True,
            ),
        )

        # 9. Preparar respuesta
        user_dto = UserResponseDTO.model_validate(user)

        return RefreshAccessTokenResponseDTO(
            access_token=new_access_token,
            csrf_token=csrf_token,
            token_type="bearer",  # nosec B106 - Not a password, it's OAuth2 token type
            user=user_dto,
            message="Access token renovado exitosamente",
            device_id=device_id,
            refresh_token=nuevo_refresco[0] if nuevo_refresco else None,
            refresh_token_max_age=nuevo_refresco[1] if nuevo_refresco else None,
        )

    async def _bloquea(self, user_id: UserId, refresh_token_jwt: str) -> RefreshToken | None:
        """
        Toma los bloqueos siempre en el mismo orden (F-02) y da el token bloqueado: la
        cuenta (compartido: solo choca con un cambio de contraseña, que la bloquea
        entera), el dispositivo (los refrescos, el cierre de sesión y el robo de un
        dispositivo, en fila) y el token (quien espera lee lo que dejó el otro: un solo
        sustituto, sin robo falso). Sin ciclos, no hay interbloqueos.
        """
        await self._uow.users.lock_for_sessions(user_id)
        previo = await self._uow.refresh_tokens.find_by_token_hash(refresh_token_jwt)
        if previo is not None and previo.device_id is not None:
            await self._uow.user_devices.find_by_id_for_update(previo.device_id)
        return await self._uow.refresh_tokens.find_by_token_hash_for_update(refresh_token_jwt)

    async def _robo_si_vuelve_un_anulado(
        self,
        token: RefreshToken,
        user: User,
        request: RefreshAccessTokenRequestDTO,
        ahora: datetime,
    ) -> None:
        """
        El sustituto anulado de una respuesta perdida no llegó nunca al navegador: si
        alguien vuelve con él, tenía la sesión (robo, Agustín). Con el dispositivo ya
        revocado, es un rechazo más (lo da `_rechaza_si_no_vale`).
        """
        if paso_del_refresco(token, None, ahora) is not PasoDelRefresco.ROBO:
            return
        dispositivo = await self._dispositivo_del_token(token)
        if dispositivo is not None and dispositivo.is_active:
            await self._cierra_por_robo(dispositivo, user, request)

    async def _paso(
        self,
        token: RefreshToken,
        dispositivo: UserDevice,
        user: User,
        request: RefreshAccessTokenRequestDTO,
        ahora: datetime,
    ) -> tuple[PasoDelRefresco, RefreshToken | None]:
        """
        Aplica la regla del dominio (`paso_del_refresco`) a un token que vale.

        - ROBO → cierra la sesión del dispositivo (A4); gana a BE #734: un atacante
          con la cookie de dispositivo no esquiva la detección.
        - YA_CERRADA → rechazo REVOKED (se mira BE #734 como siempre).
        - SOLO_ACCESO o REANUDA con el navegador en un login más nuevo →
          SESSION_REPLACED (A5): ni access ni refresh de la sesión vieja.

        El sustituto es del mismo dispositivo, cuya fila ya está bloqueada: nadie lo
        usa a la vez, y se lee tal como lo dejó el último refresco.
        """
        sustituto = None
        if token.is_replaced and token.replaced_by_id is not None:
            sustituto = await self._uow.refresh_tokens.find_by_id(token.replaced_by_id)
        paso = paso_del_refresco(token, sustituto, ahora)
        if paso is PasoDelRefresco.ROBO:
            await self._cierra_por_robo(dispositivo, user, request)
        if paso is PasoDelRefresco.YA_CERRADA:
            revocado = RefreshRejectedError(RefreshRejection.REFRESH_TOKEN_REVOKED)
            revocado.sustituido = (token.device_id, token.created_at)
            raise revocado
        if paso is not PasoDelRefresco.ROTA and await self._sesion_mas_nueva(
            token.device_id, token.created_at, request
        ):
            mas_nueva = RefreshRejectedError(RefreshRejection.NEWER_SESSION_IN_BROWSER)
            mas_nueva.conserva_la_cookie = True
            raise mas_nueva
        return paso, sustituto

    async def _rota(
        self, token: RefreshToken, user_id_str: str, ahora: datetime
    ) -> tuple[str, int]:
        """
        Emite el sucesor de `token` (dentro de la transacción del que llama) y da su JWT
        y lo que le queda en segundos: la misma caducidad absoluta, no 7 días más.
        """
        restante = token.expires_at - ahora
        nuevo_jwt = self._token_service.create_refresh_token(
            data={"sub": user_id_str}, expires_delta=restante
        )
        sucesor = token.sustituye(nuevo_jwt, ahora)
        await self._uow.refresh_tokens.save(sucesor)
        await self._uow.refresh_tokens.save(token)
        return nuevo_jwt, max(int(restante.total_seconds()), 0)

    async def _cierra_por_robo(
        self, dispositivo: UserDevice, user: User, request: RefreshAccessTokenRequestDTO
    ) -> None:
        """
        Robo (A4): revoca el dispositivo y todos sus tokens (la cadena entera, también
        el vigente) en una transacción, con su fila ya bloqueada; lo deja en el log de
        seguridad (HIGH, a Sentry con su tope) y avisa al usuario por correo en
        segundo plano. Revocar el dispositivo corta al instante el access del atacante
        (se comprueba por su `did`) y cualquier sustituto que se colara choca con él
        (Agustín). Ni el log ni el correo cambian la respuesta: siempre lanza el
        rechazo REFRESH_TOKEN_REUSED.
        """
        async with self._uow:
            if dispositivo.is_active:
                dispositivo.revoke()
                await self._uow.user_devices.save(dispositivo)
            revocados = await self._uow.refresh_tokens.revoke_all_for_device(dispositivo.id)
        user_id_str = str(user.id.value)
        device_id = str(dispositivo.id.value)
        registra_sin_romper(
            "Refresh reuse",
            lambda: self._security_audit.log_refresh_token_reuse_detected(
                user_id=user_id_str,
                ip_address=request.ip_address or "unknown",
                user_agent=request.user_agent or "unknown",
                device_id=device_id,
                tokens_revoked_count=revocados,
            ),
        )
        try:
            await self._aviso_de_cierre.avisa(
                AvisoDeSesionCerradaRequestDTO(
                    user_id=user_id_str,
                    email=user.email.value,
                    nombre=user.first_name,
                    device_id=device_id,
                    verificado=user.is_email_verified(),
                )
            )
        except Exception as error:
            logger.error("Session closed notice failed: %s", type(error).__name__)
        raise RefreshRejectedError(RefreshRejection.REFRESH_TOKEN_REUSED)

    async def _usa_el_dispositivo(
        self, request: RefreshAccessTokenRequestDTO, dispositivo: UserDevice
    ) -> str:
        """Apunta el uso del dispositivo de este refresco, el de su token, y da su id.

        El del token manda: antes se registraba otro por su cuenta (sin cookie y con IP
        nueva, uno nuevo y huérfano), y el `did` y la cookie apuntaban a dos distintos
        (/code-review, BE #737). La ruta le vuelve a poner la cookie siempre. Dentro de
        la transacción del que llama, con la rotación (F-02).
        """
        dispositivo.update_last_used()
        dispositivo.update_ip_address(request.ip_address or UNRESOLVED_IP_PLACEHOLDER)
        dispositivo.update_country(request.country_code)
        dispositivo.update_installed_app(request.installed_app)
        if request.user_agent:
            dispositivo.update_user_agent(request.user_agent)
        await self._uow.user_devices.save(dispositivo)
        return str(dispositivo.id.value)

    async def _rechaza_si_no_vale(self, refresh_token_entity: RefreshToken) -> None:
        """Rechaza, con su motivo, el token revocado o caducado en BD."""
        if refresh_token_entity.revoked:
            # Revocado por 24 h sin uso sigue siendo el final normal: lo vuelve a
            # mandar otra pestaña, o la cookie que se quedó (/code-review, 5 nov)
            dispositivo = await self._dispositivo_del_token(refresh_token_entity)
            # Solo si el dispositivo sigue activo: uno revocado es un rechazo, no un
            # final normal, aunque además lleve 24 h sin usarse (revisor de la PR)
            if dispositivo is not None and dispositivo.is_active and dispositivo.is_idle():
                raise RefreshRejectedError(RefreshRejection.SESSION_IDLE)
            # Refresh token fue revocado explícitamente (logout): sustituido
            revocado = RefreshRejectedError(RefreshRejection.REFRESH_TOKEN_REVOKED)
            revocado.sustituido = (
                refresh_token_entity.device_id,
                refresh_token_entity.created_at,
            )
            raise revocado

        if refresh_token_entity.is_expired():
            # Refresh token expiró (aunque JWT aún no lo detectara): sustituido
            caducado = RefreshRejectedError(RefreshRejection.REFRESH_TOKEN_EXPIRED)
            caducado.sustituido = (refresh_token_entity.device_id, refresh_token_entity.created_at)
            raise caducado

    async def _dispositivo_del_token(self, refresh_token_entity: RefreshToken) -> UserDevice | None:
        if refresh_token_entity.device_id is None:
            return None
        return await self._uow.user_devices.find_by_id(refresh_token_entity.device_id)
