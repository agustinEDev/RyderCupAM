"""
JugadoresDelPartido - Los jugadores de un partido con el reparto de su formato (BE #502).

Estaba dentro de la reasignación de jugadores; salió a su propio sitio para
compartirlo (BE #502), y es la pieza de quien tenga que construir los dos bandos
de un partido ya generado.

Trae a los usuarios en **una sola consulta**. La reasignación los pedía todos a
la vez (`asyncio.gather`) sobre la misma sesión, y SQLAlchemy no admite dos
operaciones a la vez en una sesión: con jugadores que no estaban ya cargados
podía reventar.
"""

from collections.abc import Sequence
from dataclasses import replace
from decimal import Decimal

from src.modules.competition.application.exceptions import (
    PendingGameNotRecalculableError,
    TeeNotRatedForPlayerError,
)
from src.modules.competition.application.services.course_context import (
    contexto_del_campo,
    course_context_for,
)
from src.modules.competition.application.services.match_players_builder import (
    MatchPlayersBuilder,
    TeeColorNotFoundError,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.golf_course.domain.services.stroke_context import StrokeContext
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.playing_handicap_calculator import (
    PlayingHandicapCalculator,
    TeeRating,
)
from src.shared.domain.services.tee_lookup import TeeKey
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.play_mode import PlayMode


class PlayerNotEnrolledError(Exception):
    """El jugador no tiene inscripción aprobada."""

    pass


class JugadoresDelPartido:
    """Construye los dos bandos de un partido, con los golpes que da su formato."""

    def __init__(
        self,
        golf_course_repository: IGolfCourseRepository,
        user_repository: UserRepositoryInterface,
        handicap_calculator: PlayingHandicapCalculator | None = None,
    ):
        self._gc_repo = golf_course_repository
        self._user_repo = user_repository
        self._calculator = handicap_calculator or PlayingHandicapCalculator()
        self._match_players = MatchPlayersBuilder()

    async def construir(
        self,
        uow: CompetitionUnitOfWorkInterface,
        round_entity: Round,
        competition: Competition,
        team_a_ids: Sequence[UserId],
        team_b_ids: Sequence[UserId],
    ) -> tuple[list[MatchPlayer], list[MatchPlayer]]:
        """
        Raises:
            PlayerNotEnrolledError: Si alguno no tiene inscripción aprobada:
                sin ella no se sabe desde qué barra juega ni con qué hándicap
        """
        enrollments = await uow.enrollments.find_by_competition_and_status(
            round_entity.competition_id, EnrollmentStatus.APPROVED
        )
        enrollment_map = {str(e.user_id.value): e for e in enrollments}
        for uid in [*team_a_ids, *team_b_ids]:
            if str(uid.value) not in enrollment_map:
                raise PlayerNotEnrolledError(f"El jugador {uid} no tiene inscripción aprobada")

        is_scratch = competition.play_mode == PlayMode.SCRATCH
        (
            tee_ratings,
            holes_by_stroke_index,
            user_handicap_map,
            user_gender_map,
            holes_by_tee,
        ) = await self._datos_de_handicap(round_entity, is_scratch, [*team_a_ids, *team_b_ids])

        # Los cambios de barras de su campo (R1 y R2)
        cambios = await uow.barras_por_campo.del_campo(
            round_entity.competition_id, round_entity.golf_course_id
        )
        return self._match_players.build(
            round_entity.match_format,
            list(team_a_ids),
            list(team_b_ids),
            enrollment_map,
            tee_ratings,
            self._calculator,
            round_entity.get_effective_allowance(),
            is_scratch,
            user_handicap_map,
            holes_by_stroke_index,
            user_gender_map,
            competition.max_playing_handicap,
            holes_by_tee,
            cambios,
        )

    async def con_otra_barra(
        self,
        round_entity: Round,
        competition: Competition,
        partido: Match,
        user_id: UserId,
        tee_color: TeeColor | None,
        genero: Gender | None,
        contextos: dict[GolfCourseId, StrokeContext] | None = None,
    ) -> tuple[list[MatchPlayer], list[MatchPlayer]] | None:
        """
        Los dos bandos de un partido ya generado cuando un jugador cambia de barras
        (BE #912). Decidido con Agustín: los demás se quedan como se generaron.

        Parte de la foto guardada de cada uno (su barra y su hándicap índice, que
        es el de entonces: el perfil no llega a lo ya generado, como al refrescar
        hándicaps) y solo cambia la barra de quien la cambia. Con golpes se vuelve
        a hacer el reparto de siempre (`MatchPlayersBuilder`): el hándicap de juego
        de él y lo que dependa de él (la diferencia en individual, el reparto
        frente al más bajo en fourball, el del equipo en foursomes). En SCRATCH no
        hay reparto: solo cambia su foto y las de los demás quedan tal cual.

        Args:
            contextos: El contexto de cada campo ya leído en esta ejecución, para
                no leer el mismo campo una vez por partido

        Returns:
            Los dos bandos nuevos, o None si su barra queda igual que la guardada:
            entonces no se toca nada de nadie

        Raises:
            TeeNotRatedForPlayerError: Si SUS barras no están valoradas en este campo
            PendingGameNotRecalculableError: Si falta el campo, una foto no tiene su
                hándicap índice, o la barra guardada de otro ya no está valorada
        """
        is_scratch = competition.play_mode == PlayMode.SCRATCH
        contexto = await contexto_del_campo(self._gc_repo, round_entity.golf_course_id, contextos)
        guardada = partido.find_player(user_id)
        if guardada is None:
            return None

        # Primero su barra, que solo necesita la suya: así lo de los demás (sus
        # índices) solo se exige si de verdad hay que rehacer
        suya = Enrollment(
            id=EnrollmentId.generate(),
            competition_id=competition.id,
            user_id=user_id,
            status=EnrollmentStatus.APPROVED,
            tee_color=tee_color,
        )
        clave = str(user_id.value)
        color, su_genero, valoracion, _ = self._match_players.resolve_player_data(
            user_id,
            {clave: suya},
            contexto.tee_ratings,
            {},
            {clave: genero},
            contexto.holes_by_tee if is_scratch else None,
        )
        # Con golpes, la valoración antes que nada: la misma barra que la guardada
        # que el campo ya no valora tampoco vale
        if valoracion is None and not is_scratch:
            raise TeeNotRatedForPlayerError(
                "Sus barras no están valoradas en el campo de este partido"
            )
        if (color, su_genero) == (guardada.tee_color, guardada.tee_gender):
            return None

        if is_scratch:
            # Sin golpes no hay nada que repartir: los demás, tal cual estaban (sin
            # volver a buscarlos en el campo), y él con sus barras nuevas
            def con_la_suya(jugadores: Sequence[MatchPlayer]) -> list[MatchPlayer]:
                return [
                    replace(j, tee_color=color, tee_gender=su_genero) if j.user_id == user_id else j
                    for j in jugadores
                ]

            return con_la_suya(partido.team_a_players), con_la_suya(partido.team_b_players)

        # Con golpes, cada uno con su foto: la barra guardada (con su género, para
        # que se busque la misma) y su índice guardado; él, con la barra nueva
        inscripciones: dict[str, Enrollment] = {clave: suya}
        indices: dict[str, Decimal] = {}
        generos: dict[str, Gender | None] = {clave: genero}
        for foto in (*partido.team_a_players, *partido.team_b_players):
            if foto.player_handicap is None:
                raise PendingGameNotRecalculableError(
                    "Un jugador del partido no tiene guardado su hándicap índice"
                )
            indices[str(foto.user_id.value)] = foto.player_handicap
            if foto.user_id == user_id:
                continue
            inscripciones[str(foto.user_id.value)] = Enrollment(
                id=EnrollmentId.generate(),
                competition_id=competition.id,
                user_id=foto.user_id,
                status=EnrollmentStatus.APPROVED,
                tee_color=foto.tee_color,
            )
            generos[str(foto.user_id.value)] = foto.tee_gender

        try:
            return self._match_players.build(
                round_entity.match_format,
                [p.user_id for p in partido.team_a_players],
                [p.user_id for p in partido.team_b_players],
                inscripciones,
                contexto.tee_ratings,
                self._calculator,
                round_entity.get_effective_allowance(),
                is_scratch,
                indices,
                contexto.holes_by_stroke_index,
                generos,
                competition.max_playing_handicap,
                contexto.holes_by_tee,
            )
        except TeeColorNotFoundError as e:
            # La suya ya está comprobada: es la guardada de otro la que falta
            raise PendingGameNotRecalculableError(
                "La barra guardada de otro jugador del partido ya no está valorada"
            ) from e

    async def _datos_de_handicap(
        self, round_entity: Round, is_scratch: bool, player_ids: list[UserId]
    ) -> tuple[
        dict[TeeKey, TeeRating],
        list[int],
        dict[str, Decimal],
        dict[str, Gender | None],
        dict[TeeKey, list[int]],
    ]:
        """Barras y hoyos del campo, y hándicap y género de cada jugador."""
        tee_ratings: dict[tuple[str, str | None], TeeRating] = {}
        holes_by_stroke_index: list[int] = []
        holes_by_tee: dict[tuple[str, str | None], list[int]] = {}
        user_handicap_map: dict[str, Decimal] = {}
        user_gender_map: dict[str, Gender | None] = {}

        # También en SCRATCH: sin golpes, pero cada uno guarda el género de su
        # barra, y con él su tarjeta y las muestras del mapa (RyderCupWeb #880)
        golf_course = await self._gc_repo.find_by_id(round_entity.golf_course_id)
        if not golf_course and not is_scratch:
            raise ValueError(
                "Se requiere un campo de golf para el modo HANDICAP. "
                "Asocie un campo de golf aprobado a la competición."
            )
        if golf_course:
            context = course_context_for(golf_course)
            tee_ratings = context.tee_ratings
            holes_by_stroke_index = context.holes_by_stroke_index
            holes_by_tee = context.holes_by_tee

            for user in await self._user_repo.find_by_ids(list(player_ids)):
                # En SCRATCH solo el género: el hándicap no cuenta
                if not is_scratch and user.handicap is not None:
                    user_handicap_map[str(user.id.value)] = Decimal(str(user.handicap.value))
                user_gender_map[str(user.id.value)] = user.gender

        return (
            tee_ratings,
            holes_by_stroke_index,
            user_handicap_map,
            user_gender_map,
            holes_by_tee,
        )
