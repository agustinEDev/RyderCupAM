"""
Golf Course Mapper - Mapea entidades de dominio a DTOs.
"""

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    GolfCourseResponseDTO,
    HoleDTO,
    TeeDTO,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse


class GolfCourseMapper:
    """
    Mapper para convertir GolfCourse entity a Response DTOs.

    Evita duplicación de código en los use cases.
    """

    @staticmethod
    def to_response_dto(golf_course: GolfCourse) -> GolfCourseResponseDTO:
        """
        Mapea GolfCourse entity a GolfCourseResponseDTO.

        Args:
            golf_course: Entidad de dominio

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
                    tee_category=tee.category.value,
                    identifier=tee.identifier,
                    course_rating=tee.course_rating,
                    slope_rating=tee.slope_rating,
                )
                for tee in golf_course.tees
            ],
            holes=[
                HoleDTO(
                    hole_number=hole.number,
                    par=hole.par,
                    stroke_index=hole.stroke_index,
                )
                for hole in golf_course.holes
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
        )
