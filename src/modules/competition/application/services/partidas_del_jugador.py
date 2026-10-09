"""
Las partidas de un jugador cuando deja su sitio (#251, PR 4).

Decidido con Agustín el 9 oct 2026: al retirarse (D2) o al cambiarse de franja
(D3) sale de sus partidas que aún no han salido; lo jugado se queda.

Una partida a la que le llegó su hora ya salió, aunque su estado no lo diga:
hasta la PR 5 nadie la pasa a IN_PROGRESS (revisión de la PR 4).
"""

from collections.abc import Sequence
from datetime import datetime

from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.movimientos_de_partidas import (
    MovimientosDePartidas,
)
from src.modules.competition.domain.services.zona_horaria import zona_del_campo
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


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


async def sacar_de_sus_partidas(
    uow: CompetitionUnitOfWorkInterface,
    competition_id: CompetitionId,
    user_id: UserId,
    round_id: RoundId | None = None,
    zonas: ICompetitionTimezone | None = None,
    ahora: datetime | None = None,
) -> None:
    """
    Le saca de sus partidas sin salir: de todas, o solo de la de esa franja.

    Si una se vacía, desaparece y las de detrás suben (M3), salvo que alguna de
    la franja ya haya salido; de una que ya salió no sale (lo mira `sacar`).
    """
    for partida in await uow.partidas.del_jugador(competition_id, user_id):
        if round_id is not None and partida.round_id != round_id:
            continue
        franja = await uow.rounds.find_by_id(partida.round_id)
        de_la_franja = await uow.partidas.de_la_franja(partida.round_id)
        salidas = await salidas_por_hora(franja, de_la_franja, zonas, ahora) if franja else set()
        cambios = MovimientosDePartidas.sacar(de_la_franja, user_id, salidas)
        await uow.partidas.borrar(cambios.borrar)
        await uow.partidas.guardar(cambios.guardar)
