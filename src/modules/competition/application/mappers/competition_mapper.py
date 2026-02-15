"""Mapper para convertir entidades Competition a DTOs de presentación."""

import logging

from src.modules.competition.application.dto.competition_dto import (
    CompetitionResponseDTO,
    CountryResponseDTO,
    CreatorDTO,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)


class CompetitionDTOMapper:
    """
    Mapper para convertir entidades Competition a DTOs de presentación.

    RESPONSABILIDAD: Capa de aplicación
    - Convertir entidades de dominio a DTOs
    - Calcular campos derivados para UI (is_creator, enrolled_count, location)
    - Formatear datos para el frontend
    """

    @staticmethod
    async def to_response_dto(
        competition: Competition,
        current_user_id: UserId,
        uow: CompetitionUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface | None = None,
    ) -> CompetitionResponseDTO:
        """
        Convierte una entidad Competition a CompetitionResponseDTO.

        Calcula campos dinámicos:
        - is_creator: si el usuario actual es el creador
        - enrolled_count: número de enrollments APPROVED
        - location: string formateado con nombres de países
        - creator: información completa del creador (si user_uow es provisto)
        """
        # Calcular enrolled_count
        enrolled_count = await uow.enrollments.count_approved(competition.id)

        # Calcular pending_enrollments_count (solicitudes pendientes)
        pending_enrollments_count = await uow.enrollments.count_pending(competition.id)

        # Obtener enrollment status del usuario actual (si existe)
        user_enrollment_status = None
        user_enrollment = await uow.enrollments.find_by_user_and_competition(
            current_user_id, competition.id
        )
        if user_enrollment:
            user_enrollment_status = (
                user_enrollment.status.value
                if hasattr(user_enrollment.status, "value")
                else user_enrollment.status
            )
            logger.debug(
                "Found enrollment for user %s in competition %s: %s",
                current_user_id.value,
                competition.id.value,
                user_enrollment_status,
            )
        else:
            logger.debug(
                "No enrollment found for user %s in competition %s",
                current_user_id.value,
                competition.id.value,
            )

        # Formatear location
        location_str = await CompetitionDTOMapper._format_location(competition, uow)

        # Obtener lista de países con detalles
        countries_list = await CompetitionDTOMapper._get_countries_list(competition, uow)

        # Obtener información del creador (si user_uow es provisto)
        creator_dto = None
        if user_uow:
            creator_dto = await CompetitionDTOMapper._get_creator_dto(
                competition.creator_id, user_uow
            )

        # Construir DTO
        return CompetitionResponseDTO(
            id=competition.id.value,
            creator_id=competition.creator_id.value,
            creator=creator_dto,
            name=str(competition.name),
            status=competition.status.value,
            # Dates
            start_date=competition.dates.start_date,
            end_date=competition.dates.end_date,
            # Location - raw codes
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
            # Location - formatted
            location=location_str,
            # Location - countries array
            countries=countries_list,
            # Play Mode
            play_mode=competition.play_mode.value,
            # Config
            max_players=competition.max_players,
            team_assignment=(
                competition.team_assignment.value
                if hasattr(competition.team_assignment, "value")
                else competition.team_assignment
            ),
            # Teams
            team_1_name=competition.team_1_name,
            team_2_name=competition.team_2_name,
            # Campos calculados
            is_creator=(competition.creator_id == current_user_id),
            enrolled_count=enrolled_count,
            pending_enrollments_count=pending_enrollments_count,
            user_enrollment_status=user_enrollment_status,
            # Timestamps
            created_at=competition.created_at,
            updated_at=competition.updated_at,
        )

    @staticmethod
    async def _format_location(
        competition: Competition,
        uow: CompetitionUnitOfWorkInterface,
    ) -> str:
        """Formatea la ubicación como string legible (ej: "Spain, France")."""
        location = competition.location
        country_names = []

        # País principal
        main_country = await uow.countries.find_by_code(location.main_country)
        if main_country:
            country_names.append(main_country.name_en)

        # País adyacente 1
        if location.adjacent_country_1:
            country = await uow.countries.find_by_code(location.adjacent_country_1)
            if country:
                country_names.append(country.name_en)

        # País adyacente 2
        if location.adjacent_country_2:
            country = await uow.countries.find_by_code(location.adjacent_country_2)
            if country:
                country_names.append(country.name_en)

        return ", ".join(country_names) if country_names else "Unknown"

    @staticmethod
    async def _get_countries_list(
        competition: Competition,
        uow: CompetitionUnitOfWorkInterface,
    ) -> list[CountryResponseDTO]:
        """Obtiene la lista completa de países participantes con códigos y nombres."""
        location = competition.location
        countries = []

        # País principal
        main_country = await uow.countries.find_by_code(location.main_country)
        if main_country:
            countries.append(
                CountryResponseDTO(
                    code=main_country.code.value,
                    name_en=main_country.name_en,
                    name_es=main_country.name_es,
                )
            )

        # País adyacente 1
        if location.adjacent_country_1:
            country = await uow.countries.find_by_code(location.adjacent_country_1)
            if country:
                countries.append(
                    CountryResponseDTO(
                        code=country.code.value,
                        name_en=country.name_en,
                        name_es=country.name_es,
                    )
                )

        # País adyacente 2
        if location.adjacent_country_2:
            country = await uow.countries.find_by_code(location.adjacent_country_2)
            if country:
                countries.append(
                    CountryResponseDTO(
                        code=country.code.value,
                        name_en=country.name_en,
                        name_es=country.name_es,
                    )
                )

        return countries

    @staticmethod
    async def _get_creator_dto(
        creator_id: UserId,
        user_uow: UserUnitOfWorkInterface,
        *,
        include_email: bool = False,
    ) -> CreatorDTO | None:
        """
        Obtiene la información del creador de una competición.

        Assumes caller manages the user_uow transaction context.
        """
        creator = await user_uow.users.find_by_id(creator_id)

        if not creator:
            logger.warning("Creator with id %s not found", creator_id.value)
            return None

        return CreatorDTO(
            id=creator.id.value,
            first_name=creator.first_name,
            last_name=creator.last_name,
            email=str(creator.email) if include_email else None,
            handicap=creator.handicap.value if creator.handicap else None,
            country_code=(creator.country_code.value if creator.country_code else None),
        )
