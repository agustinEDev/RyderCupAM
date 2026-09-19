"""
Caso de Uso: Actualizar Competition.

Permite actualizar una competición existente (solo en estado DRAFT).
"""

from src.modules.competition.application.dto.competition_dto import (
    UpdateCompetitionRequestDTO,
    UpdateCompetitionResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import (
    CompetitionName,
)
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.user.domain.value_objects.user_id import UserId


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

    def __init__(self, uow: CompetitionUnitOfWorkInterface, location_builder: LocationBuilder):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
            location_builder: Domain Service para construir Location
        """
        self._uow = uow
        self._location_builder = location_builder

    @staticmethod
    def _campos_de_localizacion(request: UpdateCompetitionRequestDTO) -> set[str]:
        """Campos de localización que el payload trae CON valor.

        Se mira `model_fields_set` para separar «no lo mandes» de «mándalo vacío»,
        y además se descarta el `None` explícito: `countries: []` quita los países
        acompañantes, `countries: null` no toca nada.
        """
        candidatos = ("main_country", "adjacent_country_1", "adjacent_country_2", "countries")
        enviados = request.model_fields_set
        return {c for c in candidatos if c in enviados and getattr(request, c) is not None}

    async def _construir_location(
        self, request: UpdateCompetitionRequestDTO, competition: Competition
    ) -> Location:
        """Construye la nueva localización a partir de lo que llega y de lo que hay.

        Tres reglas, de más fuerte a más débil:

        - Con `main_country` se rehace entera. Los acompañantes son los que lleguen,
          porque los de antes no tienen por qué ser adyacentes al país nuevo.
        - Con la lista `countries` manda la lista entera: lo que no esté en ella se va.
        - Con un campo adyacente suelto se cambia solo ese hueco y **el otro se
          conserva**; si no, repetir un país borraba al otro sin avisar.
        """
        enviados = self._campos_de_localizacion(request)
        actual = competition.location

        if "main_country" in enviados:
            return await self._location_builder.build_from_codes(
                main_country=request.main_country,
                adjacent_country_1=request.adjacent_country_1,
                adjacent_country_2=request.adjacent_country_2,
            )

        principal = str(actual.main_country)

        if "countries" in enviados:
            return await self._location_builder.build_from_codes(
                main_country=principal,
                adjacent_country_1=request.adjacent_country_1,
                adjacent_country_2=request.adjacent_country_2,
            )

        def hueco(campo: str, valor_actual) -> str | None:
            if campo in enviados:
                return getattr(request, campo)
            return str(valor_actual) if valor_actual else None

        return await self._location_builder.build_from_codes(
            main_country=principal,
            adjacent_country_1=hueco("adjacent_country_1", actual.adjacent_country_1),
            adjacent_country_2=hueco("adjacent_country_2", actual.adjacent_country_2),
        )

    async def execute(
        self,
        competition_id: CompetitionId,
        request: UpdateCompetitionRequestDTO,
        user_id: UserId,
        is_admin: bool = False,
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
            if not is_admin and not competition.is_creator(user_id):
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

            # La localización se reconstruye en cuanto llega cualquiera de sus campos,
            # no solo con `main_country`: la pantalla permite cambiar los países
            # acompañantes sin tocar el principal, y entonces el principal no llega.
            #
            # «Llega» es traer el campo CON valor: `countries: []` significa «quítalos»
            # y `countries: null` significa «no los toques», que es lo que manda un
            # cliente que serializa el formulario entero con sus huecos.
            location = self._campos_de_localizacion(request)
            nueva_location = None
            if location:
                nueva_location = await self._construir_location(request, competition)

            play_mode = PlayMode(request.play_mode) if request.play_mode else None

            team_assignment = (
                TeamAssignment(request.team_assignment) if request.team_assignment else None
            )

            # 5. Actualizar la competición usando el método de dominio
            competition.update_info(
                name=name,
                dates=dates,
                location=nueva_location,
                play_mode=play_mode,
                max_players=request.max_players,
                team_assignment=team_assignment,
                team_1_name=request.team_1_name,
                team_2_name=request.team_2_name,
                max_playing_handicap=request.max_playing_handicap,
            )

            # 6. Persistir cambios
            await self._uow.competitions.update(competition)

        # 7. Retornar DTO de respuesta
        return UpdateCompetitionResponseDTO(
            id=competition.id.value,
            name=str(competition.name),
            updated_at=competition.updated_at,
        )
