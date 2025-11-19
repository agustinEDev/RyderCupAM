# -*- coding: utf-8 -*-
"""
Caso de Uso: Crear Competition.

Permite a un usuario crear una nueva competición en estado DRAFT.
"""

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
    CreateCompetitionResponseDTO,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.handicap_settings import (
    HandicapSettings,
    HandicapType,
)
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)


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
        self,
        request: CreateCompetitionRequestDTO,
        creator_id: UserId
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
            # 1. Validar que el nombre no exista para este creador
            name_vo = CompetitionName(request.name)
            existing = await self._uow.competitions.exists_with_name(name_vo, creator_id)
            if existing:
                raise CompetitionAlreadyExistsError(
                    f"Ya existe una competición con el nombre '{request.name}'"
                )

            # 2. Construir Location usando Domain Service (valida países y adyacencias)
            location = await self._location_builder.build_from_codes(
                main_country=request.main_country,
                adjacent_country_1=request.adjacent_country_1,
                adjacent_country_2=request.adjacent_country_2
            )

            # 3. Construir HandicapSettings
            handicap_settings = self._build_handicap_settings(
                request.handicap_type,
                request.handicap_percentage
            )

            # 4. Construir DateRange
            date_range = DateRange(
                start_date=request.start_date,
                end_date=request.end_date
            )

            # 5. Construir TeamAssignment desde string
            team_assignment_vo = TeamAssignment(request.team_assignment)

            # 6. Crear la entidad Competition usando factory method
            competition = Competition.create(
                id=CompetitionId.generate(),
                creator_id=creator_id,
                name=name_vo,
                dates=date_range,
                location=location,
                team_1_name="Team 1",  # Default, se puede cambiar con UpdateCompetition
                team_2_name="Team 2",  # Default, se puede cambiar con UpdateCompetition
                handicap_settings=handicap_settings,
                max_players=request.max_players,
                team_assignment=team_assignment_vo
            )

            # 6. Persistir la competición
            await self._uow.competitions.add(competition)

            # 7. Commit de la transacción
            await self._uow.commit()

        # 8. Retornar DTO de respuesta
        return CreateCompetitionResponseDTO(
            id=competition.id.value,
            creator_id=competition.creator_id.value,
            name=str(competition.name),
            status=competition.status.value,
            start_date=competition.dates.start_date,
            end_date=competition.dates.end_date,
            # Location
            country_code=competition.location.main_country.value,
            secondary_country_code=competition.location.adjacent_country_1.value if competition.location.adjacent_country_1 else None,
            tertiary_country_code=competition.location.adjacent_country_2.value if competition.location.adjacent_country_2 else None,
            location=str(competition.location),
            # Handicap
            handicap_type=competition.handicap_settings.type.value,
            handicap_percentage=competition.handicap_settings.percentage,
            # Config
            max_players=competition.max_players,
            team_assignment=competition.team_assignment.value,
            # Timestamps
            created_at=competition.created_at,
            updated_at=competition.updated_at
        )

    def _build_handicap_settings(
        self,
        handicap_type: str,
        handicap_percentage: int | None
    ) -> HandicapSettings:
        """
        Construye el Value Object HandicapSettings.

        Args:
            handicap_type: Tipo de hándicap (SCRATCH o PERCENTAGE)
            handicap_percentage: Porcentaje (90, 95, 100) si es PERCENTAGE

        Returns:
            HandicapSettings configurado

        Raises:
            ValueError: Si el tipo o porcentaje no son válidos
        """
        h_type = HandicapType(handicap_type)

        if h_type == HandicapType.SCRATCH:
            return HandicapSettings(h_type, None)  # Scratch requiere None explícitamente
        else:
            # PERCENTAGE requiere porcentaje
            return HandicapSettings(h_type, handicap_percentage)
