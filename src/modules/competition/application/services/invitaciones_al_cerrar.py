"""
Al cerrar la inscripción, las invitaciones pendientes se quedan sin plaza (#710).

Decidido el 24 sep: aceptar una pendiente con el draft hecho descuadraba los
partidos. La inscripción se cierra por dos caminos —cerrarla a mano y nombrar a
los capitanes—, así que la regla vive aquí y la llaman los dos.
"""

from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId


async def sin_plaza_para_las_pendientes(
    uow: CompetitionUnitOfWorkInterface, competition_id: CompetitionId
) -> None:
    """Rechaza por falta de plazas las pendientes; las ya caducadas, caducadas.

    Una que caducó sin que nadie la pasara a EXPIRED no se quedó sin plaza: se
    quedó sin respuesta, y así debe constar.
    """
    for invitacion in await uow.invitations.find_pending_by_competition(competition_id):
        invitacion.check_expiration()
        if invitacion.is_pending():
            invitacion.reject_for_no_room()
        await uow.invitations.update(invitacion)
