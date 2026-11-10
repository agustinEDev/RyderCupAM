import secrets
from datetime import UTC, datetime, timedelta

from src.modules.user.domain.exceptions.email_change_exceptions import (
    EmailChangeExpiredError,
    EmailChangeInvalidError,
)
from src.modules.user.domain.exceptions.invalid_reset_token_error import InvalidResetTokenError
from src.modules.user.domain.exceptions.verification_token_expired_error import (
    VerificationTokenExpiredError,
)
from src.shared.domain.events.domain_event import DomainEvent
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

from ..errors.user_errors import InvalidAvatarPresetError
from ..events.account_deactivated_event import AccountDeactivatedEvent
from ..events.account_locked_event import AccountLockedEvent
from ..events.account_reactivated_event import AccountReactivatedEvent
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
from ..services import terms_of_service
from ..value_objects.avatar_source import AvatarSource
from ..value_objects.email import Email
from ..value_objects.handicap import Handicap
from ..value_objects.password import Password
from ..value_objects.token_hash import hash_del_enlace
from ..value_objects.user_avatar_upload_id import UserAvatarUploadId
from ..value_objects.user_id import UserId

# Account Lockout Configuration
# El RESPALDO de la cuenta (BE #732, ADR-043): suma los fallos de todas las redes,
# contra un ataque repartido. Cada red se frena antes por su cuenta (correo + red),
# y el dispositivo fiable del dueño no se bloquea con estos
MAX_FAILED_ATTEMPTS = 50
FAILED_ATTEMPTS_WINDOW = timedelta(hours=1)
LOCKOUT_DURATION_MINUTES = 30
# Al fallo 25 de la hora se avisa al dueño, sin bloquear
FAILED_ATTEMPTS_EARLY_NOTICE = 25
# Contra el ataque lento (49 por hora sin llegar nunca a 50): 150 en 24 horas
# bloquean 24 horas a los dispositivos desconocidos
MAX_FAILED_ATTEMPTS_PER_DAY = 150
FAILED_ATTEMPTS_DAY_WINDOW = timedelta(hours=24)
DAY_LOCKOUT = timedelta(hours=24)

# Los enlaces del correo (fase 3, F-04/F-05/F-10): se guardan con su SHA-256, nunca en
# claro, y caducan. La verificación vale 48 horas; restablecer la contraseña, una hora
VERIFICATION_TOKEN_LIFETIME = timedelta(hours=48)
PASSWORD_RESET_TOKEN_LIFETIME = timedelta(hours=1)
# Registrarse con el correo de una cuenta verificada avisa al dueño, como mucho uno al
# día por cuenta (fase 3, B2)
REGISTER_ATTEMPT_NOTICE_INTERVAL = timedelta(hours=24)
# «Olvidé mi contraseña»: como mucho 10 correos por cuenta en 24 horas, vengan de donde
# vengan (fase 3, H2). Cada red tiene antes su 3/hora por correo (H1)
MAX_PASSWORD_RESET_EMAILS_PER_DAY = 10
PASSWORD_RESET_EMAILS_WINDOW = timedelta(hours=24)

# Avatar Configuration
AVATAR_PRESET_COUNT = 10
AVATAR_MAX_STORED_UPLOADS = 5

# Cuanto puede ir por delante la ultima visita al feed antes de darla por mala:
# lo justo para el desfase entre relojes, no las horas de una zona horaria
FEED_SEEN_FUTURE_TOLERANCE = timedelta(minutes=5)


def _como_password(contrasena: str | Password) -> Password:
    """La contraseña como Value Object: ya calculada, tal cual (el bcrypt se hizo fuera
    de la transacción, BE #283); en texto plano, se valida y se calcula aquí."""
    if isinstance(contrasena, Password):
        if not contrasena.de_texto_plano:
            # Un hash cualquiera se saltaría la política (revisores del bloque 2)
            raise ValueError("A ready Password must come from Password.from_plain_text")
        return contrasena
    return Password.from_plain_text(contrasena)


class User:
    """
    Entidad User - Representa un usuario en el sistema.

    Un usuario es alguien que puede registrarse, hacer login
    y participar en torneos Ryder Cup.
    """

    def _validate_profile_update(
        self, first_name, last_name, country_code_str, gender_str=None, alias=None
    ):
        """Valida los datos nuevos del perfil antes de aplicarlos."""
        if (
            first_name is None
            and last_name is None
            and country_code_str is None
            and gender_str is None
            and alias is None
        ):
            raise ValueError(
                "At least one field (first_name, last_name, country_code, gender or alias) "
                "must be provided"
            )
        if first_name is not None and first_name.strip() == "":
            raise ValueError("first_name cannot be empty")
        if last_name is not None and last_name.strip() == "":
            raise ValueError("last_name cannot be empty")

    def _detect_profile_changes(
        self, first_name, last_name, country_code_str, gender_str=None, alias=None
    ):
        """Qué campos del perfil cambian respecto a los actuales."""
        old_first_name = self.first_name
        old_last_name = self.last_name
        old_country_code = self.country_code
        old_gender = self.gender
        first_name_changed = first_name is not None and first_name != old_first_name
        last_name_changed = last_name is not None and last_name != old_last_name
        new_country_code = old_country_code
        country_code_changed = False
        if country_code_str is not None:
            new_country_code = CountryCode(country_code_str) if country_code_str else None
            country_code_changed = new_country_code != old_country_code
        new_gender = old_gender
        gender_changed = False
        if gender_str is not None:
            new_gender = Gender(gender_str) if gender_str else None
            gender_changed = new_gender != old_gender
        # Mismo convenio que country_code y gender: `None` es "no lo han
        # mandado" y la cadena vacía es "quítamelo". Sin esa distinción no
        # habría forma de volver al nombre real una vez puesto un alias
        old_alias = self.alias
        new_alias = old_alias
        alias_changed = False
        if alias is not None:
            new_alias = alias or None
            alias_changed = new_alias != old_alias
        return (
            first_name_changed,
            last_name_changed,
            country_code_changed,
            gender_changed,
            alias_changed,
            new_country_code,
            new_gender,
            new_alias,
            old_first_name,
            old_last_name,
            old_country_code,
            old_alias,
        )

    def __init__(
        self,
        id: UserId | None,
        email: Email | None,
        password: Password | None,
        first_name: str,
        last_name: str,
        alias: str | None = None,
        handicap: Handicap | None = None,
        handicap_updated_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        email_verified: bool = False,
        verification_token: str | None = None,
        verification_token_expires_at: datetime | None = None,
        country_code: CountryCode | None = None,
        password_reset_token: str | None = None,
        reset_token_expires_at: datetime | None = None,
        password_reset_emails_in_window: int = 0,
        password_reset_window_started_at: datetime | None = None,
        register_attempt_notice_at: datetime | None = None,
        pending_email: str | None = None,
        pending_email_token: str | None = None,
        pending_email_expires_at: datetime | None = None,
        failed_login_attempts: int = 0,
        locked_until: datetime | None = None,
        failed_login_window_started_at: datetime | None = None,
        failed_login_notice_at: datetime | None = None,
        failed_login_day_attempts: int = 0,
        failed_login_day_window_started_at: datetime | None = None,
        is_admin: bool = False,
        is_active: bool = True,
        feed_last_seen_at=None,
        share_activity: bool = True,
        gender: Gender | None = None,
        avatar_source: AvatarSource = AvatarSource.NONE,
        avatar_preset_id: int | None = None,
        active_avatar_upload_id: UserAvatarUploadId | None = None,
        terms_accepted_at: datetime | None = None,
        terms_version: str | None = None,
        domain_events: list[DomainEvent] | None = None,
    ):
        # Asignación de atributos privados (encapsulación)
        """La cuenta, con todos sus campos (también el correo pendiente, #749)."""
        self._id = id
        self._email = email
        self._password = password
        self._first_name = first_name
        self._last_name = last_name
        self._alias = alias
        self._handicap = handicap
        self._handicap_updated_at = handicap_updated_at
        self._created_at = created_at or datetime.now()
        self._updated_at = updated_at or datetime.now()
        self._email_verified = email_verified
        # Los dos enlaces, con su hash (fase 3, C3)
        self._verification_token = verification_token
        self._verification_token_expires_at = verification_token_expires_at
        self._country_code = country_code
        self._password_reset_token = password_reset_token
        self._reset_token_expires_at = reset_token_expires_at
        # El cupo diario de correos de restablecer (H2) y el último aviso de registro (B2)
        self._password_reset_emails_in_window = password_reset_emails_in_window
        self._password_reset_window_started_at = password_reset_window_started_at
        self._register_attempt_notice_at = register_attempt_notice_at
        # El correo nuevo, hasta que se confirme desde la dirección nueva (#749)
        self._pending_email = pending_email
        self._pending_email_token = pending_email_token
        self._pending_email_expires_at = pending_email_expires_at
        self._failed_login_attempts = failed_login_attempts
        self._locked_until = locked_until
        self._failed_login_window_started_at = failed_login_window_started_at
        self._failed_login_notice_at = failed_login_notice_at
        self._failed_login_day_attempts = failed_login_day_attempts
        self._failed_login_day_window_started_at = failed_login_day_window_started_at
        self._is_admin = is_admin
        self._is_active = is_active
        self._feed_last_seen_at = feed_last_seen_at
        self._share_activity = share_activity
        self._gender = gender
        self._avatar_source = avatar_source
        self._avatar_preset_id = avatar_preset_id
        self._active_avatar_upload_id = active_avatar_upload_id
        self._terms_accepted_at = terms_accepted_at
        self._terms_version = terms_version
        self._domain_events = domain_events or []

    # ===========================================
    # PROPERTIES (Encapsulación — solo lectura)
    # ===========================================

    @property
    def id(self) -> UserId | None:
        return self._id

    @property
    def email(self) -> Email | None:
        return self._email

    @property
    def password(self) -> Password | None:
        """La contraseña, o None si la cuenta no tiene (solo Google)."""
        return self._password

    @property
    def first_name(self) -> str:
        return self._first_name

    @property
    def last_name(self) -> str:
        return self._last_name

    @property
    def alias(self) -> str | None:
        """El apodo público, o None si esta persona no ha puesto ninguno."""
        return self._alias

    @property
    def handicap(self) -> Handicap | None:
        return self._handicap

    @property
    def handicap_updated_at(self) -> datetime | None:
        return self._handicap_updated_at

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    @property
    def email_verified(self) -> bool:
        return self._email_verified

    @property
    def verification_token(self) -> str | None:
        """El SHA-256 del token del enlace de verificación, nunca el token."""
        return self._verification_token

    @property
    def verification_token_expires_at(self) -> datetime | None:
        """Cuándo caduca el enlace de verificación (48 h tras generarlo)."""
        return self._verification_token_expires_at

    @property
    def register_attempt_notice_at(self) -> datetime | None:
        """Cuándo se avisó al dueño del último intento de registro con su correo."""
        return self._register_attempt_notice_at

    @property
    def password_reset_emails_in_window(self) -> int:
        """Los correos de restablecer enviados en la ventana de 24 h en curso."""
        return self._password_reset_emails_in_window

    @property
    def password_reset_window_started_at(self) -> datetime | None:
        """Cuándo empezó la ventana de 24 h de los correos de restablecer."""
        return self._password_reset_window_started_at

    @property
    def country_code(self) -> CountryCode | None:
        return self._country_code

    @property
    def password_reset_token(self) -> str | None:
        """El SHA-256 del token del enlace de restablecer, nunca el token."""
        return self._password_reset_token

    @property
    def pending_email_token(self) -> str | None:
        """El token del enlace que confirma el correo nuevo, si hay cambio pendiente."""
        return self._pending_email_token

    @property
    def pending_email_expires_at(self) -> datetime | None:
        """Hasta cuándo vale el cambio pendiente."""
        return self._pending_email_expires_at

    def pending_email_at(self, ahora: datetime) -> str | None:
        """El correo pendiente, si lo hay y no ha caducado a esa hora."""
        pendiente = self._pending_email
        if pendiente is None or self.pending_email_expires_at is None:
            return None
        return pendiente if ahora <= self.pending_email_expires_at else None

    @property
    def pending_email(self) -> str | None:
        """El correo pendiente ahora (para la respuesta del perfil)."""
        return self.pending_email_at(datetime.now())

    @property
    def reset_token_expires_at(self) -> datetime | None:
        return self._reset_token_expires_at

    @property
    def failed_login_attempts(self) -> int:
        return self._failed_login_attempts

    @property
    def locked_until(self) -> datetime | None:
        return self._locked_until

    @property
    def failed_login_window_started_at(self) -> datetime | None:
        """Cuándo empezó la hora en la que se cuentan los fallos del respaldo."""
        return self._failed_login_window_started_at

    @property
    def failed_login_notice_at(self) -> datetime | None:
        """El último correo de «intentos fallidos» (BE #732): uno por hora como mucho."""
        return self._failed_login_notice_at

    def apunta_el_aviso_de_fallos(self, ahora: datetime) -> None:
        """Reserva el correo de intentos fallidos: cuenta para el tope de uno por hora."""
        self._failed_login_notice_at = ahora
        self._updated_at = ahora

    def devuelve_el_aviso_de_fallos(self, anterior: datetime | None) -> None:
        """Un aviso reservado que no salió: vuelve el que había antes."""
        self._failed_login_notice_at = anterior

    @property
    def is_admin(self) -> bool:
        return self._is_admin

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def feed_last_seen_at(self):
        """Cuándo miró su feed por última vez. None si nunca lo ha abierto."""
        return self._feed_last_seen_at

    @property
    def share_activity(self) -> bool:
        """Si sus logros se publican en el feed de sus amigos."""
        return self._share_activity

    def mark_feed_as_seen(self, at) -> None:
        """
        Deja de avisar de lo publicado hasta esta fecha.

        Nunca hacia atras: una marca con un reloj que va por detras (otro
        servidor, un ajuste de hora) resucitaria como novedad lo ya visto.

        Salvo que la guardada vaya por delante mas de
        `FEED_SEEN_FUTURE_TOLERANCE`: eso ya no es desfase de reloj sino una
        marca vieja en hora local de un servidor que no esta en UTC, y
        respetarla congelaria el aviso esas horas.
        """
        previa = self._feed_last_seen_at
        if previa is None or at > previa or previa - at > FEED_SEEN_FUTURE_TOLERANCE:
            self._feed_last_seen_at = at

    def set_activity_sharing(self, enabled: bool) -> None:
        """
        Enciende o apaga la publicación de logros.

        Apagarlo no basta con dejar de generar eventos nuevos: lo ya publicado
        también debe retirarse, y de eso se encarga el caso de uso.
        """
        self._share_activity = enabled

    @property
    def gender(self) -> Gender | None:
        return self._gender

    @property
    def avatar_source(self) -> AvatarSource:
        return self._avatar_source

    @property
    def avatar_preset_id(self) -> int | None:
        return self._avatar_preset_id

    @property
    def active_avatar_upload_id(self) -> UserAvatarUploadId | None:
        return self._active_avatar_upload_id

    @property
    def terms_accepted_at(self) -> datetime | None:
        """
        Cuándo aceptó la versión de `terms_version` (UTC), o None si nunca.

        Es la primera aceptación de esa versión: aceptarla otra vez no la cambia.
        """
        return self._terms_accepted_at

    @property
    def terms_version(self) -> str | None:
        """La versión más reciente de los Términos que ha aceptado, o None si nunca."""
        return self._terms_version

    @property
    def terms_accepted(self) -> bool:
        """
        Si tiene aceptada la versión VIGENTE de los Términos.

        Haber aceptado una anterior no basta: al cambiar la versión vigente,
        todos vuelven a aceptar.
        """
        return self._terms_version == terms_of_service.current_terms_version()

    def accept_terms(self, version: str) -> bool:
        """
        Deja constancia de que acepta esa versión de los Términos, con la hora de ahora (UTC).

        Idempotente: si ya tenía aceptada esa misma versión no cambia nada, ni
        la fecha, para que la fecha guardada sea la de la primera aceptación.

        Args:
            version: La versión aceptada (la vigente, la decide quien llama)

        Returns:
            True si ha cambiado algo; False si ya la tenía aceptada

        Raises:
            ValueError: Si la versión está vacía o no cabe en la columna
        """
        terms_of_service.validate_terms_version(version)
        if self._terms_version == version:
            return False
        self._terms_version = version
        self._terms_accepted_at = datetime.now(UTC)
        self._updated_at = datetime.now()
        return True

    def set_preset_avatar(self, preset_id: int) -> None:
        """
        Activa un avatar predefinido (catálogo fijo 1..AVATAR_PRESET_COUNT).

        Preset y foto subida son mutuamente excluyentes: activar un preset
        desactiva cualquier foto subida como avatar activo (sin borrar el
        historial de subidas, que se conserva para poder volver a él).
        """
        if not (1 <= preset_id <= AVATAR_PRESET_COUNT):
            raise InvalidAvatarPresetError(
                f"preset_id debe estar entre 1 y {AVATAR_PRESET_COUNT}, recibido: {preset_id}"
            )
        self._avatar_source = AvatarSource.PRESET
        self._avatar_preset_id = preset_id
        self._active_avatar_upload_id = None
        self._updated_at = datetime.now()

    def set_uploaded_avatar(self, upload_id: UserAvatarUploadId) -> None:
        """
        Activa como avatar una foto ya subida por el propio usuario (nueva o del historial).

        Mutuamente excluyente con el preset: activar una foto subida desactiva
        cualquier preset activo.
        """
        self._avatar_source = AvatarSource.UPLOAD
        self._avatar_preset_id = None
        self._active_avatar_upload_id = upload_id
        self._updated_at = datetime.now()

    def clear_avatar(self) -> None:
        """Quita el avatar activo (vuelve al placeholder por defecto). No borra el historial de subidas."""
        self._avatar_source = AvatarSource.NONE
        self._avatar_preset_id = None
        self._active_avatar_upload_id = None
        self._updated_at = datetime.now()

    def get_full_name(self) -> str:
        """
        Devuelve el nombre LEGAL del usuario.

        No mira el alias a propósito: la búsqueda de hándicap en la RFEG y los
        correos transaccionales van por aquí, y la federación busca por el
        nombre con el que uno está federado. Para enseñar a alguien por
        pantalla, `display_name`.
        """
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def display_name(self) -> str:
        """
        El nombre con el que la aplicación pinta a esta persona: su alias si
        lo tiene, y si no su nombre completo.

        Este es el ÚNICO sitio donde vive ese fallback. El backend lo resuelve
        y lo manda ya resuelto para que el frontend no reparta `alias || nombre`
        por cada pantalla.
        """
        return self._alias or self.get_full_name()

    def display_name_or_legal(self, use_real_name: bool) -> str:
        """
        `display_name`, salvo que quien pregunta quiera el nombre legal.

        Quién quiere una cosa u otra —y por qué— no es asunto de esta
        entidad: le llega ya decidido en el argumento. Este agregado no sabe
        en qué pantalla ni en qué contexto se está preguntando, y no tiene
        que saberlo.

        Es el único sitio donde vive esta segunda excepción al fallback de
        `display_name`, igual que ese es el único sitio del primero: sin él,
        cada pantalla que quisiera la excepción escribiría por su cuenta el
        mismo `get_full_name() if ... else display_name`, listas para quedar
        descoordinadas en cuanto una cambiara sin las otras.
        """
        return self.get_full_name() if use_real_name else self.display_name

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
            # Una cuenta solo de Google: el mismo bcrypt que las demás, o el
            # tiempo de respuesta delataría que el email está registrado (#281)
            return Password.verifica_contra_el_relleno(plain_password)
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
        old_handicap = self._handicap

        # Validar si es un Handicap válido usando el Value Object
        if new_handicap is not None:
            validated = Handicap(new_handicap)  # Valida el rango
            self._handicap = validated
        else:
            self._handicap = None

        # Actualizar timestamps
        # handicap_updated_at se guarda en UTC (columna timezone-aware) para que el
        # frontend pueda convertirlo correctamente a la hora local del usuario.
        now = datetime.now()
        self._handicap_updated_at = datetime.now(UTC)
        self._updated_at = now

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

    def confirm_email_ownership(self) -> None:
        """
        Da el correo por verificado, sin token: alguien demostró que es suyo por otro
        camino (un Google que lo verificó, o el enlace de restablecer que llegó a su
        buzón). Solo actúa si aún no lo estaba.
        """
        if not self.email_verified:
            self._email_verified = True
            self._verification_token = None
            self._verification_token_expires_at = None
            self._updated_at = datetime.now()

    def claim_with_verified_oauth(self) -> bool:
        """
        Un proveedor que verificó el correo se queda una cuenta SIN verificar.

        Esa cuenta la pudo crear cualquiera con este correo (pre-captura): su
        contraseña nunca se demostró del dueño del correo, así que se quita, y la
        cuenta queda verificada. El que llama cierra sus sesiones. El dueño puede
        ponerse contraseña con «Olvidé mi contraseña».

        Returns:
            True si se la quedó; False si ya estaba verificada (no cambia nada)
        """
        if self.email_verified:
            return False
        self._password = None
        # Un «Olvidé mi contraseña» de antes del cambio de manos, tampoco, ni un
        # cambio de correo que pidiera quien la creó
        self._password_reset_token = None
        self._reset_token_expires_at = None
        self.cancel_email_change()
        self.confirm_email_ownership()
        return True

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
        gender: str | None = None,
        alias: str | None = None,
    ) -> None:
        """
        Actualiza la información personal del usuario (nombre, apellidos, país,
        género y alias).
        Solo emite evento si al menos uno de los campos cambió.
        El evento ahora incluye el cambio de country_code (old/new) si aplica.

        El alias sigue el convenio de country_code y gender: `None` significa
        "no se ha enviado" y la cadena vacía "quítamelo", que devuelve al
        usuario a su nombre real.
        """
        self._validate_profile_update(first_name, last_name, country_code_str, gender, alias)
        (
            first_name_changed,
            last_name_changed,
            country_code_changed,
            gender_changed,
            alias_changed,
            new_country_code,
            new_gender,
            new_alias,
            old_first_name,
            old_last_name,
            _old_country_code,
            old_alias,
        ) = self._detect_profile_changes(first_name, last_name, country_code_str, gender, alias)

        if (
            not first_name_changed
            and not last_name_changed
            and not country_code_changed
            and not gender_changed
            and not alias_changed
        ):
            return

        if first_name_changed:
            self._first_name = first_name
        if last_name_changed:
            self._last_name = last_name
        if country_code_changed:
            self._country_code = new_country_code
        if gender_changed:
            self._gender = new_gender
        if alias_changed:
            self._alias = new_alias

        self._updated_at = datetime.now()

        self._add_domain_event(
            UserProfileUpdatedEvent(
                user_id=str(self.id.value),
                old_first_name=old_first_name if first_name_changed else None,
                new_first_name=first_name if first_name_changed else None,
                old_last_name=old_last_name if last_name_changed else None,
                new_last_name=last_name if last_name_changed else None,
                old_alias=old_alias if alias_changed else None,
                new_alias=new_alias if alias_changed else None,
                updated_at=self.updated_at,
            )
        )

    # Cuánto vale el enlace que confirma un correo nuevo
    HORAS_PARA_CONFIRMAR_EL_CORREO = 24

    def request_email_change(self, new_email: str, ahora: datetime) -> str:
        """
        Pide cambiar el correo: el nuevo queda pendiente y la cuenta sigue con el de
        antes (y verificada, si lo estaba) hasta confirmarlo desde la dirección nueva.

        Pedir otro sustituye al pendiente: su token deja de valer.

        Returns:
            El token del enlace que va al correo nuevo

        Raises:
            ValueError: si es el mismo correo que ya tiene
        """
        nuevo = Email(new_email)
        if self.email is not None and nuevo == self.email:
            raise ValueError("El correo nuevo es el mismo que el actual")
        token = secrets.token_urlsafe(32)
        self._pending_email = str(nuevo.value)
        # Con hash: quien lea la BD no puede confirmar el cambio (auditoría OWASP)
        self._pending_email_token = hash_del_enlace(token)
        self._pending_email_expires_at = ahora + timedelta(
            hours=self.HORAS_PARA_CONFIRMAR_EL_CORREO
        )
        self._updated_at = datetime.now()
        return token

    def pending_email_token_matches(self, token: str) -> bool:
        """Si hay cambio pendiente y el token es el de su enlace (sin mirar la hora)."""
        guardado = self.pending_email_token
        if self._pending_email is None or not guardado:
            return False
        # En bytes: compare_digest con un str no ASCII lanzaba (un 500)
        return secrets.compare_digest(guardado.encode(), hash_del_enlace(token or "").encode())

    def confirm_email_change(self, token: str, ahora: datetime) -> None:
        """
        Confirma el correo pendiente con el token de su enlace: pasa a ser el de la
        cuenta, verificado. Un «Olvidé mi contraseña» pedido para el de antes no vale.

        Raises:
            EmailChangeInvalidError: si no hay ese cambio pendiente (otro token)
            EmailChangeExpiredError: si caducó (y se anula)
        """
        pendiente = self._pending_email
        if pendiente is None or not self.pending_email_token_matches(token):
            raise EmailChangeInvalidError("No pending email change with that token")
        if self.pending_email_expires_at is None or ahora > self.pending_email_expires_at:
            self.cancel_email_change()
            raise EmailChangeExpiredError("The pending email change expired")
        viejo = str(self.email.value) if self.email else ""
        self._email = Email(pendiente)
        self._email_verified = True
        self._verification_token = None
        self._verification_token_expires_at = None
        self._password_reset_token = None
        self._reset_token_expires_at = None
        self.cancel_email_change()
        self._add_domain_event(
            UserEmailChangedEvent(
                user_id=str(self.id.value),
                old_email=viejo,
                new_email=pendiente,
                changed_at=self._updated_at,
            )
        )

    def cancel_email_change(self) -> None:
        """Anula el cambio de correo pendiente: su enlace deja de valer."""
        self._pending_email = None
        self._pending_email_token = None
        self._pending_email_expires_at = None
        self._updated_at = datetime.now()

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

        self._email = new_email_vo
        self._email_verified = False  # Requiere nueva verificación
        # El enlace de verificación del correo de antes tampoco vale para este, ni un
        # cambio de correo pendiente (lo sustituye este)
        self._verification_token = None
        self._verification_token_expires_at = None
        self.cancel_email_change()
        # Un «Olvidé mi contraseña» pedido para el correo de antes no vale para este:
        # verificaría el nuevo sin que nadie lo haya demostrado (#749)
        self._password_reset_token = None
        self._reset_token_expires_at = None
        self._updated_at = datetime.now()

        self._add_domain_event(
            UserEmailChangedEvent(
                user_id=str(self.id.value),
                old_email=old_email_str,
                new_email=new_email,
                changed_at=self.updated_at,
            )
        )

    def change_password(self, new_password: str | Password) -> None:
        """
        Cambia el password del usuario.

        Args:
            new_password: Nuevo password en texto plano, o ya calculado con
                `Password.from_plain_text` (BE #283: el bcrypt se hace fuera de la
                transacción y aquí no se repite). Otro Password lanza ValueError

        Raises:
            ValueError: Si el password no es válido
        """
        self._password = _como_password(new_password)
        self._updated_at = datetime.now()

        self._add_domain_event(
            UserPasswordChangedEvent(
                user_id=str(self.id.value),
                changed_at=self.updated_at,
                changed_from_ip=None,
            )
        )

    def generate_verification_token(self, ahora: datetime | None = None) -> str:
        """
        Genera el enlace de verificación del correo: vale 48 horas (fase 3, C1).

        Se guarda su SHA-256, nunca el token (C3): quien lea la BD no puede verificar.

        Args:
            ahora: La hora de referencia (por defecto, la de ahora)

        Returns:
            str: El token en claro, para el enlace del correo
        """
        token = secrets.token_urlsafe(32)
        self.set_verification_token(token, ahora=ahora)
        self._updated_at = datetime.now()
        return token

    def set_verification_token(self, token: str, ahora: datetime | None = None) -> None:
        """
        Apunta un token de verificación ya generado (y ya enviado): su hash y 48 horas.

        A diferencia de `generate_verification_token()`, no genera el token ni toca
        `updated_at`. Existe para el reenvío, que genera el token ANTES de enviarlo
        y solo lo guarda si el envío salió (ver `ResendVerificationEmailUseCase`).

        Args:
            token: Token de verificación generado previamente
            ahora: La hora de referencia (por defecto, la de ahora)
        """
        self._verification_token = hash_del_enlace(token)
        self._verification_token_expires_at = (
            ahora or datetime.now()
        ) + VERIFICATION_TOKEN_LIFETIME

    def verify_email(self, token: str, ahora: datetime | None = None) -> bool:
        """
        Verifica el email del usuario usando el token proporcionado.

        Args:
            token: Token de verificación
            ahora: La hora de referencia (por defecto, la de ahora)

        Returns:
            bool: True si la verificación fue exitosa

        Raises:
            VerificationTokenExpiredError: Si el token es el suyo pero pasaron 48 horas
            ValueError: Si el email ya está verificado o el token es inválido (otro, o
                uno guardado en claro antes del cambio, o uno sin caducidad)
        """
        if self.email_verified:
            raise ValueError("El email ya está verificado")

        guardado = self.verification_token
        if not guardado or not secrets.compare_digest(
            guardado.encode(), hash_del_enlace(token or "").encode()
        ):
            raise ValueError("Token de verificación inválido")
        caduca = self.verification_token_expires_at
        if caduca is None:
            # Sin caducidad no se da por bueno (no lo escribe ningún camino actual)
            raise ValueError("Token de verificación inválido")
        if (ahora or datetime.now()) > caduca:
            raise VerificationTokenExpiredError()

        # Token válido - proceder con verificación
        self._email_verified = True
        self._verification_token = None
        self._verification_token_expires_at = None
        self._updated_at = datetime.now()

        # Emitir evento de dominio
        self._add_domain_event(
            EmailVerifiedEvent(
                user_id=str(self.id.value),
                email=str(self.email.value),
                verified_at=self.updated_at,
            )
        )

        return True

    def reserva_el_aviso_de_registro(self, ahora: datetime) -> bool:
        """
        Reserva el aviso al dueño de que alguien se registró con su correo (fase 3, B2):
        como mucho uno cada 24 horas por cuenta. Si cabe, apunta la hora.

        Returns:
            True si toca avisar (y queda apuntado); False si ya se avisó en las 24 h
        """
        ultimo = self._register_attempt_notice_at
        if ultimo is not None and ahora - ultimo < REGISTER_ATTEMPT_NOTICE_INTERVAL:
            return False
        self._register_attempt_notice_at = ahora
        return True

    def reinicia_el_cupo_de_reset(self) -> None:
        """
        Pone a cero el cupo de correos de restablecer (fase 3, M-2): la cuenta acaba de
        demostrar que es suya (inicio de sesión o restablecimiento con éxito).
        """
        self._password_reset_emails_in_window = 0
        self._password_reset_window_started_at = None

    def cuenta_un_correo_de_reset(self, ahora: datetime) -> bool:
        """
        Cuenta un correo de restablecer contra el cupo de la cuenta (fase 3, H2): 10 en
        24 horas, vengan de la red que vengan. La ventana empieza en el primero.

        Returns:
            True si cabe (y queda contado); False si la cuenta agotó el cupo
        """
        inicio = self._password_reset_window_started_at
        if inicio is None or ahora - inicio >= PASSWORD_RESET_EMAILS_WINDOW:
            self._password_reset_window_started_at = ahora
            self._password_reset_emails_in_window = 0
        if self._password_reset_emails_in_window >= MAX_PASSWORD_RESET_EMAILS_PER_DAY:
            return False
        self._password_reset_emails_in_window += 1
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
        self,
        ip_address: str | None = None,
        user_agent: str | None = None,
        ahora: datetime | None = None,
    ) -> str:
        """
        Genera el enlace de restablecer la contraseña: vale una hora (fase 3, C2).

        Se guarda su SHA-256, nunca el token (C3). Pedir otro sustituye al anterior,
        que deja de valer. Emite un PasswordResetRequestedEvent para auditoría.

        Args:
            ip_address: IP desde donde se solicitó el reseteo (para auditoría)
            user_agent: User agent del navegador (para detección de anomalías)
            ahora: La hora de referencia (por defecto, la de ahora)

        Returns:
            str: El token en claro, para el enlace del correo
        """
        token = secrets.token_urlsafe(32)
        self._password_reset_token = hash_del_enlace(token)

        now = ahora or datetime.now()
        expires_at = now + PASSWORD_RESET_TOKEN_LIFETIME
        self._reset_token_expires_at = expires_at
        self._updated_at = now

        # Emitir evento de dominio para auditoría
        self._add_domain_event(
            PasswordResetRequestedEvent(
                user_id=str(self.id.value),
                email=str(self.email.value),
                requested_at=now,
                reset_token_expires_at=expires_at,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )

        return token

    def can_reset_password(self, token: str, ahora: datetime | None = None) -> bool:
        """
        Si el token es el del enlace de restablecer vigente y no ha caducado (1 hora).

        Args:
            token: Token de reseteo a validar (en claro, el del enlace)
            ahora: La hora de referencia (por defecto, la de ahora)

        Returns:
            bool: True si es el suyo y está en plazo

        Raises:
            InvalidResetTokenError: Si no hay ninguna solicitud de reseteo activa
        """
        if not self.password_reset_token:
            raise InvalidResetTokenError("No hay ninguna solicitud de reseteo de contraseña activa")

        # Se compara el hash (compare_digest, sin atajos por el tiempo): un token
        # guardado en claro antes del cambio no es el hash de nada que llegue
        if not secrets.compare_digest(
            self.password_reset_token.encode(), hash_del_enlace(token or "").encode()
        ):
            return False

        if not self.reset_token_expires_at:
            return False

        return (ahora or datetime.now()) <= self.reset_token_expires_at

    def reset_password(
        self,
        token: str,
        new_password: str | Password,
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
            new_password: Nueva contraseña en texto plano (será hasheada), o ya
                calculada con `Password.from_plain_text` (BE #283). Otra, ValueError
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
            raise InvalidResetTokenError()

        # Cambiar la contraseña (Password VO valida la política de seguridad); ya
        # calculada, tal cual (BE #283)
        self._password = _como_password(new_password)

        # Invalidar el token (uso único)
        self._password_reset_token = None
        self._reset_token_expires_at = None
        # Demostró que el buzón es suyo: el cupo diario de correos, a cero (M-2)
        self.reinicia_el_cupo_de_reset()

        # Actualizar timestamp
        now = datetime.now()
        self._updated_at = now

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

    def record_failed_login(self, ahora: datetime | None = None) -> str | None:
        """
        Apunta un login fallido en el RESPALDO de la cuenta (BE #732, ADR-043).

        Dos contadores de todas las redes juntas:
        - la hora (FAILED_ATTEMPTS_WINDOW): al fallo 25 se avisa al dueño, y con 50
          se bloquea 30 minutos;
        - el día (FAILED_ATTEMPTS_DAY_WINDOW): con 150 se bloquea 24 horas, contra
          el ataque lento que nunca llega a 50 en una hora.
        Cada ventana empieza en su primer fallo; tras un bloqueo, el siguiente fallo
        abre una nueva (el contador se queda en el tope hasta entonces, para que el
        log del desbloqueo diga los fallos de verdad). El bloqueo solo frena a los
        dispositivos desconocidos: el fiable del dueño y Google entran igual.

        Returns:
            «dia» o «respaldo» si este fallo bloquea, «aviso» si es el 25 de la
            hora, o None.
        """
        now = ahora or datetime.now()
        self._updated_at = now

        inicio = self._failed_login_window_started_at
        if (
            inicio is None
            or now - inicio >= FAILED_ATTEMPTS_WINDOW
            or self._failed_login_attempts >= MAX_FAILED_ATTEMPTS
        ):
            self._failed_login_attempts = 0
            self._failed_login_window_started_at = now
        self._failed_login_attempts += 1

        dia = self._failed_login_day_window_started_at
        if (
            dia is None
            or now - dia >= FAILED_ATTEMPTS_DAY_WINDOW
            or self._failed_login_day_attempts >= MAX_FAILED_ATTEMPTS_PER_DAY
        ):
            self._failed_login_day_attempts = 0
            self._failed_login_day_window_started_at = now
        self._failed_login_day_attempts += 1

        if self._failed_login_day_attempts >= MAX_FAILED_ATTEMPTS_PER_DAY:
            self._bloquea(now, now + DAY_LOCKOUT, self._failed_login_day_attempts)
            return "dia"
        if self._failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            self._bloquea(
                now, now + timedelta(minutes=LOCKOUT_DURATION_MINUTES), self._failed_login_attempts
            )
            return "respaldo"
        if self._failed_login_attempts == FAILED_ATTEMPTS_EARLY_NOTICE:
            return "aviso"
        return None

    def _bloquea(self, ahora: datetime, hasta: datetime, fallos: int) -> None:
        """Bloquea el respaldo hasta `hasta`, con los fallos del contador que lo bloqueó."""
        self._locked_until = hasta
        self._add_domain_event(
            AccountLockedEvent(
                user_id=str(self.id.value),
                locked_until=hasta,
                failed_attempts=fallos,
                locked_at=ahora,
            )
        )

    @property
    def failed_login_attempts_for_audit(self) -> int:
        """Los fallos que cuentan para la auditoría: el mayor de la hora y del día.

        Con el bloqueo de 24 horas, la hora puede llevar 3 y el día 150 (CodeRabbit).
        """
        return max(self._failed_login_attempts, self._failed_login_day_attempts)

    def is_locked(self, ahora: datetime | None = None) -> bool:
        """
        Si el RESPALDO de la cuenta está bloqueado ahora (se acaba solo a los 30 min).
        """
        if self.locked_until is None:
            return False
        return (ahora or datetime.now()) < self.locked_until

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
            - Solo accesible por Admin (lo comprueba la ruta con require_admin)
            - Quién desbloqueó queda en el log de seguridad (lo escribe el caso de uso)
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
        # Solo una cuenta bloqueada: un contador viejo de fallos no es un bloqueo
        if not self.is_locked():
            raise ValueError("La cuenta no está bloqueada")

        now = datetime.now()
        old_locked_until = self.locked_until
        old_failed_attempts = self.failed_login_attempts_for_audit

        # Resetear estado de bloqueo
        self._failed_login_attempts = 0
        self._locked_until = None
        self._failed_login_window_started_at = None
        self._failed_login_day_attempts = 0
        self._failed_login_day_window_started_at = None
        self._updated_at = now

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

    def set_is_admin(self, is_admin: bool) -> None:
        """Concede o revoca privilegios de administrador (solo desde el panel de admin)."""
        self._is_admin = is_admin
        self._updated_at = datetime.now()

    # === Account Deactivation Methods (Admin) ===

    def deactivate(self, deactivated_by_user_id: str) -> None:
        """
        Desactiva la cuenta del usuario (solo Admin, desde el panel de administración).

        Una cuenta desactivada no puede iniciar sesión (ver LoginUserUseCase),
        pero conserva todos sus datos (torneos, partidas, amistades) intactos.
        Es una acción reversible mediante reactivate().

        Emite AccountDeactivatedEvent para auditoría.

        Args:
            deactivated_by_user_id: ID del admin que realiza la desactivación

        Raises:
            ValueError: Si la cuenta ya está desactivada
        """
        if not self._is_active:
            raise ValueError("Account is already deactivated")

        now = datetime.now()
        self._is_active = False
        self._updated_at = now

        self._add_domain_event(
            AccountDeactivatedEvent(
                user_id=str(self.id.value),
                deactivated_by_user_id=deactivated_by_user_id,
                deactivated_at=now,
            )
        )

    def reactivate(self, reactivated_by_user_id: str) -> None:
        """
        Reactiva una cuenta previamente desactivada por un admin.

        Emite AccountReactivatedEvent para auditoría.

        Args:
            reactivated_by_user_id: ID del admin que realiza la reactivación

        Raises:
            ValueError: Si la cuenta ya está activa
        """
        if self._is_active:
            raise ValueError("Account is already active")

        now = datetime.now()
        self._is_active = True
        self._updated_at = now

        self._add_domain_event(
            AccountReactivatedEvent(
                user_id=str(self.id.value),
                reactivated_by_user_id=reactivated_by_user_id,
                reactivated_at=now,
            )
        )

    def __str__(self) -> str:
        """Representación string del usuario (sin mostrar password)."""
        return f"User(id={self.id}, email={self.email}, name={self.get_full_name()})"
