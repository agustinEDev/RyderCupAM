"""
Las partidas de un jugador cuando deja su sitio (#251, PR 4).

Decidido con Agustín el 9 oct 2026: al retirarse (D2) o al cambiarse de franja
(D3) sale de sus partidas que aún no han salido; lo jugado se queda.
"""

from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.movimientos_de_partidas import (
    MovimientosDePartidas,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


async def sacar_de_sus_partidas(
    uow: CompetitionUnitOfWorkInterface,
    competition_id: CompetitionId,
    user_id: UserId,
    round_id: RoundId | None = None,
) -> None:
    """
    Le saca de sus partidas sin salir: de todas, o solo de la de esa franja.

    Si una se vacía, desaparece y las de detrás suben (M3); de una que ya salió
    no sale (lo mira `sacar`).
    """
    for partida in await uow.partidas.del_jugador(competition_id, user_id):
        if round_id is not None and partida.round_id != round_id:
            continue
        cambios = MovimientosDePartidas.sacar(
            await uow.partidas.de_la_franja(partida.round_id), user_id
        )
        await uow.partidas.borrar(cambios.borrar)
        await uow.partidas.guardar(cambios.guardar)
