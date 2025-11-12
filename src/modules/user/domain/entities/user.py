from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List
import secrets

from ..value_objects.user_id import UserId
from ..value_objects.email import Email
from ..value_objects.password import Password
from src.shared.domain.events.domain_event import DomainEvent


class User:
    """
    Entidad User - Representa un usuario en el sistema.
    
    Un usuario es alguien que puede registrarse, hacer login
    y participar en torneos Ryder Cup.
    """
    
    def __init__(
        self,
        id: Optional[UserId],
        email: Optional[Email],
        password: Optional[Password],
        first_name: str,
        last_name: str,
        handicap: Optional[float] = None,
        handicap_updated_at: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        email_verified: bool = False,
        verification_token: Optional[str] = None,
        domain_events: Optional[List[DomainEvent]] = None
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
        self._domain_events: List[DomainEvent] = domain_events or []
    
    def get_full_name(self) -> str:
        """Devuelve el nombre completo del usuario."""
        return f"{self.first_name} {self.last_name}".strip()
    
    def has_valid_email(self) -> bool:
        """Verifica si el usuario tiene un email válido."""
        return self.email is not None
    
    def is_valid(self) -> bool:
        """Verifica si el usuario es válido (todos los campos requeridos)."""
        return (
            self.has_valid_email() and
            self.first_name.strip() != "" and
            self.last_name.strip() != "" and
            self.password is not None
        )
    
    def verify_password(self, plain_password: str) -> bool:
        """Verifica si el password plano coincide con el hasheado."""
        if self.password is None:
            return False
        return self.password.verify(plain_password)

    def update_handicap(self, new_handicap: Optional[float]) -> None:
        """
        Actualiza el hándicap del usuario y emite un evento de dominio.

        Valida que el hándicap esté en el rango permitido (-10.0 a 54.0)
        y solo emite el evento si el valor realmente cambió.

        Args:
            new_handicap: Nuevo valor del hándicap (None para eliminar)

        Raises:
            ValueError: Si el hándicap no está en el rango válido
        """
        from ..value_objects.handicap import Handicap
        from ..events.handicap_updated_event import HandicapUpdatedEvent

        old_handicap = getattr(self, 'handicap', None)

        # Validar si es un Handicap válido usando el Value Object
        if new_handicap is not None:
            validated = Handicap(new_handicap)  # Valida el rango
            self.handicap = validated.value
        else:
            self.handicap = None

        # Actualizar timestamps
        now = datetime.now()
        self.handicap_updated_at = now
        self.updated_at = now

        # Emitir evento solo si cambió
        if old_handicap != self.handicap:
            self._add_domain_event(HandicapUpdatedEvent(
                user_id=str(self.id.value),
                old_handicap=old_handicap,
                new_handicap=self.handicap,
                updated_at=self.updated_at
            ))

    @classmethod
    def create(cls, first_name: str, last_name: str, email_str: str, plain_password: str) -> 'User':
        """
        Factory method para crear usuario con Value Objects.
        
        Args:
            first_name: Nombre del usuario
            last_name: Apellido del usuario  
            email_str: Email en formato string
            plain_password: Password en texto plano
            
        Returns:
            User: Nueva instancia con ID generado y Value Objects
        """
        user_id = UserId.generate()
        email = Email(email_str)
        password = Password.from_plain_text(plain_password)
        
        user = cls(
            id=user_id,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            handicap=None,
            handicap_updated_at=None,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Generar evento de registro
        from src.modules.user.domain.events.user_registered_event import UserRegisteredEvent
        user._add_domain_event(UserRegisteredEvent(
            user_id=str(user_id.value),
            email=email_str,
            first_name=first_name,
            last_name=last_name
        ))
        
        return user
    
    # === Métodos para manejo de eventos de dominio ===
    
    def _add_domain_event(self, event: DomainEvent) -> None:
        """Agrega un evento de dominio a la colección interna."""
        if not hasattr(self, '_domain_events'):
            self._domain_events = []
        self._domain_events.append(event)
    
    def get_domain_events(self) -> List[DomainEvent]:
        """Obtiene una copia de todos los eventos de dominio pendientes."""
        if not hasattr(self, '_domain_events'):
            self._domain_events = []
        return self._domain_events.copy()
    
    def clear_domain_events(self) -> None:
        """Limpia todos los eventos de dominio de la colección."""
        if not hasattr(self, '_domain_events'):
            self._domain_events = []
        self._domain_events.clear()

    def has_domain_events(self) -> bool:
        """Verifica si la entidad tiene eventos de dominio pendientes."""
        if not hasattr(self, '_domain_events'):
            self._domain_events = []
        return len(self._domain_events) > 0

    def record_logout(self, logged_out_at: datetime, token_used: Optional[str] = None) -> None:
        """
        Registra un evento de logout para este usuario.
        
        Args:
            logged_out_at: Timestamp del logout
            token_used: Token JWT utilizado (opcional)
        """
        from src.modules.user.domain.events.user_logged_out_event import UserLoggedOutEvent
        
        self._add_domain_event(UserLoggedOutEvent(
            user_id=str(self.id.value),
            logged_out_at=logged_out_at,
            token_used=token_used
        ))

    def record_login(self, logged_in_at: datetime, ip_address: Optional[str] = None,
                    user_agent: Optional[str] = None, session_id: Optional[str] = None) -> None:
        """
        Registra un evento de login exitoso para este usuario.

        Args:
            logged_in_at: Timestamp del login exitoso
            ip_address: Dirección IP desde donde se hizo login (opcional)
            user_agent: User agent del browser/app (opcional)
            session_id: ID de la sesión creada (opcional)
        """
        from src.modules.user.domain.events.user_logged_in_event import UserLoggedInEvent

        self._add_domain_event(UserLoggedInEvent(
            user_id=str(self.id.value),
            logged_in_at=logged_in_at,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            login_method="email"  # Por ahora solo email, preparado para OAuth
        ))

    def update_profile(self, first_name: Optional[str] = None, last_name: Optional[str] = None) -> None:
        """
        Actualiza la información personal del usuario (nombre y apellidos).

        Solo emite evento si al menos uno de los campos cambió.

        Args:
            first_name: Nuevo nombre (None = no cambiar)
            last_name: Nuevo apellido (None = no cambiar)

        Raises:
            ValueError: Si ambos parámetros son None o si los valores son strings vacíos
        """
        from src.modules.user.domain.events.user_profile_updated_event import UserProfileUpdatedEvent

        # Validar que al menos un campo se quiera actualizar
        if first_name is None and last_name is None:
            raise ValueError("At least one field (first_name or last_name) must be provided")

        # Validar que los campos no sean strings vacíos
        if first_name is not None and first_name.strip() == "":
            raise ValueError("first_name cannot be empty")
        if last_name is not None and last_name.strip() == "":
            raise ValueError("last_name cannot be empty")

        # Guardar valores anteriores
        old_first_name = self.first_name
        old_last_name = self.last_name

        # Determinar qué cambió
        first_name_changed = first_name is not None and first_name != old_first_name
        last_name_changed = last_name is not None and last_name != old_last_name

        # Si nada cambió realmente, no hacer nada
        if not first_name_changed and not last_name_changed:
            return

        # Aplicar cambios
        if first_name_changed:
            self.first_name = first_name
        if last_name_changed:
            self.last_name = last_name

        # Actualizar timestamp
        self.updated_at = datetime.now()

        # Emitir evento
        self._add_domain_event(UserProfileUpdatedEvent(
            user_id=str(self.id.value),
            old_first_name=old_first_name if first_name_changed else None,
            new_first_name=first_name if first_name_changed else None,
            old_last_name=old_last_name if last_name_changed else None,
            new_last_name=last_name if last_name_changed else None,
            updated_at=self.updated_at
        ))

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
        from src.modules.user.domain.events.user_email_changed_event import UserEmailChangedEvent

        new_email_vo = Email(new_email)
        old_email_str = str(self.email.value) if self.email else ""

        if new_email == old_email_str:
            return  # No cambió nada

        self.email = new_email_vo
        self.email_verified = False  # Requiere nueva verificación
        self.updated_at = datetime.now()

        self._add_domain_event(UserEmailChangedEvent(
            user_id=str(self.id.value),
            old_email=old_email_str,
            new_email=new_email,
            changed_at=self.updated_at
        ))

    def change_password(self, new_password: str) -> None:
        """
        Cambia el password del usuario.

        Args:
            new_password: Nuevo password en texto plano

        Raises:
            ValueError: Si el password no es válido
        """
        from src.modules.user.domain.events.user_password_changed_event import UserPasswordChangedEvent

        new_password_vo = Password.from_plain_text(new_password)
        self.password = new_password_vo
        self.updated_at = datetime.now()

        self._add_domain_event(UserPasswordChangedEvent(
            user_id=str(self.id.value),
            changed_at=self.updated_at,
            changed_from_ip=None
        ))

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
        from src.modules.user.domain.events.email_verified_event import EmailVerifiedEvent

        if self.email_verified:
            raise ValueError("El email ya está verificado")

        if self.verification_token != token:
            raise ValueError("Token de verificación inválido")

        # Token válido - proceder con verificación
        self.email_verified = True
        self.verification_token = None
        self.updated_at = datetime.now()

        # Emitir evento de dominio
        self._add_domain_event(EmailVerifiedEvent(
            user_id=str(self.id.value),
            email=str(self.email.value),
            verified_at=self.updated_at
        ))

        return True

    def is_email_verified(self) -> bool:
        """
        Verifica si el email del usuario ha sido confirmado.

        Returns:
            bool: True si el email está verificado
        """
        return self.email_verified

    def __str__(self) -> str:
        """Representación string del usuario (sin mostrar password)."""
        return f"User(id={self.id}, email={self.email}, name={self.get_full_name()})"