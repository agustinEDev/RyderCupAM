"""Golf Course DTOs."""

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    # Request DTOs
    ApproveGolfCourseRequestDTO,
    # Response DTOs
    ApproveGolfCourseResponseDTO,
    GetGolfCourseByIdRequestDTO,
    GetGolfCourseByIdResponseDTO,
    GolfCourseResponseDTO,
    HoleDTO,
    ListApprovedGolfCoursesRequestDTO,
    ListApprovedGolfCoursesResponseDTO,
    ListPendingGolfCoursesRequestDTO,
    ListPendingGolfCoursesResponseDTO,
    RejectGolfCourseRequestDTO,
    RejectGolfCourseResponseDTO,
    RequestGolfCourseRequestDTO,
    RequestGolfCourseResponseDTO,
    TeeDTO,
)

__all__ = [
    "ApproveGolfCourseRequestDTO",
    "ApproveGolfCourseResponseDTO",
    "GetGolfCourseByIdRequestDTO",
    "GetGolfCourseByIdResponseDTO",
    # Common DTOs
    "GolfCourseResponseDTO",
    "HoleDTO",
    "ListApprovedGolfCoursesRequestDTO",
    "ListApprovedGolfCoursesResponseDTO",
    "ListPendingGolfCoursesRequestDTO",
    "ListPendingGolfCoursesResponseDTO",
    "RejectGolfCourseRequestDTO",
    "RejectGolfCourseResponseDTO",
    # Request DTOs
    "RequestGolfCourseRequestDTO",
    # Response DTOs
    "RequestGolfCourseResponseDTO",
    "TeeDTO",
]
