# -*- coding: utf-8 -*-
"""Tests para Competition DTOs."""

import pytest
from datetime import date, datetime
from uuid import uuid4
from pydantic import ValidationError
from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
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
            handicap_type="SCRATCH",
            max_players=24,
            team_assignment="MANUAL"
        )

        assert dto.name == "Ryder Cup 2025"
        assert dto.main_country == "ES"
        assert dto.handicap_type == "SCRATCH"

    def test_uppercase_country_codes(self):
        """Debe convertir códigos de país a mayúsculas."""
        dto = CreateCompetitionRequestDTO(
            name="Test Cup",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="es",
            adjacent_country_1="pt",
            handicap_type="SCRATCH"
        )

        assert dto.main_country == "ES"
        assert dto.adjacent_country_1 == "PT"

    def test_uppercase_handicap_type(self):
        """Debe convertir handicap_type a mayúsculas."""
        dto = CreateCompetitionRequestDTO(
            name="Test Cup",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="scratch"
        )

        assert dto.handicap_type == "SCRATCH"

    def test_percentage_requires_percentage_value(self):
        """Si handicap_type es PERCENTAGE, handicap_percentage es requerido."""
        with pytest.raises(ValueError, match="handicap_percentage es requerido"):
            CreateCompetitionRequestDTO(
                name="Test Cup",
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 3),
                main_country="ES",
                handicap_type="PERCENTAGE"
            )

    def test_percentage_with_valid_percentage(self):
        """Debe aceptar PERCENTAGE con porcentaje válido."""
        dto = CreateCompetitionRequestDTO(
            name="Test Cup",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="PERCENTAGE",
            handicap_percentage=90
        )

        assert dto.handicap_type == "PERCENTAGE"
        assert dto.handicap_percentage == 90

    def test_scratch_cannot_have_percentage(self):
        """Si handicap_type es SCRATCH, handicap_percentage debe ser None."""
        with pytest.raises(ValueError, match="handicap_percentage debe ser None"):
            CreateCompetitionRequestDTO(
                name="Test Cup",
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 3),
                main_country="ES",
                handicap_type="SCRATCH",
                handicap_percentage=90
            )

    def test_start_date_must_be_before_end_date(self):
        """start_date debe ser anterior a end_date."""
        with pytest.raises(ValueError, match="start_date debe ser anterior a end_date"):
            CreateCompetitionRequestDTO(
                name="Test Cup",
                start_date=date(2025, 6, 3),
                end_date=date(2025, 6, 1),
                main_country="ES",
                handicap_type="SCRATCH"
            )

    def test_invalid_handicap_type(self):
        """Debe rechazar handicap_type inválido."""
        with pytest.raises(ValueError, match="handicap_type debe ser"):
            CreateCompetitionRequestDTO(
                name="Test Cup",
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 3),
                main_country="ES",
                handicap_type="INVALID"
            )

    def test_invalid_team_assignment(self):
        """Debe rechazar team_assignment inválido."""
        with pytest.raises(ValueError, match="team_assignment debe ser"):
            CreateCompetitionRequestDTO(
                name="Test Cup",
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 3),
                main_country="ES",
                handicap_type="SCRATCH",
                team_assignment="INVALID"
            )

    def test_name_too_short(self):
        """Debe rechazar nombre menor a 3 caracteres."""
        with pytest.raises(ValidationError):
            CreateCompetitionRequestDTO(
                name="RC",
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 3),
                main_country="ES",
                handicap_type="SCRATCH"
            )

    def test_name_too_long(self):
        """Debe rechazar nombre mayor a 100 caracteres."""
        with pytest.raises(ValidationError):
            CreateCompetitionRequestDTO(
                name="A" * 101,
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 3),
                main_country="ES",
                handicap_type="SCRATCH"
            )

    def test_max_players_below_minimum(self):
        """Debe rechazar max_players menor a 2."""
        with pytest.raises(ValidationError):
            CreateCompetitionRequestDTO(
                name="Test Cup",
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 3),
                main_country="ES",
                handicap_type="SCRATCH",
                max_players=1
            )

    def test_max_players_above_maximum(self):
        """Debe rechazar max_players mayor a 100."""
        with pytest.raises(ValidationError):
            CreateCompetitionRequestDTO(
                name="Test Cup",
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 3),
                main_country="ES",
                handicap_type="SCRATCH",
                max_players=101
            )

    def test_handicap_percentage_below_90(self):
        """Debe rechazar handicap_percentage menor a 90."""
        with pytest.raises(ValidationError):
            CreateCompetitionRequestDTO(
                name="Test Cup",
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 3),
                main_country="ES",
                handicap_type="PERCENTAGE",
                handicap_percentage=89
            )

    def test_handicap_percentage_above_100(self):
        """Debe rechazar handicap_percentage mayor a 100."""
        with pytest.raises(ValidationError):
            CreateCompetitionRequestDTO(
                name="Test Cup",
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 3),
                main_country="ES",
                handicap_type="PERCENTAGE",
                handicap_percentage=101
            )


class TestUpdateCompetitionRequestDTO:
    """Tests para UpdateCompetitionRequestDTO."""

    def test_all_fields_optional(self):
        """Todos los campos deben ser opcionales."""
        dto = UpdateCompetitionRequestDTO()
        assert dto.name is None
        assert dto.start_date is None
        assert dto.handicap_type is None

    def test_partial_update_name_only(self):
        """Debe permitir actualizar solo el nombre."""
        dto = UpdateCompetitionRequestDTO(name="New Name")
        assert dto.name == "New Name"
        assert dto.start_date is None

    def test_uppercase_conversions(self):
        """Debe convertir strings a mayúsculas."""
        dto = UpdateCompetitionRequestDTO(
            main_country="fr",
            handicap_type="percentage",
            team_assignment="automatic"
        )

        assert dto.main_country == "FR"
        assert dto.handicap_type == "PERCENTAGE"
        assert dto.team_assignment == "AUTOMATIC"
