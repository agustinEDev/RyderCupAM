"""
JornadasDeLaCompeticion - Los días de juego de un stroke play, en horas absolutas (#251).

Para saber si el organizador puede actualizar los hándicaps hace falta saber
cuándo sale el primero de cada jornada y cuándo acaba el día, y eso es hora del
CAMPO: las franjas guardan «las 9:00» de allí. Cada franja se pasa a hora
absoluta con la zona de su campo.
"""

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from src.modules.competition.application.ports.competition_timezone import (
    ICompetitionTimezone,
)
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.services.ventana_de_actualizacion import Jornada
from src.modules.competition.domain.services.zona_horaria import zona_del_campo
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId


class ZonaDesconocidaError(Exception):
    """Algún campo de las franjas no tiene zona horaria: no se sabe cuándo sale nadie."""


class JornadasDeLaCompeticion:
    """Pasa las franjas a jornadas: primera salida y medianoche, en UTC."""

    @staticmethod
    async def de(sesiones: list[Round], zonas: ICompetitionTimezone) -> list[Jornada]:
        """
        Raises:
            ZonaDesconocidaError: Si el campo de alguna franja no tiene zona
        """
        por_dia: dict[date, list[datetime]] = defaultdict(list)
        medianoche: dict[date, datetime] = {}
        por_campo: dict[GolfCourseId, ZoneInfo | None] = {}
        for sesion in sesiones:
            hoja = sesion.hoja_de_salidas
            if hoja is None:
                continue
            # Una consulta por campo, no por franja
            if sesion.golf_course_id not in por_campo:
                por_campo[sesion.golf_course_id] = zona_del_campo(
                    await zonas.for_course(sesion.golf_course_id)
                )
            zona = por_campo[sesion.golf_course_id]
            if zona is None:
                raise ZonaDesconocidaError(
                    "El campo de una franja no tiene zona horaria: no se sabe a qué hora "
                    "sale nadie."
                )
            dia = sesion.round_date
            por_dia[dia].append(datetime.combine(dia, hoja.primera_salida, zona).astimezone(UTC))
            fin = datetime.combine(dia + timedelta(days=1), time(0, 0), zona).astimezone(UTC)
            medianoche[dia] = max(medianoche.get(dia, fin), fin)
        return [
            Jornada(primera_salida=min(salidas), fin=medianoche[dia])
            for dia, salidas in sorted(por_dia.items())
        ]
