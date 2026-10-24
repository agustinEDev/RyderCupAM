"""Adaptador: las partidas jugadas juntos salen de las partidas rapidas y los torneos."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.modules.competition.application.services.participantes_de_la_clasificacion import (
    generales_netas,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.clasificacion import EstadoEnClasificacion
from src.modules.competition.domain.services.scoring_opening_service import (
    ScoringOpeningService,
)
from src.modules.competition.domain.services.tarjeta_de_stroke_play import TarjetaDeStrokePlay
from src.modules.competition.domain.value_objects.estado_de_tarjeta import EstadoDeTarjeta
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.application.services.match_play_result import (
    match_play_reading,
    quick_match_strokes,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.services.stroke_allocation_service import (
    ParticipantStrokes,
    StrokeAllocationService,
)
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.social.application.ports.shared_games_interface import (
    SharedGame,
    SharedGameKind,
    SharedGamesInterface,
    StrokePlayStanding,
)
from src.modules.social.domain.services.counted_round import (
    counting_units,
    holes_by_side,
    match_play_counts,
)
from src.modules.social.domain.services.head_to_head import (
    CardResult,
    Outcome,
    Relation,
    relation_between,
    stroke_play_outcome,
    team_outcome,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.match_play_scoring import MatchPlayScoring
from src.shared.domain.services.stroke_play_scoring import HoleSetup, StrokePlayScoring
from src.shared.domain.value_objects.scoring_format import ScoringFormat

# Terminados y con resultado oficial. Fuera el walkover: uno no se presento, asi
# que no lo jugasteis juntos (decision conservadora, BE-3)
FINISHED_MATCH_STATUSES = (MatchStatus.COMPLETED, MatchStatus.CONCEDED)

# La modalidad de un torneo de stroke play, en la escala del cara a cara
_SCORING_BY_TOURNAMENT = {
    TournamentType.STABLEFORD: ScoringFormat.STABLEFORD,
    TournamentType.MEDAL: ScoringFormat.MEDAL,
}


@dataclass
class _Leido:
    """Todo lo leido de las tres fuentes antes de resolver campos y jugadores."""

    rapidas: list[QuickMatch] = field(default_factory=list)
    golpes_rapidas: dict = field(default_factory=dict)
    partidos: list[Match] = field(default_factory=list)
    grupos: list[Partida] = field(default_factory=list)
    validados: dict = field(default_factory=dict)
    rondas: dict = field(default_factory=dict)
    competiciones: dict = field(default_factory=dict)
    # Los stroke play COMPLETADOS que jugaron los dos, en cualquier grupo (J),
    # y su general final, calculada para todos de una vez
    torneos_cerrados: list[Competition] = field(default_factory=list)
    generales: dict = field(default_factory=dict)


class SharedGamesAdapter(SharedGamesInterface):
    """
    Junta las tres fuentes de partidas y resuelve quien gano cada una.

    Cada fuente se lee en su propia unidad de trabajo, en serie —comparten
    sesion por debajo—, y solo despues se resuelven campos y jugadores, en
    bloque: una lista de veinte partidas no dispara una consulta por partida.

    Quien gana sale de las cuentas de cada modulo, no de una copia: el reparto
    de golpes y el motor de match play de la partida rapida, el resultado
    oficial del partido de torneo y la tarjeta de stroke play del torneo.
    """

    def __init__(
        self,
        quick_match_uow: QuickMatchUnitOfWorkInterface,
        competition_uow: CompetitionUnitOfWorkInterface,
        golf_course_uow: GolfCourseUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        stroke_allocation_service: StrokeAllocationService | None = None,
        scoring_service: MatchPlayScoring | None = None,
        stroke_play_scoring: StrokePlayScoring | None = None,
    ):
        self._quick_match_uow = quick_match_uow
        self._competition_uow = competition_uow
        self._golf_course_uow = golf_course_uow
        self._user_uow = user_uow

        self._stroke_allocation = stroke_allocation_service or StrokeAllocationService()
        self._scoring = scoring_service or MatchPlayScoring()
        self._stroke_play = stroke_play_scoring or StrokePlayScoring()

    async def between(self, viewer_id: UserId, other_id: UserId) -> list[SharedGame]:
        leido = _Leido()
        await self._leer_rapidas(leido, viewer_id, other_id)
        await self._leer_torneos(leido, viewer_id, other_id)
        campos = await self._campos(leido)
        usuarios = await self._usuarios(leido)
        torneos = [
            juego
            for competicion in leido.torneos_cerrados
            if (juego := self._de_torneo_cerrado(competicion, leido, viewer_id, other_id))
        ]

        return (
            [
                self._de_rapida(m, leido, campos, usuarios, viewer_id, other_id)
                for m in leido.rapidas
            ]
            # Sin su ronda no se sabe ni cuando ni donde: no se enseña
            + [
                self._de_partido(m, ronda, leido, campos, viewer_id, other_id)
                for m in leido.partidos
                if (ronda := leido.rondas.get(m.round_id)) is not None
            ]
            + [
                self._de_grupo(g, ronda, leido, campos, viewer_id, other_id)
                for g in leido.grupos
                if (ronda := leido.rondas.get(g.round_id)) is not None
            ]
            + torneos
        )

    # ==================== Lectura ====================

    async def _leer_rapidas(self, leido: _Leido, viewer_id: UserId, other_id: UserId) -> None:
        async with self._quick_match_uow:
            leido.rapidas = await self._quick_match_uow.quick_matches.list_shared_by(
                viewer_id, other_id, QuickMatchStatus.COMPLETED
            )
            if not leido.rapidas:
                return
            golpes = await self._quick_match_uow.quick_match_hole_scores.find_by_matches(
                [m.id for m in leido.rapidas]
            )
        for golpe in golpes:
            leido.golpes_rapidas.setdefault(golpe.quick_match_id, {}).setdefault(
                golpe.participant_id, {}
            )[golpe.hole_number] = golpe.score

    async def _leer_torneos(self, leido: _Leido, viewer_id: UserId, other_id: UserId) -> None:
        async with self._competition_uow:
            uow = self._competition_uow
            leido.partidos = await uow.matches.find_with_both_players(
                viewer_id, other_id, FINISHED_MATCH_STATUSES
            )
            grupos = [
                grupo
                for grupo in await uow.partidas.con_los_dos(viewer_id, other_id)
                if self._jugaron_el_grupo(grupo, viewer_id, other_id)
            ]
            # Los stroke play en los que estuvieron los dos, en el mismo grupo
            # o no: si ya se completaron, cuentan enteros por su general (J)
            con_los_dos = await uow.partidas.competiciones_con_los_dos(viewer_id, other_id)

            # Rondas y competiciones de una vez, no una por partido
            round_ids = {m.round_id for m in leido.partidos} | {g.round_id for g in grupos}
            if round_ids:
                leido.rondas = {r.id: r for r in await uow.rounds.find_by_ids(list(round_ids))}
            competition_ids = {r.competition_id for r in leido.rondas.values()}
            competition_ids.update(con_los_dos)
            if competition_ids:
                leido.competiciones = {
                    c.id: c for c in await uow.competitions.find_by_ids(list(competition_ids))
                }
            leido.torneos_cerrados = [
                c
                for c in leido.competiciones.values()
                if c.id in set(con_los_dos) and _stroke_play_completado(c)
            ]
            # El grupo de un torneo ya completado no sale suelto: lo cuenta
            # la entrada del torneo entero
            leido.grupos = [
                g
                for g in grupos
                if not _stroke_play_completado(leido.competiciones.get(g.competition_id))
            ]
            # La general final de todos, por lotes: las mismas consultas con
            # uno que con veinte (revision del 22 oct 2026)
            leido.generales = await generales_netas(uow, leido.torneos_cerrados)
            if leido.grupos:
                for golpe in await uow.golpes_de_partida.de_las_partidas(
                    [g.id for g in leido.grupos]
                ):
                    if golpe.validado:
                        leido.validados.setdefault((golpe.partida_id, golpe.user_id), {})[
                            golpe.hoyo
                        ] = golpe.golpes_validados

    @staticmethod
    def _jugaron_el_grupo(grupo: Partida, viewer_id: UserId, other_id: UserId) -> bool:
        """Acabado y con los dos en el campo: un no presentado no jugo con nadie."""
        if grupo.estado != EstadoPartida.COMPLETED:
            return False
        tarjetas = grupo.estados_de_tarjeta
        return all(
            tarjetas.get(uid) not in (None, EstadoDeTarjeta.NO_PRESENTADO)
            for uid in (viewer_id, other_id)
        )

    async def _campos(self, leido: _Leido) -> dict[GolfCourseId, GolfCourse]:
        """Todos los campos jugados, en una sola consulta."""
        ids = {m.golf_course_id for m in leido.rapidas}
        ids.update(r.golf_course_id for r in leido.rondas.values() if r is not None)
        if not ids:
            return {}
        async with self._golf_course_uow:
            campos = await self._golf_course_uow.golf_courses.find_by_ids(list(ids))
        return {c.id: c for c in campos}

    async def _usuarios(self, leido: _Leido) -> dict[UserId, User]:
        """
        Los registrados de las partidas rapidas, en una sola consulta: el reparto
        de golpes de una partida vieja tira del handicap de su perfil.
        """
        ids = {p.user_id for m in leido.rapidas for p in m.participants if p.user_id is not None}
        if not ids:
            return {}
        async with self._user_uow:
            usuarios = await self._user_uow.users.find_by_ids(list(ids))
        return {u.id: u for u in usuarios if u.id is not None}

    # ==================== Partida rapida ====================

    def _de_rapida(
        self,
        match: QuickMatch,
        leido: _Leido,
        campos: dict[GolfCourseId, GolfCourse],
        usuarios: dict[UserId, User],
        viewer_id: UserId,
        other_id: UserId,
    ) -> SharedGame:
        course = campos.get(match.golf_course_id)
        golpes = leido.golpes_rapidas.get(match.id, {})
        yo = match.find_participant(ParticipantId(viewer_id.value))
        el = match.find_participant(ParticipantId(other_id.value))
        relation, outcome, sin_terminar = Relation.AGAINST, None, False

        if match.match_format is None:
            # Cuentan los que tienen los hoyos de la referencia, 9 o mas: si
            # alguno de los dos no, la partida sale sin terminar (tabla A)
            cuentan = counting_units({pid: hoyos.keys() for pid, hoyos in golpes.items() if hoyos})
            sin_terminar = not (
                yo and el and yo.participant_id in cuentan and el.participant_id in cuentan
            )
            # Sin campo no hay reparto de golpes, y a bruto no se juzga. Sin
            # hándicap se juega con 0, como en la propia partida y en su aviso
            # (Agustín, 22 oct 2026): se juzga igual
            if (
                not sin_terminar
                and course is not None
                and match.scoring_format is not None
                and yo
                and el
            ):
                golpes_recibidos = quick_match_strokes(
                    match, course, usuarios, self._stroke_allocation
                )
                outcome = stroke_play_outcome(
                    self._tarjeta(course, yo, golpes, golpes_recibidos, usuarios),
                    self._tarjeta(course, el, golpes, golpes_recibidos, usuarios),
                    match.scoring_format,
                )
            formato = match.scoring_format.value if match.scoring_format else ""
        else:
            relation, outcome, sin_terminar = self._match_play_rapido(
                match, course, golpes, usuarios, yo, el
            )
            formato = match.match_format.value

        return SharedGame(
            kind=SharedGameKind.QUICK_MATCH,
            game_id=str(match.id.value),
            played_on=match.played_at.date(),
            played_at=_sin_zona(match.played_at),
            golf_course_id=str(match.golf_course_id.value),
            golf_course_name=course.name if course else None,
            format=formato,
            relation=relation,
            outcome=outcome,
            unfinished=sin_terminar,
        )

    def _match_play_rapido(
        self,
        match: QuickMatch,
        course: GolfCourse | None,
        golpes: dict,
        usuarios: dict[UserId, User],
        yo: QuickMatchParticipant | None,
        el: QuickMatchParticipant | None,
    ) -> tuple[Relation, Outcome | None, bool]:
        """La relacion, el resultado desde mi bando y si quedo sin terminar."""
        rosters = match.team_rosters()
        if rosters is None or yo is None or el is None:
            return Relation.AGAINST, None, False
        team_a_ids, team_b_ids = rosters
        mi_bando = "A" if yo.participant_id in team_a_ids else "B"
        su_bando = "A" if el.participant_id in team_a_ids else "B"
        relation = relation_between(mi_bando, su_bando)
        # Sin campo no hay reparto: sale, pero no se juzga. Tampoco se sabe si
        # se decidio antes de tiempo, asi que no se marca a medias. Un hándicap
        # que falte ya no lo impide: juega con 0 (Agustín, 22 oct 2026)
        if course is None:
            return relation, None, False

        lectura = match_play_reading(
            match,
            golpes,
            quick_match_strokes(match, course, usuarios, self._stroke_allocation),
            self._scoring,
        )
        # Cuenta si se decidio antes de tiempo o si los dos bandos entregaron
        # los mismos hoyos, 9 o mas (tabla A)
        if not match_play_counts(
            holes_by_side(golpes, team_a_ids, match.match_format),
            holes_by_side(golpes, team_b_ids, match.match_format),
            lectura.decided_early,
        ):
            return relation, None, True
        return relation, team_outcome(lectura.winner, mi_bando), False

    def _tarjeta(
        self,
        course: GolfCourse,
        participant: QuickMatchParticipant,
        golpes: dict,
        golpes_recibidos: dict[ParticipantId, ParticipantStrokes],
        usuarios: dict[UserId, User],
    ) -> CardResult | None:
        """
        Sus puntos y sus netos con los golpes que le dio la partida (su barra y
        el allowance de la modalidad), que es lo que pinta su clasificacion.
        """
        recibidos = golpes_recibidos.get(participant.participant_id)
        if recibidos is None:
            return None
        # Sin barra, la tarjeta del campo: es la que usa el reparto en ese caso
        tarjeta = (
            course.hole_card_for(participant.tee_color, participant.tee_gender)
            if participant.tee_color is not None
            else course.reference_card
        )
        hoyos = [HoleSetup(h.number, h.par, h.stroke_index) for h in tarjeta]
        totales = self._stroke_play.compute_participant_totals(
            handicap=recibidos.playing_handicap,
            holes=hoyos,
            scores_by_hole=golpes.get(participant.participant_id, {}),
        )
        # Ya se sabe que cuentan los dos (`counting_units`): con los mismos
        # hoyos, sus totales se comparan
        # El índice con el que jugó la partida, el mismo que desempata su aviso
        user = usuarios.get(participant.user_id) if participant.user_id else None
        return CardResult(
            complete=True,
            points=totales.stableford_points,
            net_to_par=totales.to_par,
            handicap=participant.effective_handicap(
                user.handicap.value if user and user.handicap else None
            ),
        )

    # ==================== Torneo ====================

    def _de_partido(
        self,
        match: Match,
        ronda: Round,
        leido: _Leido,
        campos: dict[GolfCourseId, GolfCourse],
        viewer_id: UserId,
        other_id: UserId,
    ) -> SharedGame:
        """El resultado oficial del partido, desde mi bando."""
        mi_bando = match.get_player_team(viewer_id) or ""
        su_bando = match.get_player_team(other_id) or ""
        return self._de_torneo(
            kind=SharedGameKind.TOURNAMENT_MATCH,
            game_id=str(match.id.value),
            ronda=ronda,
            leido=leido,
            campos=campos,
            formato=ronda.match_format.value,
            relation=relation_between(mi_bando, su_bando),
            outcome=team_outcome(match.get_winner(), mi_bando),
        )

    def _de_grupo(
        self,
        grupo: Partida,
        ronda: Round,
        leido: _Leido,
        campos: dict[GolfCourseId, GolfCourse],
        viewer_id: UserId,
        other_id: UserId,
    ) -> SharedGame:
        """Rivales del mismo grupo: puntos o netos de sus tarjetas validadas."""
        competicion = leido.competiciones.get(grupo.competition_id)
        tipo = competicion.tournament_type if competicion else None
        scoring = _SCORING_BY_TOURNAMENT.get(tipo) if tipo else None
        outcome = None
        if scoring is not None:
            outcome = stroke_play_outcome(
                self._tarjeta_de_grupo(grupo, viewer_id, leido),
                self._tarjeta_de_grupo(grupo, other_id, leido),
                scoring,
            )
        return self._de_torneo(
            kind=SharedGameKind.TOURNAMENT_GROUP,
            game_id=str(grupo.id),
            ronda=ronda,
            leido=leido,
            campos=campos,
            formato=tipo.value if tipo else "",
            relation=Relation.AGAINST,
            outcome=outcome,
        )

    @staticmethod
    def _tarjeta_de_grupo(grupo: Partida, user_id: UserId, leido: _Leido) -> CardResult | None:
        """
        Su tarjeta con lo validado. Completa solo si la entrego con los 18: un
        retirado no se juzga, aunque en Stableford la clasificacion le cuente
        lo jugado (caso 10, la opcion conservadora).
        """
        foto = next((j for j in grupo.jugadores if j.user_id == user_id), None)
        if foto is None:
            return None
        tarjeta = TarjetaDeStrokePlay.de(foto, leido.validados.get((grupo.id, user_id), {}))
        entregada = grupo.estados_de_tarjeta.get(user_id) == EstadoDeTarjeta.ENTREGADA
        return CardResult(
            complete=entregada and tarjeta.completa,
            points=tarjeta.puntos,
            net_to_par=tarjeta.al_par_neto,
            # El de su inscripción, el mismo que desempata la clasificación (H)
            handicap=foto.handicap,
        )

    @staticmethod
    def _de_torneo_cerrado(
        competicion: Competition, leido: _Leido, viewer_id: UserId, other_id: UserId
    ) -> SharedGame | None:
        """
        Un stroke play COMPLETADO, entero (tabla del 22 oct 2026, J): quien
        quedo por delante en la general final gana, con el desempate por
        hándicap; si comparten puesto, empate. Cuenta una vez por torneo,
        aunque jugaran varias rondas o en grupos distintos.

        Quien no se presento a nada (NP) no jugo el torneo: no sale. Quien no
        quedo clasificado (retirado, NR) sale sin puesto y no cuenta.
        """
        general = leido.generales.get(competicion.id, [])
        filas = {fila.user_id: fila for fila in general}
        mia, suya = filas.get(viewer_id), filas.get(other_id)
        no_presentado = EstadoEnClasificacion.NP
        if mia is None or suya is None or no_presentado in (mia.estado, suya.estado):
            return None
        outcome = None
        if mia.puesto is not None and suya.puesto is not None:
            if mia.puesto == suya.puesto:
                outcome = Outcome.HALVED
            else:
                outcome = Outcome.WON if mia.puesto < suya.puesto else Outcome.LOST
        return SharedGame(
            kind=SharedGameKind.TOURNAMENT_STROKE_PLAY,
            game_id=str(competicion.id.value),
            # Se cuenta el dia que acaba: es cuando hay general final
            played_on=competicion.dates.end_date,
            golf_course_id=None,
            golf_course_name=None,
            format=competicion.tournament_type.value,
            relation=Relation.AGAINST,
            outcome=outcome,
            competition_id=str(competicion.id.value),
            competition_name=competicion.name.value,
            standing=StrokePlayStanding(
                my_position=mia.puesto,
                my_tied=mia.empatado,
                their_position=suya.puesto,
                their_tied=suya.empatado,
                total_players=len(general),
            ),
        )

    @staticmethod
    def _de_torneo(
        *,
        kind: SharedGameKind,
        game_id: str,
        ronda: Round,
        leido: _Leido,
        campos: dict[GolfCourseId, GolfCourse],
        formato: str,
        relation: Relation,
        outcome: Outcome | None,
    ) -> SharedGame:
        competicion: Competition | None = leido.competiciones.get(ronda.competition_id)
        course = campos.get(ronda.golf_course_id)
        return SharedGame(
            kind=kind,
            game_id=game_id,
            played_on=ronda.round_date,
            played_at=_instante_de_la_ronda(ronda, course),
            golf_course_id=str(ronda.golf_course_id.value),
            golf_course_name=course.name if course else None,
            format=formato,
            relation=relation,
            outcome=outcome,
            competition_id=str(competicion.id.value) if competicion else None,
            competition_name=competicion.name.value if competicion else None,
        )


def _stroke_play_completado(competicion: Competition | None) -> bool:
    """Un Stableford o un Medal ya completado: tiene general final (J)."""
    return (
        competicion is not None
        and competicion.stroke_play is not None
        and competicion.is_completed()
    )


def _sin_zona(instante: datetime) -> datetime:
    """En UTC y sin zona, la escala en la que se comparan las tres fuentes."""
    if instante.tzinfo is None:
        return instante
    return instante.astimezone(UTC).replace(tzinfo=None)


def _instante_de_la_ronda(ronda: Round, course: GolfCourse | None) -> datetime | None:
    """
    Cuando se jugo una ronda: la hora de su sesion (6, 12 o 18 locales), la
    misma con la que se abre su anotacion, pasada a UTC con la zona del campo.

    Sin zona conocida no se sabe el instante en UTC: None, y la partida se
    ordena como el principio de su dia, sin mezclar la hora local con las UTC
    de las demas (CodeRabbit BE #633).
    """
    abre = ScoringOpeningService.opens_at(
        ronda.round_date, ronda.session_type, course.timezone if course else None
    )
    return _sin_zona(abre) if abre is not None else None
