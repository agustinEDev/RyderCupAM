import secrets
from datetime import datetime, timedelta

from src.shared.domain.events.domain_event import DomainEvent
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

from ..events.account_locked_event import AccountLockedEvent
from ..events.account_unlocked_event import AccountUnlockedEvent
from ..events.email_verified_event import EmailVerifiedEvent
from ..events.google_account_unlinked_event import GoogleAccountUnlinkedEvent
from ..events.handicap_updated_event import HandicapUpdatedEvent
from ..events.password_reset_completed_event import PasswordResetCompletedEvent
from ..events.password_reset_requested_event import PasswordResetRequestedEvent
from ..events.user_email_changed_event import UserEmailChangedEvent
from ..events.user_logged_in_event import UserLoggedInEvent
from ..events.user_logged_out_event import UserLoggedOutEvent
from ..events.user_password_changed_event import UserPasswordChangedEvent
from ..events.user_profile_updated_event import UserProfileUpdatedEvent
from ..events.user_registered_event import UserRegisteredEvent
from ..value_objects.email import Email
from ..value_objects.handicap import Handicap
from ..value_objects.password import Password
from ..value_objects.user_id import UserId

# Account Lockout Configuration
MAX_FAILED_ATTEMPTS = 10
LOCKOUT_DURATION_MINUTES = 30


class User:
    """
    Entidad User - Representa un usuario en el sistema.

    Un usuario es alguien que puede registrarse, hacer login
    y participar en torneos Ryder Cup.
    """

    def _validate_profile_update(self, first_name, last_name, country_code_str):
        if first_name is None and last_name is None and country_code_str is None:
            raise ValueError(
                "At least one field (first_name, last_name, or country_code) must be provided"
            )
        if first_name is not None and first_name.strip() == "":
            raise ValueError("first_name cannot be empty")
        if last_name is not None and last_name.strip() == "":
            raise ValueError("last_name cannot be empty")

    def _detect_profile_changes(self, first_name, last_name, country_code_str):
        old_first_name = self.first_name
        old_last_name = self.last_name
        old_country_code = self.country_code
        first_name_changed = first_name is not None and first_name != old_first_name
        last_name_changed = last_name is not None and last_name != old_last_name
        new_country_code = old_country_code
        country_code_changed = False
        if country_code_str is not None:
            new_country_code = CountryCode(country_code_str) if country_code_str else None
            country_code_changed = new_country_code != old_country_code
        return (
            first_name_changed,
            last_name_changed,
            country_code_changed,
            new_country_code,
            old_first_name,
            old_last_name,
            old_country_code,
        )

    def __init__(
        self,
        id: UserId | None,
        email: Email | None,
        password: Password | None,
        first_name: str,
        last_name: str,
        handicap: float | None = None,
        handicap_updated_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        email_verified: bool = False,
        verification_token: str | None = None,
        country_code: CountryCode | None = None,
        password_reset_token: str | None = None,
        reset_token_expires_at: datetime | None = None,
        failed_login_attempts: int = 0,
        locked_until: datetime | None = None,
        is_admin: bool = False,
        gender: Gender | None = None,
        domain_events: list[DomainEvent] | None = None,
    ):
        self.id = id
        self.email = email
        self.password = password
        self.first_name = first_name
        self.last_name = last_name
        self.handicap = handicap
        self.handicap_updated_at = handicap_updated_at
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        self.email_verified = email_verified
        self.verification_token = verification_token
        self.country_code = country_code
        self.password_reset_token = password_reset_token
        self.reset_token_expires_at = reset_token_expires_at
        self.failed_login_attempts = failed_login_attempts
        self.locked_until = locked_until
        self.is_admin = is_admin
        self.gender = gender
        self._domain_events = domain_events or []

    def get_full_name(self) -> str:
        """Devuelve el nombre completo del usuario."""
        return f"{self.first_name} {self.last_name}".strip()

    def has_valid_email(self) -> bool:
        """Verifica si el usuario tiene un email válido."""
        return self.email is not None

    def is_valid(self) -> bool:
        """Verifica si el usuario es válido (todos los campos requeridos)."""
        return (
            self.has_valid_email()
            and self.first_name.strip() != ""
            and self.last_name.strip() != ""
        )

    @property
    def has_password(self) -> bool:
        """Verifica si el usuario tiene password (False para OAuth-only users)."""
        return self.password is not None

    def is_system_admin(self) -> bool:
        """
        Verifica si el usuario tiene privilegios de administrador del sistema.

        Returns:
            bool: True si el usuario es administrador, False en caso contrario
        """
        return self.is_admin

    def verify_password(self, plain_password: str) -> bool:
        """Verifica si el password plano coincide con el hasheado."""
        if self.password is None:
            return False
        return self.password.verify(plain_password)

    def update_handicap(self, new_handicap: float | None) -> None:
        """
        Actualiza el hándicap del usuario y emite un evento de dominio.

        Valida que el hándicap esté en el rango permitido (-10.0 a 54.0)
        y solo emite el evento si el valor realmente cambió.

        Args:
            new_handicap: Nuevo valor del hándicap (None para eliminar)

        Raises:
            ValueError: Si el hándicap no está en el rango válido
        """
        old_handicap = getattr(self, "handicap", None)

        # Validar si es un Handicap válido usando el Value Object
        if new_handicap is not None:
            validated = Handicap(new_handicap)  # Valida el rango
            self.handicap = validated
        else:
            self.handicap = None

        # Actualizar timestamps
        now = datetime.now()
        self.handicap_updated_at = now
        self.updated_at = now

        # Emitir evento solo si cambió
        if old_handicap != self.handicap:
            self._add_domain_event(
                HandicapUpdatedEvent(
                    user_id=str(self.id.value),
                    old_handicap=old_handicap.value if old_handicap else None,
                    new_handicap=self.handicap.value if self.handicap else None,
                    updated_at=self.updated_at,
                )
            )

    @classmethod
    def create(
        cls,
        first_name: str,
        last_name: str,
        email_str: str,
        plain_password: str,
        country_code_str: str | None = None,
        is_admin: bool = False,
        gender: Gender | None = None,
    ) -> "User":
        """
        Factory method para crear usuario con Value Objects.

        Args:
            first_name: Nombre del usuario
            last_name: Apellido del usuario
            email_str: Email en formato string
            plain_password: Password en texto plano
            country_code_str: Código ISO del país (opcional, ej: "ES", "FR")
            is_admin: Si el usuario tiene privilegios de administrador (default: False)
            gender: Género del usuario (opcional, MALE/FEMALE)

        Returns:
            User: Nueva instancia con ID generado y Value Objects
        """
        user_id = UserId.generate()
        email = Email(email_str)
        password = Password.from_plain_text(plain_password)

        # Convertir country_code si existe
        country_code = CountryCode(country_code_str) if country_code_str else None

        user = cls(
            id=user_id,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            handicap=None,
            handicap_updated_at=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            country_code=country_code,
            is_admin=is_admin,
            gender=gender,
        )

        # Generar evento de registro
        user._add_domain_event(
            UserRegisteredEvent(
                user_id=str(user_id.value),
                email=email_str,
                first_name=first_name,
                last_name=last_name,
            )
        )

        return user

    @classmethod
    def create_from_oauth(
        cls,
        first_name: str,
        last_name: str,
        email_str: str,
        email_verified: bool = True,
        country_code_str: str | None = None,
        gender: Gender | None = None,
    ) -> "User":
        """
        Factory method para crear usuario desde OAuth (sin password).

        El usuario se crea con email_verified según lo que indica el proveedor OAuth.
        No tiene password — debe vincular uno si desea login por email/password.

        Args:
            first_name: Nombre del usuario (de Google profile)
            last_name: Apellido del usuario (de Google profile)
            email_str: Email del usuario en Google
            email_verified: Si Google verificó el email (default True)
            country_code_str: Código ISO del país (opcional)
            gender: Género del usuario (opcional)

        Returns:
            User: Nueva instancia sin password
        """
        user_id = UserId.generate()
        email = Email(email_str)
        country_code = CountryCode(country_code_str) if country_code_str else None

        user = cls(
            id=user_id,
            email=email,
            password=None,
            first_name=first_name,
            last_name=last_name,
            handicap=None,
            handicap_updated_at=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            email_verified=email_verified,
            country_code=country_code,
            gender=gender,
        )

        user._add_domain_event(
            UserRegisteredEvent(
                user_id=str(user_id.value),
                email=email_str,
                first_name=first_name,
                last_name=last_name,
                registration_method="google",
                is_email_verified=email_verified,
            )
        )

        return user

    # === Métodos para manejo de eventos de dominio ===

    def _add_domain_event(self, event: DomainEvent) -> None:
        """Agrega un evento de dominio a la colección interna."""
        if not hasattr(self, "_domain_events"):
            self._domain_events = []
        self._domain_events.append(event)

    def get_domain_events(self) -> list[DomainEvent]:
        """Obtiene una copia de todos los eventos de dominio pendientes."""
        if not hasattr(self, "_domain_events"):
            self._domain_events = []
        return self._domain_events.copy()

    def clear_domain_events(self) -> None:
        """Limpia todos los eventos de dominio de la colección."""
        if not hasattr(self, "_domain_events"):
            self._domain_events = []
        self._domain_events.clear()

    def has_domain_events(self) -> bool:
        """Verifica si la entidad tiene eventos de dominio pendientes."""
        if not hasattr(self, "_domain_events"):
            self._domain_events = []
        return len(self._domain_events) > 0

    def verify_email_from_oauth(self) -> None:
        """
        Marca el email como verificado tras auto-link con cuenta OAuth.

        Google ya verificó el email del usuario, por lo que podemos
        confirmar la verificación sin token.
        Solo actúa si el email aún no está verificado.
        """
        if not self.email_verified:
            self.email_verified = True
            self.updated_at = datetime.now()

    def record_google_unlinked(self, provider: str, unlinked_at: datetime) -> None:
        """
        Registra un evento de desvinculación de cuenta Google.

        Args:
            provider: Proveedor OAuth desvinculado (ej: "google")
            unlinked_at: Timestamp de la desvinculación
        """
        self._add_domain_event(
            GoogleAccountUnlinkedEvent(
                user_id=str(self.id.value),
                provider=provider,
                unlinked_at=unlinked_at,
            )
        )

    def record_logout(self, logged_out_at: datetime, token_used: str | None = None) -> None:
        """
        Registra un evento de logout para este usuario.

        Args:
            logged_out_at: Timestamp del logout
            token_used: Token JWT utilizado (opcional)
        """
        self._add_domain_event(
            UserLoggedOutEvent(
                user_id=str(self.id.value),
                logged_out_at=logged_out_at,
                token_used=token_used,
            )
        )

    def record_login(
        self,
        logged_in_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
        session_id: str | None = None,
        login_method: str = "email",
    ) -> None:
        """
        Registra un evento de login exitoso para este usuario.

        Args:
            logged_in_at: Timestamp del login exitoso
            ip_address: Dirección IP desde donde se hizo login (opcional)
            user_agent: User agent del browser/app (opcional)
            session_id: ID de la sesión creada (opcional)
            login_method: Método de login ("email" o "google")
        """
        self._add_domain_event(
            UserLoggedInEvent(
                user_id=str(self.id.value),
                logged_in_at=logged_in_at,
                ip_address=ip_address,
                user_agent=user_agent,
                session_id=session_id,
                login_method=login_method,
            )
        )

    def update_profile(
        self,
        first_name: str | None = None,
        last_name: str | None = None,
        country_code_str: str | None = None,
    ) -> None:
        """
        Actualiza la información personal del usuario (nombre, apellidos y país).
        Solo emite evento si al menos uno de los campos cambió.
        El evento ahora incluye el cambio de country_code (old/new) si aplica.
        """
        self._validate_profile_update(first_name, last_name, country_code_str)
        (
            first_name_changed,
            last_name_changed,
            country_code_changed,
            new_country_code,
            old_first_name,
            old_last_name,
            _old_country_code,
        ) = self._detect_profile_changes(first_name, last_name, country_code_str)

        if not first_name_changed and not last_name_changed and not country_code_changed:
            return

        if first_name_changed:
            self.first_name = first_name
        if last_name_changed:
            self.last_name = last_name
        if country_code_changed:
            self.country_code = new_country_code

        self.updated_at = datetime.now()

        self._add_domain_event(
            UserProfileUpdatedEvent(
                user_id=str(self.id.value),
                old_first_name=old_first_name if first_name_changed else None,
                new_first_name=first_name if first_name_changed else None,
                old_last_name=old_last_name if last_name_changed else None,
                new_last_name=last_name if last_name_changed else None,
                updated_at=self.updated_at,
            )
        )

    def change_email(self, new_email: str) -> None:
        """
        Cambia el email del usuario y resetea la verificación.

        Cuando se cambia el email, el usuario debe verificar el nuevo correo:
        - Marca email_verified como False
        - Genera un nuevo token de verificación
        - Emite evento de cambio de email

        Args:
            new_email: Nuevo email (ya validado por el use case)

        Raises:
            ValueError: Si el email no es válido
        """
        new_email_vo = Email(new_email)
        old_email_str = str(self.email.value) if self.email else ""

        if new_email == old_email_str:
            return  # No cambió nada

        self.email = new_email_vo
        self.email_verified = False  # Requiere nueva verificación
        self.updated_at = datetime.now()

        self._add_domain_event(
            UserEmailChangedEvent(
                user_id=str(self.id.value),
                old_email=old_email_str,
                new_email=new_email,
                changed_at=self.updated_at,
            )
        )

    def change_password(self, new_password: str) -> None:
        """
        Cambia el password del usuario.

        Args:
            new_password: Nuevo password en texto plano

        Raises:
            ValueError: Si el password no es válido
        """
        new_password_vo = Password.from_plain_text(new_password)
        self.password = new_password_vo
        self.updated_at = datetime.now()

        self._add_domain_event(
            UserPasswordChangedEvent(
                user_id=str(self.id.value),
                changed_at=self.updated_at,
                changed_from_ip=None,
            )
        )

    def generate_verification_token(self) -> str:
        """
        Genera un token de verificación seguro para confirmar el email.

        Returns:
            str: Token de verificación único
        """
        token = secrets.token_urlsafe(32)
        self.verification_token = token
        self.updated_at = datetime.now()
        return token

    def verify_email(self, token: str) -> bool:
        """
        Verifica el email del usuario usando el token proporcionado.

        Args:
            token: Token de verificación

        Returns:
            bool: True si la verificación fue exitosa

        Raises:
            ValueError: Si el email ya está verificado o el token es inválido
        """
        if self.email_verified:
            raise ValueError("El email ya está verificado")

        if self.verification_token != token:
            raise ValueError("Token de verificación inválido")

        # Token válido - proceder con verificación
        self.email_verified = True
        self.verification_token = None
        self.updated_at = datetime.now()

        # Emitir evento de dominio
        self._add_domain_event(
            EmailVerifiedEvent(
                user_id=str(self.id.value),
                email=str(self.email.value),
                verified_at=self.updated_at,
            )
        )

        return True

    def is_email_verified(self) -> bool:
        """
        Verifica si el email del usuario ha sido confirmado.

        Returns:
            bool: True si el email está verificado
        """
        return self.email_verified

    def is_spanish(self) -> bool:
        """
        Verifica si el usuario es español (España).

        Esta información es relevante para determinar si el usuario puede
        acceder a funcionalidades específicas de RFEG (Real Federación Española de Golf).

        Returns:
            bool: True si el usuario tiene nacionalidad española (ES), False en caso contrario

        Ejemplos:
            >>> user = User(..., country_code=CountryCode("ES"))
            >>> user.is_spanish()
            True
            >>> user2 = User(..., country_code=CountryCode("FR"))
            >>> user2.is_spanish()
            False
            >>> user3 = User(..., country_code=None)
            >>> user3.is_spanish()
            False
        """
        return self.country_code is not None and self.country_code.value == "ES"

    # === Password Reset Methods ===

    def generate_password_reset_token(
        self, ip_address: str | None = None, user_agent: str | None = None
    ) -> str:
        """
        Genera un token seguro de reseteo de contraseña con expiración de 24 horas.

        Este método:
        1. Genera un token criptográficamente seguro (URL-safe, 32 bytes)
        2. Establece la fecha de expiración a 24 horas desde ahora
        3. Emite un PasswordResetRequestedEvent para auditoría

        Args:
            ip_address: IP desde donde se solicitó el reseteo (para auditoría)
            user_agent: User agent del navegador (para detección de anomalías)

        Returns:
            str: Token de reseteo único y seguro

        Security:
            - Token generado con secrets.token_urlsafe() (CSPRNG)
            - Expiración automática en 24 horas
            - Evento de dominio registrado para auditoría (OWASP A09)
            - IP y User-Agent capturados para análisis de seguridad

        Ejemplo:
            >>> user = User(...)
            >>> token = user.generate_password_reset_token(ip_address="192.168.1.1")
            >>> # Token válido por 24 horas
        """
        # Generar token seguro (mismo método que email verification)
        token = secrets.token_urlsafe(32)
        self.password_reset_token = token

        # Establecer expiración a 24 horas desde ahora
        now = datetime.now()
        self.reset_token_expires_at = now + timedelta(hours=24)
        self.updated_at = now

        # Emitir evento de dominio para auditoría
        self._add_domain_event(
            PasswordResetRequestedEvent(
                user_id=str(self.id.value),
                email=str(self.email.value),
                requested_at=now,
                reset_token_expires_at=self.reset_token_expires_at,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )

        return token

    def can_reset_password(self, token: str) -> bool:
        """
        Valida si un token de reseteo es válido y no ha expirado.

        Validaciones:
        1. El token coincide con el almacenado
        2. El token no ha expirado (< 24 horas desde su generación)
        3. Existe un token de reseteo activo

        Args:
            token: Token de reseteo a validar

        Returns:
            bool: True si el token es válido y está dentro del plazo de 24h

        Raises:
            ValueError: Si no hay token de reseteo activo

        Security:
            - Validación estricta de expiración (24 horas máximo)
            - Prevención de timing attacks (verificación en orden constante)
            - No revela información sobre la existencia del usuario

        Ejemplo:
            >>> user.generate_password_reset_token()
            >>> user.can_reset_password(token)  # True (dentro de 24h)
            >>> # Después de 25 horas...
            >>> user.can_reset_password(token)  # False (expirado)
        """
        # Validar que existe un token activo
        if not self.password_reset_token:
            raise ValueError("No hay ninguna solicitud de reseteo de contraseña activa")

        # Validar que el token coincide (usando compare_digest para prevenir timing attacks)
        if not secrets.compare_digest(self.password_reset_token, token):
            return False

        # Validar que no ha expirado
        if not self.reset_token_expires_at:
            return False

        now = datetime.now()
        return now <= self.reset_token_expires_at

    def reset_password(
        self,
        token: str,
        new_password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """
        Resetea la contraseña del usuario usando un token válido.

        Este método:
        1. Valida el token y su expiración
        2. Cambia la contraseña por la nueva (hasheada con bcrypt)
        3. Invalida el token de reseteo (uso único)
        4. Emite evento PasswordResetCompletedEvent (trigger para invalidar sesiones)

        Args:
            token: Token de reseteo generado previamente
            new_password: Nueva contraseña en texto plano (será hasheada)
            ip_address: IP desde donde se hizo el reseteo (para auditoría)
            user_agent: User agent del navegador (para detección de anomalías)

        Raises:
            ValueError: Si el token es inválido, expirado, o la contraseña no cumple la política

        Security:
            - Validación de token con can_reset_password()
            - Password hasheado con bcrypt 12 rounds (OWASP ASVS V2.4.1)
            - Token invalidado después del primer uso (uso único)
            - Evento emitido para invalidar TODAS las sesiones activas
            - Política de contraseñas aplicada por el Value Object Password

        Post-Condiciones:
            - password_reset_token = None (token invalidado)
            - reset_token_expires_at = None (expiración limpiada)
            - Todas las sesiones activas deben ser invalidadas (por event handler)

        Ejemplo:
            >>> user.reset_password(
            ...     token="abc123...",
            ...     new_password="NewSecure123!",
            ...     ip_address="192.168.1.1"
            ... )
            >>> # Password cambiado, sesiones invalidadas, token eliminado
        """
        # Validar el token antes de proceder
        if not self.can_reset_password(token):
            raise ValueError("Token de reseteo inválido o expirado")

        # Cambiar la contraseña (Password VO valida la política de seguridad)
        new_password_vo = Password.from_plain_text(new_password)
        self.password = new_password_vo

        # Invalidar el token (uso único)
        self.password_reset_token = None
        self.reset_token_expires_at = None

        # Actualizar timestamp
        now = datetime.now()
        self.updated_at = now

        # Emitir evento de dominio (trigger para invalidar refresh tokens)
        self._add_domain_event(
            PasswordResetCompletedEvent(
                user_id=str(self.id.value),
                email=str(self.email.value),
                completed_at=now,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )

    # === Account Lockout Methods ===

    def record_failed_login(self) -> None:
        """
        Registra un intento fallido de login y bloquea la cuenta si se excede el límite.

        Este método:
        1. Incrementa el contador de intentos fallidos
        2. Si alcanza MAX_FAILED_ATTEMPTS (10), bloquea la cuenta por 30 minutos
        3. Emite AccountLockedEvent cuando se bloquea

        Post-Condiciones:
            - failed_login_attempts incrementado en 1
            - Si >= 10: locked_until = NOW() + 30 minutos
            - AccountLockedEvent emitido si se bloqueó

        Security (OWASP A07):
            - Previene ataques de fuerza bruta
            - Bloqueo temporal (30 min) vs permanente
            - Evento de auditoría para análisis de seguridad

        Ejemplo:
            >>> user.record_failed_login()  # Intento 1
            >>> user.failed_login_attempts
            1
            >>> # ... 9 intentos más ...
            >>> user.record_failed_login()  # Intento 10
            >>> user.is_locked()
            True
        """
        self.failed_login_attempts += 1
        self.updated_at = datetime.now()

        # Bloquear si alcanza el límite
        if self.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            now = datetime.now()
            self.locked_until = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)

            # Emitir evento de bloqueo
            self._add_domain_event(
                AccountLockedEvent(
                    user_id=str(self.id.value),
                    locked_until=self.locked_until,
                    failed_attempts=self.failed_login_attempts,
                    locked_at=now,
                )
            )

    def is_locked(self) -> bool:
        """
        Verifica si la cuenta está actualmente bloqueada.

        Validaciones:
        1. Si locked_until es None → NO está bloqueada
        2. Si locked_until > NOW() → SÍ está bloqueada (aún dentro del período)
        3. Si locked_until <= NOW() → NO está bloqueada (período expiró)

        Returns:
            bool: True si la cuenta está bloqueada, False si no lo está o el bloqueo expiró

        Security:
            - Auto-desbloqueo tras LOCKOUT_DURATION_MINUTES (30 min)
            - No requiere intervención manual para desbloqueos temporales

        Ejemplo:
            >>> user.locked_until = datetime.now() + timedelta(minutes=10)
            >>> user.is_locked()
            True
            >>> # Después de 10 minutos...
            >>> user.is_locked()
            False
        """
        if self.locked_until is None:
            return False

        now = datetime.now()
        return now < self.locked_until

    def unlock(self, unlocked_by_user_id: str) -> None:
        """
        Desbloquea manualmente la cuenta (solo Admin).

        Este método:
        1. Resetea el contador de intentos fallidos a 0
        2. Elimina el timestamp de bloqueo (locked_until = None)
        3. Emite AccountUnlockedEvent para auditoría

        Args:
            unlocked_by_user_id: ID del admin que realizó el desbloqueo

        Raises:
            ValueError: Si la cuenta no está bloqueada

        Security:
            - Solo accesible por Admin (verificado en Application Layer)
            - Evento de auditoría registra quién desbloqueó
            - Previene abuso de auto-desbloqueo

        Ejemplo:
            >>> user.is_locked()
            True
            >>> user.unlock(unlocked_by_user_id="admin-uuid-123")
            >>> user.is_locked()
            False
            >>> user.failed_login_attempts
            0
        """
        if not self.is_locked() and self.failed_login_attempts == 0:
            raise ValueError("La cuenta no está bloqueada")

        now = datetime.now()
        old_locked_until = self.locked_until
        old_failed_attempts = self.failed_login_attempts

        # Resetear estado de bloqueo
        self.failed_login_attempts = 0
        self.locked_until = None
        self.updated_at = now

        # Emitir evento de desbloqueo
        self._add_domain_event(
            AccountUnlockedEvent(
                user_id=str(self.id.value),
                unlocked_by=unlocked_by_user_id,
                unlocked_at=now,
                previous_locked_until=old_locked_until,
                previous_failed_attempts=old_failed_attempts,
            )
        )

    def reset_failed_attempts(self) -> None:
        """
        Resetea el contador de intentos fallidos tras un login exitoso.

        Este método debe llamarse cuando:
        - El usuario hace login exitosamente
        - Se quiere limpiar el contador sin desbloquear (casos especiales)

        Post-Condiciones:
            - failed_login_attempts = 0
            - locked_until permanece sin cambios (si existe, se mantendrá hasta expirar)

        Security:
            - Solo resetea contador, NO desbloquea la cuenta
            - Si la cuenta está bloqueada, permanece bloqueada hasta expiración o unlock manual

        Ejemplo:
            >>> user.failed_login_attempts = 5
            >>> user.reset_failed_attempts()
            >>> user.failed_login_attempts
            0
        """
        if self.failed_login_attempts > 0:
            self.failed_login_attempts = 0
            self.updated_at = datetime.now()

    def __str__(self) -> str:
        """Representación string del usuario (sin mostrar password)."""
        return f"User(id={self.id}, email={self.email}, name={self.get_full_name()})"
