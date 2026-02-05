"""
Caso de Uso: Crear Competition.

Permite a un usuario crear una nueva competición en estado DRAFT.
"""

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
    CreateCompetitionResponseDTO,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.competition_policy import CompetitionPolicy
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import (
    CompetitionName,
)
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.user.domain.value_objects.user_id import UserId


class CompetitionAlreadyExistsError(Exception):
    """Excepción lanzada cuando ya existe una competición con el mismo nombre."""

    pass


class CreateCompetitionUseCase:
    """
    Caso de uso para crear una nueva competición.

    Orquesta:
    1. Validación de unicidad del nombre
    2. Construcción de Value Objects (usando LocationBuilder para validar países)
    3. Creación de la entidad Competition
    4. Persistencia mediante UoW

    Responsabilidades:
    - Convertir DTOs a Value Objects
    - Validar reglas de negocio de aplicación (nombre único)
    - Delegar validaciones de dominio a Domain Services
    - Crear la entidad de dominio
    - Persistir mediante repositorio
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow
        # Domain Service para construir Location (patrón UserFinder)
        self._location_builder = LocationBuilder(self._uow.countries)

    async def execute(
        self, request: CreateCompetitionRequestDTO, creator_id: UserId
    ) -> CreateCompetitionResponseDTO:
        """
        Ejecuta el caso de uso de creación de competición.

        Args:
            request: DTO con los datos de la competición
            creator_id: ID del usuario que crea la competición

        Returns:
            DTO con los datos de la competición creada

        Raises:
            CompetitionAlreadyExistsError: Si ya existe una competición con ese nombre
            InvalidCountryError: Si algún país no existe o no es adyacente (from LocationBuilder)
            ValueError: Si los Value Objects no son válidos
        """
        async with self._uow:
            # 1. Business logic guard: Validar límite de competiciones por creador
            existing_count = await self._uow.competitions.count_by_creator(creator_id)
            CompetitionPolicy.can_create_competition(creator_id, existing_count)

            # 2. Business logic guard: Validar rango de fechas razonable
            CompetitionPolicy.validate_date_range(
                request.start_date, request.end_date, request.name
            )

            # 3. Validar que el nombre no exista para este creador
            name_vo = CompetitionName(request.name)
            existing = await self._uow.competitions.exists_with_name(name_vo, creator_id)
            if existing:
                raise CompetitionAlreadyExistsError(
                    f"Ya existe una competición con el nombre '{request.name}'"
                )

            # 4. Construir Location usando Domain Service (valida países y adyacencias)
            location = await self._location_builder.build_from_codes(
                main_country=request.main_country,
                adjacent_country_1=request.adjacent_country_1,
                adjacent_country_2=request.adjacent_country_2,
            )

            # 5. Construir PlayMode
            play_mode = PlayMode(request.play_mode)

            # 6. Construir DateRange
            date_range = DateRange(start_date=request.start_date, end_date=request.end_date)

            # 7. Construir TeamAssignment desde string
            team_assignment_vo = TeamAssignment(request.team_assignment)

            # 8. Crear la entidad Competition usando factory method
            competition = Competition.create(
                id=CompetitionId.generate(),
                creator_id=creator_id,
                name=name_vo,
                dates=date_range,
                location=location,
                team_1_name=request.team_1_name,
                team_2_name=request.team_2_name,
                play_mode=play_mode,
                max_players=request.max_players,
                team_assignment=team_assignment_vo,
            )

            # 9. Persistir la competición
            await self._uow.competitions.add(competition)

        # 11. Retornar DTO de respuesta
        return CreateCompetitionResponseDTO(
            id=competition.id.value,
            creator_id=competition.creator_id.value,
            name=str(competition.name),
            status=competition.status.value,
            start_date=competition.dates.start_date,
            end_date=competition.dates.end_date,
            # Location
            country_code=competition.location.main_country.value,
            secondary_country_code=(
                competition.location.adjacent_country_1.value
                if competition.location.adjacent_country_1
                else None
            ),
            tertiary_country_code=(
                competition.location.adjacent_country_2.value
                if competition.location.adjacent_country_2
                else None
            ),
            location=str(competition.location),
            # Play Mode
            play_mode=competition.play_mode.value,
            # Nombres de equipos
            team_1_name=competition.team_1_name,
            team_2_name=competition.team_2_name,
            # Config
            max_players=competition.max_players,
            team_assignment=competition.team_assignment.value,
            # Timestamps
            created_at=competition.created_at,
            updated_at=competition.updated_at,
        )

