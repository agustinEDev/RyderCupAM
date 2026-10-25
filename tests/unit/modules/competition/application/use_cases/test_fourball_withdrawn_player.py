"""
Fourball de torneo con un jugador retirado: los casos de uso (25 oct 2026).

| #    | caso                                                       | esperado                         |
|------|------------------------------------------------------------|----------------------------------|
| W1   | se retira él mismo, su pareja, el organizador o un admin   | queda retirado                   |
| W1b  | un rival o alguien de fuera                                | NotMatchPlayerError (403)        |
| W1c  | una regla del dominio (individual, el último del bando...)  | WithdrawalNotAllowedError (409)  |
| W5   | deshacer, las mismas personas                              | vuelve a jugar                   |
| W9   | al retirar o deshacer, la decisión del partido             | se recalcula                     |
| W19  | el retirado intenta anotar su bola o entregar              | PlayerWithdrawnError             |
| W19b | y si lo retiran mientras su golpe espera el bloqueo        | PlayerWithdrawnError             |
| W20  | el retirado intenta conceder por su bando                  | NotMatchPlayerError (403)        |
| W10  | su pareja anota al rival que él marcaba                    | se acepta                        |
| W12  | entregan los otros tres                                    | el partido se cierra             |
| W13  | la clasificación                                           | usa la misma regla               |
| W18  | la vista de anotar: retirados, marcadores efectivos y hoyos | con la regla nueva               |
"""

import copy
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.competition.application.dto.scoring_dto import SubmitHoleScoreBodyDTO
from src.modules.competition.application.exceptions import (
    NotMatchPlayerError,
    PlayerWithdrawnError,
    WithdrawalNotAllowedError,
)
from src.modules.competition.application.use_cases.concede_match_use_case import (
    ConcedeMatchUseCase,
)
from src.modules.competition.application.use_cases.get_leaderboard_use_case import (
    GetLeaderboardUseCase,
)
from src.modules.competition.application.use_cases.get_scoring_view_use_case import (
    GetScoringViewUseCase,
)
from src.modules.competition.application.use_cases.submit_hole_score_use_case import (
    SubmitHoleScoreUseCase,
)
from src.modules.competition.application.use_cases.submit_scorecard_use_case import (
    SubmitScorecardUseCase,
)
from src.modules.competition.application.use_cases.withdraw_match_player_use_case import (
    WithdrawMatchPlayerUseCase,
)
from src.modules.competition.domain.entities.hole_score import HoleScore
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.match_format import MatchFormat

F = MatchFormat.FOURBALL
CREADOR = UserId.generate()


def _jugador() -> MatchPlayer:
    return MatchPlayer.create(
        user_id=UserId.generate(),
        playing_handicap=0,
        tee_color=TeeColor.YELLOW,
        strokes_received=[],
    )


class _Escena:
    """Un fourball en juego, con su sesión y su competición en el UoW en memoria."""

    def __init__(self, formato: MatchFormat = F):
        self.uow = InMemoryUnitOfWork()
        self.ronda = MagicMock()
        self.ronda.id = RoundId.generate()
        self.ronda.match_format = formato
        self.ronda.status = RoundStatus.IN_PROGRESS
        self.ronda.competition_id = MagicMock()
        self.ronda.golf_course_id = GolfCourseId.generate()
        # La vista de anotar, que devuelve el golpe, pinta la fecha y la sesion
        self.ronda.round_date = None
        self.ronda.session_type = MagicMock(value="MORNING")
        self.uow._rounds._rounds[self.ronda.id] = self.ronda
        competicion = MagicMock()
        competicion.is_creator = lambda uid: uid == CREADOR
        competicion.require_ryder_cup.return_value = MagicMock(
            team_1_name="Europa", team_2_name="América"
        )
        self.uow.competitions.find_by_id = AsyncMock(return_value=competicion)
        por_bando = 1 if formato == MatchFormat.SINGLES else 2
        self.match = Match.create(
            round_id=self.ronda.id,
            match_number=1,
            team_a_players=[_jugador() for _ in range(por_bando)],
            team_b_players=[_jugador() for _ in range(por_bando)],
        )
        self.match.set_marker_assignments(
            ScoringService().generate_marker_assignments(
                self.match.team_a_players, self.match.team_b_players, formato
            )
        )
        self.match.start()

    @property
    def a1(self) -> UserId:
        return self.match.team_a_players[0].user_id

    @property
    def a2(self) -> UserId:
        return self.match.team_a_players[1].user_id

    @property
    def b1(self) -> UserId:
        return self.match.team_b_players[0].user_id

    async def guardar(self, filas=()):
        await self.uow.matches.add(self.match)
        for fila in filas:
            await self.uow.hole_scores.add(fila)

    async def retirar(self, quien, actor, *, admin=False, deshacer=False):
        caso = WithdrawMatchPlayerUseCase(self.uow, ScoringService())
        return await caso.execute(
            str(self.match.id), actor, str(quien), is_admin=admin, undo=deshacer
        )

    async def partido(self) -> Match:
        return await self.uow.matches.find_by_id(self.match.id)


def _fila(match, hoyo, jugador, team, golpes, validada=True):
    fila = HoleScore.create(
        match_id=match.id, hole_number=hoyo, player_user_id=jugador, team=team, strokes_received=0
    )
    if validada:
        fila.set_own_score(golpes)
        fila.set_marker_score(golpes)
    fila.recalculate_validation()
    return fila


def _diez_hoyos_para_b_sin_la_bola_de_a1(e: _Escena) -> list[HoleScore]:
    """Del 1 al 10: A1 sin anotar, A2 hace 5, B gana con 4. Con A1 fuera, 10&8 para B."""
    filas = []
    for hoyo in range(1, 11):
        filas += [
            _fila(e.match, hoyo, e.a1, "A", None, validada=False),
            _fila(e.match, hoyo, e.a2, "A", 5),
            _fila(e.match, hoyo, e.b1, "B", 4),
            _fila(e.match, hoyo, e.match.team_b_players[1].user_id, "B", 6),
        ]
    return filas


class TestQuienPuede:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("actor", ["el_mismo", "su_pareja", "organizador", "admin"])
    async def test_w1_who_can_withdraw_him(self, actor):
        e = _Escena()
        await e.guardar()
        quien = {
            "el_mismo": e.a1,
            "su_pareja": e.a2,
            "organizador": CREADOR,
            "admin": UserId.generate(),
        }

        await e.retirar(e.a1, quien[actor], admin=actor == "admin")

        assert (await e.partido()).withdrawn_player_ids == (e.a1,)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("actor", ["rival", "de_fuera"])
    async def test_w1b_a_rival_or_an_outsider_cannot(self, actor):
        e = _Escena()
        await e.guardar()
        quien = e.b1 if actor == "rival" else UserId.generate()

        with pytest.raises(NotMatchPlayerError):
            await e.retirar(e.a1, quien)
        assert (await e.partido()).withdrawn_player_ids == ()

    @pytest.mark.asyncio
    async def test_w1c_a_domain_rule_is_a_409_not_a_500(self):
        e = _Escena(MatchFormat.SINGLES)
        await e.guardar()

        with pytest.raises(WithdrawalNotAllowedError):
            await e.retirar(e.a1, e.a1)

    @pytest.mark.asyncio
    async def test_w5_the_same_people_can_undo_it(self):
        e = _Escena()
        await e.guardar()
        await e.retirar(e.a1, e.a2)

        await e.retirar(e.a1, e.a1, deshacer=True)

        assert (await e.partido()).withdrawn_player_ids == ()

    @pytest.mark.asyncio
    async def test_w5b_a_rival_cannot_undo_it(self):
        e = _Escena()
        await e.guardar()
        await e.retirar(e.a1, e.a2)

        with pytest.raises(NotMatchPlayerError):
            await e.retirar(e.a1, e.b1, deshacer=True)


class TestLaDecision:
    @pytest.mark.asyncio
    async def test_w9_withdrawing_decides_it_and_undoing_keeps_what_closed(self):
        """
        Given diez hoyos que solo esperaban su bola / When se le retira / Then
        10&8; y al deshacer, esos diez se quedan cerrados sin él (code-review:
        antes volvían a esperarle y el partido se atascaba).
        """
        e = _Escena()
        await e.guardar(_diez_hoyos_para_b_sin_la_bola_de_a1(e))
        assert (await e.partido()).is_decided is False

        await e.retirar(e.a1, e.a2)
        decidido = await e.partido()
        assert decidido.decided_result == {"winner": "B", "score": "10&8"}

        respuesta = await e.retirar(e.a1, e.a2, deshacer=True)
        vuelto = await e.partido()
        assert vuelto.withdrawn_player_ids == ()
        assert vuelto.holes_without_ball == {e.a1: tuple(range(1, 11))}
        assert vuelto.decided_result == {"winner": "B", "score": "10&8"}
        assert respuesta.decided_result.score == "10&8"

    @pytest.mark.asyncio
    async def test_w9d_undoing_brings_his_ball_back_where_nothing_closed(self):
        """Given un hoyo abierto también por otra bola / When vuelve / Then ahí su bola cuenta otra vez."""
        e = _Escena()
        b2 = e.match.team_b_players[1].user_id
        await e.guardar(
            [
                _fila(e.match, 1, e.a1, "A", None, validada=False),
                _fila(e.match, 1, e.a2, "A", 5),
                _fila(e.match, 1, e.b1, "B", 4),
                _fila(e.match, 1, b2, "B", None, validada=False),
            ]
        )
        await e.retirar(e.a1, e.a2)

        await e.retirar(e.a1, e.a2, deshacer=True)

        assert (await e.partido()).holes_without_ball == {}

    @pytest.mark.asyncio
    async def test_w9b_scoring_a_hole_keeps_the_withdrawn_player_out(self):
        e = _Escena()
        filas = _diez_hoyos_para_b_sin_la_bola_de_a1(e)
        e.match.withdraw_player(e.a1, F)
        await e.guardar(filas)

        await SubmitHoleScoreUseCase(e.uow, AsyncMock(), ScoringService())._check_decided(
            e.match, e.match.id, F
        )

        assert e.match.decided_result == {"winner": "B", "score": "10&8"}

    @pytest.mark.asyncio
    async def test_w13_the_leaderboard_follows_the_same_rule(self):
        e = _Escena()
        filas = _diez_hoyos_para_b_sin_la_bola_de_a1(e)
        e.match.withdraw_player(e.a1, F)
        await e.guardar(filas)

        resultado = await GetLeaderboardUseCase(
            e.uow, MagicMock(), ScoringService()
        )._compute_decided_result(e.match, F)

        assert resultado == {"winner": "B", "score": "10&8"}

    @pytest.mark.asyncio
    async def test_w13b_the_live_leaderboard_too(self):
        """Given A1 retirado y diez hoyos para B sin su bola / Then la clasificación en juego, B 10 arriba."""
        e = _Escena()
        filas = _diez_hoyos_para_b_sin_la_bola_de_a1(e)
        e.match.withdraw_player(e.a1, F)
        await e.guardar(filas)

        estado = await GetLeaderboardUseCase(
            e.uow, MagicMock(), ScoringService()
        )._compute_in_progress_standing(e.match, e.ronda)

        assert estado[1] == "B"
        assert estado[2] == 10


class TestAnotarYEntregar:
    def _usuarios(self):
        repo = AsyncMock()
        usuario = MagicMock()
        usuario.display_name = "Jugador"
        usuario.display_name_or_legal = MagicMock(return_value="Jugador")
        repo.find_by_id = AsyncMock(return_value=usuario)
        return repo

    @pytest.mark.asyncio
    async def test_w19_the_withdrawn_player_cannot_score_his_ball(self):
        e = _Escena()
        e.match.withdraw_player(e.a1, F)
        await e.guardar()
        rival = next(
            a.marks_user_id for a in e.match.marker_assignments if a.scorer_user_id == e.a1
        )
        body = SubmitHoleScoreBodyDTO(own_score=4, marked_player_id=str(rival), marked_score=4)

        with pytest.raises(PlayerWithdrawnError):
            await SubmitHoleScoreUseCase(e.uow, self._usuarios(), ScoringService()).execute(
                str(e.match.id), 1, body, e.a1
            )

    @pytest.mark.asyncio
    async def test_w19c_withdrawn_while_his_hole_waited_for_the_lock(self):
        """
        Revisor sin contexto: el golpe leía el partido sin bloquear, su pareja lo
        retiraba entretanto y al entrar guardaba su bola. Se vuelve a mirar tras
        el bloqueo.
        """
        e = _Escena()
        await e.guardar()
        antes = copy.deepcopy(e.match)
        e.match.withdraw_player(e.a1, F)
        e.uow.matches.find_by_id = AsyncMock(return_value=antes)
        rival = next(
            a.marks_user_id for a in e.match.marker_assignments if a.scorer_user_id == e.a1
        )
        body = SubmitHoleScoreBodyDTO(own_score=4, marked_player_id=str(rival), marked_score=4)

        with pytest.raises(PlayerWithdrawnError):
            await SubmitHoleScoreUseCase(e.uow, self._usuarios(), ScoringService()).execute(
                str(e.match.id), 1, body, e.a1
            )

    @pytest.mark.asyncio
    async def test_w20_the_withdrawn_player_cannot_concede_his_partner_can(self):
        """Decidido el 25 oct 2026: retirado ya no decide por el bando; su pareja sí."""
        e = _Escena()
        e.match.withdraw_player(e.a1, F)
        await e.guardar()
        caso = ConcedeMatchUseCase(e.uow, ScoringService())

        with pytest.raises(NotMatchPlayerError):
            await caso.execute(str(e.match.id), e.a1, "A")
        await caso.execute(str(e.match.id), e.a2, "A")

        assert (await e.partido()).status.value == "CONCEDED"

    @pytest.mark.asyncio
    async def test_w19b_nor_hand_in_a_scorecard(self):
        e = _Escena()
        e.match.withdraw_player(e.a1, F)
        await e.guardar()

        with pytest.raises(PlayerWithdrawnError):
            await SubmitScorecardUseCase(e.uow, ScoringService()).execute(str(e.match.id), e.a1)

    @pytest.mark.asyncio
    async def test_w10_his_partner_scores_the_rival_he_marked(self):
        e = _Escena()
        e.match.withdraw_player(e.a1, F)
        # Las filas del hoyo, como las crea quien abre el partido
        await e.guardar(
            [
                HoleScore.create(
                    match_id=e.match.id,
                    hole_number=1,
                    player_user_id=p.user_id,
                    team=equipo,
                    strokes_received=0,
                )
                for equipo, bando in (("A", e.match.team_a_players), ("B", e.match.team_b_players))
                for p in bando
            ]
        )
        rival = next(
            a.marks_user_id for a in e.match.marker_assignments if a.scorer_user_id == e.a1
        )
        body = SubmitHoleScoreBodyDTO(marked_player_id=str(rival), marked_score=4)

        await SubmitHoleScoreUseCase(e.uow, self._usuarios(), ScoringService()).execute(
            str(e.match.id), 1, body, e.a2
        )

        fila = await e.uow.hole_scores.find_one(e.match.id, 1, rival)
        assert fila.marker_score == 4

    @pytest.mark.asyncio
    async def test_w12b_the_result_leaves_his_unvalidated_ball_out(self):
        """Tres hoyos con B delante y la bola de A1 sin validar: con A1 fuera, «3UP» para B."""
        e = _Escena()
        filas = [f for f in _diez_hoyos_para_b_sin_la_bola_de_a1(e) if f.hole_number <= 3]
        e.match.withdraw_player(e.a1, F)
        await e.guardar(filas)

        respuesta = await SubmitScorecardUseCase(e.uow, ScoringService()).execute(
            str(e.match.id), e.b1
        )

        assert (respuesta.result.winner, respuesta.result.score) == ("B", "3UP")

    @pytest.mark.asyncio
    async def test_w12_the_other_three_close_the_match(self):
        e = _Escena()
        e.match.withdraw_player(e.a1, F)
        await e.guardar()
        caso = SubmitScorecardUseCase(e.uow, ScoringService())

        respuestas = [
            await caso.execute(str(e.match.id), jugador)
            for jugador in (e.a2, e.b1, e.match.team_b_players[1].user_id)
        ]

        assert [r.match_complete for r in respuestas] == [False, False, True]


class TestLaVistaDeAnotar:
    @pytest.mark.asyncio
    async def test_w18_the_view_shows_the_withdrawn_and_who_marks_whom_now(self):
        e = _Escena()
        filas = _diez_hoyos_para_b_sin_la_bola_de_a1(e)
        e.match.withdraw_player(e.a1, F)
        await e.guardar(filas)
        rival = next(
            a.marks_user_id for a in e.match.marker_assignments if a.scorer_user_id == e.a1
        )

        vista = await GetScoringViewUseCase(
            e.uow, TestAnotarYEntregar()._usuarios(), ScoringService()
        ).execute(str(e.match.id))

        assert vista.withdrawn_player_ids == [str(e.a1)]
        marca_a2 = {
            m.marks_user_id for m in vista.marker_assignments if m.scorer_user_id == str(e.a2)
        }
        assert str(rival) in marca_a2
        assert all(m.marks_user_id != str(e.a1) for m in vista.marker_assignments)
        assert all(m.scorer_user_id != str(e.a1) for m in vista.marker_assignments)
        # Los diez hoyos cerrados sin su bola: 10 arriba para B
        assert vista.match_standing.leading_team == "B"
        assert vista.match_standing.holes_played == 10
        assert all(s.hole_result is not None for s in vista.scores if s.hole_number <= 10)
