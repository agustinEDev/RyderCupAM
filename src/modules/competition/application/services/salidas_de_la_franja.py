"""
Las partidas de una franja a las que ya les llegó su hora, con la zona del campo.

Aparte para que la usen la vista de la franja y los movimientos de jugadores sin
importarse entre ellos (#544).
"""

from collections.abc import Sequence
from datetime import datetime

from src.modules.competition.application.ports.competition_timezone import (
    ICompetitionTimezone,
)
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.services.zona_horaria import zona_del_campo
from src.modules.competition.domain.value_objects.partida_id import PartidaId


async def salidas_por_hora(
    franja: Round,
    partidas: Sequence[Partida],
    zonas: ICompetitionTimezone | None,
    ahora: datetime | None,
) -> set[PartidaId]:
    """
    Las partidas de la franja a las que ya les llegó su hora.

    Sin zona horaria (o sin reloj) no se sabe: entonces cuenta solo su estado.
    """
    hoja = franja.hoja_de_salidas
    if hoja is None or zonas is None or ahora is None:
        return set()
    zona = zona_del_campo(await zonas.for_course(franja.golf_course_id))
    if zona is None:
        return set()
    return {
        p.id
        for p in partidas
        # Con huecos en la numeración puede no tener salida en la hoja: su estado manda
        if 1 <= p.numero <= hoja.numero_de_salidas
        and ahora >= datetime.combine(franja.round_date, hoja.hora_de(p.numero), zona)
    }


async def las_que_salieron(
    franja: Round,
    partidas: Sequence[Partida],
    zonas: ICompetitionTimezone | None,
    ahora: datetime | None,
) -> set[PartidaId]:
    """
    Las que ya salieron (#544): tienen golpes, o les llegó su hora con la zona del
    campo. La única regla: la usan la vista y los cambios de partidas.
    """
    return {p.id for p in partidas if p.empezada} | await salidas_por_hora(
        franja, partidas, zonas, ahora
    )


async def numeros_libres(
    franja: Round,
    partidas: Sequence[Partida],
    zonas: ICompetitionTimezone,
    ahora: datetime,
) -> list[int]:
    """Las salidas de la hoja sin partida cuya hora aún no ha llegado (#544)."""
    hoja = franja.hoja_de_salidas
    zona = zona_del_campo(await zonas.for_course(franja.golf_course_id))
    if hoja is None or zona is None:
        return []
    ocupados = {p.numero for p in partidas}
    return [
        n
        for n in range(1, hoja.numero_de_salidas + 1)
        if n not in ocupados and ahora < datetime.combine(franja.round_date, hoja.hora_de(n), zona)
    ]
