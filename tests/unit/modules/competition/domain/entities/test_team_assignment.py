"""Tests para TeamAssignment entity."""

from datetime import datetime

import pytest

from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.team_assignment_id import (
    TeamAssignmentId,
)
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.user.domain.value_objects.user_id import UserId


class TestTeamAssignmentCreate:
    """Tests para creación de TeamAssignment"""

    def test_create_with_valid_data(self):
        """Crea asignación con datos válidos."""
        competition_id = CompetitionId.generate()
        team_a = [UserId.generate(), UserId.generate()]
        team_b = [UserId.generate(), UserId.generate()]

        assignment = TeamAssignment.create(
            competition_id=competition_id,
            mode=TeamAssignmentMode.AUTOMATIC,
            team_a_player_ids=team_a,
            team_b_player_ids=team_b,
        )

        assert assignment.id is not None
        assert assignment.competition_id == competition_id
        assert assignment.mode == TeamAssignmentMode.AUTOMATIC
        assert len(assignment.team_a_player_ids) == 2
        assert len(assignment.team_b_player_ids) == 2

    def test_create_with_manual_mode(self):
        """Crea asignación manual."""
        assignment = TeamAssignment.create(
            competition_id=CompetitionId.generate(),
            mode=TeamAssignmentMode.MANUAL,
            team_a_player_ids=[UserId.generate()],
            team_b_player_ids=[UserId.generate()],
        )

        assert assignment.mode == TeamAssignmentMode.MANUAL

    def test_create_with_unbalanced_teams_raises(self):
        """Error si equipos no tienen mismo número de jugadores."""
        with pytest.raises(ValueError, match="Teams must have equal players"):
            TeamAssignment.create(
                competition_id=CompetitionId.generate(),
                mode=TeamAssignmentMode.AUTOMATIC,
                team_a_player_ids=[UserId.generate(), UserId.generate()],
                team_b_player_ids=[UserId.generate()],
            )

    def test_create_with_empty_teams_raises(self):
        """Error si equipos están vacíos."""
        with pytest.raises(ValueError, match="must have at least one player"):
            TeamAssignment.create(
                competition_id=CompetitionId.generate(),
                mode=TeamAssignmentMode.AUTOMATIC,
                team_a_player_ids=[],
                team_b_player_ids=[],
            )

    def test_create_with_player_in_both_teams_raises(self):
        """Error si jugador está en ambos equipos."""
        player_id = UserId.generate()

        with pytest.raises(ValueError, match="cannot be in both teams"):
            TeamAssignment.create(
                competition_id=CompetitionId.generate(),
                mode=TeamAssignmentMode.AUTOMATIC,
                team_a_player_ids=[player_id],
                team_b_player_ids=[player_id],
            )

    def test_create_with_duplicate_in_team_raises(self):
        """Error si hay duplicados dentro del mismo equipo."""
        player_id = UserId.generate()

        with pytest.raises(ValueError, match="Duplicate players"):
            TeamAssignment.create(
                competition_id=CompetitionId.generate(),
                mode=TeamAssignmentMode.AUTOMATIC,
                team_a_player_ids=[player_id, player_id],
                team_b_player_ids=[UserId.generate(), UserId.generate()],
            )


class TestTeamAssignmentReconstruct:
    """Tests para reconstrucción de TeamAssignment"""

    def test_reconstruct_from_db(self):
        """Reconstruye asignación desde BD."""
        assignment_id = TeamAssignmentId.generate()
        competition_id = CompetitionId.generate()
        created = datetime(2026, 1, 1, 10, 0)

        assignment = TeamAssignment.reconstruct(
            id=assignment_id,
            competition_id=competition_id,
            mode=TeamAssignmentMode.MANUAL,
            team_a_player_ids=[UserId.generate()],
            team_b_player_ids=[UserId.generate()],
            created_at=created,
        )

        assert assignment.id == assignment_id
        assert assignment.created_at == created


class TestTeamAssignmentQueryMethods:
    """Tests para métodos de consulta"""

    def test_is_player_in_team_a(self):
        """Verifica si jugador está en Equipo A."""
        player_a = UserId.generate()
        player_b = UserId.generate()

        assignment = TeamAssignment.create(
            competition_id=CompetitionId.generate(),
            mode=TeamAssignmentMode.AUTOMATIC,
            team_a_player_ids=[player_a],
            team_b_player_ids=[player_b],
        )

        assert assignment.is_player_in_team_a(player_a) is True
        assert assignment.is_player_in_team_a(player_b) is False

    def test_is_player_in_team_b(self):
        """Verifica si jugador está en Equipo B."""
        player_a = UserId.generate()
        player_b = UserId.generate()

        assignment = TeamAssignment.create(
            competition_id=CompetitionId.generate(),
            mode=TeamAssignmentMode.AUTOMATIC,
            team_a_player_ids=[player_a],
            team_b_player_ids=[player_b],
        )

        assert assignment.is_player_in_team_b(player_b) is True
        assert assignment.is_player_in_team_b(player_a) is False

    def test_get_player_team(self):
        """Obtiene equipo de un jugador."""
        player_a = UserId.generate()
        player_b = UserId.generate()
        other = UserId.generate()

        assignment = TeamAssignment.create(
            competition_id=CompetitionId.generate(),
            mode=TeamAssignmentMode.AUTOMATIC,
            team_a_player_ids=[player_a],
            team_b_player_ids=[player_b],
        )

        assert assignment.get_player_team(player_a) == "A"
        assert assignment.get_player_team(player_b) == "B"
        assert assignment.get_player_team(other) is None

    def test_total_players(self):
        """Retorna total de jugadores asignados."""
        assignment = TeamAssignment.create(
            competition_id=CompetitionId.generate(),
            mode=TeamAssignmentMode.AUTOMATIC,
            team_a_player_ids=[UserId.generate(), UserId.generate(), UserId.generate()],
            team_b_player_ids=[UserId.generate(), UserId.generate(), UserId.generate()],
        )

        assert assignment.total_players() == 6

    def test_players_per_team(self):
        """Retorna jugadores por equipo."""
        assignment = TeamAssignment.create(
            competition_id=CompetitionId.generate(),
            mode=TeamAssignmentMode.AUTOMATIC,
            team_a_player_ids=[UserId.generate(), UserId.generate()],
            team_b_player_ids=[UserId.generate(), UserId.generate()],
        )

        assert assignment.players_per_team() == 2


class TestTeamAssignmentEquality:
    """Tests para igualdad y hash"""

    def test_assignments_with_same_id_are_equal(self):
        """Asignaciones con mismo ID son iguales."""
        assignment_id = TeamAssignmentId.generate()
        now = datetime.now()

        assignment1 = TeamAssignment.reconstruct(
            id=assignment_id,
            competition_id=CompetitionId.generate(),
            mode=TeamAssignmentMode.AUTOMATIC,
            team_a_player_ids=[UserId.generate()],
            team_b_player_ids=[UserId.generate()],
            created_at=now,
        )
        assignment2 = TeamAssignment.reconstruct(
            id=assignment_id,
            competition_id=CompetitionId.generate(),
            mode=TeamAssignmentMode.MANUAL,
            team_a_player_ids=[UserId.generate()],
            team_b_player_ids=[UserId.generate()],
            created_at=now,
        )

        assert assignment1 == assignment2

    def test_assignment_can_be_used_in_set(self):
        """TeamAssignment puede usarse en set."""
        assignment = TeamAssignment.create(
            competition_id=CompetitionId.generate(),
            mode=TeamAssignmentMode.AUTOMATIC,
            team_a_player_ids=[UserId.generate()],
            team_b_player_ids=[UserId.generate()],
        )

        assignment_set = {assignment}
        assert assignment in assignment_set
