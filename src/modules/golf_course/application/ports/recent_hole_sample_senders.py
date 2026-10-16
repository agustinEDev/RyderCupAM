"""
Puerto: quién ha aportado hace poco una muestra de hoyo (BE #532, 16 oct 2026).

Cada jugador aporta como mucho una muestra por campo, hoyo y barra cada 10
minutos. Hace falta saber quién la mandó, y eso no puede llegar a la base de
datos ni a los logs (las muestras son anónimas): por eso es un puerto, y la
implementación lo guarda solo en la memoria del proceso y lo olvida en cuanto
pasa la ventana.
"""

from abc import ABC, abstractmethod

from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.value_objects.gender import Gender


class IRecentHoleSampleSenders(ABC):
    """Los jugadores que aportaron hace poco una muestra a cada barra de cada hoyo."""

    @abstractmethod
    def allowed(
        self,
        user_id: str,
        golf_course_id: GolfCourseId,
        hole_number: int,
        tee_color: TeeColor,
        tee_gender: Gender | None,
    ) -> bool:
        """Si el jugador puede aportar ya otra muestra a esa barra del hoyo."""

    @abstractmethod
    def record(
        self,
        user_id: str,
        golf_course_id: GolfCourseId,
        hole_number: int,
        tee_color: TeeColor,
        tee_gender: Gender | None,
    ) -> None:
        """
        Apunta que el jugador aportó una muestra a esa barra del hoyo. Solo se
        llama con la muestra ya guardada y confirmada.
        """
