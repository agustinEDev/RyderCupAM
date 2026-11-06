"""Account Locked Event - Emitido cuando una cuenta es bloqueada por intentos fallidos."""

from datetime import datetime

from src.shared.domain.events.domain_event import DomainEvent


class AccountLockedEvent(DomainEvent):
    """
    Evento de dominio emitido cuando una cuenta de usuario es bloqueada
    debido a múltiples intentos fallidos de login.

    Este evento se dispara automáticamente cuando:
    - el respaldo de la cuenta llega a MAX_FAILED_ATTEMPTS (50 en una hora, todas
      las redes; BE #732)
    - locked_until es asignado (NOW + 30 minutos)
    Los bloqueos de cada red los lleva el freno del login, en memoria, sin evento

    Security (OWASP A09):
        - Severity: HIGH (indica potencial ataque de fuerza bruta)
        - Requiere notificación al usuario por email
        - Puede disparar alertas de seguridad

    Attributes:
        user_id: ID del usuario cuya cuenta fue bloqueada
        locked_until: Timestamp cuando expira el bloqueo (30 min desde ahora)
        failed_attempts: Número de intentos fallidos que causaron el bloqueo
        locked_at: Timestamp cuando se bloqueó la cuenta
    """

    def __init__(
        self,
        user_id: str,
        locked_until: datetime,
        failed_attempts: int,
        locked_at: datetime,
    ):
        super().__init__()
        self.user_id = user_id
        self.locked_until = locked_until
        self.failed_attempts = failed_attempts
        self.locked_at = locked_at
