"""
Caso de Uso: Actualizar Competition.

Permite actualizar una competición existente (solo en estado DRAFT).
"""

from src.modules.competition.application.dto.competition_dto import (
    UpdateCompetitionRequestDTO,
    UpdateCompetitionResponseDTO,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import (
    CompetitionName,
)
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.user.domain.value_objects.user_id import UserId


class CompetitionNotFoundError(Exception):
    """Excepción lanzada cuando la competición no existe."""

    pass


class NotCompetitionCreatorError(Exception):
    """Excepción lanzada cuando el usuario no es el creador de la competición."""

    pass


class CompetitionNotEditableError(Exception):
    """Excepción lanzada cuando la competición no está en estado DRAFT."""

    pass


class UpdateCompetitionUseCase:
    """
    Caso de uso para actualizar una competición existente.

    Restricciones:
    - Solo se puede actualizar en estado DRAFT
    - Solo el creador puede actualizar
    - Todos los campos son opcionales (actualización parcial)

    Orquesta:
    1. Validar que la competición existe
    2. Validar que el usuario es el creador
    3. Validar que está en estado DRAFT
    4. Actualizar solo los campos proporcionados
    5. Persistir cambios
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow
        self._location_builder = LocationBuilder(self._uow.countries)

    async def execute(
        self,
        competition_id: CompetitionId,
        request: UpdateCompetitionRequestDTO,
        user_id: UserId,
    ) -> UpdateCompetitionResponseDTO:
        """
        Ejecuta el caso de uso de actualización de competición.

        Args:
            competition_id: ID de la competición a actualizar
            request: DTO con los datos a actualizar (todos opcionales)
            user_id: ID del usuario que solicita la actualización

        Returns:
            DTO con los datos de la competición actualizada

        Raises:
            CompetitionNotFoundError: Si la competición no existe
            NotCompetitionCreatorError: Si el usuario no es el creador
            CompetitionNotEditableError: Si no está en estado DRAFT
        """
        async with self._uow:
            # 1. Buscar la competición
            competition = await self._uow.competitions.find_by_id(competition_id)
            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {competition_id.value}"
                )

            # 2. Validar que el usuario es el creador
            if not competition.is_creator(user_id):
                raise NotCompetitionCreatorError("Solo el creador puede actualizar la competición")

            # 3. Validar que está en estado DRAFT (se puede modificar)
            if not competition.allows_modifications():
                raise CompetitionNotEditableError(
                    f"No se puede modificar una competición en estado {competition.status.value}. "
                    f"Solo se permite en estado DRAFT."
                )

            # 4. Construir los Value Objects y obtener valores opcionales
            name = CompetitionName(request.name) if request.name else None

            dates = None
            if request.start_date and request.end_date:
                dates = DateRange(request.start_date, request.end_date)
            elif request.start_date or request.end_date:
                raise ValueError(
                    "Se deben proporcionar ambas fechas (start_date y end_date) para actualizarlas."
                )

            location = None
            if request.main_country:
                location = await self._location_builder.build_from_codes(
                    main_country=request.main_country,
                    adjacent_country_1=request.adjacent_country_1,
                    adjacent_country_2=request.adjacent_country_2,
                )

            play_mode = PlayMode(request.play_mode) if request.play_mode else None

            team_assignment = (
                TeamAssignment(request.team_assignment) if request.team_assignment else None
            )

            # 5. Actualizar la competición usando el método de dominio
            competition.update_info(
                name=name,
                dates=dates,
                location=location,
                play_mode=play_mode,
                max_players=request.max_players,
                team_assignment=team_assignment,
                team_1_name=request.team_1_name,
                team_2_name=request.team_2_name,
            )

            # 6. Persistir cambios
            await self._uow.competitions.update(competition)

        # 7. Retornar DTO de respuesta
        return UpdateCompetitionResponseDTO(
            id=competition.id.value,
            name=str(competition.name),
            updated_at=competition.updated_at,
        )
