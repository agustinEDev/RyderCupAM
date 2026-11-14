"""
Lo que ve el organizador de quién es una invitación (auditoría de la fase 6, B-01/B-03).

Invitando por id se leía el correo de cualquier usuario, y por correo se sabía si ese
correo tenía cuenta. Decidido por Agustín el 14 nov 2026:
- elegida a un usuario: su nombre (y su id), nunca su correo;
- tecleando un correo: solo ese correo, tenga cuenta o no, mientras no responda;
- tecleando un correo y ya respondida (aceptada o rechazada): también su nombre.

El invitado ve su invitación como siempre: esto es solo para quien la manda.
"""

from dataclasses import dataclass

from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.user.domain.value_objects.user_id import UserId

RESPONDIDAS = frozenset({InvitationStatus.ACCEPTED, InvitationStatus.DECLINED})


@dataclass(frozen=True)
class QuienEsElInvitado:
    """El correo, el usuario y el nombre que se enseñan al organizador."""

    email: str | None
    user_id: UserId | None
    nombre: str | None


def lo_que_ve_el_organizador(invitation: Invitation, nombre: str | None) -> QuienEsElInvitado:
    """
    Args:
        invitation: La invitación (al responderla, queda atada a quien la respondió)
        nombre: El nombre del invitado si tiene cuenta (o None)
    """
    # Sin usuario solo puede ser por correo, aunque no lleve la marca: así sale bien una
    # guardada por la release anterior mientras conviven (revisor de B-03)
    if not invitation.sent_by_email and invitation.invitee_user_id is not None:
        return QuienEsElInvitado(None, invitation.invitee_user_id, nombre)
    if invitation.status in RESPONDIDAS:
        return QuienEsElInvitado(invitation.invitee_email, invitation.invitee_user_id, nombre)
    return QuienEsElInvitado(invitation.invitee_email, None, None)
