"""
Proveedores del juego de una competición: rondas y agenda, partidos y partidas, sobres,
anotación y clasificaciones.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, TypeVar

from fastapi import Depends

from src.config.dependencies.comun import (
    get_amigos,
    get_competition_activity_publisher,
    get_competition_uow,
    get_eventos_de_amigos,
    get_golf_course_uow,
    get_handicap_service,
    get_reloj_del_servidor,
    get_uow,
)
from src.modules.competition.application.ports.amigos_interface import AmigosInterface
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.ports.eventos_de_amigos_interface import (
    EventosDeAmigosInterface,
)
from src.modules.competition.application.services.envelope_desk import EnvelopeDesk
from src.modules.competition.application.services.jugadores_de_la_partida import (
    JugadoresDeLaPartida,
)
from src.modules.competition.application.use_cases.anotar_hoyo_de_partida_use_case import (
    AnotarHoyoDePartidaUseCase,
)
from src.modules.competition.application.use_cases.clasificaciones_use_case import (
    ClasificacionDeLaFranjaUseCase,
    ClasificacionGeneralUseCase,
    ClasificacionScratchUseCase,
)
from src.modules.competition.application.use_cases.concede_match_use_case import (
    ConcedeMatchUseCase,
)
from src.modules.competition.application.use_cases.configure_schedule_use_case import (
    ConfigureScheduleUseCase,
)
from src.modules.competition.application.use_cases.create_round_use_case import (
    CreateRoundUseCase,
)
from src.modules.competition.application.use_cases.declare_walkover_use_case import (
    DeclareWalkoverUseCase,
)
from src.modules.competition.application.use_cases.delete_round_use_case import (
    DeleteRoundUseCase,
)
from src.modules.competition.application.use_cases.entregar_tarjeta_de_partida_use_case import (
    EntregarTarjetaDePartidaUseCase,
    RetirarseDePartidaUseCase,
)
from src.modules.competition.application.use_cases.generate_matches_use_case import (
    GenerateMatchesUseCase,
)
from src.modules.competition.application.use_cases.get_envelopes_use_case import (
    GetEnvelopesUseCase,
)
from src.modules.competition.application.use_cases.get_leaderboard_use_case import (
    GetLeaderboardUseCase,
)
from src.modules.competition.application.use_cases.get_match_detail_use_case import (
    GetMatchDetailUseCase,
)
from src.modules.competition.application.use_cases.get_schedule_use_case import (
    GetScheduleUseCase,
)
from src.modules.competition.application.use_cases.get_scoring_view_use_case import (
    GetScoringViewUseCase,
)
from src.modules.competition.application.use_cases.list_my_pending_envelopes_use_case import (
    ListMyPendingEnvelopesUseCase,
)
from src.modules.competition.application.use_cases.list_my_sessions_without_matches_use_case import (
    ListMySessionsWithoutMatchesUseCase,
)
from src.modules.competition.application.use_cases.listas_de_espera_use_case import (
    DejarDeEsperarUseCase,
    EntendidoUseCase,
    EsperarUseCase,
    MisPlazasAsignadasUseCase,
)
from src.modules.competition.application.use_cases.organizador_de_partidas_use_case import (
    BorrarHoyoDePartidaUseCase,
    CerrarFranjaUseCase,
    CorregirHoyoDePartidaUseCase,
    MarcarNoPresentadoUseCase,
    ReabrirTarjetaUseCase,
    RetirarJugadorUseCase,
    ValidarLoAnotadoUseCase,
)
from src.modules.competition.application.use_cases.partidas_use_case import (
    BorrarPartidasUseCase,
    CambiarMarcadoresUseCase,
    GenerarPartidasUseCase,
    MisPartidasUseCase,
    MoverJugadorUseCase,
    ReordenarPartidasUseCase,
    VerPartidasUseCase,
)
from src.modules.competition.application.use_cases.plazas_en_franjas_use_case import (
    CogerPlazaUseCase,
    SoltarPlazaUseCase,
)
from src.modules.competition.application.use_cases.reassign_match_players_use_case import (
    ReassignMatchPlayersUseCase,
)
from src.modules.competition.application.use_cases.reset_envelopes_use_case import (
    ResetEnvelopesUseCase,
)
from src.modules.competition.application.use_cases.reveal_envelopes_use_case import (
    RevealEnvelopesUseCase,
)
from src.modules.competition.application.use_cases.submit_envelope_use_case import (
    SubmitEnvelopeUseCase,
)
from src.modules.competition.application.use_cases.submit_hole_score_use_case import (
    SubmitHoleScoreUseCase,
)
from src.modules.competition.application.use_cases.submit_scorecard_use_case import (
    SubmitScorecardUseCase,
)
from src.modules.competition.application.use_cases.update_match_status_use_case import (
    UpdateMatchStatusUseCase,
)
from src.modules.competition.application.use_cases.update_round_use_case import (
    UpdateRoundUseCase,
)
from src.modules.competition.application.use_cases.ver_anotacion_de_partida_use_case import (
    VerAnotacionDePartidaUseCase,
)
from src.modules.competition.application.use_cases.withdraw_match_player_use_case import (
    WithdrawMatchPlayerUseCase,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.schedule_format_service import (
    ScheduleFormatService,
)
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.infrastructure.services.competition_timezone_from_course import (
    CompetitionTimezoneFromCourse,
)
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.handicap_service import HandicapService
from src.shared.domain.services.playing_handicap_calculator import (
    PlayingHandicapCalculator,
)


def get_scoring_service() -> ScoringService:
    """Proveedor del servicio de dominio ScoringService (match play + lo de la Ryder)."""
    return ScoringService()


def get_coger_plaza_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> CogerPlazaUseCase:
    """Coger plaza en una franja de stroke play (#251); quien deja una pierde su aviso de salida."""
    return CogerPlazaUseCase(
        uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        actividad=actividad,
    )


def get_soltar_plaza_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> SoltarPlazaUseCase:
    """Soltar la plaza en una franja de stroke play (#251); a quien la lista se la da, su aviso."""
    return SoltarPlazaUseCase(uow, actividad=actividad)


def get_anotar_hoyo_de_partida_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    reloj: Callable[[], datetime] = Depends(get_reloj_del_servidor),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> AnotarHoyoDePartidaUseCase:
    """Anotar un hoyo en una partida (#251): la zona del campo da la hora de apertura."""
    return AnotarHoyoDePartidaUseCase(
        uow=uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=reloj,
        actividad=actividad,
    )


def get_entregar_tarjeta_de_partida_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> EntregarTarjetaDePartidaUseCase:
    """Entregar la tarjeta de una partida (#251)."""
    return EntregarTarjetaDePartidaUseCase(uow=uow)


def get_retirarse_de_partida_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> RetirarseDePartidaUseCase:
    """Retirarse de una partida (#251)."""
    return RetirarseDePartidaUseCase(uow=uow)


def get_corregir_hoyo_de_partida_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    reloj: Callable[[], datetime] = Depends(get_reloj_del_servidor),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> CorregirHoyoDePartidaUseCase:
    """El organizador corrige un hoyo de una partida (#251)."""
    return CorregirHoyoDePartidaUseCase(
        uow=uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=reloj,
        actividad=actividad,
    )


def get_reabrir_tarjeta_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    reloj: Callable[[], datetime] = Depends(get_reloj_del_servidor),
) -> ReabrirTarjetaUseCase:
    """El organizador reabre una tarjeta (#251)."""
    return ReabrirTarjetaUseCase(
        uow=uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=reloj,
    )


def get_marcar_no_presentado_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    reloj: Callable[[], datetime] = Depends(get_reloj_del_servidor),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> MarcarNoPresentadoUseCase:
    """El organizador marca a alguien como no presentado (#251); avisa a quien se recoloca (G3)."""
    return MarcarNoPresentadoUseCase(
        uow=uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=reloj,
        actividad=actividad,
    )


def get_retirar_jugador_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    reloj: Callable[[], datetime] = Depends(get_reloj_del_servidor),
) -> RetirarJugadorUseCase:
    """El organizador retira a quien ya jugó (#550)."""
    return RetirarJugadorUseCase(
        uow=uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=reloj,
    )


def get_borrar_hoyo_de_partida_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    reloj: Callable[[], datetime] = Depends(get_reloj_del_servidor),
) -> BorrarHoyoDePartidaUseCase:
    """El organizador borra lo anotado en un hoyo (13 oct 2026)."""
    return BorrarHoyoDePartidaUseCase(
        uow=uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=reloj,
    )


def get_validar_lo_anotado_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    reloj: Callable[[], datetime] = Depends(get_reloj_del_servidor),
) -> ValidarLoAnotadoUseCase:
    """El organizador valida lo anotado de quien juega sin marcador (QA del 11 oct 2026)."""
    return ValidarLoAnotadoUseCase(
        uow=uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=reloj,
    )


def get_cerrar_franja_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    reloj: Callable[[], datetime] = Depends(get_reloj_del_servidor),
) -> CerrarFranjaUseCase:
    """El organizador cierra las partidas de una franja (#251)."""
    return CerrarFranjaUseCase(
        uow=uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        user_repository=user_uow.users,
        reloj=reloj,
    )


def get_clasificacion_de_la_franja_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    eventos: EventosDeAmigosInterface = Depends(get_eventos_de_amigos),
) -> ClasificacionDeLaFranjaUseCase:
    """La clasificación de una franja (#251)."""
    return ClasificacionDeLaFranjaUseCase(uow=uow, user_repository=user_uow.users, eventos=eventos)


def get_clasificacion_general_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    eventos: EventosDeAmigosInterface = Depends(get_eventos_de_amigos),
) -> ClasificacionGeneralUseCase:
    """La clasificación general de un stroke play (#251)."""
    return ClasificacionGeneralUseCase(uow=uow, user_repository=user_uow.users, eventos=eventos)


def get_clasificacion_scratch_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    eventos: EventosDeAmigosInterface = Depends(get_eventos_de_amigos),
) -> ClasificacionScratchUseCase:
    """La clasificación scratch de un stroke play (#251)."""
    return ClasificacionScratchUseCase(uow=uow, user_repository=user_uow.users, eventos=eventos)


def get_ver_anotacion_de_partida_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    eventos: EventosDeAmigosInterface = Depends(get_eventos_de_amigos),
) -> VerAnotacionDePartidaUseCase:
    """La partida para anotar y las tarjetas de los suyos (#251), con la llave (27 oct)."""
    return VerAnotacionDePartidaUseCase(
        uow=uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        user_repository=user_uow.users,
        golf_courses=gc_uow.golf_courses,
        eventos=eventos,
    )


def get_jugadores_de_la_partida(
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> JugadoresDeLaPartida:
    """La foto de los jugadores de una partida (#251): campo y usuarios, misma sesión."""
    return JugadoresDeLaPartida(gc_uow.golf_courses, user_uow.users, PlayingHandicapCalculator())


def get_generar_partidas_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    jugadores: JugadoresDeLaPartida = Depends(get_jugadores_de_la_partida),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> GenerarPartidasUseCase:
    """Generar las partidas de una franja (#251): el campo da barras y zona horaria."""
    return GenerarPartidasUseCase(
        uow=uow,
        jugadores=jugadores,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        user_repository=user_uow.users,
        reloj=lambda: datetime.now(UTC),
        actividad=actividad,
    )


def get_mover_jugador_de_partida_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    jugadores: JugadoresDeLaPartida = Depends(get_jugadores_de_la_partida),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> MoverJugadorUseCase:
    """Mover a un jugador de partida (#251): quien no tenía, saca su foto con el campo."""
    return MoverJugadorUseCase(
        uow=uow,
        jugadores=jugadores,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        user_repository=user_uow.users,
        reloj=lambda: datetime.now(UTC),
        actividad=actividad,
    )


T = TypeVar("T")


def _de_las_partidas(
    caso_de_uso: Callable[..., T],
    uow: CompetitionUnitOfWorkInterface,
    gc_uow: GolfCourseUnitOfWorkInterface,
    user_uow: UserUnitOfWorkInterface,
    **extra: Any,
) -> T:
    """Los que solo necesitan la zona del campo y los nombres (#251); `extra`, lo de cada uno."""
    return caso_de_uso(
        uow=uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        user_repository=user_uow.users,
        reloj=lambda: datetime.now(UTC),
        **extra,
    )


def get_reordenar_partidas_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> ReordenarPartidasUseCase:
    """Reordenar las partidas de una franja (#251): avisa a quien cambia de hora (G3)."""
    return _de_las_partidas(ReordenarPartidasUseCase, uow, gc_uow, user_uow, actividad=actividad)


def get_cambiar_marcadores_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> CambiarMarcadoresUseCase:
    """Cambiar los marcadores de una partida (#251)."""
    return _de_las_partidas(CambiarMarcadoresUseCase, uow, gc_uow, user_uow)


def get_borrar_partidas_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> BorrarPartidasUseCase:
    """Borrar las partidas de una franja (#251)."""
    return _de_las_partidas(BorrarPartidasUseCase, uow, gc_uow, user_uow, actividad=actividad)


def get_ver_partidas_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    amigos: AmigosInterface = Depends(get_amigos),
    eventos: EventosDeAmigosInterface = Depends(get_eventos_de_amigos),
) -> VerPartidasUseCase:
    """Ver las partidas de una franja (#251), con los sin partida que deja ver la regla."""
    return _de_las_partidas(
        VerPartidasUseCase, uow, gc_uow, user_uow, amigos=amigos, eventos=eventos
    )


def get_mis_partidas_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> MisPartidasUseCase:
    """Mis partidas en una competición (#251), con el nombre de su campo (BE #532)."""
    return MisPartidasUseCase(
        uow=uow, user_repository=user_uow.users, golf_courses=gc_uow.golf_courses
    )


def get_esperar_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> EsperarUseCase:
    """Apuntarse a la lista de espera de una franja (#251)."""
    return EsperarUseCase(uow)


def get_dejar_de_esperar_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> DejarDeEsperarUseCase:
    """Salir de la lista de espera de una franja (#251); sin nada más, sale de la competición."""
    return DejarDeEsperarUseCase(uow, actividad=actividad)


def get_mis_plazas_asignadas_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> MisPlazasAsignadasUseCase:
    """Las plazas que asignó la lista de espera, para «Requiere tu atención» (#251)."""
    return MisPlazasAsignadasUseCase(uow)


def get_entendido_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> EntendidoUseCase:
    """«Entendido»: ya ha visto la plaza que le asignó la lista (#251)."""
    return EntendidoUseCase(uow)


# ======================================================================================
# ROUND, MATCH & TEAM ASSIGNMENT USE CASE PROVIDERS (Sprint 2 - Block 7)
# ======================================================================================


def get_create_round_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    reloj: Callable[[], datetime] = Depends(get_reloj_del_servidor),
) -> CreateRoundUseCase:
    """Proveedor del caso de uso CreateRoundUseCase: con la zona, para no crear una franja pasada."""
    return CreateRoundUseCase(
        uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=reloj,
    )


def get_update_round_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    jugadores: JugadoresDeLaPartida = Depends(get_jugadores_de_la_partida),
    reloj: Callable[[], datetime] = Depends(get_reloj_del_servidor),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> UpdateRoundUseCase:
    """Proveedor del caso de uso UpdateRoundUseCase: con el campo, rehace las partidas (#251)."""
    return UpdateRoundUseCase(
        uow,
        jugadores=jugadores,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=reloj,
        actividad=actividad,
    )


def get_delete_round_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> DeleteRoundUseCase:
    """Proveedor del caso de uso DeleteRoundUseCase (olvida en Actividad lo de la ronda)."""
    return DeleteRoundUseCase(uow, actividad=actividad)


def get_get_schedule_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
    amigos: AmigosInterface = Depends(get_amigos),
    eventos: EventosDeAmigosInterface = Depends(get_eventos_de_amigos),
) -> GetScheduleUseCase:
    """Proveedor del caso de uso GetScheduleUseCase (cross-module: Competition + GolfCourse).

    Lleva la mesa de sobres: mirar la agenda abre los que ya tocan, como mirar
    la página del sobre (BE #367).
    """
    return GetScheduleUseCase(
        uow,
        gc_uow.golf_courses,
        sobres=EnvelopeDesk(
            uow,
            user_uow.users,
            timezone_service=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
            generador=_generador_al_abrir(uow, gc_uow, user_uow, scoring_service, actividad),
        ),
        amigos=amigos,
        eventos=eventos,
    )


def get_get_match_detail_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    eventos: EventosDeAmigosInterface = Depends(get_eventos_de_amigos),
) -> GetMatchDetailUseCase:
    """Proveedor del caso de uso GetMatchDetailUseCase, con la llave (27 oct)."""
    return GetMatchDetailUseCase(uow, eventos=eventos)


def get_update_match_status_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> UpdateMatchStatusUseCase:
    """Proveedor del caso de uso UpdateMatchStatusUseCase."""
    return UpdateMatchStatusUseCase(uow, actividad=actividad)


def get_declare_walkover_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> DeclareWalkoverUseCase:
    """Proveedor del caso de uso DeclareWalkoverUseCase."""
    return DeclareWalkoverUseCase(uow, actividad=actividad)


def get_configure_schedule_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> ConfigureScheduleUseCase:
    """Proveedor del caso de uso ConfigureScheduleUseCase (olvida en Actividad lo sustituido)."""
    return ConfigureScheduleUseCase(
        uow, schedule_format_service=ScheduleFormatService(), actividad=actividad
    )


def _construir_generador(
    uow, gc_uow, user_uow, scoring_service, handicap_service=None, actividad=None
) -> GenerateMatchesUseCase:
    """El unico sitio que monta GenerateMatchesUseCase.

    Lo usan el boton de «Generar» y la apertura de los sobres (BE #361): con
    dos sitios, una dependencia nueva del constructor se olvidaria en uno y la
    generacion automatica saldria cableada distinta sin que nadie lo notara.
    """
    return GenerateMatchesUseCase(
        uow=uow,
        golf_course_repository=gc_uow.golf_courses,
        user_repository=user_uow.users,
        handicap_calculator=PlayingHandicapCalculator(),
        scoring_service=scoring_service,
        handicap_service=handicap_service,
        actividad=actividad,
    )


def _generador_al_abrir(
    uow, gc_uow, user_uow, scoring_service, actividad=None
) -> GenerateMatchesUseCase:
    """Lo que crea los partidos al abrirse los sobres (BE #361).

    Sobre la MISMA Unit of Work que el caso de uso de los sobres: abrirlos y
    crear los partidos van en una transaccion. Sin servicio de handicap: al
    abrir no se pregunta a la RFEG, que seria una llamada de red por jugador
    dentro de la lectura de la pantalla.
    """
    return _construir_generador(uow, gc_uow, user_uow, scoring_service, actividad=actividad)


def get_list_my_sessions_without_matches_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> ListMySessionsWithoutMatchesUseCase:
    """Proveedor del caso de uso ListMySessionsWithoutMatchesUseCase (BE #361)."""
    return ListMySessionsWithoutMatchesUseCase(uow)


def get_submit_envelope_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> SubmitEnvelopeUseCase:
    """Proveedor del caso de uso SubmitEnvelopeUseCase (FE #655).

    Lleva la zona del campo porque entregar mira el plazo: pasada la hora los
    sobres se abren y la entrega llega tarde.
    """
    return SubmitEnvelopeUseCase(
        uow,
        user_uow.users,
        timezone_service=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        generador=_generador_al_abrir(uow, gc_uow, user_uow, scoring_service, actividad),
    )


def get_envelopes_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> GetEnvelopesUseCase:
    """Proveedor del caso de uso GetEnvelopesUseCase (FE #655).

    Lleva la zona del campo porque mirar los sobres es lo que los abre cuando
    llega su hora —6 horas antes de la sesion—, sin ningun proceso de fondo.
    """
    return GetEnvelopesUseCase(
        uow,
        user_uow.users,
        timezone_service=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        generador=_generador_al_abrir(uow, gc_uow, user_uow, scoring_service, actividad),
    )


def get_reveal_envelopes_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> RevealEnvelopesUseCase:
    """Proveedor del caso de uso RevealEnvelopesUseCase (FE #655).

    El repositorio de usuarios es para el handicap del sobre que haya que
    rellenar: el propio de la inscripcion si lo tiene, y si no el del jugador.

    La zona del campo es para saber si esta sesion llega a tener plazo: la que
    no lo tiene —campo sin zona— no se abre sola nunca, y ahi el organizador
    conserva la llave. Sin este cableado esa sesion se quedaria atascada.
    """
    return RevealEnvelopesUseCase(
        uow,
        user_uow.users,
        timezone_service=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        generador=_generador_al_abrir(uow, gc_uow, user_uow, scoring_service, actividad),
    )


def get_list_my_pending_envelopes_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ListMyPendingEnvelopesUseCase:
    """Proveedor del caso de uso ListMyPendingEnvelopesUseCase (FE #655).

    La hora la pone el SERVIDOR: con la del movil, un telefono atrasado
    resucitaria avisos de sesiones ya jugadas. Y la zona del campo es lo que
    convierte la franja en una hora, que es contra lo que se mide el plazo.
    """
    return ListMyPendingEnvelopesUseCase(
        uow,
        timezone_service=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
    )


def get_reset_envelopes_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> ResetEnvelopesUseCase:
    """Proveedor del caso de uso ResetEnvelopesUseCase (FE #655).

    Sin zona horaria: rehacer los sobres no mira ningun reloj, solo que no se
    haya jugado nada de esa sesion.
    """
    return ResetEnvelopesUseCase(uow, user_uow.users, actividad=actividad)


def get_generate_matches_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    handicap_service: HandicapService = Depends(get_handicap_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> GenerateMatchesUseCase:
    """Proveedor del caso de uso GenerateMatchesUseCase (cross-module: Competition + GolfCourse + User)."""
    return _construir_generador(uow, gc_uow, user_uow, scoring_service, handicap_service, actividad)


def get_reassign_match_players_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> ReassignMatchPlayersUseCase:
    """Proveedor del caso de uso ReassignMatchPlayersUseCase (cross-module: Competition + GolfCourse + User)."""
    return ReassignMatchPlayersUseCase(
        uow=uow,
        golf_course_repository=gc_uow.golf_courses,
        user_repository=user_uow.users,
        handicap_calculator=PlayingHandicapCalculator(),
        scoring_service=scoring_service,
        actividad=actividad,
    )


# ======================================================================================
# SCORING USE CASE PROVIDERS (Sprint 4 - Live Scoring)
# ======================================================================================


def get_get_scoring_view_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    eventos: EventosDeAmigosInterface = Depends(get_eventos_de_amigos),
) -> GetScoringViewUseCase:
    """Proveedor del caso de uso GetScoringViewUseCase (cross-module: Competition + GolfCourse + User)."""
    return GetScoringViewUseCase(
        uow, user_uow.users, scoring_service, gc_uow.golf_courses, eventos=eventos
    )


def get_submit_hole_score_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> SubmitHoleScoreUseCase:
    """Proveedor del caso de uso SubmitHoleScoreUseCase (cross-module: Competition + GolfCourse + User)."""
    return SubmitHoleScoreUseCase(
        uow, user_uow.users, scoring_service, gc_uow.golf_courses, actividad=actividad
    )


def get_submit_scorecard_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> SubmitScorecardUseCase:
    """Proveedor del caso de uso SubmitScorecardUseCase (el campo, para el par de la raya)."""
    return SubmitScorecardUseCase(
        uow, scoring_service, actividad=actividad, golf_course_repo=gc_uow.golf_courses
    )


def get_get_leaderboard_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    eventos: EventosDeAmigosInterface = Depends(get_eventos_de_amigos),
) -> GetLeaderboardUseCase:
    """Proveedor del caso de uso GetLeaderboardUseCase, con la llave (27 oct)."""
    return GetLeaderboardUseCase(uow, user_uow.users, scoring_service, eventos=eventos)


def get_concede_match_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> ConcedeMatchUseCase:
    """Proveedor del caso de uso ConcedeMatchUseCase."""
    return ConcedeMatchUseCase(uow, scoring_service, actividad=actividad)


def get_withdraw_match_player_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
) -> WithdrawMatchPlayerUseCase:
    """Proveedor de WithdrawMatchPlayerUseCase (fourball con un jugador retirado)."""
    return WithdrawMatchPlayerUseCase(uow, scoring_service)
