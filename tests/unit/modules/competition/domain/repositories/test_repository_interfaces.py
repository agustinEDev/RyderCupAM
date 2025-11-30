"""Tests para verificar la estructura de las interfaces de repositorio."""

import inspect
from abc import ABC

import pytest

from src.modules.competition.domain.repositories.competition_repository_interface import (
    CompetitionRepositoryInterface,
)
from src.modules.competition.domain.repositories.enrollment_repository_interface import (
    EnrollmentRepositoryInterface,
)
from src.shared.domain.repositories.country_repository_interface import CountryRepositoryInterface


class TestCompetitionRepositoryInterface:
    """Tests para verificar la estructura de CompetitionRepositoryInterface."""

    def test_is_abstract_class(self):
        """CompetitionRepositoryInterface debe ser una clase abstracta."""
        assert issubclass(CompetitionRepositoryInterface, ABC)

    def test_has_add_method(self):
        """Debe tener método add."""
        assert hasattr(CompetitionRepositoryInterface, 'add')
        assert inspect.iscoroutinefunction(CompetitionRepositoryInterface.add)

    def test_has_update_method(self):
        """Debe tener método update."""
        assert hasattr(CompetitionRepositoryInterface, 'update')
        assert inspect.iscoroutinefunction(CompetitionRepositoryInterface.update)

    def test_has_delete_method(self):
        """Debe tener método delete."""
        assert hasattr(CompetitionRepositoryInterface, 'delete')
        assert inspect.iscoroutinefunction(CompetitionRepositoryInterface.delete)

    def test_has_find_by_id_method(self):
        """Debe tener método find_by_id."""
        assert hasattr(CompetitionRepositoryInterface, 'find_by_id')
        assert inspect.iscoroutinefunction(CompetitionRepositoryInterface.find_by_id)

    def test_has_find_by_creator_method(self):
        """Debe tener método find_by_creator."""
        assert hasattr(CompetitionRepositoryInterface, 'find_by_creator')
        assert inspect.iscoroutinefunction(CompetitionRepositoryInterface.find_by_creator)

    def test_has_find_by_status_method(self):
        """Debe tener método find_by_status."""
        assert hasattr(CompetitionRepositoryInterface, 'find_by_status')
        assert inspect.iscoroutinefunction(CompetitionRepositoryInterface.find_by_status)

    def test_has_find_active_in_date_range_method(self):
        """Debe tener método find_active_in_date_range."""
        assert hasattr(CompetitionRepositoryInterface, 'find_active_in_date_range')
        assert inspect.iscoroutinefunction(CompetitionRepositoryInterface.find_active_in_date_range)

    def test_has_exists_with_name_method(self):
        """Debe tener método exists_with_name."""
        assert hasattr(CompetitionRepositoryInterface, 'exists_with_name')
        assert inspect.iscoroutinefunction(CompetitionRepositoryInterface.exists_with_name)

    def test_has_count_by_creator_method(self):
        """Debe tener método count_by_creator."""
        assert hasattr(CompetitionRepositoryInterface, 'count_by_creator')
        assert inspect.iscoroutinefunction(CompetitionRepositoryInterface.count_by_creator)

    def test_cannot_instantiate_directly(self):
        """No se debe poder instanciar directamente (clase abstracta)."""
        with pytest.raises(TypeError):
            CompetitionRepositoryInterface()


class TestEnrollmentRepositoryInterface:
    """Tests para verificar la estructura de EnrollmentRepositoryInterface."""

    def test_is_abstract_class(self):
        """EnrollmentRepositoryInterface debe ser una clase abstracta."""
        assert issubclass(EnrollmentRepositoryInterface, ABC)

    def test_has_add_method(self):
        """Debe tener método add."""
        assert hasattr(EnrollmentRepositoryInterface, 'add')
        assert inspect.iscoroutinefunction(EnrollmentRepositoryInterface.add)

    def test_has_update_method(self):
        """Debe tener método update."""
        assert hasattr(EnrollmentRepositoryInterface, 'update')
        assert inspect.iscoroutinefunction(EnrollmentRepositoryInterface.update)

    def test_has_find_by_id_method(self):
        """Debe tener método find_by_id."""
        assert hasattr(EnrollmentRepositoryInterface, 'find_by_id')
        assert inspect.iscoroutinefunction(EnrollmentRepositoryInterface.find_by_id)

    def test_has_find_by_competition_method(self):
        """Debe tener método find_by_competition."""
        assert hasattr(EnrollmentRepositoryInterface, 'find_by_competition')
        assert inspect.iscoroutinefunction(EnrollmentRepositoryInterface.find_by_competition)

    def test_has_find_by_competition_and_status_method(self):
        """Debe tener método find_by_competition_and_status."""
        assert hasattr(EnrollmentRepositoryInterface, 'find_by_competition_and_status')
        assert inspect.iscoroutinefunction(EnrollmentRepositoryInterface.find_by_competition_and_status)

    def test_has_find_by_user_method(self):
        """Debe tener método find_by_user."""
        assert hasattr(EnrollmentRepositoryInterface, 'find_by_user')
        assert inspect.iscoroutinefunction(EnrollmentRepositoryInterface.find_by_user)

    def test_has_exists_for_user_in_competition_method(self):
        """Debe tener método exists_for_user_in_competition."""
        assert hasattr(EnrollmentRepositoryInterface, 'exists_for_user_in_competition')
        assert inspect.iscoroutinefunction(EnrollmentRepositoryInterface.exists_for_user_in_competition)

    def test_has_count_approved_method(self):
        """Debe tener método count_approved."""
        assert hasattr(EnrollmentRepositoryInterface, 'count_approved')
        assert inspect.iscoroutinefunction(EnrollmentRepositoryInterface.count_approved)

    def test_has_find_by_competition_and_team_method(self):
        """Debe tener método find_by_competition_and_team."""
        assert hasattr(EnrollmentRepositoryInterface, 'find_by_competition_and_team')
        assert inspect.iscoroutinefunction(EnrollmentRepositoryInterface.find_by_competition_and_team)

    def test_cannot_instantiate_directly(self):
        """No se debe poder instanciar directamente (clase abstracta)."""
        with pytest.raises(TypeError):
            EnrollmentRepositoryInterface()


class TestCountryRepositoryInterface:
    """Tests para verificar la estructura de CountryRepositoryInterface."""

    def test_is_abstract_class(self):
        """CountryRepositoryInterface debe ser una clase abstracta."""
        assert issubclass(CountryRepositoryInterface, ABC)

    def test_has_find_by_code_method(self):
        """Debe tener método find_by_code."""
        assert hasattr(CountryRepositoryInterface, 'find_by_code')
        assert inspect.iscoroutinefunction(CountryRepositoryInterface.find_by_code)

    def test_has_find_all_active_method(self):
        """Debe tener método find_all_active."""
        assert hasattr(CountryRepositoryInterface, 'find_all_active')
        assert inspect.iscoroutinefunction(CountryRepositoryInterface.find_all_active)

    def test_has_are_adjacent_method(self):
        """Debe tener método are_adjacent."""
        assert hasattr(CountryRepositoryInterface, 'are_adjacent')
        assert inspect.iscoroutinefunction(CountryRepositoryInterface.are_adjacent)

    def test_has_find_adjacent_countries_method(self):
        """Debe tener método find_adjacent_countries."""
        assert hasattr(CountryRepositoryInterface, 'find_adjacent_countries')
        assert inspect.iscoroutinefunction(CountryRepositoryInterface.find_adjacent_countries)

    def test_has_exists_method(self):
        """Debe tener método exists."""
        assert hasattr(CountryRepositoryInterface, 'exists')
        assert inspect.iscoroutinefunction(CountryRepositoryInterface.exists)

    def test_cannot_instantiate_directly(self):
        """No se debe poder instanciar directamente (clase abstracta)."""
        with pytest.raises(TypeError):
            CountryRepositoryInterface()
