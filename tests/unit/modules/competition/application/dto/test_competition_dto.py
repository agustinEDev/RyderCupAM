"""Tests para Competition DTOs."""

from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.modules.competition.application.dto.competition_dto import (
    ActivateCompetitionRequestDTO,
    CancelCompetitionRequestDTO,
    CloseEnrollmentsRequestDTO,
    CompleteCompetitionRequestDTO,
    CreateCompetitionRequestDTO,
    DeleteCompetitionRequestDTO,
    StartCompetitionRequestDTO,
    UpdateCompetitionRequestDTO,
)


class TestCreateCompetitionRequestDTO:
    """Tests para CreateCompetitionRequestDTO."""

    def test_create_with_valid_data(self):
        """Debe crear DTO con datos válidos."""
        dto = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
            max_players=24,
            team_assignment="MANUAL",
        )

        assert dto.name == "Ryder Cup 2025"
        assert dto.main_country == "ES"
        assert dto.play_mode == "SCRATCH"

    def test_uppercase_country_codes(self):
        """Debe convertir códigos de país a mayúsculas."""
        dto = CreateCompetitionRequestDTO(
            name="Test Cup",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="es",
            adjacent_country_1="pt",
            play_mode="SCRATCH",
        )

        assert dto.main_country == "ES"
        assert dto.adjacent_country_1 == "PT"

    def test_uppercase_play_mode(self):
        """Debe convertir play_mode a mayúsculas."""
        dto = CreateCompetitionRequestDTO(
            name="Test Cup",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            play_mode="scratch",
        )

        assert dto.play_mode == "SCRATCH"

    def test_handicap_play_mode(self):
        """Debe aceptar HANDICAP como play_mode válido."""
        dto = CreateCompetitionRequestDTO(
            name="Test Cup",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            play_mode="HANDICAP",
        )

        assert dto.play_mode == "HANDICAP"

    def test_start_date_must_be_before_end_date(self):
        """start_date debe ser anterior a end_date."""
        with pytest.raises(ValueError, match="start_date debe ser anterior a end_date"):
            CreateCompetitionRequestDTO(
                name="Test Cup",
                start_date=date(2025, 6, 3),
                end_date=date(2025, 6, 1),
                main_country="ES",
                play_mode="SCRATCH",
            )

    def test_invalid_play_mode(self):
        """Debe rechazar play_mode inválido."""
        with pytest.raises(ValueError, match="play_mode debe ser"):
            CreateCompetitionRequestDTO(
                name="Test Cup",
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 3),
                main_country="ES",
                play_mode="INVALID",
            )

    def test_invalid_team_assignment(self):
        """Debe rechazar team_assignment inválido."""
        with pytest.raises(ValueError, match="team_assignment debe ser"):
            CreateCompetitionRequestDTO(
                name="Test Cup",
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 3),
                main_country="ES",
                play_mode="SCRATCH",
                team_assignment="INVALID",
            )

    def test_name_too_short(self):
        """Debe rechazar nombre menor a 3 caracteres."""
        with pytest.raises(ValidationError):
            CreateCompetitionRequestDTO(
                name="RC",
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 3),
                main_country="ES",
                play_mode="SCRATCH",
            )

    def test_name_too_long(self):
        """Debe rechazar nombre mayor a 100 caracteres."""
        with pytest.raises(ValidationError):
            CreateCompetitionRequestDTO(
                name="A" * 101,
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 3),
                main_country="ES",
                play_mode="SCRATCH",
            )

    def test_max_players_below_minimum(self):
        """Debe rechazar max_players menor a 2."""
        with pytest.raises(ValidationError):
            CreateCompetitionRequestDTO(
                name="Test Cup",
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 3),
                main_country="ES",
                play_mode="SCRATCH",
                max_players=1,
            )

    def test_max_players_above_maximum(self):
        """Debe rechazar max_players mayor a 100."""
        with pytest.raises(ValidationError):
            CreateCompetitionRequestDTO(
                name="Test Cup",
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 3),
                main_country="ES",
                play_mode="SCRATCH",
                max_players=101,
            )


class TestUpdateCompetitionRequestDTO:
    """Tests para UpdateCompetitionRequestDTO."""

    def test_all_fields_optional(self):
        """Todos los campos deben ser opcionales."""
        dto = UpdateCompetitionRequestDTO()
        assert dto.name is None
        assert dto.start_date is None
        assert dto.play_mode is None

    def test_partial_update_name_only(self):
        """Debe permitir actualizar solo el nombre."""
        dto = UpdateCompetitionRequestDTO(name="New Name")
        assert dto.name == "New Name"
        assert dto.start_date is None

    def test_uppercase_conversions(self):
        """Debe convertir strings a mayúsculas."""
        dto = UpdateCompetitionRequestDTO(
            main_country="fr", play_mode="handicap", team_assignment="automatic"
        )

        assert dto.main_country == "FR"
        assert dto.play_mode == "HANDICAP"
        assert dto.team_assignment == "AUTOMATIC"


# ======================================================================================
# Tests para DTOs de Transiciones de Estado
# ======================================================================================


class TestActivateCompetitionRequestDTO:
    """Tests para ActivateCompetitionRequestDTO."""

    def test_create_with_valid_competition_id(self):
        """Debe crear DTO con competition_id válido."""
        comp_id = uuid4()
        dto = ActivateCompetitionRequestDTO(competition_id=comp_id)

        assert dto.competition_id == comp_id

    def test_competition_id_is_required(self):
        """competition_id es requerido."""
        with pytest.raises(ValidationError):
            ActivateCompetitionRequestDTO()


class TestCloseEnrollmentsRequestDTO:
    """Tests para CloseEnrollmentsRequestDTO."""

    def test_create_with_valid_competition_id(self):
        """Debe crear DTO con competition_id válido."""
        comp_id = uuid4()
        dto = CloseEnrollmentsRequestDTO(competition_id=comp_id)

        assert dto.competition_id == comp_id

    def test_competition_id_is_required(self):
        """competition_id es requerido."""
        with pytest.raises(ValidationError):
            CloseEnrollmentsRequestDTO()


class TestStartCompetitionRequestDTO:
    """Tests para StartCompetitionRequestDTO."""

    def test_create_with_valid_competition_id(self):
        """Debe crear DTO con competition_id válido."""
        comp_id = uuid4()
        dto = StartCompetitionRequestDTO(competition_id=comp_id)

        assert dto.competition_id == comp_id

    def test_competition_id_is_required(self):
        """competition_id es requerido."""
        with pytest.raises(ValidationError):
            StartCompetitionRequestDTO()


class TestCompleteCompetitionRequestDTO:
    """Tests para CompleteCompetitionRequestDTO."""

    def test_create_with_valid_competition_id(self):
        """Debe crear DTO con competition_id válido."""
        comp_id = uuid4()
        dto = CompleteCompetitionRequestDTO(competition_id=comp_id)

        assert dto.competition_id == comp_id

    def test_competition_id_is_required(self):
        """competition_id es requerido."""
        with pytest.raises(ValidationError):
            CompleteCompetitionRequestDTO()


# ======================================================================================
# Tests para DTOs de Delete y Cancel
# ======================================================================================


class TestDeleteCompetitionRequestDTO:
    """Tests para DeleteCompetitionRequestDTO."""

    def test_create_with_valid_competition_id(self):
        """Debe crear DTO con competition_id válido."""
        comp_id = uuid4()
        dto = DeleteCompetitionRequestDTO(competition_id=comp_id)

        assert dto.competition_id == comp_id

    def test_competition_id_is_required(self):
        """competition_id es requerido."""
        with pytest.raises(ValidationError):
            DeleteCompetitionRequestDTO()


class TestCancelCompetitionRequestDTO:
    """Tests para CancelCompetitionRequestDTO."""

    def test_create_with_competition_id_only(self):
        """Debe crear DTO solo con competition_id (reason opcional)."""
        comp_id = uuid4()
        dto = CancelCompetitionRequestDTO(competition_id=comp_id)

        assert dto.competition_id == comp_id
        assert dto.reason is None

    def test_create_with_reason(self):
        """Debe crear DTO con reason opcional."""
        comp_id = uuid4()
        dto = CancelCompetitionRequestDTO(competition_id=comp_id, reason="Mal tiempo")

        assert dto.competition_id == comp_id
        assert dto.reason == "Mal tiempo"

    def test_reason_max_length(self):
        """reason debe tener un máximo de 500 caracteres."""
        comp_id = uuid4()
        long_reason = "x" * 501

        with pytest.raises(ValidationError):
            CancelCompetitionRequestDTO(competition_id=comp_id, reason=long_reason)

    def test_reason_accepts_500_characters(self):
        """reason debe aceptar exactamente 500 caracteres."""
        comp_id = uuid4()
        valid_reason = "x" * 500

        dto = CancelCompetitionRequestDTO(competition_id=comp_id, reason=valid_reason)

        assert len(dto.reason) == 500

    def test_competition_id_is_required(self):
        """competition_id es requerido."""
        with pytest.raises(ValidationError):
            CancelCompetitionRequestDTO(reason="Test")
