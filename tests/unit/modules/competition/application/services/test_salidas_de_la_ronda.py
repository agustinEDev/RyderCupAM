"""
La foto de las salidas de una ronda y lo que cambia entre dos fotos (G, 22 oct 2026).

Tabla aprobada por Agustin (G1-G4, G11):

| Caso                                              | Resultado                                  |
|---------------------------------------------------|--------------------------------------------|
| Partidas de stroke play                           | Hora de su partida y compañeros de grupo   |
| Con otra hoja de salidas                          | La hora sale de esa hoja, no de la franja  |
| Partido individual                                | Sin hora, sin compañero, un rival          |
| Partido de fourball                               | Su compañero y los dos rivales             |
| Jugador nuevo en la ronda                         | Aviso, `changed` False                     |
| Otra hora / otros compañeros / otros rivales      | Aviso, `changed` True                      |
| Mismos compañeros en otro orden                   | Sin aviso                                  |
| Mismo partido con otro id (regenerado)            | Sin aviso                                  |
| Otro dia u otra sesion                            | Aviso, `changed` True                      |
| Sale de la ronda                                  | Pierde el aviso                            |
"""

from datetime import date, time
from decimal import Decimal
from uuid import uuid4

from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    TeeTimeAssignment,
)
from src.modules.competition.application.services.salidas_de_la_ronda import (
    cambios,
    de_las_partidas,
    de_los_partidos,
)
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.jugador_de_partida import JugadorDePartida
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat

SABADO = date(2026, 10, 24)


def _franja() -> Round:
    return Round.create_franja(
        competition_id=CompetitionId(uuid4()),
        golf_course_id=GolfCourseId.generate(),
        round_date=SABADO,
        session_type=SessionType.MORNING,
        hoja_de_salidas=HojaDeSalidas(time(9, 0), time(10, 0), 10, 4),
    )


def _foto(user_id: UserId) -> JugadorDePartida:
    return JugadorDePartida(
        user_id=user_id,
        handicap=Decimal("0"),
        playing_handicap=0,
        tee_color=TeeColor.YELLOW,
        tee_gender=Gender.MALE,
        golpes_por_hoyo=(0,) * 18,
        par_por_hoyo=(4,) * 18,
    )


def _partida(franja: Round, numero: int, jugadores: list[UserId]) -> Partida:
    return Partida.crear(franja.competition_id, franja.id, numero, [_foto(u) for u in jugadores])


def _jugador(user_id: UserId) -> MatchPlayer:
    return MatchPlayer.create(
        user_id=user_id,
        playing_handicap=0,
        tee_color=TeeColor.YELLOW,
        tee_gender=Gender.MALE,
        strokes_received=[],
    )


def _sesion(formato: MatchFormat) -> Round:
    return Round.create(
        competition_id=CompetitionId(uuid4()),
        golf_course_id=GolfCourseId.generate(),
        round_date=SABADO,
        session_type=SessionType.AFTERNOON,
        match_format=formato,
    )


def _partido(ronda: Round, numero: int, a: list[UserId], b: list[UserId]) -> Match:
    return Match.create(
        round_id=ronda.id,
        match_number=numero,
        team_a_players=[_jugador(u) for u in a],
        team_b_players=[_jugador(u) for u in b],
    )


def _ids(n: int) -> list[UserId]:
    return [UserId(uuid4()) for _ in range(n)]


def _salida(user_id, hora=time(9, 0), con=(), contra=(), partido=None, dia=SABADO):
    return TeeTimeAssignment(
        user_id=user_id,
        round_date=dia,
        session_type=SessionType.MORNING,
        tee_time=hora,
        partner_ids=tuple(con),
        opponent_ids=tuple(contra),
        match_id=partido,
    )


class TestFotoDeStrokePlay:
    def test_hour_of_its_group_and_its_group_mates(self):
        franja = _franja()
        a, b, c, d, e = _ids(5)

        salidas = de_las_partidas(
            franja, [_partida(franja, 1, [a, b, c]), _partida(franja, 2, [d, e])]
        )

        assert set(salidas) == {a, b, c, d, e}
        assert salidas[a] == TeeTimeAssignment(
            user_id=a,
            round_date=SABADO,
            session_type=SessionType.MORNING,
            tee_time=time(9, 0),
            partner_ids=(b, c),
            opponent_ids=(),
            match_id=None,
            changed=False,
        )
        assert salidas[e].tee_time == time(9, 10)
        assert salidas[e].partner_ids == (d,)

    def test_with_another_tee_sheet_the_hour_comes_from_it(self):
        franja = _franja()
        a, b = _ids(2)

        salidas = de_las_partidas(
            franja, [_partida(franja, 2, [a, b])], HojaDeSalidas(time(8, 0), time(10, 0), 8, 4)
        )

        assert salidas[a].tee_time == time(8, 8)


class TestFotoDeRyder:
    def test_singles_no_hour_no_partner_one_rival(self):
        ronda = _sesion(MatchFormat.SINGLES)
        a, b = _ids(2)
        partido = _partido(ronda, 1, [a], [b])

        salidas = de_los_partidos(ronda, [partido])

        assert salidas[a] == TeeTimeAssignment(
            user_id=a,
            round_date=SABADO,
            session_type=SessionType.AFTERNOON,
            tee_time=None,
            partner_ids=(),
            opponent_ids=(b,),
            match_id=partido.id,
            changed=False,
        )
        assert salidas[b].opponent_ids == (a,)

    def test_fourball_partner_and_two_rivals(self):
        ronda = _sesion(MatchFormat.FOURBALL)
        a1, a2, b1, b2 = _ids(4)

        salidas = de_los_partidos(ronda, [_partido(ronda, 1, [a1, a2], [b1, b2])])

        assert salidas[a1].partner_ids == (a2,)
        assert salidas[a1].opponent_ids == (b1, b2)
        assert salidas[b2].partner_ids == (b1,)
        assert salidas[b2].opponent_ids == (a1, a2)


class TestCambios:
    def test_someone_new_is_notified_not_as_a_change(self):
        a = UserId(uuid4())

        avisos, fuera = cambios({}, {a: _salida(a)})

        assert [(s.user_id, s.changed) for s in avisos] == [(a, False)]
        assert fuera == []

    def test_nothing_changes_nobody_is_notified(self):
        a, b = _ids(2)

        avisos, fuera = cambios({a: _salida(a, con=[b])}, {a: _salida(a, con=[b])})

        assert (avisos, fuera) == ([], [])

    def test_another_hour_is_a_change(self):
        a = UserId(uuid4())

        avisos, _ = cambios({a: _salida(a)}, {a: _salida(a, hora=time(9, 10))})

        assert [(s.tee_time, s.changed) for s in avisos] == [(time(9, 10), True)]

    def test_other_partners_is_a_change(self):
        a, b, c = _ids(3)

        avisos, _ = cambios({a: _salida(a, con=[b])}, {a: _salida(a, con=[c])})

        assert [(s.partner_ids, s.changed) for s in avisos] == [((c,), True)]

    def test_other_rivals_is_a_change(self):
        a, b, c = _ids(3)

        avisos, _ = cambios({a: _salida(a, contra=[b])}, {a: _salida(a, contra=[c])})

        assert [(s.opponent_ids, s.changed) for s in avisos] == [((c,), True)]

    def test_another_day_is_a_change(self):
        a = UserId(uuid4())

        avisos, _ = cambios({a: _salida(a)}, {a: _salida(a, dia=date(2026, 10, 25))})

        assert [s.changed for s in avisos] == [True]

    def test_same_partners_in_another_order_is_not_a_change(self):
        a, b, c = _ids(3)

        avisos, _ = cambios({a: _salida(a, con=[b, c])}, {a: _salida(a, con=[c, b])})

        assert avisos == []

    def test_same_match_with_another_id_is_not_a_change(self):
        a, b = _ids(2)

        avisos, _ = cambios(
            {a: _salida(a, contra=[b], partido=MatchId.generate())},
            {a: _salida(a, contra=[b], partido=MatchId.generate())},
        )

        assert avisos == []

    def test_whoever_leaves_the_round_loses_the_notice(self):
        a, b = _ids(2)

        avisos, fuera = cambios({a: _salida(a), b: _salida(b)}, {b: _salida(b)})

        assert avisos == []
        assert fuera == [a]

    def test_only_who_changes_in_a_mixed_batch(self):
        quieto, cambia, nuevo, sale = _ids(4)

        avisos, fuera = cambios(
            {quieto: _salida(quieto), cambia: _salida(cambia), sale: _salida(sale)},
            {
                quieto: _salida(quieto),
                cambia: _salida(cambia, hora=time(9, 20)),
                nuevo: _salida(nuevo),
            },
        )

        assert {(s.user_id, s.changed) for s in avisos} == {(cambia, True), (nuevo, False)}
        assert fuera == [sale]
