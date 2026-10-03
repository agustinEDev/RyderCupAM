"""Mapper para convertir entidades Competition a DTOs de presentación."""

import logging

from src.modules.competition.application.dto.competition_dto import (
    CaptaincyResponseDTO,
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
        is_admin: bool = False,
    ) -> CompetitionResponseDTO:
        """
        Convierte una entidad Competition a CompetitionResponseDTO.

        Calcula campos dinámicos:
        - is_creator: si el usuario actual es el creador
        - enrolled_count: número de enrollments APPROVED
        - location: string formateado con nombres de países
        - creator: información completa del creador (si user_uow es provisto)

        pending_enrollments_count solo se calcula y expone para el creador
        de la competición o para administradores (is_admin=True).
        """
        is_creator = competition.creator_id == current_user_id

        # Calcular enrolled_count
        enrolled_count = await uow.enrollments.count_approved(competition.id)

        # Calcular pending_enrollments_count (solo visible para creador/admin)
        pending_enrollments_count = 0
        if is_creator or is_admin:
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
            max_playing_handicap=competition.max_playing_handicap,
            enrollment_opens_days_before=competition.enrollment_opens_days_before,
            visibility=str(competition.visibility),
            # Tipo de torneo y lo de la Ryder (vacío si no lo es)
            **CompetitionDTOMapper.tournament_fields(competition),
            # Campos calculados
            is_creator=is_creator,
            enrolled_count=enrolled_count,
            pending_enrollments_count=pending_enrollments_count,
            user_enrollment_status=user_enrollment_status,
            # Timestamps
            created_at=competition.created_at,
            updated_at=competition.updated_at,
        )

    @staticmethod
    def tournament_fields(competition: Competition) -> dict:
        """
        El tipo de torneo, su modalidad y lo que es solo de la Ryder Cup (#251).

        Un solo sitio para las respuestas que lo llevan (la ficha, la de crear y
        la de editar), que antes lo construían a mano leyendo la pieza de la
        Ryder como si siempre existiera. En un Stableford o un Medal no existe:
        sus campos van vacíos.
        """
        ryder_cup = competition.ryder_cup

        def valor(user_id: UserId | None):
            return user_id.value if user_id else None

        return {
            "tournament_type": str(competition.tournament_type),
            "modality": str(competition.modality),
            "team_1_name": ryder_cup.team_1_name if ryder_cup else None,
            "team_2_name": ryder_cup.team_2_name if ryder_cup else None,
            "team_assignment": ryder_cup.team_assignment.value if ryder_cup else None,
            "setup_mode": str(ryder_cup.setup_mode) if ryder_cup else None,
            "team_a_captain_id": valor(ryder_cup.team_a_captain_id) if ryder_cup else None,
            "team_b_captain_id": valor(ryder_cup.team_b_captain_id) if ryder_cup else None,
            "team_a_vice_captain_id": (
                valor(ryder_cup.team_a_vice_captain_id) if ryder_cup else None
            ),
            "team_b_vice_captain_id": (
                valor(ryder_cup.team_b_vice_captain_id) if ryder_cup else None
            ),
        }

    @staticmethod
    def to_captaincy_dto(competition: Competition) -> CaptaincyResponseDTO:
        """Capitanes y subcapitanes de la competición (BE #320)."""

        def valor(user_id: UserId | None):
            """El UUID del jugador, o None si el puesto está vacío."""
            return user_id.value if user_id else None

        ryder_cup = competition.require_ryder_cup()
        return CaptaincyResponseDTO(
            id=competition.id.value,
            team_a_captain_id=valor(ryder_cup.team_a_captain_id),
            team_b_captain_id=valor(ryder_cup.team_b_captain_id),
            team_a_vice_captain_id=valor(ryder_cup.team_a_vice_captain_id),
            team_b_vice_captain_id=valor(ryder_cup.team_b_vice_captain_id),
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
            display_name=creator.display_name,
            email=str(creator.email) if include_email else None,
            handicap=creator.handicap.value if creator.handicap else None,
            country_code=(creator.country_code.value if creator.country_code else None),
        )
