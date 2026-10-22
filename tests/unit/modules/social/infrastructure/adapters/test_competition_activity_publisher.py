"""
Tests del adaptador que lleva a Actividad lo de `competition` (BE-2): que
traduce bien y que la clasificacion final sale de la general oficial, sin
recalcularla.
"""

from datetime import date, time
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.jugador_de_partida import JugadorDePartida
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.social.application.use_cases.publish_competition_notices_use_case import (
    MatchOutcome,
    StandingRef,
    TeeTimeRef,
    TournamentRef,
)
from src.modules.social.infrastructure.adapters.competition_activity_publisher import (
    CompetitionActivityPublisher,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat

pytestmark = pytest.mark.asyncio


class _Avisos:
    """El caso de uso social, apuntando lo que recibe."""

    def __init__(self):
        self.llamadas: list[tuple] = []

    def __getattr__(self, nombre):
        async def _apunta(*args, **kwargs):
            self.llamadas.append((nombre, args, kwargs))

        return _apunta


class _General:
    """La general oficial: lo que devuelve, tal cual."""

    def __init__(self, filas, tipo="STABLEFORD"):
        self.pedida: list = []
        self._respuesta = SimpleNamespace(tournament_type=tipo, rows=filas)

    async def execute(self, competition_id, categoria=None):
        self.pedida.append((competition_id, categoria))
        return self._respuesta


class _Inscripciones:
    """La UoW de competition, solo para releer una inscripcion; aprobada si no se dice."""

    def __init__(self, estado: EnrollmentStatus | None = EnrollmentStatus.APPROVED):
        self._estado = estado
        self.enrollments = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def find_by_id(self, enrollment_id):
        if self._estado is None:
            return None
        return SimpleNamespace(id=enrollment_id, status=self._estado)


def _competicion(visibility=Visibility.PUBLIC, stroke_play=None):
    return SimpleNamespace(
        id=CompetitionId(uuid4()),
        name="Open de Otoño",
        dates=SimpleNamespace(start_date=date(2027, 3, 3), end_date=date(2027, 3, 4)),
        visibility=visibility,
        stroke_play=stroke_play,
    )


def _ref(competicion, is_public=True) -> TournamentRef:
    return TournamentRef(
        competition_id=str(competicion.id.value),
        name="Open de Otoño",
        start_date=date(2027, 3, 3),
        end_date=date(2027, 3, 4),
        is_public=is_public,
    )


def _en_partido(user_id: UserId) -> MatchPlayer:
    return MatchPlayer.create(
        user_id=user_id,
        playing_handicap=0,
        tee_color=TeeColor.YELLOW,
        tee_gender=Gender.MALE,
        strokes_received=[],
    )


def _en_partida(user_id: UserId) -> JugadorDePartida:
    return JugadorDePartida(
        user_id=user_id,
        handicap=Decimal("0"),
        playing_handicap=0,
        tee_color=TeeColor.YELLOW,
        tee_gender=Gender.MALE,
        golpes_por_hoyo=(0,) * 18,
        par_por_hoyo=(4,) * 18,
    )


async def _inscritos(uow, competicion, jugadores, estado=EnrollmentStatus.APPROVED) -> None:
    async with uow:
        for jugador in jugadores:
            await uow.enrollments.add(
                Enrollment(
                    id=EnrollmentId.generate(),
                    competition_id=competicion.id,
                    user_id=jugador,
                    status=estado,
                )
            )


@pytest.fixture
def avisos():
    return _Avisos()


class TestTraduccion:
    async def test_g_las_salidas_se_releen_de_la_ronda(self, avisos):
        """
        G3. No publica la foto que trae la accion: le da al caso de uso como
        releer la ronda, que lo hace con el candado puesto. La hora va
        «HH:MM», el partido por su id, la sesion por su nombre.
        """
        competicion = _competicion()
        uow = InMemoryUnitOfWork()
        yo, pedro, juan, luis = (UserId(uuid4()) for _ in range(4))
        sesion = Round.create(
            competition_id=competicion.id,
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2027, 3, 3),
            session_type=SessionType.AFTERNOON,
            match_format=MatchFormat.FOURBALL,
        )
        partido = Match.create(
            round_id=sesion.id,
            match_number=1,
            team_a_players=[_en_partido(yo), _en_partido(pedro)],
            team_b_players=[_en_partido(juan), _en_partido(luis)],
        )
        async with uow:
            await uow.rounds.add(sesion)
            await uow.matches.add(partido)
        await _inscritos(uow, competicion, [yo, pedro, juan, luis])
        adaptador = CompetitionActivityPublisher(avisos, _General([]), uow)

        # Lo que trae la accion no cuenta: puede ser viejo
        await adaptador.tee_times(competicion, sesion.id, [], [UserId(uuid4())])

        ((nombre, (torneo, ronda, releer), _),) = avisos.llamadas
        assert (nombre, torneo, ronda) == ("tee_times", _ref(competicion), str(sesion.id.value))
        assert sorted(await releer(), key=lambda r: str(r.user_id)) == sorted(
            [
                TeeTimeRef(
                    user_id=yo,
                    round_date=date(2027, 3, 3),
                    session_type="AFTERNOON",
                    tee_time=None,
                    partner_ids=(pedro,),
                    opponent_ids=(juan, luis),
                    match_id=str(partido.id.value),
                ),
                TeeTimeRef(
                    user_id=pedro,
                    round_date=date(2027, 3, 3),
                    session_type="AFTERNOON",
                    tee_time=None,
                    partner_ids=(yo,),
                    opponent_ids=(juan, luis),
                    match_id=str(partido.id.value),
                ),
                TeeTimeRef(
                    user_id=juan,
                    round_date=date(2027, 3, 3),
                    session_type="AFTERNOON",
                    tee_time=None,
                    partner_ids=(luis,),
                    opponent_ids=(yo, pedro),
                    match_id=str(partido.id.value),
                ),
                TeeTimeRef(
                    user_id=luis,
                    round_date=date(2027, 3, 3),
                    session_type="AFTERNOON",
                    tee_time=None,
                    partner_ids=(juan,),
                    opponent_ids=(yo, pedro),
                    match_id=str(partido.id.value),
                ),
            ],
            key=lambda r: str(r.user_id),
        )

    async def test_g_la_hora_de_stroke_play_va_hh_mm(self, avisos):
        competicion = _competicion()
        uow = InMemoryUnitOfWork()
        yo, pedro = UserId(uuid4()), UserId(uuid4())
        franja = Round.create_franja(
            competition_id=competicion.id,
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2027, 3, 3),
            session_type=SessionType.MORNING,
            hoja_de_salidas=HojaDeSalidas(time(9, 0), time(10, 0), 5, 4),
        )
        async with uow:
            await uow.rounds.add(franja)
            await uow.partidas.anadir(
                [Partida.crear(competicion.id, franja.id, 2, [_en_partida(yo), _en_partida(pedro)])]
            )
        await _inscritos(uow, competicion, [yo, pedro])
        adaptador = CompetitionActivityPublisher(avisos, _General([]), uow)

        await adaptador.tee_times(competicion, franja.id, [], [])

        ((_, (_, _, releer), _),) = avisos.llamadas
        assert [
            (r.tee_time, r.partner_ids, r.match_id) for r in await releer() if r.user_id == yo
        ] == [("09:05", (pedro,), None)]

    async def test_g_quien_ya_no_esta_inscrito_no_tiene_salida(self, avisos):
        """
        Revision final del 22 oct: quien se dio de baja sigue en su partido
        hasta que lo reasignen, pero no recupera su aviso.
        """
        competicion = _competicion()
        uow = InMemoryUnitOfWork()
        yo, baja = UserId(uuid4()), UserId(uuid4())
        sesion = Round.create(
            competition_id=competicion.id,
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2027, 3, 3),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        async with uow:
            await uow.rounds.add(sesion)
            await uow.matches.add(
                Match.create(
                    round_id=sesion.id,
                    match_number=1,
                    team_a_players=[_en_partido(yo)],
                    team_b_players=[_en_partido(baja)],
                )
            )
        await _inscritos(uow, competicion, [yo])
        await _inscritos(uow, competicion, [baja], EnrollmentStatus.WITHDRAWN)
        adaptador = CompetitionActivityPublisher(avisos, _General([]), uow)

        await adaptador.tee_times(competicion, sesion.id, [], [])

        ((_, (_, _, releer), _),) = avisos.llamadas
        assert [r.user_id for r in await releer()] == [yo]

    async def test_g_el_no_presentado_va_fuera_de_juego(self, avisos):
        competicion = _competicion()
        uow = InMemoryUnitOfWork()
        falta, yo = UserId(uuid4()), UserId(uuid4())
        franja = Round.create_franja(
            competition_id=competicion.id,
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2027, 3, 3),
            session_type=SessionType.MORNING,
            hoja_de_salidas=HojaDeSalidas(time(9, 0), time(10, 0), 5, 4),
        )
        partida = Partida.crear(competicion.id, franja.id, 1, [_en_partida(falta), _en_partida(yo)])
        partida.no_presentado(falta, [])
        async with uow:
            await uow.rounds.add(franja)
            await uow.partidas.anadir([partida])
        await _inscritos(uow, competicion, [falta, yo])
        adaptador = CompetitionActivityPublisher(avisos, _General([]), uow)

        await adaptador.tee_times(competicion, franja.id, [], [])

        ((_, (_, _, releer), _),) = avisos.llamadas
        assert {r.user_id: r.out_of_play for r in await releer()} == {falta: True, yo: False}

    async def test_g_una_ronda_que_ya_no_existe_no_tiene_salidas(self, avisos):
        adaptador = CompetitionActivityPublisher(avisos, _General([]), InMemoryUnitOfWork())

        await adaptador.tee_times(_competicion(), RoundId.generate(), [], [])

        ((_, (_, _, releer), _),) = avisos.llamadas
        assert await releer() == []

    async def test_inscrito_en_un_publico(self, avisos):
        competicion = _competicion()
        inscripcion = SimpleNamespace(id=SimpleNamespace(value=uuid4()), user_id=UserId(uuid4()))

        await CompetitionActivityPublisher(avisos, _General([]), _Inscripciones()).enrolled(
            competicion, inscripcion, accepted_request=True
        )

        assert avisos.llamadas == [
            (
                "enrolled",
                (inscripcion.user_id, _ref(competicion), str(inscripcion.id.value), True),
                {},
            )
        ]

    @pytest.mark.parametrize(
        "estado", [EnrollmentStatus.WITHDRAWN, EnrollmentStatus.CANCELLED, None]
    )
    async def test_8_si_ya_no_esta_inscrito_no_se_publica(self, avisos, estado):
        """
        8. Given una inscripcion que se retiro (o se borro) antes de publicar
        su aviso / When se publica / Then nada: el aviso llegaria tarde.
        """
        inscripcion = SimpleNamespace(id=SimpleNamespace(value=uuid4()), user_id=UserId(uuid4()))

        await CompetitionActivityPublisher(avisos, _General([]), _Inscripciones(estado)).enrolled(
            _competicion(), inscripcion, accepted_request=True
        )

        assert avisos.llamadas == []

    async def test_un_privado_no_es_publico(self, avisos):
        competicion = _competicion(visibility=Visibility.PRIVATE)
        inscripcion = SimpleNamespace(id=SimpleNamespace(value=uuid4()), user_id=UserId(uuid4()))

        await CompetitionActivityPublisher(avisos, _General([]), _Inscripciones()).enrolled(
            competicion, inscripcion, accepted_request=False
        )

        (_, args, _) = avisos.llamadas[0]
        assert args[1].is_public is False

    async def test_retirar_cancelar_y_reabrir_van_por_el_id(self, avisos):
        competicion = _competicion()
        jugador = UserId(uuid4())
        adaptador = CompetitionActivityPublisher(avisos, _General([]), _Inscripciones())

        await adaptador.left(competicion.id, jugador)
        await adaptador.cancelled(competicion.id)
        await adaptador.reopened(competicion.id)
        await adaptador.made_private(competicion.id)
        await adaptador.deleted(competicion.id)

        crudo = str(competicion.id.value)
        assert avisos.llamadas == [
            ("left", (jugador, crudo), {}),
            ("tournament_cancelled", (crudo,), {}),
            ("reopened", (crudo,), {}),
            ("tournament_made_private", (crudo,), {}),
            ("tournament_deleted", (crudo,), {}),
        ]

    async def test_borrar_una_ronda_va_por_los_ids(self, avisos):
        competicion = _competicion()
        ronda = RoundId.generate()
        adaptador = CompetitionActivityPublisher(avisos, _General([]), _Inscripciones())

        await adaptador.round_deleted(competicion.id, ronda)

        assert avisos.llamadas == [
            ("round_deleted", (str(competicion.id.value), str(ronda.value)), {})
        ]

    async def test_invitaciones_por_su_id(self, avisos):
        competicion = _competicion()
        invitacion = SimpleNamespace(
            id=SimpleNamespace(value=uuid4()), invitee_user_id=UserId(uuid4())
        )
        adaptador = CompetitionActivityPublisher(avisos, _General([]), _Inscripciones())

        await adaptador.invited(competicion, invitacion)
        await adaptador.invitation_withdrawn(invitacion)
        await adaptador.invitation_answered(invitacion)

        crudo = str(invitacion.id.value)
        assert avisos.llamadas == [
            ("invited", (invitacion.invitee_user_id, _ref(competicion), crudo), {}),
            ("invitation_withdrawn", (invitacion.invitee_user_id, crudo), {}),
            ("invitation_answered", (invitacion.invitee_user_id, crudo), {}),
        ]

    async def test_invitaciones_cerradas_solas_por_su_id(self, avisos):
        con_cuenta = SimpleNamespace(
            id=SimpleNamespace(value=uuid4()), invitee_user_id=UserId(uuid4())
        )
        sin_cuenta = SimpleNamespace(id=SimpleNamespace(value=uuid4()), invitee_user_id=None)
        adaptador = CompetitionActivityPublisher(avisos, _General([]), _Inscripciones())

        await adaptador.invitations_closed([con_cuenta, sin_cuenta])

        assert avisos.llamadas == [
            (
                "invitations_closed",
                ([(con_cuenta.invitee_user_id, str(con_cuenta.id.value))],),
                {},
            )
        ]

    async def test_solicitudes_cerradas_y_rechazada(self, avisos):
        competicion = _competicion()
        una = SimpleNamespace(id=SimpleNamespace(value=uuid4()), user_id=UserId(uuid4()))
        otra = SimpleNamespace(id=SimpleNamespace(value=uuid4()), user_id=UserId(uuid4()))
        adaptador = CompetitionActivityPublisher(avisos, _General([]), _Inscripciones())

        await adaptador.requests_closed(competicion, [una, otra])
        await adaptador.request_rejected(competicion, una)

        assert avisos.llamadas == [
            (
                "requests_closed",
                (
                    _ref(competicion),
                    [(una.user_id, str(una.id.value)), (otra.user_id, str(otra.id.value))],
                ),
                {},
            ),
            ("request_rejected", (una.user_id, _ref(competicion), str(una.id.value)), {}),
        ]

    @pytest.mark.parametrize(
        ("result", "winner", "score"),
        [
            ({"winner": "A", "score": "3&2"}, "A", "3&2"),
            ({"winner": "B", "score": "CONCEDED"}, "B", "CONCEDED"),
            (None, None, None),
        ],
    )
    async def test_partido_terminado(self, avisos, result, winner, score):
        competicion = _competicion()
        a, b = UserId(uuid4()), UserId(uuid4())
        partido = SimpleNamespace(
            id=SimpleNamespace(value=uuid4()),
            team_a_players=(SimpleNamespace(user_id=a),),
            team_b_players=(SimpleNamespace(user_id=b),),
            result=result,
        )
        ronda = SimpleNamespace(round_date=date(2027, 3, 4))

        await CompetitionActivityPublisher(avisos, _General([]), _Inscripciones()).match_finished(
            competicion, ronda, partido
        )

        assert avisos.llamadas == [
            (
                "match_finished",
                (
                    _ref(competicion),
                    MatchOutcome(
                        match_id=str(partido.id.value),
                        played_on=date(2027, 3, 4),
                        team_a=(a,),
                        team_b=(b,),
                        winner=winner,
                        score=score,
                    ),
                ),
                {},
            )
        ]

    async def test_una_ronda_sin_fecha_toma_el_primer_dia(self, avisos):
        competicion = _competicion()
        partido = SimpleNamespace(
            id=SimpleNamespace(value=uuid4()),
            team_a_players=(),
            team_b_players=(),
            result={"winner": "A", "score": "1UP"},
        )

        await CompetitionActivityPublisher(avisos, _General([]), _Inscripciones()).match_finished(
            competicion, SimpleNamespace(round_date=None), partido
        )

        assert avisos.llamadas[0][1][1].played_on == date(2027, 3, 3)


class TestClasificacionFinal:
    async def test_c14_sale_de_la_general_oficial(self, avisos):
        """C14. Given la general oficial / When termina / Then sus filas tal cual."""
        competicion = _competicion(stroke_play=object())
        ana, eva = uuid4(), uuid4()
        general = _General(
            [
                SimpleNamespace(
                    user_id=ana, position=1, tied=False, value=40, status="CLASIFICADO"
                ),
                SimpleNamespace(user_id=eva, position=None, tied=False, value=None, status="NR"),
            ],
            tipo="STABLEFORD",
        )

        await CompetitionActivityPublisher(avisos, general, _Inscripciones()).completed(competicion)

        assert general.pedida == [(competicion.id.value, None)]
        assert avisos.llamadas == [
            (
                "final_standings",
                (
                    _ref(competicion),
                    "STABLEFORD",
                    [
                        StandingRef(UserId(ana), 1, False, 40, "CLASIFICADO"),
                        StandingRef(UserId(eva), None, False, None, "NR"),
                    ],
                ),
                {},
            )
        ]

    async def test_una_ryder_no_tiene_clasificacion_individual(self, avisos):
        general = _General([])

        await CompetitionActivityPublisher(avisos, general, _Inscripciones()).completed(
            _competicion()
        )

        assert general.pedida == []
        assert avisos.llamadas == []
