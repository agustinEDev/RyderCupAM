"""Una invitación que aún se puede aceptar: lo justo para ofrecerla (27 oct 2026)."""

from dataclasses import dataclass
from datetime import datetime

from src.modules.competition.domain.value_objects.invitation_id import InvitationId


@dataclass(frozen=True)
class InvitacionPendiente:
    """Su id, para responderla, y cuándo caduca (hora del servidor, sin zona)."""

    id: InvitationId
    expires_at: datetime
