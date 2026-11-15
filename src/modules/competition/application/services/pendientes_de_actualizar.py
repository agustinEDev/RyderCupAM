"""
PendientesDeActualizar - Quién falta en una actualización de hándicaps (#251).

Los inscritos sin hándicap personalizado que no tienen respuesta de la RFEG en
esa actualización (o la tienen fallida). La misma regla para la pasada, que les
pregunta, y para la ficha, que se los enseña al organizador.
"""

from collections.abc import Iterable, Mapping

from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    ActualizacionDeHandicaps,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    Candidato,
    Intento,
    RefrescoDeHandicapsService,
)
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.user.domain.value_objects.user_id import UserId


class PendientesDeActualizar:
    """Quién falta, en el orden de las inscripciones."""

    @staticmethod
    async def de(
        uow: CompetitionUnitOfWorkInterface, actualizacion: ActualizacionDeHandicaps
    ) -> list[UserId]:
        inscritos = await uow.enrollments.find_by_competition_and_status(
            actualizacion.competition_id, EnrollmentStatus.APPROVED
        )
        resultados = await uow.handicap_updates.resultados(actualizacion.id)
        return PendientesDeActualizar.de_lo_leido(inscritos, resultados)

    @staticmethod
    def de_lo_leido(
        inscritos: Iterable[Enrollment], resultados: Mapping[UserId, Intento]
    ) -> list[UserId]:
        """Lo mismo, con los inscritos aprobados y lo apuntado ya leídos."""
        candidatos = [
            Candidato(user_id=i.user_id, handicap_personalizado=i.has_custom_handicap())
            for i in inscritos
        ]
        return RefrescoDeHandicapsService.a_quien(
            candidatos, {u: i.resultado for u, i in resultados.items()}
        )
