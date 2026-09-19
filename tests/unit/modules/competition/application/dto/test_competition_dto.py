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

    def test_start_date_must_be_before_or_equal_to_end_date(self):
        """start_date debe ser anterior o igual a end_date."""
        with pytest.raises(ValueError, match="start_date debe ser anterior o igual a end_date"):
            CreateCompetitionRequestDTO(
                name="Test Cup",
                start_date=date(2025, 6, 3),
                end_date=date(2025, 6, 1),
                main_country="ES",
                play_mode="SCRATCH",
            )

    def test_start_date_equal_to_end_date_is_allowed(self):
        """Una competición de un solo día (start_date == end_date) es válida."""
        dto = CreateCompetitionRequestDTO(
            name="Test Cup",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 1),
            main_country="ES",
            play_mode="SCRATCH",
        )

        assert dto.start_date == dto.end_date

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

    def test_max_players_accepts_the_cap(self):
        """Debe aceptar exactamente 100, el cupo máximo de hoy."""
        dto = CreateCompetitionRequestDTO(
            name="Test Cup",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
            max_players=100,
        )

        assert dto.max_players == 100

    def test_max_players_accepts_the_minimum(self):
        """Debe aceptar exactamente 2, que sigue siendo el mínimo."""
        dto = CreateCompetitionRequestDTO(
            name="Test Cup",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
            max_players=2,
        )

        assert dto.max_players == 2

    def test_max_players_defaults_to_twelve(self):
        """Sin el campo debe quedar en 12: una Ryder entre amigos son 12 jugadores."""
        dto = CreateCompetitionRequestDTO(
            name="Test Cup",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
        )

        assert dto.max_players == 12


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

    def test_max_players_accepts_the_frontend_field_name(self):
        """El cupo debe llegar bajo `number_of_players`, que es lo que manda el cliente.

        Sin el alias, Pydantic descartaba la clave como extra desconocida y el PUT
        respondía 200 sin cambiar nada.
        """
        dto = UpdateCompetitionRequestDTO(number_of_players=20)

        assert dto.max_players == 20

    def test_max_players_accepts_the_canonical_field_name(self):
        """El nombre canónico debe seguir valiendo: es el que usa el propio backend."""
        dto = UpdateCompetitionRequestDTO(max_players=20)

        assert dto.max_players == 20

    def test_max_players_stays_none_when_absent(self):
        """Ausente significa «no lo toques», no «ponlo por defecto»."""
        dto = UpdateCompetitionRequestDTO(name="New Name")

        assert dto.max_players is None

    def test_max_players_alias_wins_over_the_field_name(self):
        """Con los dos nombres a la vez manda el alias, el que llega del cliente.

        No debería pasar, pero si pasa el comportamiento queda fijado aquí y no
        depende del orden en que Pydantic recorra el payload.
        """
        dto = UpdateCompetitionRequestDTO.model_validate(
            {"number_of_players": 20, "max_players": 30}
        )

        assert dto.max_players == 20

    def test_max_players_above_maximum(self):
        """Debe rechazar un cupo mayor a 100, venga con el nombre que venga."""
        with pytest.raises(ValidationError):
            UpdateCompetitionRequestDTO(number_of_players=101)

        with pytest.raises(ValidationError):
            UpdateCompetitionRequestDTO(max_players=101)

    def test_max_players_below_minimum(self):
        """Debe rechazar un cupo menor a 2, venga con el nombre que venga."""
        with pytest.raises(ValidationError):
            UpdateCompetitionRequestDTO(number_of_players=1)

        with pytest.raises(ValidationError):
            UpdateCompetitionRequestDTO(max_players=1)

    def test_max_players_accepts_the_boundaries(self):
        """Debe aceptar los dos extremos exactos."""
        assert UpdateCompetitionRequestDTO(number_of_players=2).max_players == 2
        assert UpdateCompetitionRequestDTO(number_of_players=100).max_players == 100

    def test_countries_is_converted_like_on_create(self):
        """`countries` debe convertirse a adjacent_country_1/2, igual que al crear.

        La pantalla manda el mismo payload para crear y para editar. Sin este
        campo, cambiar los países acompañantes no tenía ningún efecto y la
        respuesta seguía siendo un 200.
        """
        dto = UpdateCompetitionRequestDTO(countries=["PT"])

        assert dto.adjacent_country_1 == "PT"
        assert dto.adjacent_country_2 is None

    def test_countries_converts_both_positions(self):
        """Los dos países acompañantes, en orden."""
        dto = UpdateCompetitionRequestDTO(countries=["PT", "FR"])

        assert dto.adjacent_country_1 == "PT"
        assert dto.adjacent_country_2 == "FR"

    def test_countries_are_placed_as_they_come(self):
        """El DTO coloca el código, no lo normaliza: de eso sabe `CountryCode`.

        Que una minúscula acabe guardada como ISO se comprueba de punta a punta en
        los tests de integración del endpoint, que es donde se ve de verdad.
        """
        dto = UpdateCompetitionRequestDTO(countries=["pt", "fr"])

        assert dto.adjacent_country_1 == "pt"
        assert dto.adjacent_country_2 == "fr"

    def test_empty_countries_leaves_both_adjacent_none(self):
        """Lista vacía es «sin países acompañantes», que es como se quitan."""
        dto = UpdateCompetitionRequestDTO(countries=[])

        assert dto.adjacent_country_1 is None
        assert dto.adjacent_country_2 is None

    def test_explicit_adjacent_countries_win_over_countries(self):
        """Si vienen los dos formatos manda el explícito, igual que al crear."""
        dto = UpdateCompetitionRequestDTO(countries=["PT"], adjacent_country_1="FR")

        assert dto.adjacent_country_1 == "FR"


class TestCountriesFieldIsHostile:
    """El campo `countries` recibe lo que mande el cliente, no lo que esperamos.

    Vale para los dos DTOs: el validador estaba copiado y el defecto también.
    Lo que nunca puede pasar es que una entrada rara salga como 500; el contrato
    dice 422.
    """

    @staticmethod
    def crear(**kwargs):
        return CreateCompetitionRequestDTO(
            name="Test Cup",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
            **kwargs,
        )

    def test_update_rejects_country_objects(self):
        """Es la forma que devuelve el propio GET: `[{"code": "PT", ...}]`.

        Un cliente que lea, edite y reenvíe mandaba esto y reventaba con un
        AttributeError, que FastAPI convierte en 500.
        """
        with pytest.raises(ValidationError):
            UpdateCompetitionRequestDTO.model_validate(
                {"countries": [{"code": "PT", "name_es": "Portugal"}]}
            )

    def test_create_rejects_country_objects(self):
        with pytest.raises(ValidationError):
            CreateCompetitionRequestDTO.model_validate(
                {
                    "name": "Test Cup",
                    "start_date": "2025-06-01",
                    "end_date": "2025-06-03",
                    "main_country": "ES",
                    "play_mode": "SCRATCH",
                    "countries": [{"code": "PT", "name_es": "Portugal"}],
                }
            )

    def test_update_rejects_a_name_instead_of_a_code(self):
        """Solo códigos ISO de dos letras: «PORTUGAL» se colaba tal cual."""
        with pytest.raises(ValidationError):
            UpdateCompetitionRequestDTO(countries=["PORTUGAL"])

    def test_create_rejects_a_name_instead_of_a_code(self):
        with pytest.raises(ValidationError):
            self.crear(countries=["PORTUGAL"])

    def test_update_rejects_a_hole_in_the_list(self):
        with pytest.raises(ValidationError):
            UpdateCompetitionRequestDTO(countries=[None])

    def test_create_rejects_a_hole_in_the_list(self):
        with pytest.raises(ValidationError):
            self.crear(countries=[None])

    def test_update_still_converts_valid_codes(self):
        dto = UpdateCompetitionRequestDTO(countries=["PT", "FR"])

        assert dto.adjacent_country_1 == "PT"
        assert dto.adjacent_country_2 == "FR"

    def test_create_still_converts_valid_codes(self):
        dto = self.crear(countries=["PT", "FR"])

        assert dto.adjacent_country_1 == "PT"
        assert dto.adjacent_country_2 == "FR"


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
