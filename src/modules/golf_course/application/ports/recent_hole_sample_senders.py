"""
Puerto: quién ha aportado hace poco una muestra de hoyo (BE #532, 16 oct 2026).

Cada jugador aporta como mucho una muestra por campo, hoyo y barra cada 10
minutos. Hace falta saber quién la mandó, y eso no puede llegar a la base de
datos ni a los logs (las muestras son anónimas): por eso es un puerto, y la
implementación lo guarda solo en la memoria del proceso y lo olvida en cuanto
pasa la ventana.

Mirar y apartar el hueco es una sola operación (`reserve`): si fueran dos, dos
peticiones a la vez del mismo jugador verían las dos el hueco libre. Luego la
reserva se confirma (la muestra se guardó y se confirmó la transacción) o se
suelta (no se guardó, por lo que sea).
"""

from abc import ABC, abstractmethod

from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.value_objects.gender import Gender


class IRecentHoleSampleSenders(ABC):
    """Los jugadores que aportaron hace poco (o están aportando) a cada barra de cada hoyo."""

    @abstractmethod
    def reserve(
        self,
        user_id: str,
        golf_course_id: GolfCourseId,
        hole_number: int,
        tee_color: TeeColor,
        tee_gender: Gender | None,
    ) -> bool:
        """
        Aparta el hueco del jugador en esa barra del hoyo, si lo tiene libre: ni
        una muestra suya aceptada en la ventana, ni otra reserva suya en curso.
        """

    @abstractmethod
    def confirm(
        self,
        user_id: str,
        golf_course_id: GolfCourseId,
        hole_number: int,
        tee_color: TeeColor,
        tee_gender: Gender | None,
    ) -> None:
        """La muestra reservada se guardó y se confirmó: empieza su ventana."""

    @abstractmethod
    def release(
        self,
        user_id: str,
        golf_course_id: GolfCourseId,
        hole_number: int,
        tee_color: TeeColor,
        tee_gender: Gender | None,
    ) -> None:
        """La muestra reservada no se guardó: el hueco vuelve a quedar libre."""
