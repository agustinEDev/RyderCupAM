"""
Cambiar a un jugador de equipo sin deshacer el reparto (release social 3, T1-T4, 28 oct 2026).
"""

from datetime import datetime
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.envelope import Envelope
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.match_format import MatchFormat


def _reparto():
    a = [UserId(uuid4()) for _ in range(2)]
    b = [UserId(uuid4()) for _ in range(2)]
    return (
        TeamAssignment.create(
            competition_id=CompetitionId(uuid4()),
            mode=TeamAssignmentMode.MANUAL,
            team_a_player_ids=a,
            team_b_player_ids=b,
        ),
        a,
        b,
    )


class TestElReparto:
    def test_quitar_a_uno_le_saca_de_su_equipo_y_deja_a_los_demas(self):
        reparto, a, b = _reparto()

        assert reparto.quitar(a[0]) is True

        assert reparto.team_a_player_ids == (a[1],)
        assert reparto.team_b_player_ids == tuple(b)

    def test_quitar_a_quien_no_esta_no_cambia_nada(self):
        reparto, a, _ = _reparto()

        assert reparto.quitar(UserId(uuid4())) is False

        assert reparto.team_a_player_ids == tuple(a)

    def test_poner_a_uno_sin_equipo_al_final_del_suyo(self):
        reparto, _, b = _reparto()
        nuevo = UserId(uuid4())

        reparto.poner(nuevo, "B")

        assert reparto.team_b_player_ids == (*b, nuevo)

    def test_poner_a_uno_del_otro_equipo_le_mueve(self):
        reparto, a, b = _reparto()

        reparto.poner(a[0], "B")

        assert reparto.team_a_player_ids == (a[1],)
        assert reparto.team_b_player_ids == (*b, a[0])

    def test_poner_en_un_equipo_que_no_existe(self):
        reparto, a, _ = _reparto()

        with pytest.raises(ValueError):
            reparto.poner(a[0], "C")


class TestElSobre:
    def _entregado(self):
        jugadores = [UserId(uuid4()) for _ in range(2)]
        sobre = Envelope.create(
            CompetitionId(uuid4()), RoundId.generate(), "A", MatchFormat.SINGLES
        )
        sobre.submit([[j] for j in jugadores], jugadores, jugadores[0], datetime.now())
        return sobre

    def test_reabrir_un_entregado_lo_vacia(self):
        sobre = self._entregado()

        assert sobre.reabrir() is True

        assert sobre.is_submitted() is False
        assert sobre.submitted_at is None
        assert sobre.submitted_by is None
        assert sobre.is_sealed() is True

    def test_reabrir_uno_abierto_tambien(self):
        sobre = self._entregado()
        sobre.reveal()

        assert sobre.reabrir() is True

        assert sobre.is_sealed() is True

    def test_reabrir_uno_vacio_no_cambia_nada(self):
        sobre = Envelope.create(
            CompetitionId(uuid4()), RoundId.generate(), "A", MatchFormat.SINGLES
        )

        assert sobre.reabrir() is False
