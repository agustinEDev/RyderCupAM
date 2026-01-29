"""
Golf Course Application Layer.

Contiene:
- DTOs (Data Transfer Objects)
- Use Cases (Application Services)
- Mappers (Entity to DTO conversion)
"""

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    ApproveGolfCourseRequestDTO,
    ApproveGolfCourseResponseDTO,
    GetGolfCourseByIdRequestDTO,
    GetGolfCourseByIdResponseDTO,
    # Common DTOs
    GolfCourseResponseDTO,
    HoleDTO,
    ListApprovedGolfCoursesRequestDTO,
    ListApprovedGolfCoursesResponseDTO,
    ListPendingGolfCoursesRequestDTO,
    ListPendingGolfCoursesResponseDTO,
    RejectGolfCourseRequestDTO,
    RejectGolfCourseResponseDTO,
    # Request DTOs
    RequestGolfCourseRequestDTO,
    # Response DTOs
    RequestGolfCourseResponseDTO,
    TeeDTO,
)
from src.modules.golf_course.application.mappers.golf_course_mapper import GolfCourseMapper
from src.modules.golf_course.application.use_cases.approve_golf_course_use_case import (
    ApproveGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.get_golf_course_by_id_use_case import (
    GetGolfCourseByIdUseCase,
)
from src.modules.golf_course.application.use_cases.list_approved_golf_courses_use_case import (
    ListApprovedGolfCoursesUseCase,
)
from src.modules.golf_course.application.use_cases.list_pending_golf_courses_use_case import (
    ListPendingGolfCoursesUseCase,
)
from src.modules.golf_course.application.use_cases.reject_golf_course_use_case import (
    RejectGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.request_golf_course_use_case import (
    RequestGolfCourseUseCase,
)

__all__ = [
    "ApproveGolfCourseRequestDTO",
    "ApproveGolfCourseResponseDTO",
    "ApproveGolfCourseUseCase",
    "GetGolfCourseByIdRequestDTO",
    "GetGolfCourseByIdResponseDTO",
    "GetGolfCourseByIdUseCase",
    # Mappers
    "GolfCourseMapper",
    # Common DTOs
    "GolfCourseResponseDTO",
    "HoleDTO",
    "ListApprovedGolfCoursesRequestDTO",
    "ListApprovedGolfCoursesResponseDTO",
    "ListApprovedGolfCoursesUseCase",
    "ListPendingGolfCoursesRequestDTO",
    "ListPendingGolfCoursesResponseDTO",
    "ListPendingGolfCoursesUseCase",
    "RejectGolfCourseRequestDTO",
    "RejectGolfCourseResponseDTO",
    "RejectGolfCourseUseCase",
    # Request DTOs
    "RequestGolfCourseRequestDTO",
    # Response DTOs
    "RequestGolfCourseResponseDTO",
    # Use Cases
    "RequestGolfCourseUseCase",
    "TeeDTO",
]
