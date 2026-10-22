"""
Las partidas que dos jugadores terminaron juntos, y quien gano cada una (BE-3).

| Caso                                                     | Resultado                        |
|----------------------------------------------------------|----------------------------------|
| Partida rapida Stableford: mas puntos con peor bruto     | Contra él, gana (nunca en bruto) |
| Partida rapida Medal: menos netos con peor bruto         | Contra él, gana                  |
| Partida rapida singles por hoyos                         | Contra él, quien gano los hoyos  |
| Partida rapida fourball en el mismo bando                | Con él, el resultado del equipo  |
| Partida rapida fourball en bandos contrarios             | Contra él                        |
| Oculta por mi / por él (casos 9 y 13)                    | Fuera                            |
| Sin terminar (caso 7)                                    | Fuera                            |
| Tarjeta a medias en stroke play (caso 10)                | Sale, pero sin resultado         |
| Partido de torneo terminado (caso 9)                     | El resultado oficial             |
| Partido de torneo concedido                              | Cuenta, con su resultado         |
| Partido de torneo en juego / por walkover (caso 7)       | Fuera                            |
| Foursomes de torneo en el mismo bando                    | Con él                           |
| Mismo equipo Ryder, partidos distintos                   | No es jugar juntos               |
| Grupo de stroke play de torneo acabado                   | Contra él, por puntos o netos    |
| Grupo sin acabar / uno no presentado                     | Fuera                            |
| Grupo con uno retirado                                   | Sale, sin resultado              |
| Cada partida trae fecha, campo, formato y enlace         | Caso 11                          |
| Jugadores y campos en bloque (caso 19)                   | Sin una consulta por partida     |
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.services.marcadores_en_cadena import MarcadoresEnCadena
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.estado_de_tarjeta import EstadoDeTarjeta
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.competition.domain.value_objects.jugador_de_partida import JugadorDePartida
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryCompetitionUnitOfWork,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.entities.quick_match_hole_score import QuickMatchHoleScore
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_hole_score_id import (
    QuickMatchHoleScoreId,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.quick_match.infrastructure.persistence.in_memory.in_memory_quick_match_unit_of_work import (
    InMemoryQuickMatchUnitOfWork,
)
from src.modules.social.application.ports.shared_games_interface import SharedGameKind
from src.modules.social.domain.services.head_to_head import Outcome, Relation
from src.modules.social.infrastructure.adapters.shared_games_adapter import SharedGamesAdapter
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.play_mode import PlayMode
from src.shared.domain.value_objects.scoring_format import ScoringFormat

pytestmark = pytest.mark.asyncio

HOLES = range(1, 19)
DIA = date(2026, 9, 20)


class _Mundo:
    """Las cuatro fuentes en memoria y el adaptador que las junta."""

    def __init__(self):
        self.users = InMemoryUserUnitOfWork()
        self.qm = InMemoryQuickMatchUnitOfWork()
        self.comp = InMemoryCompetitionUnitOfWork()
        self.courses = InMemoryGolfCourseUnitOfWork()

    def adapter(self) -> SharedGamesAdapter:
        return SharedGamesAdapter(self.qm, self.comp, self.courses, self.users)

    async def jugador(self, nombre: str, handicap: float | None = 0) -> User:
        user = User.create(
            first_name=nombre,
            last_name="Golfista",
            email_str=f"{nombre.lower()}_{uuid4().hex[:8]}@test.com",
            plain_password="SecureP@ssw0rd123",
        )
        if handicap is not None:
            user.update_handicap(handicap)
        async with self.users:
            await self.users.users.save(user)
        return user

    async def campo(
        self, creador: User, nombre: str = "El Saler", timezone: str | None = None
    ) -> GolfCourse:
        """Par 72: 18 hoyos de par 4, indice 1 a 18."""
        course = GolfCourse.create(
            timezone=timezone,
            name=nombre,
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=creador.id,
            tees=[
                Tee(
                    color=TeeColor.YELLOW,
                    gender=Gender.MALE,
                    identifier="Yellow",
                    course_rating=72.0,
                    slope_rating=113,
                )
            ],
            holes=[Hole(number=i, par=4, stroke_index=i) for i in HOLES],
        )
        course.approve()
        async with self.courses:
            await self.courses.golf_courses.save(course)
        return course

    async def partida_rapida(
        self,
        course: GolfCourse,
        creador: User,
        otros: list[QuickMatchParticipant],
        golpes: list[int],
        *,
        scoring_format: ScoringFormat | None = None,
        match_format: MatchFormat | None = None,
        play_mode: PlayMode = PlayMode.HANDICAP,
        hoyos: list[int] | None = None,
        terminar: bool = True,
    ) -> QuickMatch:
        """`golpes[i]` son los golpes por hoyo del participante i (0 = creador)."""
        match = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=creador.id,
            golf_course_id=course.id,
            match_format=match_format,
            scoring_format=scoring_format,
            play_mode=play_mode,
        )
        for otro in otros:
            match.add_participant(otro)
        ids = [p.participant_id for p in match.participants]
        match.start(scorer_ids=[ids[0]])
        if terminar:
            match.complete()
        async with self.qm:
            await self.qm.quick_matches.add(match)
            for indice, participant_id in enumerate(ids):
                jugados = hoyos[indice] if hoyos else 18
                for hoyo in range(1, jugados + 1):
                    await self.qm.quick_match_hole_scores.add(
                        QuickMatchHoleScore(
                            id=QuickMatchHoleScoreId.generate(),
                            quick_match_id=match.id,
                            hole_number=hoyo,
                            participant_id=participant_id,
                            score=golpes[indice],
                            recorded_by_participant_id=ids[0],
                        )
                    )
            await self.qm.commit()
        return match

    async def competicion(
        self, creador: User, tipo: TournamentType = TournamentType.RYDER_CUP
    ) -> Competition:
        competition = Competition.create(
            id=CompetitionId(uuid4()),
            creator_id=creador.id,
            name=CompetitionName("Copa de Otoño"),
            dates=DateRange(start_date=DIA, end_date=DIA + timedelta(days=2)),
            location=Location(main_country=CountryCode("ES")),
            play_mode=PlayMode.SCRATCH,
            team_1_name="Team A" if tipo.has_teams else None,
            team_2_name="Team B" if tipo.has_teams else None,
            team_assignment=TeamAssignment.MANUAL if tipo.has_teams else None,
            tournament_type=tipo,
        )
        async with self.comp:
            await self.comp.competitions.add(competition)
        return competition

    async def ronda(
        self,
        competition: Competition,
        course: GolfCourse,
        match_format: MatchFormat = MatchFormat.SINGLES,
        session_type: SessionType = SessionType.MORNING,
    ) -> Round:
        round_ = Round.create(
            competition_id=competition.id,
            golf_course_id=course.id,
            round_date=DIA,
            session_type=session_type,
            match_format=match_format,
        )
        async with self.comp:
            await self.comp.rounds.add(round_)
        return round_

    async def partido(
        self,
        round_: Round,
        equipo_a: list[User],
        equipo_b: list[User],
        *,
        ganador: str | None = "A",
        estado: str = "COMPLETED",
        numero: int = 1,
    ) -> Match:
        def jugador(user: User) -> MatchPlayer:
            return MatchPlayer(
                user_id=user.id,
                playing_handicap=0,
                tee_color=TeeColor.YELLOW,
                tee_gender=Gender.MALE,
                strokes_received=(),
            )

        match = Match.create(
            round_id=round_.id,
            match_number=numero,
            team_a_players=[jugador(u) for u in equipo_a],
            team_b_players=[jugador(u) for u in equipo_b],
        )
        if estado == "WALKOVER":
            match.declare_walkover("A")
        elif estado != "SCHEDULED":
            match.start()
            if estado == "COMPLETED":
                match.complete({"winner": ganador, "score": "3&2"})
            elif estado == "CONCEDED":
                match.concede("B")
        async with self.comp:
            await self.comp.matches.add(match)
        return match

    async def grupo(
        self,
        competition: Competition,
        round_: Round,
        golpes: dict[User, list[int]],
        *,
        estados: dict[User, EstadoDeTarjeta] | None = None,
        estado: EstadoPartida = EstadoPartida.COMPLETED,
        golpes_recibidos: dict[User, int] | None = None,
        sin_validar: dict[User, int] | None = None,
        numero: int = 1,
    ) -> Partida:
        """
        `golpes[user]` son sus golpes validados, hoyo a hoyo desde el 1.
        `sin_validar[user]` es un hoyo que solo apunto él, sin su marcador.
        """
        recibidos = golpes_recibidos or {}

        def foto(user: User) -> JugadorDePartida:
            por_hoyo = recibidos.get(user, 0)
            return JugadorDePartida(
                user_id=user.id,
                handicap=Decimal(por_hoyo * 18),
                playing_handicap=por_hoyo * 18,
                tee_color=TeeColor.YELLOW,
                tee_gender=Gender.MALE,
                golpes_por_hoyo=(por_hoyo,) * 18,
                par_por_hoyo=(4,) * 18,
            )

        cerradas = estados or {}
        # Los que no se presentaron o se retiraron ni marcan ni les marcan
        quedan = [u.id for u in golpes if not (u in cerradas and cerradas[u].fuera_de_la_partida())]
        partida = Partida(
            id=PartidaId.generate(),
            competition_id=competition.id,
            round_id=round_.id,
            numero=numero,
            jugadores=[foto(u) for u in golpes],
            marcadores=MarcadoresEnCadena.de(quedan) if len(quedan) > 1 else {},
            estado=estado,
            estados_de_tarjeta={u.id: cerradas.get(u, EstadoDeTarjeta.ENTREGADA) for u in golpes},
        )
        momento = DIA
        async with self.comp:
            await self.comp.partidas.anadir([partida])
            for user, suyos in golpes.items():
                for hoyo, valor in enumerate(suyos, start=1):
                    golpe = GolpeDePartida.crear(
                        partida.id, round_.id, competition.id, user.id, hoyo, momento
                    )
                    golpe.anotar_propio(valor, True, user.id, momento)
                    golpe.anotar_del_marcador(valor, True, user.id, momento)
                    await self.comp.golpes_de_partida.guardar(golpe)
            for user, hoyo in (sin_validar or {}).items():
                golpe = GolpeDePartida.crear(
                    partida.id, round_.id, competition.id, user.id, hoyo, momento
                )
                golpe.anotar_propio(4, True, user.id, momento)
                await self.comp.golpes_de_partida.guardar(golpe)
        return partida


@pytest.fixture
def mundo() -> _Mundo:
    return _Mundo()


async def _entre(mundo: _Mundo, yo: User, el: User):
    return await mundo.adapter().between(yo.id, el.id)


class TestPartidaRapidaStrokePlay:
    async def test_stableford_gana_quien_hace_mas_puntos_aunque_tenga_peor_bruto(self, mundo):
        """
        Given yo hcp 30 con 5 por hoyo (90) y él scratch con 4 (72) en Stableford /
        When se mira el cara a cara / Then gano yo: mis golpes me dan mas puntos.
        """
        yo = await mundo.jugador("Yo", handicap=30)
        el = await mundo.jugador("El", handicap=0)
        course = await mundo.campo(yo)
        await mundo.partida_rapida(
            course,
            yo,
            [QuickMatchParticipant.for_user(el.id)],
            [5, 4],
            scoring_format=ScoringFormat.STABLEFORD,
        )

        (partida,) = await _entre(mundo, yo, el)

        assert partida.relation == Relation.AGAINST
        assert partida.outcome == Outcome.WON

    async def test_stableford_desde_el_otro_lado_pierde(self, mundo):
        yo = await mundo.jugador("Yo", handicap=0)
        el = await mundo.jugador("El", handicap=30)
        course = await mundo.campo(yo)
        await mundo.partida_rapida(
            course,
            yo,
            [QuickMatchParticipant.for_user(el.id)],
            [4, 5],
            scoring_format=ScoringFormat.STABLEFORD,
        )

        (partida,) = await _entre(mundo, yo, el)

        assert partida.outcome == Outcome.LOST

    async def test_medal_gana_quien_hace_menos_netos_aunque_tenga_peor_bruto(self, mundo):
        yo = await mundo.jugador("Yo", handicap=30)
        el = await mundo.jugador("El", handicap=0)
        course = await mundo.campo(yo)
        await mundo.partida_rapida(
            course,
            yo,
            [QuickMatchParticipant.for_user(el.id)],
            [5, 4],
            scoring_format=ScoringFormat.MEDAL,
        )

        (partida,) = await _entre(mundo, yo, el)

        assert partida.outcome == Outcome.WON

    async def test_mismos_golpes_sin_handicap_es_empate(self, mundo):
        yo = await mundo.jugador("Yo", handicap=12)
        el = await mundo.jugador("El", handicap=3)
        course = await mundo.campo(yo)
        await mundo.partida_rapida(
            course,
            yo,
            [QuickMatchParticipant.for_user(el.id)],
            [4, 4],
            scoring_format=ScoringFormat.MEDAL,
            play_mode=PlayMode.SCRATCH,
        )

        (partida,) = await _entre(mundo, yo, el)

        assert partida.outcome == Outcome.HALVED

    async def test_si_uno_no_tiene_handicap_sale_pero_no_cuenta(self, mundo):
        """
        Partida con hándicap y él sin hándicap: se le repartiría como scratch,
        que no es su juego real. La partida sale en la lista, sin resultado.
        """
        yo = await mundo.jugador("Yo", handicap=10)
        el = await mundo.jugador("El", handicap=None)
        course = await mundo.campo(yo)
        await mundo.partida_rapida(
            course,
            yo,
            [QuickMatchParticipant.for_user(el.id)],
            [4, 5],
            scoring_format=ScoringFormat.STABLEFORD,
        )

        (partida,) = await _entre(mundo, yo, el)

        assert partida.outcome is None

    async def test_en_una_partida_scratch_el_handicap_no_hace_falta(self, mundo):
        """Nadie recibe golpes: que él no tenga hándicap no cambia nada."""
        yo = await mundo.jugador("Yo", handicap=10)
        el = await mundo.jugador("El", handicap=None)
        course = await mundo.campo(yo)
        await mundo.partida_rapida(
            course,
            yo,
            [QuickMatchParticipant.for_user(el.id)],
            [4, 5],
            scoring_format=ScoringFormat.STABLEFORD,
            play_mode=PlayMode.SCRATCH,
        )

        (partida,) = await _entre(mundo, yo, el)

        assert partida.outcome == Outcome.WON

    async def test_una_tarjeta_a_medias_sale_pero_no_cuenta(self, mundo):
        """Caso 10: él dejo el 18 sin anotar; la partida sale, sin resultado."""
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo)
        await mundo.partida_rapida(
            course,
            yo,
            [QuickMatchParticipant.for_user(el.id)],
            [4, 5],
            scoring_format=ScoringFormat.STABLEFORD,
            hoyos=[18, 17],
        )

        (partida,) = await _entre(mundo, yo, el)

        assert partida.outcome is None

    async def test_un_tercero_no_cambia_el_cara_a_cara_entre_los_dos(self, mundo):
        """El tercero gana a los dos: entre nosotros sigue ganando yo."""
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        otro = await mundo.jugador("Otro")
        course = await mundo.campo(yo)
        await mundo.partida_rapida(
            course,
            yo,
            [QuickMatchParticipant.for_user(el.id), QuickMatchParticipant.for_user(otro.id)],
            [4, 5, 3],
            scoring_format=ScoringFormat.STABLEFORD,
        )

        (partida,) = await _entre(mundo, yo, el)

        assert partida.outcome == Outcome.WON


class TestPartidaRapidaMatchPlay:
    async def test_singles_gana_quien_gano_los_hoyos(self, mundo):
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo)
        await mundo.partida_rapida(
            course,
            yo,
            [QuickMatchParticipant.for_user(el.id)],
            [5, 4],
            match_format=MatchFormat.SINGLES,
        )

        (partida,) = await _entre(mundo, yo, el)

        assert partida.relation == Relation.AGAINST
        assert partida.outcome == Outcome.LOST
        assert partida.format == "SINGLES"

    async def test_singles_por_hoyos_netos_y_no_brutos(self, mundo):
        """Yo hcp 30 a 5 por hoyo contra él scratch a 4: con mis golpes gano yo."""
        yo = await mundo.jugador("Yo", handicap=30)
        el = await mundo.jugador("El", handicap=0)
        course = await mundo.campo(yo)
        await mundo.partida_rapida(
            course,
            yo,
            [QuickMatchParticipant.for_user(el.id)],
            [5, 4],
            match_format=MatchFormat.SINGLES,
        )

        (partida,) = await _entre(mundo, yo, el)

        assert partida.outcome == Outcome.WON

    async def test_fourball_en_el_mismo_bando_es_con_el(self, mundo):
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        rival1 = await mundo.jugador("Rival1")
        rival2 = await mundo.jugador("Rival2")
        course = await mundo.campo(yo)
        await mundo.partida_rapida(
            course,
            yo,
            [
                QuickMatchParticipant.for_user(el.id, team="A"),
                QuickMatchParticipant.for_user(rival1.id, team="B"),
                QuickMatchParticipant.for_user(rival2.id, team="B"),
            ],
            [4, 4, 5, 5],
            match_format=MatchFormat.FOURBALL,
        )

        (partida,) = await _entre(mundo, yo, el)

        assert partida.relation == Relation.WITH
        assert partida.outcome == Outcome.WON

    async def test_fourball_en_bandos_contrarios_es_contra_el(self, mundo):
        yo = await mundo.jugador("Yo")
        companero = await mundo.jugador("Companero")
        el = await mundo.jugador("El")
        suyo = await mundo.jugador("Suyo")
        course = await mundo.campo(yo)
        await mundo.partida_rapida(
            course,
            yo,
            [
                QuickMatchParticipant.for_user(companero.id, team="A"),
                QuickMatchParticipant.for_user(el.id, team="B"),
                QuickMatchParticipant.for_user(suyo.id, team="B"),
            ],
            [5, 5, 4, 4],
            match_format=MatchFormat.FOURBALL,
        )

        (partida,) = await _entre(mundo, yo, el)

        assert partida.relation == Relation.AGAINST
        assert partida.outcome == Outcome.LOST

    async def test_desde_el_bando_b(self, mundo):
        """Él crea la partida (bando A) y yo juego en el B contra él: pierdo."""
        el = await mundo.jugador("El")
        suyo = await mundo.jugador("Suyo")
        yo = await mundo.jugador("Yo")
        mio = await mundo.jugador("Mio")
        course = await mundo.campo(el)
        await mundo.partida_rapida(
            course,
            el,
            [
                QuickMatchParticipant.for_user(suyo.id, team="A"),
                QuickMatchParticipant.for_user(yo.id, team="B"),
                QuickMatchParticipant.for_user(mio.id, team="B"),
            ],
            [4, 4, 5, 5],
            match_format=MatchFormat.FOURBALL,
        )

        (partida,) = await _entre(mundo, yo, el)

        assert partida.relation == Relation.AGAINST
        assert partida.outcome == Outcome.LOST

    async def test_singles_con_handicap_si_el_no_tiene_sale_pero_no_cuenta(self, mundo):
        """Sin su hándicap se le repartiría como scratch: no es su partido real."""
        yo = await mundo.jugador("Yo", handicap=10)
        el = await mundo.jugador("El", handicap=None)
        course = await mundo.campo(yo)
        await mundo.partida_rapida(
            course,
            yo,
            [QuickMatchParticipant.for_user(el.id)],
            [4, 5],
            match_format=MatchFormat.SINGLES,
        )

        (partida,) = await _entre(mundo, yo, el)

        assert partida.relation == Relation.AGAINST
        assert partida.outcome is None

    async def test_fourball_si_cualquiera_de_los_cuatro_no_tiene_handicap_no_cuenta(self, mundo):
        """Un rival sin hándicap ya tuerce el reparto de todos: conservador."""
        yo = await mundo.jugador("Yo", handicap=10)
        el = await mundo.jugador("El", handicap=12)
        rival1 = await mundo.jugador("Rival1", handicap=None)
        rival2 = await mundo.jugador("Rival2", handicap=8)
        course = await mundo.campo(yo)
        await mundo.partida_rapida(
            course,
            yo,
            [
                QuickMatchParticipant.for_user(el.id, team="A"),
                QuickMatchParticipant.for_user(rival1.id, team="B"),
                QuickMatchParticipant.for_user(rival2.id, team="B"),
            ],
            [4, 4, 5, 5],
            match_format=MatchFormat.FOURBALL,
        )

        (partida,) = await _entre(mundo, yo, el)

        assert partida.relation == Relation.WITH
        assert partida.outcome is None

    async def test_match_play_scratch_sin_handicap_si_cuenta(self, mundo):
        yo = await mundo.jugador("Yo", handicap=None)
        el = await mundo.jugador("El", handicap=None)
        course = await mundo.campo(yo)
        await mundo.partida_rapida(
            course,
            yo,
            [QuickMatchParticipant.for_user(el.id)],
            [4, 5],
            match_format=MatchFormat.SINGLES,
            play_mode=PlayMode.SCRATCH,
        )

        (partida,) = await _entre(mundo, yo, el)

        assert partida.outcome == Outcome.WON


class TestPartidasRapidasQueNoSalen:
    async def test_oculta_por_mi_no_sale(self, mundo):
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo)
        match = await mundo.partida_rapida(
            course,
            yo,
            [QuickMatchParticipant.for_user(el.id)],
            [4, 5],
            scoring_format=ScoringFormat.STABLEFORD,
        )
        match.hide_for(ParticipantId(yo.id.value))

        assert await _entre(mundo, yo, el) == []

    async def test_oculta_por_el_no_sale(self, mundo):
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo)
        match = await mundo.partida_rapida(
            course,
            yo,
            [QuickMatchParticipant.for_user(el.id)],
            [4, 5],
            scoring_format=ScoringFormat.STABLEFORD,
        )
        match.hide_for(ParticipantId(el.id.value))

        assert await _entre(mundo, yo, el) == []

    async def test_sin_terminar_no_sale(self, mundo):
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo)
        await mundo.partida_rapida(
            course,
            yo,
            [QuickMatchParticipant.for_user(el.id)],
            [4, 5],
            scoring_format=ScoringFormat.STABLEFORD,
            terminar=False,
        )

        assert await _entre(mundo, yo, el) == []

    async def test_una_partida_sin_el_no_sale(self, mundo):
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        otro = await mundo.jugador("Otro")
        course = await mundo.campo(yo)
        await mundo.partida_rapida(
            course,
            yo,
            [QuickMatchParticipant.for_user(otro.id)],
            [4, 5],
            scoring_format=ScoringFormat.STABLEFORD,
        )

        assert await _entre(mundo, yo, el) == []


class TestPartidosDeTorneo:
    async def test_terminado_trae_el_resultado_oficial(self, mundo):
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo)
        competition = await mundo.competicion(yo)
        round_ = await mundo.ronda(competition, course)
        await mundo.partido(round_, [el], [yo], ganador="A")

        (partida,) = await _entre(mundo, yo, el)

        assert partida.relation == Relation.AGAINST
        assert partida.outcome == Outcome.LOST

    async def test_empatado(self, mundo):
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo)
        competition = await mundo.competicion(yo)
        round_ = await mundo.ronda(competition, course)
        await mundo.partido(round_, [yo], [el], ganador="HALVED")

        (partida,) = await _entre(mundo, yo, el)

        assert partida.outcome == Outcome.HALVED

    async def test_concedido_cuenta_con_su_resultado(self, mundo):
        """Concede el bando B (él): gano yo."""
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo)
        competition = await mundo.competicion(yo)
        round_ = await mundo.ronda(competition, course)
        await mundo.partido(round_, [yo], [el], estado="CONCEDED")

        (partida,) = await _entre(mundo, yo, el)

        assert partida.outcome == Outcome.WON

    async def test_en_juego_no_sale(self, mundo):
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo)
        competition = await mundo.competicion(yo)
        round_ = await mundo.ronda(competition, course)
        await mundo.partido(round_, [yo], [el], estado="IN_PROGRESS")

        assert await _entre(mundo, yo, el) == []

    async def test_por_walkover_no_sale(self, mundo):
        """Uno no se presento: no lo jugasteis juntos."""
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo)
        competition = await mundo.competicion(yo)
        round_ = await mundo.ronda(competition, course)
        await mundo.partido(round_, [yo], [el], estado="WALKOVER")

        assert await _entre(mundo, yo, el) == []

    async def test_foursomes_en_el_mismo_bando_es_con_el(self, mundo):
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        rival1 = await mundo.jugador("Rival1")
        rival2 = await mundo.jugador("Rival2")
        course = await mundo.campo(yo)
        competition = await mundo.competicion(yo)
        round_ = await mundo.ronda(competition, course, MatchFormat.FOURSOMES)
        await mundo.partido(round_, [rival1, rival2], [yo, el], ganador="B")

        (partida,) = await _entre(mundo, yo, el)

        assert partida.relation == Relation.WITH
        assert partida.outcome == Outcome.WON
        assert partida.format == "FOURSOMES"

    async def test_mismo_equipo_en_partidos_distintos_no_es_jugar_juntos(self, mundo):
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        rival1 = await mundo.jugador("Rival1")
        rival2 = await mundo.jugador("Rival2")
        course = await mundo.campo(yo)
        competition = await mundo.competicion(yo)
        round_ = await mundo.ronda(competition, course)
        await mundo.partido(round_, [yo], [rival1], numero=1)
        await mundo.partido(round_, [el], [rival2], numero=2)

        assert await _entre(mundo, yo, el) == []


class TestGruposDeStrokePlay:
    async def test_stableford_por_puntos_netos(self, mundo):
        """Recibo 1 golpe por hoyo y hago 5: 36 puntos contra sus 18 a 5 sin golpes."""
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo)
        competition = await mundo.competicion(yo, TournamentType.STABLEFORD)
        round_ = await mundo.ronda(competition, course)
        await mundo.grupo(
            competition,
            round_,
            {yo: [5] * 18, el: [5] * 18},
            golpes_recibidos={yo: 1},
        )

        (partida,) = await _entre(mundo, yo, el)

        assert partida.relation == Relation.AGAINST
        assert partida.outcome == Outcome.WON
        assert partida.format == "STABLEFORD"

    async def test_medal_por_golpes_netos(self, mundo):
        """Mi bruto (90) es peor que el suyo (73), pero con mis 18 golpes hago 72 netos: gano."""
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo)
        competition = await mundo.competicion(yo, TournamentType.MEDAL)
        round_ = await mundo.ronda(competition, course)
        await mundo.grupo(
            competition,
            round_,
            {yo: [5] * 18, el: [4] * 17 + [5]},
            golpes_recibidos={yo: 1},
        )

        (partida,) = await _entre(mundo, yo, el)

        assert partida.outcome == Outcome.WON
        assert partida.format == "MEDAL"

    async def test_sin_acabar_no_sale(self, mundo):
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo)
        competition = await mundo.competicion(yo, TournamentType.STABLEFORD)
        round_ = await mundo.ronda(competition, course)
        await mundo.grupo(
            competition,
            round_,
            {yo: [4] * 18, el: [4] * 18},
            estado=EstadoPartida.IN_PROGRESS,
        )

        assert await _entre(mundo, yo, el) == []

    async def test_si_el_no_se_presento_no_jugasteis_juntos(self, mundo):
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        otro = await mundo.jugador("Otro")
        course = await mundo.campo(yo)
        competition = await mundo.competicion(yo, TournamentType.STABLEFORD)
        round_ = await mundo.ronda(competition, course)
        await mundo.grupo(
            competition,
            round_,
            {yo: [4] * 18, el: [], otro: [4] * 18},
            estados={el: EstadoDeTarjeta.NO_PRESENTADO},
        )

        assert await _entre(mundo, yo, el) == []

    async def test_si_se_retiro_sale_sin_resultado(self, mundo):
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo)
        competition = await mundo.competicion(yo, TournamentType.STABLEFORD)
        round_ = await mundo.ronda(competition, course)
        await mundo.grupo(
            competition,
            round_,
            {yo: [4] * 18, el: [4] * 10},
            estados={el: EstadoDeTarjeta.RETIRADO},
        )

        (partida,) = await _entre(mundo, yo, el)

        assert partida.outcome is None

    async def test_en_la_misma_ronda_pero_en_grupos_distintos_no_sois_rivales(self, mundo):
        """
        Rivales en stroke play = el MISMO grupo (lo que respondió Agustín): jugar
        la misma ronda del torneo saliendo en grupos distintos no cuenta.
        """
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        otro1 = await mundo.jugador("Otro1")
        otro2 = await mundo.jugador("Otro2")
        course = await mundo.campo(yo)
        competition = await mundo.competicion(yo, TournamentType.STABLEFORD)
        round_ = await mundo.ronda(competition, course)
        await mundo.grupo(competition, round_, {yo: [4] * 18, otro1: [5] * 18}, numero=1)
        await mundo.grupo(competition, round_, {el: [5] * 18, otro2: [4] * 18}, numero=2)

        assert await _entre(mundo, yo, el) == []

    async def test_retirado_aunque_tenga_los_18_validados_no_cuenta(self, mundo):
        """Solo se juzga la tarjeta entregada."""
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo)
        competition = await mundo.competicion(yo, TournamentType.STABLEFORD)
        round_ = await mundo.ronda(competition, course)
        await mundo.grupo(
            competition,
            round_,
            {yo: [4] * 18, el: [4] * 18},
            estados={el: EstadoDeTarjeta.RETIRADO},
        )

        (partida,) = await _entre(mundo, yo, el)

        assert partida.outcome is None

    async def test_entregada_con_un_hoyo_sin_validar_no_cuenta(self, mundo):
        """Caso 10: el 18 solo lo apunto él, sin su marcador: tarjeta a medias."""
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo)
        competition = await mundo.competicion(yo, TournamentType.STABLEFORD)
        round_ = await mundo.ronda(competition, course)
        await mundo.grupo(
            competition,
            round_,
            {yo: [4] * 18, el: [4] * 17},
            sin_validar={el: 18},
        )

        (partida,) = await _entre(mundo, yo, el)

        assert partida.outcome is None


class TestLoQueTraeCadaPartida:
    async def test_una_partida_rapida_trae_fecha_campo_formato_y_enlace(self, mundo):
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo, "Valderrama")
        match = await mundo.partida_rapida(
            course,
            yo,
            [QuickMatchParticipant.for_user(el.id)],
            [4, 5],
            scoring_format=ScoringFormat.STABLEFORD,
        )
        # Se creó un día y se tocó otro (ocultarla, por ejemplo): manda la creación
        match._created_at = datetime(2026, 9, 1, 9, 0)

        (partida,) = await _entre(mundo, yo, el)

        assert partida.kind == SharedGameKind.QUICK_MATCH
        assert partida.game_id == str(match.id.value)
        assert partida.played_on == date(2026, 9, 1)
        assert partida.golf_course_id == str(course.id.value)
        assert partida.golf_course_name == "Valderrama"
        assert partida.format == "STABLEFORD"
        assert partida.competition_id is None

    async def test_un_partido_de_torneo_trae_su_torneo_y_su_dia(self, mundo):
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo, "PGA Catalunya")
        competition = await mundo.competicion(yo)
        round_ = await mundo.ronda(competition, course)
        match = await mundo.partido(round_, [yo], [el])

        (partida,) = await _entre(mundo, yo, el)

        assert partida.kind == SharedGameKind.TOURNAMENT_MATCH
        assert partida.game_id == str(match.id.value)
        assert partida.played_on == DIA
        assert partida.golf_course_name == "PGA Catalunya"
        assert partida.competition_id == str(competition.id.value)
        assert partida.competition_name == "Copa de Otoño"

    async def test_un_grupo_de_torneo_trae_su_torneo(self, mundo):
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo)
        competition = await mundo.competicion(yo, TournamentType.STABLEFORD)
        round_ = await mundo.ronda(competition, course)
        grupo = await mundo.grupo(competition, round_, {yo: [4] * 18, el: [4] * 18})

        (partida,) = await _entre(mundo, yo, el)

        assert partida.kind == SharedGameKind.TOURNAMENT_GROUP
        assert partida.game_id == str(grupo.id)
        assert partida.played_on == DIA
        assert partida.competition_id == str(competition.id.value)

    async def test_salen_las_de_las_tres_fuentes(self, mundo):
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo)
        await mundo.partida_rapida(
            course,
            yo,
            [QuickMatchParticipant.for_user(el.id)],
            [4, 5],
            scoring_format=ScoringFormat.STABLEFORD,
        )
        ryder = await mundo.competicion(yo)
        await mundo.partido(await mundo.ronda(ryder, course), [yo], [el])
        stableford = await mundo.competicion(yo, TournamentType.STABLEFORD)
        await mundo.grupo(
            stableford,
            await mundo.ronda(stableford, course),
            {yo: [4] * 18, el: [4] * 18},
        )

        partidas = await _entre(mundo, yo, el)

        assert {p.kind for p in partidas} == set(SharedGameKind)


class _Contador:
    """Envuelve un metodo de un repositorio y cuenta cuantas veces se llama."""

    def __init__(self, objeto, nombre: str):
        self.llamadas = 0
        original = getattr(objeto, nombre)

        async def contado(*args, **kwargs):
            self.llamadas += 1
            return await original(*args, **kwargs)

        setattr(objeto, nombre, contado)


class TestElInstanteDeCadaPartida:
    """
    Revision del 22 oct: el instante ordena las del mismo dia. En UTC y sin
    zona, la misma escala para las tres fuentes.
    """

    async def test_la_partida_rapida_lleva_su_hora_de_creacion(self, mundo):
        """Se juegan del tiron: la hora de creacion es la del juego."""
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo)
        match = await mundo.partida_rapida(
            course,
            yo,
            [QuickMatchParticipant.for_user(el.id)],
            [4, 5],
            scoring_format=ScoringFormat.STABLEFORD,
        )
        match._created_at = datetime(2026, 9, 1, 17, 45)

        (partida,) = await _entre(mundo, yo, el)

        assert partida.played_at == datetime(2026, 9, 1, 17, 45)

    @pytest.mark.parametrize(
        ("sesion", "hora_utc"),
        [(SessionType.MORNING, 4), (SessionType.AFTERNOON, 10), (SessionType.EVENING, 16)],
    )
    async def test_un_partido_de_torneo_lleva_la_hora_de_su_sesion_en_utc(
        self, mundo, sesion, hora_utc
    ):
        """
        Given una ronda en un campo de Madrid (UTC+2 en septiembre) / Then el
        instante es la hora de su sesion (6, 12 o 18 locales) pasada a UTC.
        """
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo, timezone="Europe/Madrid")
        competition = await mundo.competicion(yo)
        round_ = await mundo.ronda(competition, course, session_type=sesion)
        await mundo.partido(round_, [yo], [el])

        (partida,) = await _entre(mundo, yo, el)

        assert partida.played_at == datetime.combine(DIA, time(hora_utc))

    async def test_un_grupo_sin_zona_conocida_no_tiene_instante(self, mundo):
        """
        Sin zona del campo no se sabe el instante en UTC: None, y se ordena como
        el principio de su dia (CodeRabbit BE #633), sin mezclar escalas.
        """
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        course = await mundo.campo(yo)
        competition = await mundo.competicion(yo, TournamentType.STABLEFORD)
        round_ = await mundo.ronda(competition, course, session_type=SessionType.AFTERNOON)
        await mundo.grupo(competition, round_, {yo: [4] * 18, el: [4] * 18})

        (partida,) = await _entre(mundo, yo, el)

        assert partida.played_at is None


class TestSinUnaConsultaPorPartida:
    async def test_jugadores_campos_y_golpes_en_bloque(self, mundo):
        """
        Caso 19: tres partidas rapidas, tres partidos y tres grupos en seis
        competiciones / When se leen / Then jugadores, campos, golpes, rondas y
        competiciones se piden de una vez, nunca uno por uno.
        """
        yo = await mundo.jugador("Yo")
        el = await mundo.jugador("El")
        campos = [await mundo.campo(yo, f"Campo {i}") for i in range(3)]
        for course in campos:
            await mundo.partida_rapida(
                course,
                yo,
                [QuickMatchParticipant.for_user(el.id)],
                [4, 5],
                scoring_format=ScoringFormat.STABLEFORD,
            )
        for course in campos:
            ryder = await mundo.competicion(yo)
            await mundo.partido(await mundo.ronda(ryder, course), [yo], [el])
            stableford = await mundo.competicion(yo, TournamentType.STABLEFORD)
            await mundo.grupo(
                stableford, await mundo.ronda(stableford, course), {yo: [4] * 18, el: [4] * 18}
            )

        uno_a_uno = [
            _Contador(mundo.users.users, "find_by_id"),
            _Contador(mundo.courses.golf_courses, "find_by_id"),
            _Contador(mundo.qm.quick_match_hole_scores, "find_by_match"),
            _Contador(mundo.comp.rounds, "find_by_id"),
            _Contador(mundo.comp.competitions, "find_by_id"),
        ]
        en_bloque = [
            _Contador(mundo.users.users, "find_by_ids"),
            _Contador(mundo.courses.golf_courses, "find_by_ids"),
            _Contador(mundo.qm.quick_match_hole_scores, "find_by_matches"),
            _Contador(mundo.comp.rounds, "find_by_ids"),
            _Contador(mundo.comp.competitions, "find_by_ids"),
        ]

        partidas = await _entre(mundo, yo, el)

        assert len(partidas) == 9
        assert {p.competition_name for p in partidas if p.competition_id} == {"Copa de Otoño"}
        assert [c.llamadas for c in uno_a_uno] == [0, 0, 0, 0, 0]
        assert [c.llamadas for c in en_bloque] == [1, 1, 1, 1, 1]
