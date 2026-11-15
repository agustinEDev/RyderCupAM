"""
Si una invitación pendiente impide mandar otra (release social 2, 27 oct 2026).

Una pendiente que ya caducó sin que nadie la abriera sigue constando PENDING:
solo pasa a EXPIRED al leerla. Al invitar se lee aquí, y si ya caducó se da por
caducada y deja mandar la nueva, en vez de contestar «ya hay una pendiente».
"""

from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus


async def pendiente_vigente(
    uow: CompetitionUnitOfWorkInterface, email: str, competition_id: CompetitionId
) -> tuple[Invitation | None, Invitation | None]:
    """
    La invitación viva que impide mandar otra a ese correo: pendiente, o en espera
    de que se reabra (revisión, 15 nov 2026: abierta a la vez que se cerraba).

    Args:
        uow: La unidad de trabajo de la petición
        email: El correo al que se invita
        competition_id: La competición

    Returns:
        (la pendiente aún vigente, la que acaba de quedar EXPIRED): como mucho
        una de las dos. La caducada, para retirar su aviso al guardar, como al
        caducar leyendo la lista (CodeRabbit)
    """
    pendiente = await uow.invitations.find_pending_by_email_and_competition(email, competition_id)
    if pendiente is None:
        en_espera = [
            i
            for i in await uow.invitations.find_by_competition_and_status_for_update(
                competition_id, InvitationStatus.ON_HOLD
            )
            if i.is_for_email(email)
        ]
        return (en_espera[0] if en_espera else None), None
    pendiente.check_expiration()
    if pendiente.is_pending():
        return pendiente, None
    await uow.invitations.update(pendiente)
    return None, pendiente
