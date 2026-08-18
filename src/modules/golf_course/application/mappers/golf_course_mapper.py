"""
Golf Course Mapper - Mapea entidades de dominio a DTOs.
"""

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    GolfCourseResponseDTO,
    GolfCourseSummaryDTO,
    HoleDTO,
    LocationDTO,
    ProvenanceDTO,
    TeeDTO,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_location import CourseLocation
from src.shared.domain.value_objects.gender import Gender


class GolfCourseMapper:
    """
    Mapper entre GolfCourse y sus DTOs, en ambos sentidos.

    Evita duplicación de código en los use cases.
    """

    @staticmethod
    def to_domain_holes(hole_dtos: list[HoleDTO]) -> list[Hole]:
        """Convierte una tarjeta recibida por la API en hoyos de dominio."""
        return [
            Hole(
                number=hole_dto.hole_number,
                par=hole_dto.par,
                stroke_index=hole_dto.stroke_index,
                meters=hole_dto.meters,
            )
            for hole_dto in hole_dtos
        ]

    @staticmethod
    def to_domain_tees(tee_dtos: list[TeeDTO]) -> list[Tee]:
        """
        Convierte las salidas recibidas por la API en salidas de dominio.

        Una salida puede traer su propia tarjeta o no traerla. Si no la trae,
        el agregado le copia la del campo al construirse.
        """
        return [
            Tee(
                gender=Gender(tee_dto.tee_gender) if tee_dto.tee_gender else None,
                color=tee_dto.color,
                identifier=tee_dto.identifier,
                course_rating=tee_dto.course_rating,
                slope_rating=tee_dto.slope_rating,
                holes=(
                    GolfCourseMapper.to_domain_holes(tee_dto.holes) if tee_dto.holes else []
                ),
            )
            for tee_dto in tee_dtos
        ]

    @staticmethod
    def to_domain_location(location_dto: LocationDTO | None) -> CourseLocation | None:
        """
        Convierte la ubicación recibida por la API en Value Object.

        Devuelve None cuando el cliente no manda ubicación, que en una edición
        significa "no la toques". Un objeto con todos sus valores a null sí
        llega como CourseLocation vacío, que es la forma de borrarla.
        """
        if location_dto is None:
            return None
        return CourseLocation(
            latitude=location_dto.latitude,
            longitude=location_dto.longitude,
            address=location_dto.address,
            city=location_dto.city,
            province=location_dto.province,
        )

    @staticmethod
    def to_summary_dto(
        golf_course: GolfCourse, *, distance_km: float | None = None
    ) -> GolfCourseSummaryDTO:
        """
        Mapea GolfCourse entity a GolfCourseSummaryDTO, para los listados.

        Args:
            golf_course: Entidad de dominio
            distance_km: Distancia a la posición consultada, si se pidió cercanía

        Returns:
            DTO de listado, sin tarjeta
        """
        return GolfCourseSummaryDTO(
            id=str(golf_course.id),
            name=golf_course.name,
            country_code=str(golf_course.country_code),
            course_type=golf_course.course_type.value,
            creator_id=str(golf_course.creator_id),
            tees=[
                TeeDTO(
                    tee_gender=tee.gender.value if tee.gender else None,
                    color=tee.color,
                    identifier=tee.identifier,
                    course_rating=tee.course_rating,
                    slope_rating=tee.slope_rating,
                    holes=None,
                )
                for tee in golf_course.tees
            ],
            approval_status=golf_course.approval_status.value,
            rejection_reason=golf_course.rejection_reason,
            total_par=golf_course.total_par,
            created_at=golf_course.created_at,
            updated_at=golf_course.updated_at,
            original_golf_course_id=(
                str(golf_course.original_golf_course_id)
                if golf_course.original_golf_course_id
                else None
            ),
            is_pending_update=golf_course.is_pending_update,
            location=(
                LocationDTO(
                    latitude=golf_course.location.latitude,
                    longitude=golf_course.location.longitude,
                    address=golf_course.location.address,
                    city=golf_course.location.city,
                    province=golf_course.location.province,
                )
                if not golf_course.location.is_empty
                else None
            ),
            distance_km=distance_km,
        )

    @staticmethod
    def to_response_dto(
        golf_course: GolfCourse, *, include_tee_scorecards: bool = True
    ) -> GolfCourseResponseDTO:
        """
        Mapea GolfCourse entity a GolfCourseResponseDTO.

        Args:
            golf_course: Entidad de dominio
            include_tee_scorecards: Si es False, las salidas se devuelven sin su
                tarjeta. Un campo puede tener hasta 14 salidas de 18 hoyos cada
                una, así que en los listados se omiten para no devolver
                centenares de hoyos por campo. El detalle sí las incluye.

        Returns:
            DTO de respuesta
        """
        return GolfCourseResponseDTO(
            id=str(golf_course.id),
            name=golf_course.name,
            country_code=str(golf_course.country_code),
            course_type=golf_course.course_type.value,
            creator_id=str(golf_course.creator_id),
            tees=[
                TeeDTO(
                    tee_gender=tee.gender.value if tee.gender else None,
                    color=tee.color,
                    identifier=tee.identifier,
                    course_rating=tee.course_rating,
                    slope_rating=tee.slope_rating,
                    holes=(
                        [
                            HoleDTO(
                                hole_number=hole.number,
                                par=hole.par,
                                stroke_index=hole.stroke_index,
                                meters=hole.meters,
                            )
                            for hole in sorted(tee.holes, key=lambda h: h.number)
                        ]
                        if include_tee_scorecards and tee.holes
                        else None
                    ),
                )
                for tee in golf_course.tees
            ],
            # Tarjeta de referencia del campo, derivada de la primera salida.
            # Se mantiene para los consumidores que no necesitan el detalle por
            # barra (estadísticas, emparejamientos, partidas rápidas).
            holes=[
                HoleDTO(
                    hole_number=hole.number,
                    par=hole.par,
                    stroke_index=hole.stroke_index,
                    meters=hole.meters,
                )
                for hole in golf_course.reference_card
            ],
            approval_status=golf_course.approval_status.value,
            rejection_reason=golf_course.rejection_reason,
            total_par=golf_course.total_par,
            created_at=golf_course.created_at,
            updated_at=golf_course.updated_at,
            original_golf_course_id=(
                str(golf_course.original_golf_course_id)
                if golf_course.original_golf_course_id
                else None
            ),
            is_pending_update=golf_course.is_pending_update,
            # Un campo sin ubicación devuelve null, y no un objeto con cinco
            # nulos dentro, para que el cliente distinga de un vistazo si sabe
            # dónde está el campo.
            location=(
                LocationDTO(
                    latitude=golf_course.location.latitude,
                    longitude=golf_course.location.longitude,
                    address=golf_course.location.address,
                    city=golf_course.location.city,
                    province=golf_course.location.province,
                )
                if not golf_course.location.is_empty
                else None
            ),
            # La procedencia siempre viaja: un campo dado de alta a mano tiene
            # origen MANUAL, que también es información.
            provenance=ProvenanceDTO(
                source=golf_course.provenance.source,
                external_id=golf_course.provenance.external_id,
                imported_at=golf_course.provenance.imported_at,
            ),
            physical_holes=golf_course.physical_holes,
        )
