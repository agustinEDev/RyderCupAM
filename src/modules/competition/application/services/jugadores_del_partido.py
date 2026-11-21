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

from collections.abc import Mapping, Sequence
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
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
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
        golf_course = await self._gc_repo.find_by_id(round_entity.golf_course_id)
        (
            tee_ratings,
            holes_by_stroke_index,
            user_handicap_map,
            user_gender_map,
            holes_by_tee,
        ) = await self._datos_de_handicap(golf_course, is_scratch, [*team_a_ids, *team_b_ids])

        # Los cambios de barras de su campo (R1 y R2)
        cambios = await uow.barras_por_campo.del_campo(
            round_entity.competition_id, round_entity.golf_course_id
        )
        # En SCRATCH, como al generar: sin barras en el campo (ni valoradas ni con
        # tarjeta) no entra en un partido. Con golpes ya lo dice el reparto; sin
        # campo se construye como siempre
        if (
            is_scratch
            and golf_course is not None
            and self._match_players.sin_barras(
                [*team_a_ids, *team_b_ids],
                enrollment_map,
                tee_ratings,
                user_gender_map,
                cambios,
                con_tarjeta=holes_by_tee,
            )
        ):
            raise TeeColorNotFoundError(
                "Un jugador no tiene barras en el campo de este partido "
                "(ni valoradas ni con tarjeta)"
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
        nuevas: Mapping[UserId, tuple[TeeColor | None, Gender | None]],
        contextos: dict[GolfCourseId, StrokeContext] | None = None,
    ) -> tuple[list[MatchPlayer], list[MatchPlayer]] | None:
        """
        Los dos bandos de un partido ya generado cuando uno o varios de sus
        jugadores cambian de barras (BE #912). Decidido con Agustín: los demás se
        quedan como se generaron.

        Parte de la foto guardada de cada uno (su barra y su hándicap índice, que
        es el de entonces: el perfil no llega a lo ya generado, como al refrescar
        hándicaps) y solo cambia la barra de los que la cambian, todos de una vez:
        así ninguno se resuelve con la barra guardada de otro que también cambia
        (un fourball con las dos de un género). Con golpes se vuelve a hacer el
        reparto de siempre (`MatchPlayersBuilder`): el hándicap de juego de ellos y
        lo que dependa de él (la diferencia en individual, el reparto frente al más
        bajo en fourball, el del equipo en foursomes). En SCRATCH no hay reparto:
        solo cambian sus fotos y las de los demás quedan tal cual.

        Args:
            nuevas: Por cada jugador que cambia, su barra (la de su inscripción; sin
                ella, la habitual de su género) y su género. Los que no están en el
                partido se ignoran
            contextos: El contexto de cada campo ya leído en esta ejecución, para
                no leer el mismo campo una vez por partido

        Returns:
            Los dos bandos nuevos, o None si las barras de todos quedan igual que
            las guardadas: entonces no se toca nada de nadie

        Raises:
            TeeNotRatedForPlayerError: Si las barras de uno de los que cambian no
                están valoradas en este campo
            PendingGameNotRecalculableError: Si falta el campo, una foto no tiene su
                hándicap índice, o la barra guardada de otro ya no está valorada
        """
        is_scratch = competition.play_mode == PlayMode.SCRATCH
        contexto = await contexto_del_campo(self._gc_repo, round_entity.golf_course_id, contextos)

        # Primero sus barras, que solo necesitan las suyas: así lo de los demás
        # (sus índices) solo se exige si de verdad hay que rehacer
        inscripciones: dict[str, Enrollment] = {}
        generos: dict[str, Gender | None] = {}
        resueltas: dict[UserId, tuple[TeeColor, Gender | None]] = {}
        for user_id, (tee_color, genero) in nuevas.items():
            guardada = partido.find_player(user_id)
            if guardada is None:
                continue
            clave = str(user_id.value)
            inscripciones[clave] = Enrollment(
                id=EnrollmentId.generate(),
                competition_id=competition.id,
                user_id=user_id,
                status=EnrollmentStatus.APPROVED,
                tee_color=tee_color,
            )
            generos[clave] = genero
            color, su_genero, valoracion, _ = self._match_players.resolve_player_data(
                user_id,
                {clave: inscripciones[clave]},
                contexto.tee_ratings,
                {},
                {clave: genero},
                contexto.holes_by_tee if is_scratch else None,
            )
            # Con golpes, la valoración antes que nada: la misma barra que la
            # guardada que el campo ya no valora tampoco vale
            if valoracion is None and not is_scratch:
                raise TeeNotRatedForPlayerError(
                    "Sus barras no están valoradas en el campo de este partido"
                )
            if (color, su_genero) != (guardada.tee_color, guardada.tee_gender):
                resueltas[user_id] = (color, su_genero)
        if not resueltas:
            return None

        if is_scratch:
            # Sin golpes no hay nada que repartir: los demás, tal cual estaban (sin
            # volver a buscarlos en el campo), y ellos con sus barras nuevas
            def con_las_suyas(jugadores: Sequence[MatchPlayer]) -> list[MatchPlayer]:
                return [
                    replace(
                        j, tee_color=resueltas[j.user_id][0], tee_gender=resueltas[j.user_id][1]
                    )
                    if j.user_id in resueltas
                    else j
                    for j in jugadores
                ]

            return con_las_suyas(partido.team_a_players), con_las_suyas(partido.team_b_players)

        # Con golpes, cada uno con su foto: la barra guardada (con su género, para
        # que se busque la misma) y su índice guardado; los que cambian, con la nueva
        indices: dict[str, Decimal] = {}
        for foto in (*partido.team_a_players, *partido.team_b_players):
            if foto.player_handicap is None:
                raise PendingGameNotRecalculableError(
                    "Un jugador del partido no tiene guardado su hándicap índice"
                )
            clave = str(foto.user_id.value)
            indices[clave] = foto.player_handicap
            if clave in inscripciones:
                continue
            inscripciones[clave] = Enrollment(
                id=EnrollmentId.generate(),
                competition_id=competition.id,
                user_id=foto.user_id,
                status=EnrollmentStatus.APPROVED,
                tee_color=foto.tee_color,
            )
            generos[clave] = foto.tee_gender

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
            # Las de los que cambian ya están comprobadas: es la guardada de otro
            raise PendingGameNotRecalculableError(
                "La barra guardada de otro jugador del partido ya no está valorada"
            ) from e

    async def _datos_de_handicap(
        self, golf_course: GolfCourse | None, is_scratch: bool, player_ids: list[UserId]
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
