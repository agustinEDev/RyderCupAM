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


async def pendiente_vigente(
    uow: CompetitionUnitOfWorkInterface, email: str, competition_id: CompetitionId
) -> tuple[Invitation | None, Invitation | None]:
    """
    La invitación pendiente que impide mandar otra a ese correo.

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
        return None, None
    pendiente.check_expiration()
    if pendiente.is_pending():
        return pendiente, None
    await uow.invitations.update(pendiente)
    return None, pendiente
