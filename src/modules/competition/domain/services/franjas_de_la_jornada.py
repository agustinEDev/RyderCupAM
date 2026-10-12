"""
FranjasDeLaJornada - Las franjas de un mismo día no se solapan (#251).

Decidido con Agustín el 7 oct 2026: saliendo todos por el 1, dos franjas a la
misma hora en el MISMO CAMPO chocarían en el tee. Tocarse también es chocar: la
última salida de una sería la primera de la otra. En campos distintos no
comparten tee y pueden coincidir.
"""

from collections.abc import Iterable
from datetime import date

from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId


class FranjasSolapadasError(ValueError):
    """Dos franjas de la misma jornada comparten alguna hora de salida."""


class FranjasDeLaJornada:
    """Comprueba una franja contra las demás del mismo día."""

    @staticmethod
    def comprobar(
        hoja: HojaDeSalidas,
        dia: date,
        campo: GolfCourseId,
        sesiones: Iterable[Round],
        excepto: RoundId | None = None,
    ) -> None:
        """
        Args:
            hoja: La hoja de la franja que se crea o se cambia
            dia: Su jornada
            campo: Su campo: solo chocan las del mismo
            sesiones: Las sesiones de la competición (se miran las de ese día)
            excepto: La propia franja, si se está editando

        Raises:
            FranjasSolapadasError: Si choca con otra, diciendo con cuál
        """
        for otra in sesiones:
            if (
                otra.id == excepto
                or otra.round_date != dia
                or otra.golf_course_id != campo
                or otra.hoja_de_salidas is None
            ):
                continue
            if hoja.se_solapa_con(otra.hoja_de_salidas):
                otra_hoja = otra.hoja_de_salidas
                raise FranjasSolapadasError(
                    f"Se solapa con la franja {otra.session_type.value} de ese día en el mismo campo "
                    f"({otra_hoja.primera_salida:%H:%M}-{otra_hoja.ultima_salida:%H:%M})."
                )
