"""
Proveedores de la organización de una competición: alta, edición, estados, listados,
inscripciones, invitaciones, equipos y capitanes, draft y hándicaps.
"""

from datetime import UTC, datetime

from fastapi import Depends

from src.config.dependencies.comun import (
    get_amigos,
    get_competition_activity_publisher,
    get_competition_uow,
    get_golf_course_uow,
    get_invitation_email_service,
    get_lanzador_de_actualizaciones,
    get_publish_tournament_achievements_use_case,
    get_uow,
)
from src.modules.competition.application.ports.amigos_interface import AmigosInterface
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.ports.invitation_email_service_interface import (
    IInvitationEmailService,
)
from src.modules.competition.application.ports.lanzador_de_actualizaciones import (
    LanzadorDeActualizaciones,
)
from src.modules.competition.application.ports.tournament_achievements_publisher_interface import (
    TournamentAchievementsPublisherInterface,
)
from src.modules.competition.application.use_cases.activate_competition_use_case import (
    ActivateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.actualizar_handicaps_use_case import (
    ActualizarHandicapsUseCase,
    VentanaDeActualizacionUseCase,
)
from src.modules.competition.application.use_cases.add_golf_course_use_case import (
    AddGolfCourseToCompetitionUseCase,
)
from src.modules.competition.application.use_cases.assign_teams_use_case import (
    AssignTeamsUseCase,
)
from src.modules.competition.application.use_cases.cancel_competition_use_case import (
    CancelCompetitionUseCase,
)
from src.modules.competition.application.use_cases.cancel_enrollment_use_case import (
    CancelEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.cancel_invitation_use_case import (
    CancelInvitationUseCase,
)
from src.modules.competition.application.use_cases.close_enrollments_use_case import (
    CloseEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.complete_competition_use_case import (
    CompleteCompetitionUseCase,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.delete_competition_use_case import (
    DeleteCompetitionUseCase,
)
from src.modules.competition.application.use_cases.direct_enroll_player_use_case import (
    DirectEnrollPlayerUseCase,
)
from src.modules.competition.application.use_cases.fill_captain_use_case import (
    FillCaptainUseCase,
)
from src.modules.competition.application.use_cases.get_competition_summary_use_case import (
    GetCompetitionSummaryUseCase,
)
from src.modules.competition.application.use_cases.get_competition_use_case import (
    GetCompetitionUseCase,
)
from src.modules.competition.application.use_cases.get_draft_use_case import GetDraftUseCase
from src.modules.competition.application.use_cases.get_handicap_update_status_use_case import (
    GetHandicapUpdateStatusUseCase,
)
from src.modules.competition.application.use_cases.handle_enrollment_use_case import (
    HandleEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.list_competition_invitations_use_case import (
    ListCompetitionInvitationsUseCase,
)
from src.modules.competition.application.use_cases.list_competitions_use_case import (
    ListCompetitionsUseCase,
)
from src.modules.competition.application.use_cases.list_enrollments_use_case import (
    ListEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.list_my_invitations_use_case import (
    ListMyInvitationsUseCase,
)
from src.modules.competition.application.use_cases.make_draft_pick_use_case import (
    MakeDraftPickUseCase,
)
from src.modules.competition.application.use_cases.name_captains_use_case import (
    NameCaptainsUseCase,
)
from src.modules.competition.application.use_cases.name_vice_captain_use_case import (
    NameViceCaptainUseCase,
)
from src.modules.competition.application.use_cases.programar_actualizacion_use_case import (
    AnularProgramacionUseCase,
    ProgramarActualizacionUseCase,
)
from src.modules.competition.application.use_cases.remove_custom_handicap_use_case import (
    RemoveCustomHandicapUseCase,
)
from src.modules.competition.application.use_cases.remove_enrolled_player_use_case import (
    RemoveEnrolledPlayerUseCase,
)
from src.modules.competition.application.use_cases.remove_golf_course_use_case import (
    RemoveGolfCourseFromCompetitionUseCase,
)
from src.modules.competition.application.use_cases.reopen_enrollments_use_case import (
    ReopenEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.reorder_golf_courses_use_case import (
    ReorderGolfCoursesUseCase,
)
from src.modules.competition.application.use_cases.request_enrollment_use_case import (
    RequestEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.respond_to_invitation_use_case import (
    RespondToInvitationUseCase,
)
from src.modules.competition.application.use_cases.revert_competition_status_use_case import (
    RevertCompetitionStatusUseCase,
)
from src.modules.competition.application.use_cases.revert_competition_to_in_progress_use_case import (
    RevertCompetitionToInProgressUseCase,
)
from src.modules.competition.application.use_cases.send_invitation_by_email_use_case import (
    SendInvitationByEmailUseCase,
)
from src.modules.competition.application.use_cases.send_invitation_by_user_id_use_case import (
    SendInvitationByUserIdUseCase,
)
from src.modules.competition.application.use_cases.set_custom_handicap_use_case import (
    SetCustomHandicapUseCase,
)
from src.modules.competition.application.use_cases.set_name_preference_use_case import (
    SetNamePreferenceUseCase,
)
from src.modules.competition.application.use_cases.start_competition_use_case import (
    StartCompetitionUseCase,
)
from src.modules.competition.application.use_cases.start_draft_use_case import (
    StartDraftUseCase,
)
from src.modules.competition.application.use_cases.undo_teams_use_case import (
    UndoTeamsUseCase,
)
from src.modules.competition.application.use_cases.update_competition_use_case import (
    UpdateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.update_stroke_play_settings_use_case import (
    UpdateStrokePlaySettingsUseCase,
)
from src.modules.competition.application.use_cases.vista_de_competicion_use_case import (
    VistaDeCompeticionUseCase,
)
from src.modules.competition.application.use_cases.withdraw_enrollment_use_case import (
    WithdrawEnrollmentUseCase,
)
from src.modules.competition.domain.policies.snake_draft_service import (
    SnakeDraftService,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.infrastructure.services.competition_timezone_from_course import (
    CompetitionTimezoneFromCourse,
)
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.social.application.use_cases.publish_tournament_achievements_use_case import (
    PublishTournamentAchievementsUseCase,
)
from src.modules.social.infrastructure.adapters.tournament_achievements_publisher import (
    TournamentAchievementsPublisher,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)


def get_tournament_achievements_publisher(
    publish_use_case: PublishTournamentAchievementsUseCase = Depends(
        get_publish_tournament_achievements_use_case
    ),
) -> TournamentAchievementsPublisherInterface:
    """Proveedor del adaptador que conecta competition con el feed social."""
    return TournamentAchievementsPublisher(publish_use_case)


def get_location_builder(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> LocationBuilder:
    """
    Proveedor del domain service LocationBuilder.

    Reutiliza el mismo `uow` (y por tanto el mismo `uow.countries`) que reciben
    los use cases que lo consumen, ya que FastAPI cachea `Depends(get_competition_uow)`
    dentro de una misma request.
    """
    return LocationBuilder(uow.countries)


def get_create_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    location_builder: LocationBuilder = Depends(get_location_builder),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> CreateCompetitionUseCase:
    """
    Proveedor del caso de uso CreateCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Depende de `get_location_builder` para el domain service de ubicación.
    3. Crea una instancia de `CreateCompetitionUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return CreateCompetitionUseCase(uow, location_builder, user_uow.users)


def get_list_competitions_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ListCompetitionsUseCase:
    """
    Proveedor del caso de uso ListCompetitionsUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `ListCompetitionsUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    # La zona del campo hace falta para abrir las programadas a las que ya les
    # toca: verlas en un listado tambien las abre (BE #331). Sin esto el caso de
    # uso funciona igual pero no abre nada, y una competicion seguiria
    # anunciando «abre el martes» el miercoles
    return ListCompetitionsUseCase(
        uow,
        zona_del_campo=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
    )


def get_vista_de_competicion_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> VistaDeCompeticionUseCase:
    """La vista de una competición: la respuesta tras escribir y la ficha (fase 5)."""
    return VistaDeCompeticionUseCase(uow, user_uow)


def get_update_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    location_builder: LocationBuilder = Depends(get_location_builder),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> UpdateCompetitionUseCase:
    """
    Proveedor del caso de uso UpdateCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Depende de `get_location_builder` para el domain service de ubicación.
    3. Crea una instancia de `UpdateCompetitionUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return UpdateCompetitionUseCase(
        uow, location_builder, golf_course_uow.golf_courses, actividad=actividad
    )


def get_get_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> GetCompetitionUseCase:
    """
    Proveedor del caso de uso GetCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `GetCompetitionUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    # La zona del campo hace falta para abrir las inscripciones a su hora (BE #319):
    # «las nueve» son las nueve de donde se juega
    return GetCompetitionUseCase(
        uow,
        zona_del_campo=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
    )


def get_competition_summary_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> GetCompetitionSummaryUseCase:
    """El resumen público de una competición (release social 3, L5)."""
    return GetCompetitionSummaryUseCase(uow)


def get_delete_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> DeleteCompetitionUseCase:
    """
    Proveedor del caso de uso DeleteCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `DeleteCompetitionUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return DeleteCompetitionUseCase(uow, actividad=actividad)


def get_activate_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> ActivateCompetitionUseCase:
    """
    Proveedor del caso de uso ActivateCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `ActivateCompetitionUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return ActivateCompetitionUseCase(uow)


def get_close_enrollments_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    lanzador: LanzadorDeActualizaciones | None = Depends(get_lanzador_de_actualizaciones),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> CloseEnrollmentsUseCase:
    """
    Proveedor del caso de uso CloseEnrollmentsUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `CloseEnrollmentsUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    # Los usuarios, para el hándicap de cada inscrito en un stroke play; y el
    # refresco con la RFEG en segundo plano, solo en producción (#251)
    return CloseEnrollmentsUseCase(uow, user_uow.users, lanzador, actividad=actividad)


def get_actualizar_handicaps_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    lanzador: LanzadorDeActualizaciones | None = Depends(get_lanzador_de_actualizaciones),
) -> ActualizarHandicapsUseCase:
    """El botón «Actualizar hándicaps» del organizador (#251): la zona da la hora de salida."""
    return ActualizarHandicapsUseCase(
        uow,
        CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        lanzador,
        reloj=lambda: datetime.now(UTC),
    )


def get_programar_actualizacion_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    lanzador: LanzadorDeActualizaciones | None = Depends(get_lanzador_de_actualizaciones),
) -> ProgramarActualizacionUseCase:
    """Programar la actualización de hándicaps (#251): la ventana se mira en esa hora."""
    return ProgramarActualizacionUseCase(
        uow,
        CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=lambda: datetime.now(UTC),
        refresco_activo=lanzador is not None,
    )


def get_anular_programacion_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> AnularProgramacionUseCase:
    """Anular la actualización de hándicaps programada (#251)."""
    return AnularProgramacionUseCase(uow)


def get_ventana_de_actualizacion_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    lanzador: LanzadorDeActualizaciones | None = Depends(get_lanzador_de_actualizaciones),
) -> VentanaDeActualizacionUseCase:
    """Si el organizador puede actualizar ahora los hándicaps, para la ficha (#251)."""
    return VentanaDeActualizacionUseCase(
        uow,
        CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=lambda: datetime.now(UTC),
        refresco_activo=lanzador is not None,
    )


def get_handicap_update_status_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> GetHandicapUpdateStatusUseCase:
    """La última actualización de hándicaps, para la ficha del organizador (#251)."""
    return GetHandicapUpdateStatusUseCase(uow, user_uow.users)


def get_name_captains_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    lanzador: LanzadorDeActualizaciones | None = Depends(get_lanzador_de_actualizaciones),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> NameCaptainsUseCase:
    """Proveedor del caso de uso NameCaptainsUseCase (BE #320), con el refresco (#251)."""
    return NameCaptainsUseCase(uow, lanzador, actividad=actividad)


def get_name_vice_captain_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> NameViceCaptainUseCase:
    """Proveedor del caso de uso NameViceCaptainUseCase (BE #320)."""
    return NameViceCaptainUseCase(uow)


def get_fill_captain_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> FillCaptainUseCase:
    """Proveedor del caso de uso FillCaptainUseCase (BE #320)."""
    return FillCaptainUseCase(uow)


def get_start_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> StartCompetitionUseCase:
    """
    Proveedor del caso de uso StartCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `StartCompetitionUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    # Los usuarios, para nombrar a quien no tenga franja en un stroke play (#251)
    return StartCompetitionUseCase(uow, user_uow.users, actividad=actividad)


def get_complete_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    achievements: TournamentAchievementsPublisherInterface = Depends(
        get_tournament_achievements_publisher
    ),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> CompleteCompetitionUseCase:
    """
    Proveedor del caso de uso CompleteCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `CompleteCompetitionUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.

    Cerrar el torneo es lo que dispara el feed de logros (BE #175), de ahí el
    publicador.
    """
    return CompleteCompetitionUseCase(uow, achievements, actividad=actividad)


def get_cancel_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> CancelCompetitionUseCase:
    """
    Proveedor del caso de uso CancelCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `CancelCompetitionUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return CancelCompetitionUseCase(uow, actividad=actividad)


def get_revert_competition_status_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> RevertCompetitionStatusUseCase:
    """
    Proveedor del caso de uso RevertCompetitionStatusUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `RevertCompetitionStatusUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return RevertCompetitionStatusUseCase(uow)


def get_revert_competition_to_in_progress_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> RevertCompetitionToInProgressUseCase:
    """
    Proveedor del caso de uso RevertCompetitionToInProgressUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `RevertCompetitionToInProgressUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return RevertCompetitionToInProgressUseCase(uow, actividad=actividad)


def get_reopen_enrollments_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> ReopenEnrollmentsUseCase:
    """
    Proveedor del caso de uso ReopenEnrollmentsUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `ReopenEnrollmentsUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return ReopenEnrollmentsUseCase(
        uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=lambda: datetime.now(UTC),
        actividad=actividad,
    )


def get_add_golf_course_to_competition_use_case(
    competition_uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> AddGolfCourseToCompetitionUseCase:
    """
    Proveedor del caso de uso AddGolfCourseToCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` y `get_golf_course_uow`.
    2. Crea una instancia de `AddGolfCourseToCompetitionUseCase` con ambas dependencias.
    3. El golf_course_repository se obtiene desde golf_course_uow.golf_courses.
    """
    return AddGolfCourseToCompetitionUseCase(
        uow=competition_uow,
        golf_course_repository=golf_course_uow.golf_courses,
    )


def get_remove_golf_course_from_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> RemoveGolfCourseFromCompetitionUseCase:
    """
    Proveedor del caso de uso RemoveGolfCourseFromCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `RemoveGolfCourseFromCompetitionUseCase` con esa dependencia.
    """
    return RemoveGolfCourseFromCompetitionUseCase(uow)


def get_reorder_golf_courses_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> ReorderGolfCoursesUseCase:
    """
    Proveedor del caso de uso ReorderGolfCoursesUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `ReorderGolfCoursesUseCase` con esa dependencia.
    """
    return ReorderGolfCoursesUseCase(uow)


def get_request_enrollment_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> RequestEnrollmentUseCase:
    """Apuntarse a una pública (28 oct 2026): abre la programada si toca y avisa."""
    return RequestEnrollmentUseCase(
        uow,
        user_uow.users,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        actividad=actividad,
    )


def get_direct_enroll_player_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> DirectEnrollPlayerUseCase:
    """Proveedor del caso de uso DirectEnrollPlayerUseCase."""
    return DirectEnrollPlayerUseCase(uow, user_uow.users, actividad=actividad)


def get_handle_enrollment_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> HandleEnrollmentUseCase:
    """Proveedor del caso de uso HandleEnrollmentUseCase."""
    return HandleEnrollmentUseCase(uow, user_uow.users, actividad=actividad)


def get_cancel_enrollment_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> CancelEnrollmentUseCase:
    """Proveedor del caso de uso CancelEnrollmentUseCase."""
    return CancelEnrollmentUseCase(uow)


def get_withdraw_enrollment_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> WithdrawEnrollmentUseCase:
    """Proveedor del caso de uso WithdrawEnrollmentUseCase."""
    return WithdrawEnrollmentUseCase(
        uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=lambda: datetime.now(UTC),
        actividad=actividad,
    )


def get_remove_enrolled_player_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> RemoveEnrolledPlayerUseCase:
    """Proveedor del caso de uso RemoveEnrolledPlayerUseCase (release social 2)."""
    return RemoveEnrolledPlayerUseCase(
        uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=lambda: datetime.now(UTC),
        actividad=actividad,
    )


def get_update_stroke_play_settings_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> UpdateStrokePlaySettingsUseCase:
    """Proveedor del caso de uso UpdateStrokePlaySettingsUseCase (#251)."""
    return UpdateStrokePlaySettingsUseCase(uow)


def get_set_custom_handicap_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> SetCustomHandicapUseCase:
    """Proveedor del caso de uso SetCustomHandicapUseCase."""
    return SetCustomHandicapUseCase(uow)


def get_set_name_preference_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> SetNamePreferenceUseCase:
    """Proveedor del caso de uso SetNamePreferenceUseCase."""
    return SetNamePreferenceUseCase(uow)


def get_remove_custom_handicap_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> RemoveCustomHandicapUseCase:
    """Proveedor del caso de uso RemoveCustomHandicapUseCase."""
    # Los usuarios: en un stroke play nadie se queda sin hándicap (#251)
    return RemoveCustomHandicapUseCase(uow, user_uow.users)


def get_list_enrollments_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    amigos: AmigosInterface = Depends(get_amigos),
) -> ListEnrollmentsUseCase:
    """Proveedor del caso de uso ListEnrollmentsUseCase (con quién ve a quién)."""
    return ListEnrollmentsUseCase(uow, amigos)


def get_assign_teams_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> AssignTeamsUseCase:
    """Proveedor del caso de uso AssignTeamsUseCase (cross-module: Competition + User)."""
    return AssignTeamsUseCase(
        uow=uow,
        user_repository=user_uow.users,
        snake_draft_service=SnakeDraftService(),
    )


def get_undo_teams_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> UndoTeamsUseCase:
    """Proveedor del caso de uso UndoTeamsUseCase (30 oct 2026)."""
    return UndoTeamsUseCase(uow=uow)


def get_start_draft_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> StartDraftUseCase:
    """Proveedor del caso de uso StartDraftUseCase (FE #653)."""
    return StartDraftUseCase(uow=uow, user_repository=user_uow.users)


def get_draft_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> GetDraftUseCase:
    """Proveedor del caso de uso GetDraftUseCase (FE #653)."""
    return GetDraftUseCase(uow=uow, user_repository=user_uow.users)


def get_make_draft_pick_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> MakeDraftPickUseCase:
    """Proveedor del caso de uso MakeDraftPickUseCase (FE #653)."""
    return MakeDraftPickUseCase(uow=uow, user_repository=user_uow.users)


def get_send_invitation_by_user_id_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IInvitationEmailService = Depends(get_invitation_email_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> SendInvitationByUserIdUseCase:
    """Proveedor del caso de uso SendInvitationByUserIdUseCase."""
    return SendInvitationByUserIdUseCase(uow, user_uow, email_service, actividad=actividad)


def get_send_invitation_by_email_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IInvitationEmailService = Depends(get_invitation_email_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> SendInvitationByEmailUseCase:
    """Proveedor del caso de uso SendInvitationByEmailUseCase."""
    return SendInvitationByEmailUseCase(uow, user_uow, email_service, actividad=actividad)


def get_list_my_invitations_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> ListMyInvitationsUseCase:
    """Proveedor del caso de uso ListMyInvitationsUseCase."""
    return ListMyInvitationsUseCase(uow, user_uow)


def get_respond_to_invitation_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> RespondToInvitationUseCase:
    """Proveedor del caso de uso RespondToInvitationUseCase."""
    return RespondToInvitationUseCase(uow, user_uow, actividad=actividad)


def get_cancel_invitation_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> CancelInvitationUseCase:
    """Proveedor del caso de uso CancelInvitationUseCase (BE #359)."""
    return CancelInvitationUseCase(uow, actividad=actividad)


def get_list_competition_invitations_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> ListCompetitionInvitationsUseCase:
    """Proveedor del caso de uso ListCompetitionInvitationsUseCase."""
    return ListCompetitionInvitationsUseCase(uow, user_uow, actividad=actividad)
