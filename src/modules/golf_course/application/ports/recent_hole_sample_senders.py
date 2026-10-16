"""
Puerto: quién ha aportado hace poco una muestra de hoyo (BE #532, 16 oct 2026).

Cada jugador aporta como mucho una muestra por campo y hoyo cada 10 minutos
(por hoyo, como las tres, desde el 17 oct). Hace falta saber quién la mandó, y eso no puede llegar a la base de
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


class IRecentHoleSampleSenders(ABC):
    """Los jugadores que aportaron hace poco (o están aportando) a cada hoyo."""

    @abstractmethod
    def reserve(
        self,
        user_id: str,
        golf_course_id: GolfCourseId,
        hole_number: int,
    ) -> bool:
        """
        Aparta el hueco del jugador en ese hoyo, si lo tiene libre: ni
        una muestra suya aceptada en la ventana, ni otra reserva suya en curso.
        """

    @abstractmethod
    def confirm(
        self,
        user_id: str,
        golf_course_id: GolfCourseId,
        hole_number: int,
    ) -> None:
        """La muestra reservada se guardó y se confirmó: empieza su ventana."""

    @abstractmethod
    def release(
        self,
        user_id: str,
        golf_course_id: GolfCourseId,
        hole_number: int,
    ) -> None:
        """La muestra reservada no se guardó: el hueco vuelve a quedar libre."""
