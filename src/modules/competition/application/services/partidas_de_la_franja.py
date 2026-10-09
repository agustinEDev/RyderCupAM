"""
Las partidas de una franja cuando cambia lo que las sostiene (#251, PR 4).

Decidido con Agustín el 9 oct 2026:

- La hoja se cambia libre (hora, intervalo): la hora de cada partida sale de su
  número. Pero si las partidas ya no caben —alguna con más jugadores que el
  tamaño nuevo, o más partidas que salidas—, el cambio se rechaza (D9).
- Otro campo, o un hándicap fijado corregido: las fotos de las partidas sin
  salir se recalculan (D9, G1). Si alguien no tiene barras en el campo nuevo, el
  cambio se rechaza con la lista (G2).
"""

from collections.abc import Collection, Sequence

from src.modules.competition.application.exceptions import FranjaInvalidaError
from src.modules.competition.application.services.jugadores_de_la_partida import (
    JugadoresDeLaPartida,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.user.domain.value_objects.user_id import UserId


def comprobar_que_caben_las_partidas(partidas: Sequence[Partida], hoja: HojaDeSalidas) -> None:
    """
    Raises:
        FranjaInvalidaError: Si alguna partida no cabe en la hoja nueva
    """
    tamano = hoja.jugadores_por_partida
    if any(len(p.jugadores) > tamano for p in partidas):
        raise FranjaInvalidaError(
            f"Hay partidas de más de {tamano} jugadores: muévelos o vuelve a generarlas antes."
        )
    if partidas and max(p.numero for p in partidas) > hoja.numero_de_salidas:
        raise FranjaInvalidaError(
            f"La franja tiene {len(partidas)} partidas y la hoja nueva solo "
            f"{hoja.numero_de_salidas} salidas."
        )


async def recalcular_partidas(
    uow: CompetitionUnitOfWorkInterface,
    jugadores: JugadoresDeLaPartida,
    competicion: Competition,
    franja: Round,
    partidas: Sequence[Partida],
    solo: Collection[UserId] | None = None,
) -> None:
    """
    Rehace la foto de los jugadores de las partidas sin salir: de todos, o `solo` de esos.

    Raises:
        JugadoresSinHandicapError, JugadoresSinBarraError: Con todos los afectados
    """
    sin_salir = [
        p
        for p in partidas
        if not p.empezada and (solo is None or any(u in solo for u in p.user_ids))
    ]
    quienes = [u for p in sin_salir for u in p.user_ids if solo is None or u in solo]
    if not quienes:
        return
    fotos = await jugadores.construir(uow, competicion, franja, quienes)
    for partida in sin_salir:
        partida.recalcular([fotos.get(j.user_id, j) for j in partida.jugadores])
    await uow.partidas.guardar(sin_salir)
