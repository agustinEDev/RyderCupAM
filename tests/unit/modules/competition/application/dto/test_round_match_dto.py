"""Tests para Round/Match DTOs."""

from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.modules.competition.application.dto.round_match_dto import (
    AssignTeamsRequestDTO,
    ConfigureScheduleRequestDTO,
    CreateRoundRequestDTO,
    DeclareWalkoverRequestDTO,
    GenerateMatchesRequestDTO,
    ManualPairingDTO,
    ReassignMatchPlayersRequestDTO,
    UpdateMatchStatusRequestDTO,
    UpdateRoundRequestDTO,
)


class TestCreateRoundRequestDTO:
    """Tests para CreateRoundRequestDTO."""

    def test_create_round_with_valid_data(self):
        """Debe crear DTO con todos los campos requeridos y opcionales."""
        competition_id = uuid4()
        golf_course_id = uuid4()

        dto = CreateRoundRequestDTO(
            competition_id=competition_id,
            golf_course_id=golf_course_id,
            round_date=date(2026, 6, 15),
            session_type="MORNING",
            match_format="SINGLES",
            handicap_mode="MATCH_PLAY",
            allowance_percentage=95,
        )

        assert dto.competition_id == competition_id
        assert dto.golf_course_id == golf_course_id
        assert dto.round_date == date(2026, 6, 15)
        assert dto.session_type == "MORNING"
        assert dto.match_format == "SINGLES"
        assert dto.handicap_mode == "MATCH_PLAY"
        assert dto.allowance_percentage == 95

    def test_create_round_uppercase_session_type(self):
        """Debe convertir session_type a mayusculas."""
        dto = CreateRoundRequestDTO(
            competition_id=uuid4(),
            golf_course_id=uuid4(),
            round_date=date(2026, 6, 15),
            session_type="morning",
            match_format="SINGLES",
        )

        assert dto.session_type == "MORNING"

    def test_create_round_uppercase_match_format(self):
        """Debe convertir match_format a mayusculas."""
        dto = CreateRoundRequestDTO(
            competition_id=uuid4(),
            golf_course_id=uuid4(),
            round_date=date(2026, 6, 15),
            session_type="MORNING",
            match_format="fourball",
        )

        assert dto.match_format == "FOURBALL"

    def test_create_round_uppercase_handicap_mode(self):
        """Debe convertir handicap_mode a mayusculas."""
        dto = CreateRoundRequestDTO(
            competition_id=uuid4(),
            golf_course_id=uuid4(),
            round_date=date(2026, 6, 15),
            session_type="MORNING",
            match_format="SINGLES",
            handicap_mode="  match_play  ",
        )

        assert dto.handicap_mode == "MATCH_PLAY"


class TestUpdateRoundRequestDTO:
    """Tests para UpdateRoundRequestDTO."""

    def test_update_round_optional_fields(self):
        """Debe permitir todos los campos opcionales como None excepto round_id."""
        round_id = uuid4()

        dto = UpdateRoundRequestDTO(round_id=round_id)

        assert dto.round_id == round_id
        assert dto.round_date is None
        assert dto.session_type is None
        assert dto.golf_course_id is None
        assert dto.match_format is None
        assert dto.handicap_mode is None
        assert dto.allowance_percentage is None
        assert dto.clear_allowance is False


class TestAssignTeamsRequestDTO:
    """Tests para AssignTeamsRequestDTO."""

    def test_assign_teams_uppercase_mode(self):
        """Debe convertir mode a mayusculas."""
        dto = AssignTeamsRequestDTO(
            competition_id=uuid4(),
            mode="automatic",
        )

        assert dto.mode == "AUTOMATIC"


class TestConfigureScheduleRequestDTO:
    """Tests para ConfigureScheduleRequestDTO."""

    def test_configure_schedule_valid_boundaries(self):
        """Debe aceptar valores en los limites de total_sessions y sessions_per_day."""
        dto = ConfigureScheduleRequestDTO(
            competition_id=uuid4(),
            mode="AUTOMATIC",
            total_sessions=18,
            sessions_per_day=3,
        )

        assert dto.total_sessions == 18
        assert dto.sessions_per_day == 3
        assert dto.mode == "AUTOMATIC"

        # Test minimum boundaries
        dto_min = ConfigureScheduleRequestDTO(
            competition_id=uuid4(),
            mode="AUTOMATIC",
            total_sessions=1,
            sessions_per_day=1,
        )

        assert dto_min.total_sessions == 1
        assert dto_min.sessions_per_day == 1

    def test_configure_schedule_invalid_sessions(self):
        """Debe rechazar sessions_per_day mayor a 3."""
        with pytest.raises(ValidationError) as exc_info:
            ConfigureScheduleRequestDTO(
                competition_id=uuid4(),
                mode="AUTOMATIC",
                total_sessions=6,
                sessions_per_day=4,
            )

        errors = exc_info.value.errors()
        assert any(
            e["loc"] == ("sessions_per_day",) and e["type"] == "less_than_equal" for e in errors
        )


class TestUpdateMatchStatusRequestDTO:
    """Tests para UpdateMatchStatusRequestDTO."""

    def test_update_match_status_uppercase_action(self):
        """Debe convertir action a mayusculas."""
        dto = UpdateMatchStatusRequestDTO(
            match_id=uuid4(),
            action="  start  ",
        )

        assert dto.action == "START"


class TestDeclareWalkoverRequestDTO:
    """Tests para DeclareWalkoverRequestDTO."""

    def test_declare_walkover_uppercase_winning_team(self):
        """Debe convertir winning_team a mayusculas."""
        dto = DeclareWalkoverRequestDTO(
            match_id=uuid4(),
            winning_team="a",
            reason="Player injury",
        )

        assert dto.winning_team == "A"
        assert dto.reason == "Player injury"


class TestGenerateMatchesRequestDTO:
    """Tests para GenerateMatchesRequestDTO."""

    def test_generate_matches_with_manual_pairings(self):
        """Debe aceptar emparejamientos manuales opcionales."""
        round_id = uuid4()
        player_a1, player_a2 = uuid4(), uuid4()
        player_b1, player_b2 = uuid4(), uuid4()

        dto = GenerateMatchesRequestDTO(
            round_id=round_id,
            manual_pairings=[
                ManualPairingDTO(
                    team_a_player_ids=[player_a1],
                    team_b_player_ids=[player_b1],
                ),
                ManualPairingDTO(
                    team_a_player_ids=[player_a2],
                    team_b_player_ids=[player_b2],
                ),
            ],
        )

        assert dto.round_id == round_id
        assert len(dto.manual_pairings) == 2
        assert dto.manual_pairings[0].team_a_player_ids == [player_a1]
        assert dto.manual_pairings[0].team_b_player_ids == [player_b1]
        assert dto.manual_pairings[1].team_a_player_ids == [player_a2]
        assert dto.manual_pairings[1].team_b_player_ids == [player_b2]


class TestReassignMatchPlayersRequestDTO:
    """Tests para ReassignMatchPlayersRequestDTO."""

    def test_reassign_match_players_required_fields(self):
        """Debe requerir match_id, team_a_player_ids y team_b_player_ids."""
        match_id = uuid4()
        player_a = uuid4()
        player_b = uuid4()

        dto = ReassignMatchPlayersRequestDTO(
            match_id=match_id,
            team_a_player_ids=[player_a],
            team_b_player_ids=[player_b],
        )

        assert dto.match_id == match_id
        assert dto.team_a_player_ids == [player_a]
        assert dto.team_b_player_ids == [player_b]

        # Verify that omitting required fields raises ValidationError
        with pytest.raises(ValidationError) as exc_info:
            ReassignMatchPlayersRequestDTO(match_id=match_id)

        errors = exc_info.value.errors()
        missing_fields = {e["loc"][0] for e in errors if e["type"] == "missing"}
        assert "team_a_player_ids" in missing_fields
        assert "team_b_player_ids" in missing_fields
