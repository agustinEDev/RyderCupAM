"""
QuickMatch Unit of Work Interface - QuickMatch Module Domain Layer.
"""

from abc import abstractmethod

from src.shared.domain.repositories.unit_of_work_interface import UnitOfWorkInterface

from .quick_match_hole_score_repository_interface import (
    QuickMatchHoleScoreRepositoryInterface,
)
from .quick_match_repository_interface import QuickMatchRepositoryInterface


class QuickMatchUnitOfWorkInterface(UnitOfWorkInterface):
    """Interfaz especifica para el Unit of Work del modulo QuickMatch."""

    @property
    @abstractmethod
    def quick_matches(self) -> QuickMatchRepositoryInterface:
        pass

    @property
    @abstractmethod
    def quick_match_hole_scores(self) -> QuickMatchHoleScoreRepositoryInterface:
        pass
