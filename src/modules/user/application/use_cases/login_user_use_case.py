"""
Login User Use Case

Caso de uso para autenticar un usuario y generar un token JWT.
Session Timeout (v1.8.0): Genera access token (15 min) + refresh token (7 días).
Security Logging (v1.8.0): Registra todos los intentos de login (exitosos y fallidos).
Freno por correo y origen (BE #732, ADR-043): 5 intentos por minuto y 10 fallos
bloquean 30 min ese origen (la red, o el dispositivo fiable) para ese correo. El
respaldo de la cuenta (50 en una hora, todas las redes) solo frena a los
dispositivos desconocidos: los fallos de otro no dejan fuera al dueño.
CSRF Protection (v1.13.0): Genera token CSRF de 256 bits para validación double-submit.
"""

from datetime import UTC, datetime
from typing import NoReturn

from src.modules.user.application.dto.device_dto import (
    UNRESOLVED_IP_PLACEHOLDER,
    AvisoDeNuevoInicioRequestDTO,
    RegisterDeviceRequestDTO,
    agente_para_el_registro,
)
from src.modules.user.application.dto.user_dto import (
    AvisoDeFallosRequestDTO,
    LoginRequestDTO,
    LoginResponseDTO,
    UserResponseDTO,
)
from src.modules.user.application.ports.aviso_de_fallos_port import IAvisoDeFallos
from src.modules.user.application.ports.aviso_de_nuevo_inicio_port import IAvisoDeNuevoInicio
from src.modules.user.application.ports.freno_del_login_port import (
    IFrenoDelLogin,
    origen_de_dispositivo,
    origen_de_red,
)
from src.modules.user.application.ports.security_audit_interface import ISecurityAuditLogger
from src.modules.user.application.ports.token_service_interface import ITokenService
from src.modules.user.application.services.datos_del_acceso import datos_del_acceso
from src.modules.user.application.services.guarda_la_sesion import (
    CUENTA_DESACTIVADA,
    guarda_la_sesion,
)
from src.modules.user.application.services.registra_sin_romper import registra_sin_romper
from src.modules.user.application.use_cases.register_device_use_case import (
    RegisterDeviceUseCase,
)
from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.exceptions import (
    AccountDeactivatedException,
    AccountLockedException,
    LoginAttemptsExceededException,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.cookie_de_dispositivo import (
    ids_de_la_cookie_de_dispositivo,
)
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.password import Password
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.application.concurrencia.bcrypt_executor import run_bcrypt


def _red_de(request: LoginRequestDTO) -> str:
    """La red del intento: la clave de los límites por red, o su IP."""
    return request.red or request.ip_address or "unknown"


class LoginUserUseCase:
    """
    Caso de uso para login de usuario.

    Responsabilidades:
    - Buscar usuario por email
    - Verificar contraseña
    - Generar access token JWT (15 min)
    - Generar refresh token JWT (7 días)
    - Guardar refresh token en BD (hasheado)
    - Devolver tokens y datos de usuario

    Session Timeout (v1.8.0):
    - Access token de corta duración (15 min) para seguridad
    - Refresh token de larga duración (7 días) para UX
    - Refresh token almacenado hasheado en BD (OWASP A02)
    """

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        token_service: ITokenService,
        register_device_use_case: RegisterDeviceUseCase,
        aviso_de_nuevo_inicio: IAvisoDeNuevoInicio,
        freno: IFrenoDelLogin,
        aviso_de_fallos: IAvisoDeFallos,
        *,
        security_audit: ISecurityAuditLogger,
    ):
        """
        Inicializa el caso de uso.

        Args:
            uow: Unit of Work para acceso a repositorios (users + refresh_tokens + user_devices)
            token_service: Servicio para generación de tokens de autenticación
            register_device_use_case: Caso de uso para registrar/actualizar dispositivos (v1.13.0)
            aviso_de_nuevo_inicio: El correo de «nuevo inicio de sesión» (BE #737)
            freno: El freno del login por correo y origen (BE #732)
            aviso_de_fallos: El correo de «intentos fallidos» al dueño (BE #732)
        """
        self._security_audit = security_audit
        self._uow = uow
        self._token_service = token_service
        self._register_device_use_case = register_device_use_case
        # El correo de «nuevo inicio de sesión» (BE #737)
        self._aviso_de_nuevo_inicio = aviso_de_nuevo_inicio
        # El freno por correo y origen, y el correo de intentos fallidos (BE #732)
        self._freno = freno
        self._aviso_de_fallos = aviso_de_fallos

    def _apunta_que_no_existe(
        self, request: LoginRequestDTO, ip_address: str, user_agent: str
    ) -> None:
        """Security Logging: login fallido porque el usuario no existe."""
        registra_sin_romper(
            "Login",
            lambda: self._security_audit.log_login_attempt(
                user_id=None,
                email=request.email,
                success=False,
                failure_reason="User not found",
                ip_address=ip_address,
                user_agent=user_agent,
            ),
        )

    def _rechaza(
        self,
        hasta: datetime,
        motivo: str,
        user: User | None,
        request: LoginRequestDTO,
        ip_address: str,
        user_agent: str,
    ) -> NoReturn:
        """Security Logging del intento bloqueado, y la excepción (el 423)."""
        registra_sin_romper(
            "Login",
            lambda: self._security_audit.log_login_attempt(
                user_id=str(user.id.value) if user else None,
                email=request.email,
                success=False,
                failure_reason=f"{motivo} until {hasta.isoformat()}",
                ip_address=ip_address,
                user_agent=user_agent,
            ),
        )
        raise AccountLockedException(
            locked_until=hasta,
            message=f"Account is locked due to too many failed login attempts. Try again after {hasta.isoformat()}",
        )

    def _rechaza_si_el_respaldo_frena(
        self, user: User, fiable: bool, request: LoginRequestDTO, contexto: tuple[str, str]
    ) -> None:
        """El 423 del respaldo de la cuenta, que solo frena a los desconocidos."""
        if not fiable and user.is_locked() and user.locked_until:
            self._rechaza(user.locked_until, "Account locked", user, request, *contexto)

    async def _dispositivo_fiable(self, user: User | None, cookie: str | None) -> str | None:
        """Un dispositivo ACTIVO de esta cuenta que vino en la cookie, o None.

        La cookie la controla el cliente: un id inventado, de otra cuenta o de uno
        revocado no da pase (BE #732). Una sola consulta, y también con un correo
        que no existe (contra un usuario que no existe): el tiempo no delata cuál
        existe.
        """
        ids = [UserDeviceId.from_string(i) for i in ids_de_la_cookie_de_dispositivo(cookie)]
        if not ids:
            return None
        async with self._uow:
            activos = await self._uow.user_devices.find_active_ids_of_user(
                ids, user.id if user else UserId.generate()
            )
        # El primero de la cookie que sea suyo y activo
        return next((str(i.value) for i in ids if i in activos), None)

    async def _origen_del_intento(
        self, user: User | None, request: LoginRequestDTO
    ) -> tuple[str, bool]:
        """
        Desde dónde se cuenta este intento, y si es un dispositivo fiable.

        Con un dispositivo activo de la cuenta en la cookie, ese dispositivo: los
        fallos de otras redes no lo bloquean. Si él mismo agotó sus fallos, pierde
        el pase y cuenta como su red. Sin él, la red.
        """
        red = origen_de_red(_red_de(request))
        dispositivo = await self._dispositivo_fiable(user, request.device_id_from_cookie)
        if user is None or dispositivo is None:
            return red, False
        origen = origen_de_dispositivo(dispositivo)
        if self._freno.bloqueado_hasta(request.email, origen) is not None:
            return red, False
        return origen, True

    def _comprueba_la_puerta(
        self,
        user: User | None,
        request: LoginRequestDTO,
        origen: str,
        fiable: bool,
        contexto: tuple[str, str],
    ) -> None:
        """
        Antes del bcrypt, en memoria: el techo de la red y el cupo del minuto (429),
        y el bloqueo de este origen (423). Bloqueado, la contraseña no se llega a
        comprobar: no se puede seguir probando. Igual exista el correo o no. El
        respaldo de la cuenta lo mira aparte `_rechaza_si_el_respaldo_frena`.
        """
        ip_address, user_agent = contexto
        # El techo de fallos de la red (30/min, todos los correos), salvo el fiable:
        # el atacante en la wifi del club no deja fuera al móvil del dueño
        if not fiable and self._freno.techo_de_la_red_agotado(_red_de(request)):
            raise LoginAttemptsExceededException(techo_de_red=True)
        if not self._freno.admite_intento(request.email, origen):
            raise LoginAttemptsExceededException()
        hasta = self._freno.bloqueado_hasta(request.email, origen)
        if hasta is not None:
            self._rechaza(hasta, "Locked for this network", user, request, ip_address, user_agent)

    def _apunta_el_fallo_sin_cuenta(
        self, request: LoginRequestDTO, origen: str, contexto: tuple[str, str]
    ) -> None:
        """Un correo que no existe cuenta en su red igual: el mismo 423 (BE #281)."""
        ip_address, user_agent = contexto
        self._apunta_que_no_existe(request, ip_address, user_agent)
        hasta = self._freno.apunta_fallo(request.email, origen)
        if hasta is not None:
            self._rechaza(hasta, "Locked for this network", None, request, ip_address, user_agent)

    async def _avisa_de_los_fallos(self, user: User, request: LoginRequestDTO, motivo) -> None:
        """El correo al dueño (BE #732). En segundo plano: no lanza ni espera."""
        if user.email is None:
            return
        await self._aviso_de_fallos.avisa(
            AvisoDeFallosRequestDTO(
                user_id=str(user.id.value),
                email=user.email.value,
                nombre=user.first_name,
                verificado=user.is_email_verified(),
                country_code=request.country_code,
                motivo=motivo,
            )
        )

    async def _apunta_el_fallo(
        self,
        user: User,
        request: LoginRequestDTO,
        origen: str,
        fiable: bool,
        contexto: tuple[str, str],
    ) -> None:
        """
        Un fallo cuenta en su origen (memoria) y en el respaldo de la cuenta (BD).

        El respaldo se suma sobre el usuario RELEÍDO con la fila bloqueada (BE #282):
        sin el bloqueo, dos intentos a la vez leían N y escribían N+1. El bcrypt ya
        pasó: la transacción es corta. Si este fallo bloquea su red o hace saltar
        el respaldo, se avisa al dueño y se responde 423.

        Raises:
            AccountLockedException: si este intento bloquea su origen o, para un
                dispositivo desconocido, el respaldo
        """
        ip_address, user_agent = contexto
        del_respaldo = None
        async with self._uow:
            bloqueado = await self._uow.users.find_by_id_for_update(user.id)
            # Sobre un respaldo que otro acaba de bloquear no se cuenta: alargaría el
            # bloqueo y repetiría su evento por cada intento en vuelo (code-review)
            if bloqueado is not None and not bloqueado.is_locked():
                # «dia» o «respaldo» si bloquea; «aviso» si es el 25 de la hora
                del_respaldo = bloqueado.record_failed_login()
                await self._uow.users.save(bloqueado)

        if bloqueado is None:
            # Se borró entre la lectura y el bloqueo: como un email que no existe
            self._apunta_el_fallo_sin_cuenta(request, origen, contexto)
            return

        hasta = self._freno.apunta_fallo(request.email, origen)
        # Un solo aviso por fallo, el del respaldo antes que el de la red: dos a la
        # vez mandaban dos correos
        if del_respaldo is not None:
            await self._avisa_de_los_fallos(bloqueado, request, del_respaldo)
        elif hasta is not None and not fiable:
            await self._avisa_de_los_fallos(bloqueado, request, "red")

        if hasta is not None:
            self._rechaza(
                hasta, "Locked for this network", bloqueado, request, ip_address, user_agent
            )
        self._rechaza_si_el_respaldo_frena(bloqueado, fiable, request, contexto)

        # Security Logging: Login fallido (contraseña incorrecta)
        registra_sin_romper(
            "Login",
            lambda: self._security_audit.log_login_attempt(
                user_id=str(bloqueado.id.value),
                email=request.email,
                success=False,
                failure_reason="Invalid credentials",
                ip_address=ip_address,
                user_agent=user_agent,
            ),
        )

    async def _releido_para_entrar(
        self, user: User, request: LoginRequestDTO, fiable: bool, contexto: tuple[str, str]
    ) -> User | None:
        """
        Con la contraseña buena, el usuario releído con la fila bloqueada antes de
        darla por buena (BE #282, revisor). En una ráfaga, todas las peticiones
        pasaban el `is_locked()` sobre la lectura sin bloqueo: la buena entraba
        aunque otro intento acabara de hacer saltar el respaldo.

        Acertar ya no pone a cero el respaldo (BE #732): suma todas las redes, y el
        dueño entrando no puede borrar los fallos de un ataque repartido. Se acaba
        con su hora.

        Returns:
            El usuario releído, o None si se borró entre medias

        Raises:
            AccountLockedException: si el respaldo acaba de saltar y no es fiable
        """
        ip_address, user_agent = contexto
        async with self._uow:
            releido = await self._uow.users.find_by_id_for_update(user.id)
        if releido is None:
            self._apunta_que_no_existe(request, ip_address, user_agent)
            return None
        self._rechaza_si_el_respaldo_frena(releido, fiable, request, contexto)
        return releido

    async def _guarda_la_sesion(
        self,
        user: User,
        comprobada: Password | None,
        refresh_token: RefreshToken,
        dispositivo_nuevo: UserDeviceId | None,
    ) -> str | None:
        """La sesión, en una transacción con la fila bloqueada, si la cuenta sigue igual.

        Returns:
            None si se guardó; si no, qué cambió (y el dispositivo que dio de alta
            este login, si lo hizo, revocado)
        """

        async def comprueba(actual: User | None) -> str | None:
            return self._cambio_a_mitad(actual, comprobada)

        async def guarda() -> None:
            await self._uow.users.save(user)
            await self._uow.refresh_tokens.save(refresh_token)

        return await guarda_la_sesion(self._uow, user.id, comprueba, guarda, dispositivo_nuevo)

    @staticmethod
    def _cambio_a_mitad(actual: User | None, comprobada: Password | None) -> str | None:
        """Qué cambió en la cuenta desde que se comprobó la contraseña, o None."""
        if actual is None:
            return "Account deleted during login"
        if not actual.is_active:
            return CUENTA_DESACTIVADA
        if actual.password is None or actual.password != comprobada:
            return "Password changed during login"
        return None

    def _rechaza_el_cambio_a_mitad(
        self, cambio: str, user: User, request: LoginRequestDTO, contexto: tuple[str, str]
    ) -> None:
        """Al log; una cuenta desactivada responde como siempre (403), lo demás 401."""
        registra_sin_romper(
            "Login",
            lambda: self._security_audit.log_login_attempt(
                user_id=str(user.id.value),
                email=request.email,
                success=False,
                failure_reason=cambio,
                ip_address=contexto[0],
                user_agent=contexto[1],
            ),
        )
        if cambio == CUENTA_DESACTIVADA:
            raise AccountDeactivatedException()

    async def execute(self, request: LoginRequestDTO) -> LoginResponseDTO | None:
        """
        El login, y cada fallo apuntado en el techo de su red (#273): una contraseña
        mala, un bloqueo (423) o una cuenta desactivada. Un rechazo por cupo (429)
        no cuenta, como antes en la ruta.
        """
        try:
            respuesta = await self._entra(request)
        except (AccountLockedException, AccountDeactivatedException):
            self._freno.apunta_fallo_en_la_red(_red_de(request))
            raise
        if respuesta is None:
            self._freno.apunta_fallo_en_la_red(_red_de(request))
        return respuesta

    async def _lee_la_cuenta(self, email: Email) -> User | None:
        """La cuenta, en su propia transacción: cerrada antes del bcrypt, que no retiene
        así una conexión del pool (BE #283)."""
        async with self._uow:
            return await self._uow.users.find_by_email(email)

    async def _entra(self, request: LoginRequestDTO) -> LoginResponseDTO | None:
        """
        Ejecuta el caso de uso de login.

        Args:
            request: DTO con email, password y contexto de seguridad (IP, User-Agent)

        Returns:
            LoginResponseDTO con access token, refresh token y datos de usuario
            None si el usuario no existe o las credenciales son inválidas

        Security Logging (v1.8.0):
            - Registra TODOS los intentos de login (exitosos y fallidos)
            - Severity HIGH para fallos (posible brute force)
            - Severity MEDIUM para éxitos (evento normal)

        Example:
            >>> request = LoginRequestDTO(
            ...     email="user@example.com",
            ...     password="P@ssw0rd123!",
            ...     ip_address="192.168.1.1",
            ...     user_agent="Mozilla/5.0..."
            ... )
            >>> response = await use_case.execute(request)
            >>> if response:
            >>>     print(response.access_token)  # Válido 15 min
            >>>     print(response.refresh_token)  # Válido 7 días
        """
        # Obtener security logger
        security_logger = self._security_audit

        # Valores por defecto para security logging si no se proporcionan
        ip_address = request.ip_address or "unknown"
        user_agent = request.user_agent or "unknown"
        contexto = (ip_address, user_agent)

        # El freno por correo y origen, antes del bcrypt (BE #732). Sin cookie de
        # dispositivo el origen es la red, y el freno en memoria decide ANTES de tocar
        # la BD: una inundación de intentos no cuesta consultas
        email = Email(request.email)
        if not ids_de_la_cookie_de_dispositivo(request.device_id_from_cookie):
            origen, fiable = origen_de_red(_red_de(request)), False
            self._comprueba_la_puerta(None, request, origen, fiable, contexto)
            user = await self._lee_la_cuenta(email)
        else:
            user = await self._lee_la_cuenta(email)
            origen, fiable = await self._origen_del_intento(user, request)
            self._comprueba_la_puerta(user, request, origen, fiable, contexto)
        # El respaldo solo frena a los desconocidos: el fiable entra igual
        if user is not None:
            self._rechaza_si_el_respaldo_frena(user, fiable, request, contexto)

        if not user:
            # El mismo bcrypt que una contraseña mala: sin él, responder antes
            # delataba qué emails están registrados (BE #281, OWASP A07)
            await run_bcrypt(Password.verifica_contra_el_relleno, request.password)
            self._apunta_el_fallo_sin_cuenta(request, origen, contexto)
            return None

        # Verificar contraseña
        if not await run_bcrypt(user.verify_password, request.password):
            await self._apunta_el_fallo(user, request, origen, fiable, contexto)
            return None

        # La que se comprobó: al guardar la sesión, la cuenta tiene que tenerla aún
        comprobada = user.password

        # La buena, pero RELEÍDA con la fila bloqueada (BE #282, revisor)
        releido = await self._releido_para_entrar(user, request, fiable, contexto)
        if releido is None:
            return None
        user = releido

        # Admin Panel (v2.4.0): Verificar si la cuenta fue desactivada por un admin.
        # Se comprueba DESPUES de validar la contraseña para no filtrar el estado
        # de la cuenta (activa/desactivada) a quien no conoce las credenciales.
        if not user.is_active:
            registra_sin_romper(
                "Login",
                lambda: security_logger.log_login_attempt(
                    user_id=str(user.id.value),
                    email=request.email,
                    success=False,
                    failure_reason="Account deactivated by admin",
                    ip_address=ip_address,
                    user_agent=user_agent,
                ),
            )
            raise AccountDeactivatedException()

        # Registrar evento de login exitoso (Clean Architecture)
        login_time = datetime.now(UTC)
        user.record_login(
            logged_in_at=login_time,
            # ip_address y user_agent se pueden agregar cuando el controlador los pase
            # session_id se podría generar aquí si fuera necesario
        )

        # Device Fingerprinting (v2.0.4): Registrar/actualizar dispositivo PRIMERO
        # Cookie-based identification: device_id_from_cookie tiene prioridad
        # Necesitamos el device_id para asociarlo con el refresh token
        # Siempre con dispositivo, también sin User-Agent: una sesión sin él no salía en
        # la lista, no avisaba y no se podía revocar (auditoría OWASP, A07)
        device_request = RegisterDeviceRequestDTO(
            user_id=str(user.id.value),
            user_agent=agente_para_el_registro(request.user_agent),
            ip_address=request.ip_address or UNRESOLVED_IP_PLACEHOLDER,
            device_id_from_cookie=request.device_id_from_cookie,
            installed_app=request.installed_app,  # BE #737
            country_code=request.country_code,
        )
        # Registrar dispositivo (crea nuevo o actualiza last_used_at + ip_address)
        device_response = await self._register_device_use_case.execute(device_request)
        # Obtener device_id para asociar con refresh token
        device_id = UserDeviceId.from_string(device_response.device_id)
        device_id_str = device_response.device_id
        # Sin su cookie (nuevo, o solo por la huella) avisa (BE #737)
        es_nuevo = device_response.is_new_device or not device_response.recognized_by_cookie

        # Los tokens, después del dispositivo: el de acceso lleva su id (`did`), y así
        # revocarlo se comprueba por id y no por una huella que cambia (BE #737)
        access_token = self._token_service.create_access_token(
            data=datos_del_acceso(str(user.id.value), device_id_str)
        )
        refresh_token_jwt = self._token_service.create_refresh_token(
            data={"sub": str(user.id.value)}
        )

        # Crear entidad RefreshToken (hashea el JWT antes de guardar)
        # IMPORTANTE: Asociar con device_id para permitir revocación correcta
        refresh_token_entity = RefreshToken.create(
            user_id=user.id, token=refresh_token_jwt, device_id=device_id, expires_in_days=7
        )

        # Persistir usuario + refresh token usando Unit of Work, con la fila
        # bloqueada y la cuenta como cuando se comprobó: si a la vez Google se la
        # quedó, la desactivaron o cambió la contraseña, no hay sesión (auditoría
        # OWASP y revisor de #749)
        # El dispositivo solo se revoca si lo dio de alta este login (no el de siempre)
        nuevo = device_id if device_response.is_new_device else None
        cambio = await self._guarda_la_sesion(user, comprobada, refresh_token_entity, nuevo)
        if cambio is not None:
            self._rechaza_el_cambio_a_mitad(cambio, user, request, contexto)
            return None

        # Entra: los fallos de ESTE origen vuelven a cero; los de los demás, no. Solo
        # con la sesión ya guardada: acertar en una desactivada, o en una que cambió a
        # mitad, no es entrar
        self._freno.olvida(request.email, origen)

        # Security Logging: Login exitoso
        registra_sin_romper(
            "Login",
            lambda: security_logger.log_login_attempt(
                user_id=str(user.id.value),
                email=request.email,
                success=True,
                failure_reason=None,
                ip_address=ip_address,
                user_agent=user_agent,
            ),
        )

        # Si entra desde un dispositivo nuevo, se le avisa por correo (BE #737). No
        # lanza: un fallo del correo no tumba el login
        if user.email is not None:
            # Nunca a un correo sin confirmar: solo le llega el de confirmación
            await self._aviso_de_nuevo_inicio.avisa(
                AvisoDeNuevoInicioRequestDTO(
                    user_id=str(user.id.value),
                    email=user.email.value,
                    nombre=user.first_name,
                    device_id=device_id_str,
                    desconocido=es_nuevo,
                    verificado=user.is_email_verified(),
                )
            )

        # Generar token CSRF (256 bits, 15 minutos de duración)
        csrf_token = self._token_service.create_csrf_token(str(user.id.value))

        # El hándicap ya no se refresca aquí: el login esperaba a la RFEG antes de
        # contestar. Lo pide el frontend después de entrar (RyderCupAM#340).

        # Crear respuesta con tokens y datos de usuario
        user_dto = UserResponseDTO.model_validate(user)

        return LoginResponseDTO(
            access_token=access_token,
            refresh_token=refresh_token_jwt,
            csrf_token=csrf_token,
            token_type="bearer",  # nosec B106 - Not a password, it's OAuth2 token type
            user=user_dto,
            email_verification_required=not user.is_email_verified(),
            # Device Fingerprinting (v2.0.4): Cookie-based identification
            device_id=device_id_str,
        )
