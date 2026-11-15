"""
La invitación que la ficha ofrece aceptar o rechazar (tabla del 27 oct 2026, filas 13-16).

Solo cuando aceptarla puede salir bien: sin inscripción (aceptar la crea, y con
otra ya hecha daría 400) y en un estado en que la política deja aceptar. Si no,
nada: se sigue pudiendo rechazar desde «Mis invitaciones» (Agustín, 27 oct).
"""

from datetime import datetime

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.exceptions.competition_violations import (
    InvitationCompetitionStatusViolation,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.competition_policy import CompetitionPolicy
from src.modules.competition.domain.value_objects.invitacion_pendiente import (
    InvitacionPendiente,
)
from src.modules.user.domain.value_objects.user_id import UserId


async def invitacion_pendiente(
    uow: CompetitionUnitOfWorkInterface,
    competition: Competition,
    quien: UserId,
    email: str | None,
    ahora: datetime,
) -> InvitacionPendiente | None:
    """
    La de quien mira, por su usuario o su correo; la más reciente. Quien organiza
    no la tiene, y ni se pregunta. Con el `uow` abierto; el reloj, el de
    `Invitation.is_expired` (hora local sin zona).
    """
    if competition.is_creator(quien):
        return None
    return await uow.invitations.pendiente_de(quien, email, competition.id, ahora)


def se_le_ofrece_aceptar(
    competition: Competition, pendiente: InvitacionPendiente | None, *, inscrito: bool
) -> bool:
    """Si la ficha le ofrece aceptarla: la tiene, no está inscrito y la política deja aceptar."""
    if pendiente is None or inscrito:
        return False
    try:
        CompetitionPolicy.can_accept_invitation(competition.status)
    except InvitationCompetitionStatusViolation:
        return False
    return True
