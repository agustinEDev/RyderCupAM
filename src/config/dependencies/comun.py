"""
Lo que comparten todos los contextos: sesión de BD, unidades de trabajo, usuario actual,
correo, log de seguridad, reloj y las piezas que un contexto le presta a otro (publicadores
de actividad, amigos, hándicap, lanzador de actualizaciones). Los demás módulos solo
importan de aquí.
"""

import logging
import os
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyCookie
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.contrasenas import instala_el_hasher_de_contrasenas
from src.config.database import async_session_maker
from src.config.refresco_de_handicaps import LanzadorEnSegundoPlano, refresco_activado
from src.config.terms_guard import require_current_terms
from src.modules.competition.application.ports.amigos_interface import AmigosInterface
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.ports.eventos_de_amigos_interface import (
    EventosDeAmigosInterface,
)
from src.modules.competition.application.ports.invitation_email_service_interface import (
    IInvitationEmailService,
)
from src.modules.competition.application.ports.lanzador_de_actualizaciones import (
    LanzadorDeActualizaciones,
)
from src.modules.competition.application.use_cases.clasificaciones_use_case import (
    ClasificacionGeneralUseCase,
)
from src.modules.competition.application.use_cases.get_leaderboard_use_case import (
    GetLeaderboardUseCase,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_unit_of_work import (
    SQLAlchemyCompetitionUnitOfWork,
)
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.infrastructure.persistence.sqlalchemy.golf_course_unit_of_work import (
    SQLAlchemyGolfCourseUnitOfWork,
)
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.infrastructure.persistence.sqlalchemy.quick_match_unit_of_work import (
    SQLAlchemyQuickMatchUnitOfWork,
)
from src.modules.social.application.ports.player_course_history_interface import (
    PlayerCourseHistoryInterface,
)
from src.modules.social.application.ports.player_differentials_interface import (
    PlayerDifferentialsInterface,
)
from src.modules.social.application.ports.social_email_service_interface import (
    ISocialEmailService,
)
from src.modules.social.application.use_cases.publish_competition_notices_use_case import (
    PublishCompetitionNoticesUseCase,
)
from src.modules.social.application.use_cases.publish_quick_match_result_use_case import (
    PublishQuickMatchResultUseCase,
)
from src.modules.social.application.use_cases.publish_round_achievements_use_case import (
    PublishRoundAchievementsUseCase,
)
from src.modules.social.application.use_cases.publish_tournament_achievements_use_case import (
    PublishTournamentAchievementsUseCase,
)
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.infrastructure.adapters.amigos_adapter import AmigosAdapter
from src.modules.social.infrastructure.adapters.competition_activity_publisher import (
    CompetitionActivityPublisher,
)
from src.modules.social.infrastructure.adapters.eventos_de_amigos_adapter import (
    EventosDeAmigosAdapter,
)
from src.modules.social.infrastructure.adapters.player_course_history_adapter import (
    PlayerCourseHistoryAdapter,
)
from src.modules.social.infrastructure.adapters.player_differentials_adapter import (
    StatsPlayerDifferentialsAdapter,
)
from src.modules.social.infrastructure.persistence.sqlalchemy.social_unit_of_work import (
    SQLAlchemySocialUnitOfWork,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.ports.image_processor_interface import IImageProcessor
from src.modules.user.application.services.datos_del_acceso import CLAIM_DEL_DISPOSITIVO
from src.modules.user.application.use_cases.get_current_user_use_case import (
    GetCurrentUserUseCase,
)
from src.modules.user.application.use_cases.get_player_stats_use_case import (
    GetPlayerStatsUseCase,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.handicap_service import HandicapService
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.external.pillow_image_processor import (
    PillowImageProcessor,
)
from src.modules.user.infrastructure.external.rfeg_handicap_service import (
    RFEGHandicapService,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork,
)
from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)
from src.shared.domain.services.match_play_scoring import MatchPlayScoring
from src.shared.infrastructure.email.email_service import EmailService
from src.shared.infrastructure.persistence.sqlalchemy.country_repository import (
    SQLAlchemyCountryRepository,
)
from src.shared.infrastructure.security.cookie_handler import COOKIE_NAME, read_access_token
from src.shared.infrastructure.security.jwt_handler import (
    verify_access_token,
)

# El hash de las contraseñas: lo decide la infraestructura (bcrypt, 12 rondas) y se
# instala aquí, al cargar la composition root, antes de cualquier petición
instala_el_hasher_de_contrasenas()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Proveedor de sesión de base de datos para la inyección de dependencias de FastAPI.

    Esta función es un generador asíncrono que:
    1. Crea una nueva sesión de SQLAlchemy para una petición entrante.
    2. Proporciona (yields) esta sesión al endpoint.
    3. Se asegura de que la sesión se cierre siempre al final,
       liberando la conexión a la base de datos.
    """
    async with async_session_maker() as session:
        yield session


def get_uow(
    session: AsyncSession = Depends(get_db_session),
) -> UserUnitOfWorkInterface:
    """
    Proveedor de la Unit of Work para la inyección de dependencias.

    Esta función:
    1. Depende de `get_db_session` para obtener una sesión de BD.
    2. Crea una instancia de `SQLAlchemyUnitOfWork` con esa sesión.
    3. Devuelve la instancia, cumpliendo con la interfaz `UserUnitOfWorkInterface`.
    """
    return SQLAlchemyUnitOfWork(session)


def get_handicap_service() -> HandicapService:
    """
    Proveedor del servicio de hándicap.

    Esta función:
    1. Crea una instancia de RFEGHandicapService.
    2. Configura el timeout apropiado.
    3. Devuelve la instancia que implementa HandicapService.

    Returns:
        Implementación concreta del servicio de hándicap (RFEG)
    """
    return RFEGHandicapService(timeout=10)


def get_email_service() -> IEmailService:
    """
    Proveedor del servicio de email.

    Esta función:
    1. Crea una instancia de EmailService (Mailgun).
    2. Devuelve la instancia que implementa IEmailService.

    Returns:
        Implementación concreta del servicio de email (Mailgun)
    """
    return EmailService()


def get_country_repository(
    session: AsyncSession = Depends(get_db_session),
) -> CountryRepositoryInterface:
    """
    Proveedor del repositorio de países.

    Esta función:
    1. Depende de `get_db_session` para obtener una sesión de BD.
    2. Crea una instancia de `SQLAlchemyCountryRepository`.
    3. Devuelve la instancia que implementa CountryRepositoryInterface.

    Returns:
        Implementación concreta del repositorio de países (SQLAlchemy)
    """
    return SQLAlchemyCountryRepository(session)


def get_fabrica_de_sesiones() -> async_sessionmaker[AsyncSession]:
    """La fábrica de sesiones de BD para lo que corre fuera de la petición (BE #737)."""
    return async_session_maker


def get_image_processor() -> IImageProcessor:
    """Proveedor del procesador de imágenes (Pillow) para avatares subidos."""
    return PillowImageProcessor()


# El esquema de seguridad de OpenAPI: la cookie httpOnly del access token, la única
# forma de autenticarse desde la 2.58.0 (F-03). auto_error=False: la falta de sesión
# la decide get_current_user, con su 401 de siempre
security = APIKeyCookie(name=COOKIE_NAME, auto_error=False)


async def get_current_user(
    request: Request,
    credentials: str | None = Depends(security),  # noqa: ARG001 - declara la cookie en OpenAPI; el token lo lee read_access_token
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> UserResponseDTO:
    """
    Dependencia para obtener el usuario actual desde el token JWT.

    El token sale solo de la cookie httpOnly "access_token" (F-03, 2.58.0): JavaScript
    no puede leerla, y la cabecera Authorization: Bearer ya no autentica.

    Flujo:
    1. Lee el token de la cookie (read_access_token, la misma regla que el rate
       limit, el CSRF y Sentry)
    2. Verifica y decodifica el token JWT
    3. Busca el usuario en la base de datos
    4. Retorna el usuario autenticado

    Args:
        request: Request de FastAPI (para leer cookies)
        credentials: La cookie, solo para declararla en OpenAPI
        uow: Unit of Work para acceso a datos

    Raises:
        HTTPException 401: Si no hay token, es inválido, o el usuario no existe

    Returns:
        Usuario autenticado

    Example:
        @router.get("/protected")
        async def protected_route(current_user: UserResponseDTO = Depends(get_current_user)):
            return {"message": f"Hello {current_user.email}"}
    """
    # Solo la cookie httpOnly (2.58.0). La misma regla con la que el rate limit decide
    # de quién es la petición (#273)
    token = read_access_token(request)

    # Sin cookie no hay sesión
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales de autenticación no proporcionadas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verificar y decodificar token (mismo código que antes)
    payload = verify_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extraer user_id del payload
    user_id_str: str | None = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: falta subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Buscar usuario
    use_case = GetCurrentUserUseCase(uow)
    user = await use_case.execute(user_id_str)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # El dispositivo del token, por su id (BE #737, cierra #730). Antes se buscaba
    # por una huella de navegador e IP que no se actualizaba: con cada actualización
    # del navegador o cambio de red no lo veía (34 de 60 en producción), y podía
    # echar a un usuario legítimo con un «revocado» falso.
    #
    # Un token sin `did` ya no vale (auditoría OWASP, A07): toda sesión tiene
    # dispositivo, y una sin él no se podía revocar. Es un 401 normal, no
    # «revocado»: la app refresca y el refresco ya trae `did`. Si la BD falla al
    # comprobarlo, la petición no pasa (decidido el 5 nov 2026)
    did = payload.get(CLAIM_DEL_DISPOSITIVO)
    if not did:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: falta el dispositivo",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        device_id = UserDeviceId.from_string(did)
    except (ValueError, TypeError):
        device_id = None
    dispositivo = None
    if device_id is not None:
        async with uow:
            dispositivo = await uow.user_devices.find_by_id_and_user(
                device_id=device_id, user_id=UserId(user_id_str)
            )
    if dispositivo is None:
        logging.getLogger(__name__).warning(
            f"Access denied: device {did} revoked or not owned by user {user_id_str}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Dispositivo revocado. Por favor, inicia sesión nuevamente.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # El dispositivo de la petición, ya comprobado: la lista lo marca como el actual
    # sin volver a leer el token
    request.state.dispositivo_actual = str(dispositivo.id.value)

    # Términos de uso (B6): sin la versión vigente aceptada, 403
    # TERMS_NOT_ACCEPTED en toda ruta con sesión salvo las exentas
    # (src/config/terms_guard.py). Va al final: un token inválido o un
    # dispositivo revocado siguen siendo un 401
    require_current_terms(request, user)

    return user


async def get_current_user_optional(
    request: Request,
    credentials: str | None = Depends(security),
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> UserResponseDTO | None:
    """
    El usuario de la sesión, o None si no hay sesión (release social 3, 28 oct 2026).

    Para lo que también ve un visitante: la clasificación por enlace. Sin token
    es un visitante; con un token caducado o inválido, el 401 de siempre, para
    que la app renueve la sesión en vez de enseñarle la vista de visitante.
    """
    if not read_access_token(request):
        return None
    return await get_current_user(request, credentials, uow)


# Enrollment Use Cases


def get_competition_uow(
    session: AsyncSession = Depends(get_db_session),
) -> CompetitionUnitOfWorkInterface:
    """
    Proveedor de la Unit of Work para el módulo Competition.

    Esta función:
    1. Depende de `get_db_session` para obtener una sesión de BD.
    2. Crea una instancia de `SQLAlchemyCompetitionUnitOfWork` con esa sesión.
    3. Devuelve la instancia, cumpliendo con la interfaz `CompetitionUnitOfWorkInterface`.

    La UoW de Competition coordina 3 repositorios:
    - competitions: Repositorio de competiciones
    - enrollments: Repositorio de inscripciones
    - countries: Repositorio de países (shared domain)
    """
    return SQLAlchemyCompetitionUnitOfWork(session)


def get_golf_course_uow(
    session: AsyncSession = Depends(get_db_session),
) -> GolfCourseUnitOfWorkInterface:
    """
    Proveedor de la Unit of Work para el módulo Golf Course.

    Esta función:
    1. Depende de `get_db_session` para obtener una sesión de BD.
    2. Crea una instancia de `SQLAlchemyGolfCourseUnitOfWork` con esa sesión.
    3. Devuelve la instancia, cumpliendo con la interfaz `GolfCourseUnitOfWorkInterface`.

    La UoW de Golf Course coordina 2 repositorios:
    - golf_courses: Repositorio de campos de golf
    - countries: Repositorio de países (shared domain)
    """
    return SQLAlchemyGolfCourseUnitOfWork(session)


def get_social_uow(
    session: AsyncSession = Depends(get_db_session),
) -> SocialUnitOfWorkInterface:
    """
    Proveedor de la Unit of Work para el módulo Social.

    Esta función:
    1. Depende de `get_db_session` para obtener una sesión de BD.
    2. Crea una instancia de `SQLAlchemySocialUnitOfWork` con esa sesión.
    3. Devuelve la instancia, cumpliendo con la interfaz `SocialUnitOfWorkInterface`.
    """
    return SQLAlchemySocialUnitOfWork(session)


def get_amigos(
    social_uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
) -> AmigosInterface:
    """Los amigos de quien mira, del módulo social (release social 2)."""
    return AmigosAdapter(social_uow)


def get_eventos_de_amigos(
    social_uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> EventosDeAmigosInterface:
    """La llave de una privada: amigos con evento en la Actividad de quien mira (27 oct)."""
    return EventosDeAmigosAdapter(social_uow, user_uow)


def get_social_email_service() -> ISocialEmailService:
    """Proveedor del servicio de email para el modulo Social (amistades)."""
    return EmailService()


def get_quick_match_uow(
    session: AsyncSession = Depends(get_db_session),
) -> QuickMatchUnitOfWorkInterface:
    """
    Proveedor de la Unit of Work para el módulo QuickMatch.

    Esta función:
    1. Depende de `get_db_session` para obtener una sesión de BD.
    2. Crea una instancia de `SQLAlchemyQuickMatchUnitOfWork` con esa sesión.
    3. Devuelve la instancia, cumpliendo con la interfaz `QuickMatchUnitOfWorkInterface`.
    """
    return SQLAlchemyQuickMatchUnitOfWork(session)


def get_get_player_stats_use_case(
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    competition_uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    quick_match_uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> GetPlayerStatsUseCase:
    """Proveedor del caso de uso GetPlayerStatsUseCase."""
    return GetPlayerStatsUseCase(user_uow, competition_uow, quick_match_uow, golf_course_uow)


async def get_activity_db_session(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[AsyncSession, None]:
    """
    Una sesion propia para publicar en Actividad, aparte de la de la peticion.

    Todas las unidades de trabajo de una peticion comparten sesion. Actividad
    publica despues de que la accion se haya guardado, y si fallara en esa
    misma sesion su `rollback` caducaria todo lo que la accion tiene cargado:
    al montar la respuesta, la sesion asincrona intentaria recargarlo y la
    peticion acabaria en 500 con la accion hecha. Con su propia sesion —del
    mismo motor, otra conexion— un fallo de Actividad no toca nada de la
    accion. Se crea con el motor de la sesion de la peticion para usar la
    misma base de datos que ella (tambien en los tests).
    """
    async with AsyncSession(bind=session.bind, expire_on_commit=False) as propia:
        yield propia


@dataclass(frozen=True)
class ActivityUnitsOfWork:
    """Las unidades de trabajo con las que publica Actividad, sobre su propia sesion."""

    user: UserUnitOfWorkInterface
    competition: CompetitionUnitOfWorkInterface
    quick_match: QuickMatchUnitOfWorkInterface
    golf_course: GolfCourseUnitOfWorkInterface
    social: SocialUnitOfWorkInterface

    @property
    def differentials(self) -> PlayerDifferentialsInterface:
        return StatsPlayerDifferentialsAdapter(
            GetPlayerStatsUseCase(self.user, self.competition, self.quick_match, self.golf_course)
        )

    @property
    def history(self) -> PlayerCourseHistoryInterface:
        return PlayerCourseHistoryAdapter(self.quick_match, self.competition, self.golf_course)


def get_activity_units_of_work(
    session: AsyncSession = Depends(get_activity_db_session),
) -> ActivityUnitsOfWork:
    """Proveedor de las unidades de trabajo de Actividad (su sesion, no la de la peticion)."""
    return ActivityUnitsOfWork(
        user=SQLAlchemyUnitOfWork(session),
        competition=SQLAlchemyCompetitionUnitOfWork(session),
        quick_match=SQLAlchemyQuickMatchUnitOfWork(session),
        golf_course=SQLAlchemyGolfCourseUnitOfWork(session),
        social=SQLAlchemySocialUnitOfWork(session),
    )


def get_publish_round_achievements_use_case(
    uows: ActivityUnitsOfWork = Depends(get_activity_units_of_work),
) -> PublishRoundAchievementsUseCase:
    """Proveedor del caso de uso PublishRoundAchievementsUseCase."""
    return PublishRoundAchievementsUseCase(
        social_uow=uows.social,
        quick_match_uow=uows.quick_match,
        golf_course_uow=uows.golf_course,
        user_uow=uows.user,
        differentials=uows.differentials,
        history=uows.history,
    )


def get_publish_tournament_achievements_use_case(
    uows: ActivityUnitsOfWork = Depends(get_activity_units_of_work),
) -> PublishTournamentAchievementsUseCase:
    """Proveedor del caso de uso PublishTournamentAchievementsUseCase."""
    return PublishTournamentAchievementsUseCase(
        social_uow=uows.social,
        competition_uow=uows.competition,
        golf_course_uow=uows.golf_course,
        user_uow=uows.user,
        differentials=uows.differentials,
        history=uows.history,
    )


def get_publish_quick_match_result_use_case(
    uows: ActivityUnitsOfWork = Depends(get_activity_units_of_work),
) -> PublishQuickMatchResultUseCase:
    """Proveedor del caso de uso PublishQuickMatchResultUseCase (BE-2)."""
    return PublishQuickMatchResultUseCase(
        uows.social, uows.quick_match, uows.golf_course, uows.user
    )


def get_publish_competition_notices_use_case(
    uows: ActivityUnitsOfWork = Depends(get_activity_units_of_work),
) -> PublishCompetitionNoticesUseCase:
    """Proveedor del caso de uso PublishCompetitionNoticesUseCase (BE-2)."""
    return PublishCompetitionNoticesUseCase(uows.social, uows.user)


def get_competition_activity_publisher(
    notices: PublishCompetitionNoticesUseCase = Depends(get_publish_competition_notices_use_case),
    uows: ActivityUnitsOfWork = Depends(get_activity_units_of_work),
    achievements: PublishTournamentAchievementsUseCase = Depends(
        get_publish_tournament_achievements_use_case
    ),
    round_achievements: PublishRoundAchievementsUseCase = Depends(
        get_publish_round_achievements_use_case
    ),
) -> CompetitionActivityPublisherInterface:
    """
    Proveedor del adaptador que lleva a Actividad lo de `competition` (BE-2).

    Con la general oficial a mano: la clasificacion final de cada uno sale de
    ella, no de otra cuenta; la de una Ryder, de su leaderboard oficial (I).
    Todo sobre la sesion propia de Actividad.
    """
    return CompetitionActivityPublisher(
        notices,
        ClasificacionGeneralUseCase(uow=uows.competition, user_repository=uows.user.users),
        uows.competition,
        ryder_scoreboard=GetLeaderboardUseCase(uows.competition, uows.user.users, ScoringService()),
        achievements=achievements,
        round_achievements=round_achievements,
    )


def get_match_play_scoring() -> MatchPlayScoring:
    """Proveedor de las reglas del match play, sin lo de la Ryder (RyderCupAM#165)."""
    return MatchPlayScoring()


_lanzador: LanzadorEnSegundoPlano | None = None


def get_lanzador_de_actualizaciones() -> LanzadorDeActualizaciones | None:
    """
    El lanzador de actualizaciones de hándicaps, uno para todo el proceso (#251).

    Solo con `HANDICAP_REFRESH_ENABLED` encendido y fuera de los tests: si no,
    al cerrar no se pregunta a la RFEG.
    """
    global _lanzador  # noqa: PLW0603 - uno por proceso, con sus tareas en marcha
    if not refresco_activado(os.environ):
        return None
    if _lanzador is None:
        _lanzador = LanzadorEnSegundoPlano(
            async_session_maker, RFEGHandicapService(timeout=10), EmailService()
        )
    return _lanzador


def get_reloj_del_servidor() -> Callable[[], datetime]:
    """
    El reloj del servidor para la anotación de las partidas (#251, PR 5).

    Decide si la anotación ya abrió; nunca una hora que mande el cliente. Es
    una dependencia para que los tests de la API puedan ponerlo en el día del
    torneo.
    """
    return lambda: datetime.now(UTC)


def get_invitation_email_service() -> IInvitationEmailService:
    """Proveedor del servicio de email para invitaciones."""
    return EmailService()
