"""Adaptador: la papelera de cada jugador la guarda el modulo de partidas rapidas."""

from collections.abc import Sequence

from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_id import (
    InvalidQuickMatchIdError,
    QuickMatchId,
)
from src.modules.social.application.ports.quick_match_trash_interface import (
    QuickMatchTrashInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class QuickMatchTrashAdapter(QuickMatchTrashInterface):
    """
    Lee de una vez las partidas de una pagina y mira la papelera de cada autor:
    un jugador con cuenta es participante con el id de su usuario.
    """

    def __init__(self, quick_match_uow: QuickMatchUnitOfWorkInterface):
        self._quick_match_uow = quick_match_uow

    async def trashed_by_author(
        self, pairs: Sequence[tuple[str, UserId]]
    ) -> set[tuple[str, UserId]]:
        legibles: dict[str, QuickMatchId] = {}
        for crudo, _ in pairs:
            # El origen puede ser de un torneo o ilegible: no tumba el feed
            try:
                legibles[crudo] = QuickMatchId(crudo)
            except (TypeError, ValueError, InvalidQuickMatchIdError):
                continue
        if not legibles:
            return set()
        async with self._quick_match_uow:
            partidas = {
                str(partida.id.value): partida
                for partida in await self._quick_match_uow.quick_matches.find_by_ids(
                    list(legibles.values())
                )
            }
        return {
            (crudo, autor)
            for crudo, autor in pairs
            # Solo un participante puede tenerla en su papelera
            if (partida := partidas.get(crudo)) is not None
            and partida.is_hidden_for(ParticipantId(autor.value))
        }
