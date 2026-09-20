"""
Caso de Uso: Obtener Competition.

Permite obtener los detalles de una competicion por su ID.
"""

from src.modules.competition.application.exceptions import CompetitionNotFoundError
from src.modules.competition.application.ports.competition_timezone import (
    ICompetitionTimezone,
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

            await self._abrir_si_toca(competition)

            return competition

    async def _abrir_si_toca(self, competition: Competition) -> None:
        """Abre las inscripciones si ya paso su hora.

        La hora escrita es local del campo donde se juega, asi que hace falta
        su zona. Sin campo todavia —o con uno cuya zona no se conoce— el torneo
        espera: no se adivina, porque abrir a deshora anuncia una cosa y hace
        otra (decidido el 20 sep).
        """
        if self._zona_del_campo is None:
            return

        # Las dos preguntas baratas primero. Casi ninguna competicion programa
        # su apertura, y resolver la zona baja a la base de datos a traerse el
        # campo entero con sus barras para leer una cadena
        if competition.enrollment_opens_at is None:
            return
        if not competition.allows_enrollment_opening():
            return

        zona = await self._zona_del_campo.for_competition(competition)
        if not competition.due_to_open(zona):
            return

        competition.activate()
        await self._uow.competitions.update(competition)
