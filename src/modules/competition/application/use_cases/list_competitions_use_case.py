"""
Caso de Uso: Listar Competitions con filtros.

Permite obtener lista de competiciones con filtros opcionales.
"""

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_status import (
    CompetitionStatus,
)
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.user.domain.value_objects.user_id import UserId

# Quien tiene una invitacion o una solicitud en marcha necesita poder mirar la
# competicion antes de decidir. Quien fue rechazado, se retiro o cancelo, no:
# su fila sigue en la tabla, pero ya no esta dentro (BE #318)
ESTADOS_QUE_DEJAN_VER = {
    EnrollmentStatus.APPROVED,
    EnrollmentStatus.REQUESTED,
    EnrollmentStatus.INVITED,
}


class ListCompetitionsUseCase:
    """
    Caso de uso para listar competiciones con filtros opcionales.

    CLEAN ARCHITECTURE: Este use case retorna ENTIDADES de dominio, NO DTOs.
    La conversión a DTOs y el cálculo de campos de presentación (is_creator,
    enrolled_count, location_formatted) es responsabilidad de la capa de
    presentación (API Layer).

    Orquesta:
    1. Aplicar filtros opcionales (status, creator_id)
    2. Retornar lista de entidades Competition

    Responsabilidades:
    - Filtrado por criterios de negocio
    - Coordinar acceso a repositorios mediante UoW

    NO es responsabilidad del use case:
    - Formatear datos para presentación
    - Calcular campos derivados para UI
    - Convertir entidades a DTOs
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para acceso a repositorios
        """
        self._uow = uow

    async def execute(
        self,
        status: str | None = None,
        creator_id: str | None = None,
        search_name: str | None = None,
        search_creator: str | None = None,
        viewer_id: str | None = None,
        is_admin: bool = False,
    ) -> list[Competition]:
        """
        Ejecuta el caso de uso de listado de competiciones.

        Args:
            status: Filtro opcional por estado (ej: "ACTIVE", "DRAFT")
            creator_id: Filtro opcional por creador (UUID string)
            search_name: Búsqueda parcial case-insensitive en nombre de competición
            search_creator: Búsqueda parcial case-insensitive en nombre del creador

        Returns:
            Lista de entidades Competition

        Raises:
            ValueError: Si los parámetros de filtro son inválidos
        """
        async with self._uow:
            # Si hay parámetros de búsqueda, usar el método find_by_filters
            if search_name or search_creator:
                encontradas = await self._fetch_with_search(
                    search_name=search_name,
                    search_creator=search_creator,
                    status=status,
                    creator_id=creator_id,
                )
                return await self.visibles_para(encontradas, viewer_id, is_admin)

            # Si no hay búsqueda, usar el método antiguo (compatibilidad)
            competitions = await self._fetch_filtered_competitions(status, creator_id)
            return await self.visibles_para(competitions, viewer_id, is_admin)

    async def visibles_para(
        self,
        competitions: list[Competition],
        viewer_id: str | None,
        is_admin: bool = False,
    ) -> list[Competition]:
        """Aparta las privadas de quien no esta dentro (BE #318).

        Publico a proposito: lo usa este caso de uso y tambien la ruta, que
        anade por su cuenta las competiciones que salen de tus inscripciones.
        Ese camino se salto el filtro y dejaba al expulsado recuperando la
        privada de la que acababan de echarlo.

        Una privada la ve su creador, quien esta dentro y quien tiene una
        invitacion o una solicitud en marcha — ese necesita mirarla antes de
        decidir. No la ve quien fue rechazado, se retiro o cancelo: su fila
        sigue en la tabla, pero ya no esta dentro.

        Un admin lo ve todo: puede editarla y borrarla, asi que no verla en el
        listado le dejaria con el permiso y sin la puerta.

        Sin saber quien mira, solo se ensena lo publico.
        """
        if is_admin:
            return competitions

        publicas = [c for c in competitions if c.visibility.is_discoverable()]
        privadas = [c for c in competitions if not c.visibility.is_discoverable()]
        if not privadas or viewer_id is None:
            return publicas

        quien = UserId(viewer_id)
        # UNA consulta por quien mira, no una por competicion: el listado trae
        # hasta 100 y el endpoint llama una vez por cada estado del filtro
        inscripciones = await self._uow.enrollments.find_by_user(quien)
        dentro_de = {
            e.competition_id for e in inscripciones if e.status in ESTADOS_QUE_DEJAN_VER
        }

        visibles = {c.id for c in publicas}
        visibles |= {
            c.id for c in privadas if c.creator_id == quien or c.id in dentro_de
        }
        # En el orden en que venian, que es el que decidio la consulta
        return [c for c in competitions if c.id in visibles]

    async def _fetch_filtered_competitions(
        self,
        status: str | None,
        creator_id: str | None,
    ) -> list[Competition]:
        """
        Obtiene competiciones aplicando filtros.

        Args:
            status: Filtro por estado (opcional)
            creator_id: Filtro por creador (opcional)

        Returns:
            Lista de entidades Competition
        """
        # Si hay filtro por status
        if status:
            status_enum = CompetitionStatus(status.upper())
            competitions = await self._uow.competitions.find_by_status(status_enum)

            # Si además hay filtro por creator_id, filtrar en memoria
            if creator_id:
                creator_user_id = UserId(creator_id)
                competitions = [c for c in competitions if c.creator_id == creator_user_id]

            return competitions

        # Si solo hay filtro por creator_id
        if creator_id:
            creator_user_id = UserId(creator_id)
            return await self._uow.competitions.find_by_creator(creator_user_id)

        # Sin filtros: retornar todas las competiciones
        return await self._uow.competitions.find_all()

    async def _fetch_with_search(
        self,
        search_name: str | None,
        search_creator: str | None,
        status: str | None,
        creator_id: str | None,
    ) -> list[Competition]:
        """
        Obtiene competiciones usando búsqueda avanzada.

        Args:
            search_name: Búsqueda en nombre de competición
            search_creator: Búsqueda en nombre del creador
            status: Filtro por estado (opcional)
            creator_id: Filtro por creador (opcional)

        Returns:
            Lista de entidades Competition
        """
        # Convertir status string a enum si existe
        status_enum = CompetitionStatus(status.upper()) if status else None

        # Convertir creator_id string a UserId si existe
        creator_user_id = UserId(creator_id) if creator_id else None

        # Usar el método find_by_filters del repositorio
        return await self._uow.competitions.find_by_filters(
            search_name=search_name,
            search_creator=search_creator,
            status=status_enum,
            creator_id=creator_user_id,
        )
