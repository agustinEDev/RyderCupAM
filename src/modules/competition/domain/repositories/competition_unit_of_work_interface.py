"""
Competition Unit of Work Interface - Competition Module Domain Layer.

Define el contrato específico para el Unit of Work del módulo de competiciones.
Esta interfaz extiende la base añadiendo acceso a los repositorios de competiciones.
"""

from abc import abstractmethod

from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)
from src.shared.domain.repositories.unit_of_work_interface import UnitOfWorkInterface

from .competition_repository_interface import CompetitionRepositoryInterface
from .enrollment_repository_interface import EnrollmentRepositoryInterface
from .hole_score_repository_interface import HoleScoreRepositoryInterface
from .invitation_repository_interface import InvitationRepositoryInterface
from .match_repository_interface import MatchRepositoryInterface
from .round_repository_interface import RoundRepositoryInterface
from .team_assignment_repository_interface import TeamAssignmentRepositoryInterface


class CompetitionUnitOfWorkInterface(UnitOfWorkInterface):
    """
    Interfaz especifica para el Unit of Work del modulo de competiciones.

    Proporciona acceso coordinado a todos los repositorios relacionados
    con el dominio de competiciones, manteniendo consistencia transaccional.
    """

    @property
    @abstractmethod
    def competitions(self) -> CompetitionRepositoryInterface:
        """Acceso al repositorio de competiciones."""
        pass

    @property
    @abstractmethod
    def enrollments(self) -> EnrollmentRepositoryInterface:
        """Acceso al repositorio de inscripciones."""
        pass

    @property
    @abstractmethod
    def countries(self) -> CountryRepositoryInterface:
        """Acceso al repositorio de paises."""
        pass

    @property
    @abstractmethod
    def rounds(self) -> RoundRepositoryInterface:
        """Acceso al repositorio de rondas."""
        pass

    @property
    @abstractmethod
    def matches(self) -> MatchRepositoryInterface:
        """Acceso al repositorio de partidos."""
        pass

    @property
    @abstractmethod
    def team_assignments(self) -> TeamAssignmentRepositoryInterface:
        """Acceso al repositorio de asignaciones de equipos."""
        pass

    @property
    @abstractmethod
    def invitations(self) -> InvitationRepositoryInterface:
        """Acceso al repositorio de invitaciones."""
        pass

    @property
    @abstractmethod
    def hole_scores(self) -> HoleScoreRepositoryInterface:
        """Acceso al repositorio de hole scores."""
        pass
