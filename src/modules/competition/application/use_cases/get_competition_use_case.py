"""
Caso de Uso: Obtener Competition.

Permite obtener los detalles de una competicion por su ID.
"""

from src.modules.competition.application.exceptions import CompetitionNotFoundError
from src.modules.competition.application.ports.competition_timezone import (
    ICompetitionTimezone,
)
from src.modules.competition.application.services.enrollment_opener import (
    EnrollmentOpener,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId


class GetCompetitionUseCase:
    """
    Caso de uso para obtener una competicion por su ID.

    Cualquier usuario puede consultar una competicion.

    **Consultar puede abrirla** (BE #319). No hay ningun proceso programado en
    el backend, asi que «las inscripciones se abren solas el miercoles a las
    nueve» significa que las abre la primera persona que pasa por ahi despues de
    esa hora. Es el mismo criterio con el que la anotacion abre al llegar el
    primer golpe (BE #305), y la razon de que esta consulta escriba.

    Orquesta:
    1. Buscar la competicion por ID
    2. Abrirla si ya le tocaba
    3. Retornar la entidad (la conversion a DTO es responsabilidad de la capa de presentacion)
    """

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        zona_del_campo: ICompetitionTimezone | None = None,
    ):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
            zona_del_campo: De donde sale la zona horaria del campo que se juega.
                Sin el, la apertura programada no se dispara — la hora escrita
                no significa nada sin saber de donde es.
        """
        self._uow = uow
        self._zona_del_campo = zona_del_campo

    async def execute(self, competition_id: CompetitionId) -> Competition | None:
        """
        Ejecuta el caso de uso de consulta de competicion.

        Retorna la entidad Competition directamente.

        Args:
            competition_id: ID de la competicion a consultar

        Returns:
            Competition: Entidad de la competicion

        Raises:
            CompetitionNotFoundError: Si la competicion no existe
        """
        async with self._uow:
            # Buscar la competicion
            competition = await self._uow.competitions.find_by_id(competition_id)

            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {competition_id.value}"
                )

            await EnrollmentOpener.abrir_las_que_toquen(
                [competition], self._uow, self._zona_del_campo
            )

            return competition

    async def tiene_equipos(self, competition_id: CompetitionId) -> bool:
        """Indica si la competición ya tiene los equipos repartidos (FE #692).

        La ficha lo necesita para ofrecer el botón correcto: con equipos, los
        capitanes ya no se cambian, y una competición reabierta solo se vuelve a
        cerrar con «Cerrar inscripciones», porque reabrir no deshace el reparto.
        No escribe nada: es una pregunta.
        """
        async with self._uow:
            reparto = await self._uow.team_assignments.find_by_competition(competition_id)
            return reparto is not None
