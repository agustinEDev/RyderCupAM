"""
Proveedores de campos de golf: alta y aprobación, mapa de hoyos, muestras y reportes.
"""

from fastapi import Depends

from src.config.dependencies.comun import (
    get_golf_course_uow,
)
from src.modules.golf_course.application.ports.recent_hole_sample_senders import (
    IRecentHoleSampleSenders,
)
from src.modules.golf_course.application.use_cases.approve_golf_course_use_case import (
    ApproveGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.approve_update_golf_course_use_case import (
    ApproveUpdateGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.create_direct_golf_course_use_case import (
    CreateDirectGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.get_golf_course_by_id_use_case import (
    GetGolfCourseByIdUseCase,
)
from src.modules.golf_course.application.use_cases.hole_map_use_cases import (
    ApproveHoleMapUseCase,
    GetApprovedHoleMapUseCase,
    GetHoleMapForReviewUseCase,
    ListPendingHoleMapsUseCase,
    RejectHoleMapUseCase,
)
from src.modules.golf_course.application.use_cases.hole_report_use_cases import (
    DiscardHoleReportUseCase,
    SubmitHoleReportUseCase,
)
from src.modules.golf_course.application.use_cases.hole_review_use_cases import (
    GetHoleReviewUseCase,
    ListHoleReviewsUseCase,
)
from src.modules.golf_course.application.use_cases.hole_sample_use_cases import (
    ListHoleSamplesUseCase,
    SubmitHoleSampleUseCase,
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
from src.modules.golf_course.application.use_cases.reject_update_golf_course_use_case import (
    RejectUpdateGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.request_golf_course_use_case import (
    RequestGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.saved_hole_use_cases import (
    DeleteHoleSampleUseCase,
    ReopenHoleUseCase,
    SaveHoleLineUseCase,
)
from src.modules.golf_course.application.use_cases.update_golf_course_use_case import (
    UpdateGolfCourseUseCase,
)
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.infrastructure.services.in_memory_recent_hole_sample_senders import (
    InMemoryRecentHoleSampleSenders,
)
from src.modules.golf_course.infrastructure.services.tzfpy_timezone_resolver import (
    TzfpyTimezoneResolver,
)


def get_request_golf_course_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> RequestGolfCourseUseCase:
    """Proveedor del caso de uso RequestGolfCourseUseCase."""
    return RequestGolfCourseUseCase(uow, TzfpyTimezoneResolver())


def get_get_golf_course_by_id_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> GetGolfCourseByIdUseCase:
    """Proveedor del caso de uso GetGolfCourseByIdUseCase."""
    return GetGolfCourseByIdUseCase(uow)


def get_list_approved_golf_courses_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ListApprovedGolfCoursesUseCase:
    """Proveedor del caso de uso ListApprovedGolfCoursesUseCase."""
    return ListApprovedGolfCoursesUseCase(uow)


def get_list_pending_golf_courses_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ListPendingGolfCoursesUseCase:
    """Proveedor del caso de uso ListPendingGolfCoursesUseCase."""
    return ListPendingGolfCoursesUseCase(uow)


def get_approve_golf_course_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ApproveGolfCourseUseCase:
    """Proveedor del caso de uso ApproveGolfCourseUseCase."""
    return ApproveGolfCourseUseCase(uow)


def get_reject_golf_course_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> RejectGolfCourseUseCase:
    """Proveedor del caso de uso RejectGolfCourseUseCase."""
    return RejectGolfCourseUseCase(uow)


def get_create_direct_golf_course_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> CreateDirectGolfCourseUseCase:
    """Proveedor del caso de uso CreateDirectGolfCourseUseCase."""
    return CreateDirectGolfCourseUseCase(uow, TzfpyTimezoneResolver())


def get_update_golf_course_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> UpdateGolfCourseUseCase:
    """Proveedor del caso de uso UpdateGolfCourseUseCase."""
    return UpdateGolfCourseUseCase(uow, TzfpyTimezoneResolver())


def get_approve_update_golf_course_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ApproveUpdateGolfCourseUseCase:
    """Proveedor del caso de uso ApproveUpdateGolfCourseUseCase."""
    return ApproveUpdateGolfCourseUseCase(uow)


def get_reject_update_golf_course_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> RejectUpdateGolfCourseUseCase:
    """Proveedor del caso de uso RejectUpdateGolfCourseUseCase."""
    return RejectUpdateGolfCourseUseCase(uow)


# Mapa de hoyos (BE #532)


def get_approved_hole_map_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> GetApprovedHoleMapUseCase:
    """Proveedor del caso de uso GetApprovedHoleMapUseCase."""
    return GetApprovedHoleMapUseCase(uow)


def get_list_pending_hole_maps_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ListPendingHoleMapsUseCase:
    """Proveedor del caso de uso ListPendingHoleMapsUseCase."""
    return ListPendingHoleMapsUseCase(uow)


def get_hole_map_for_review_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> GetHoleMapForReviewUseCase:
    """Proveedor del caso de uso GetHoleMapForReviewUseCase."""
    return GetHoleMapForReviewUseCase(uow)


def get_approve_hole_map_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ApproveHoleMapUseCase:
    """Proveedor del caso de uso ApproveHoleMapUseCase."""
    return ApproveHoleMapUseCase(uow)


def get_reject_hole_map_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> RejectHoleMapUseCase:
    """Proveedor del caso de uso RejectHoleMapUseCase."""
    return RejectHoleMapUseCase(uow)


# Una sola para todo el proceso: la ventana de 10 minutos por jugador tiene que
# verse entre peticiones. Vive solo en memoria (BE #532, 16 oct 2026)
_recent_hole_sample_senders = InMemoryRecentHoleSampleSenders()


def get_recent_hole_sample_senders() -> IRecentHoleSampleSenders:
    """Proveedor de quién aportó hace poco una muestra de hoyo (singleton del proceso)."""
    return _recent_hole_sample_senders


def get_submit_hole_sample_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    recent_senders: IRecentHoleSampleSenders = Depends(get_recent_hole_sample_senders),
) -> SubmitHoleSampleUseCase:
    """Proveedor del caso de uso SubmitHoleSampleUseCase."""
    return SubmitHoleSampleUseCase(uow, recent_senders)


# Otra ventana, aparte de la de las muestras: reportar un hoyo no gasta el hueco
# de su muestra, ni al revés (entrega 7)
_recent_hole_report_senders = InMemoryRecentHoleSampleSenders()


def get_recent_hole_report_senders() -> IRecentHoleSampleSenders:
    """Proveedor de quién reportó hace poco un hoyo (singleton del proceso)."""
    return _recent_hole_report_senders


def get_submit_hole_report_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    recent_senders: IRecentHoleSampleSenders = Depends(get_recent_hole_report_senders),
) -> SubmitHoleReportUseCase:
    """Proveedor del caso de uso SubmitHoleReportUseCase (entrega 7)."""
    return SubmitHoleReportUseCase(uow, recent_senders)


def get_discard_hole_report_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> DiscardHoleReportUseCase:
    """Proveedor del caso de uso DiscardHoleReportUseCase (entrega 7)."""
    return DiscardHoleReportUseCase(uow)


def get_list_hole_samples_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ListHoleSamplesUseCase:
    """Proveedor del caso de uso ListHoleSamplesUseCase."""
    return ListHoleSamplesUseCase(uow)


def get_save_hole_line_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> SaveHoleLineUseCase:
    """Proveedor del caso de uso SaveHoleLineUseCase (BE #575)."""
    return SaveHoleLineUseCase(uow)


def get_reopen_hole_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ReopenHoleUseCase:
    """Proveedor del caso de uso ReopenHoleUseCase (BE #575)."""
    return ReopenHoleUseCase(uow)


def get_list_hole_reviews_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ListHoleReviewsUseCase:
    """Proveedor del caso de uso ListHoleReviewsUseCase (BE #575)."""
    return ListHoleReviewsUseCase(uow)


def get_hole_review_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> GetHoleReviewUseCase:
    """Proveedor del caso de uso GetHoleReviewUseCase (BE #575)."""
    return GetHoleReviewUseCase(uow)


def get_delete_hole_sample_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> DeleteHoleSampleUseCase:
    """Proveedor del caso de uso DeleteHoleSampleUseCase (BE #575)."""
    return DeleteHoleSampleUseCase(uow)
