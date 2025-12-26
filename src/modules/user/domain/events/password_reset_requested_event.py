from datetime import datetime

from src.shared.domain.events.domain_event import DomainEvent


class PasswordResetRequestedEvent(DomainEvent):
    """
    Evento de dominio que se emite cuando un usuario solicita resetear su contraseña.

    Este evento se genera en el momento en que el usuario completa el formulario
    "Olvidé mi contraseña" y se le envía un email con el token de reseteo.

    Attributes:
        user_id: ID del usuario que solicita el reseteo
        email: Email del usuario (para envío de notificación)
        requested_at: Timestamp de cuándo se solicitó el reseteo
        reset_token_expires_at: Timestamp de expiración del token (24 horas desde requested_at)
        ip_address: Dirección IP desde donde se hizo la solicitud (para auditoría)
        user_agent: User agent del navegador (para detección de anomalías)

    Security:
        - Este evento se registra en el SecurityLogger para auditoría
        - Permite detectar intentos masivos de reseteo (posible ataque)
        - IP y User-Agent ayudan a validar la legitimidad de la solicitud
    """

    def __init__(
        self,
        user_id: str,
        email: str,
        requested_at: datetime,
        reset_token_expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None
    ):
        super().__init__()
        self.user_id = user_id
        self.email = email
        self.requested_at = requested_at
        self.reset_token_expires_at = reset_token_expires_at
        self.ip_address = ip_address
        self.user_agent = user_agent

    def __repr__(self) -> str:
        return (
            f"PasswordResetRequestedEvent(user_id={self.user_id}, "
            f"email={self.email}, requested_at={self.requested_at}, "
            f"expires_at={self.reset_token_expires_at})"
        )
