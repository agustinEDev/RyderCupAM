"""
Caso de Uso: Mirar los sobres de una sesion (FE #655).

Quien mira decide que se devuelve: un capitan ve el SUYO y, del rival, solo si
ya lo entrego —nunca su contenido, que verlo antes de tiempo es el juego
entero—. Abiertos, los ve todo el mundo con sus enfrentamientos.
"""

from uuid import UUID

from src.modules.competition.application.dto.envelope_dto import (
    EnvelopePlayerDTO,
    EnvelopesViewDTO,
)
from src.modules.competition.application.services.envelope_desk import EnvelopeDesk
from src.modules.competition.application.services.player_names import PlayerNames
from src.modules.competition.application.use_cases.submit_envelope_use_case import _a_dto
from src.modules.competition.domain.entities.envelope import Envelope
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


class GetEnvelopesUseCase:
    """Caso de uso para consultar los sobres de una sesion."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface, user_repository):
        """
        Args:
            uow: Unit of Work del modulo
            user_repository: Lo pide la mesa de sobres para los handicaps
        """
        self._uow = uow
        self._desk = EnvelopeDesk(uow, user_repository)

    async def execute(self, round_id: UUID, user_id: UserId) -> EnvelopesViewDTO:
        """
        Devuelve lo que puede ver quien pregunta.

        Args:
            round_id: La sesion
            user_id: Quien mira

        Returns:
            Su sobre si capitanea, si el rival entrego, y los enfrentamientos
            solo cuando ya estan abiertos

        Raises:
            RoundNotFoundError: Si la sesion no existe
            NotCompetitionParticipantError: Si quien pregunta no es de esta
                competicion
        """
        async with self._uow:
            ronda, competition = await self._desk.ronda_y_competicion(RoundId(round_id))
            await self._desk.comprobar_que_es_de_la_competicion(competition, user_id)
            sobres = {s.team: s for s in await self._uow.envelopes.find_by_round(ronda.id)}
            sobre_a, sobre_b = sobres.get("A"), sobres.get("B")
            abiertos = bool(
                sobre_a and sobre_b and not sobre_a.is_sealed() and not sobre_b.is_sealed()
            )

            mi_equipo = self._desk.equipo_de(competition, user_id)
            mio = sobres.get(mi_equipo) if mi_equipo else None
            rival = sobres.get("B" if mi_equipo == "A" else "A") if mi_equipo else None

            mis_jugadores = (
                await self._desk.jugadores_de(competition, mi_equipo) if mi_equipo else []
            )
            aparecen = [
                *mis_jugadores,
                *(
                    uid
                    for sobre in sobres.values()
                    if not sobre.is_sealed()
                    for fila in sobre.entries
                    for uid in fila
                ),
            ]
            nombres = await PlayerNames.de_la_competicion(
                list(dict.fromkeys(aparecen)), competition.id, self._desk.user_repository, self._uow
            )
            handicaps = dict(await self._desk.handicaps_de(competition, mis_jugadores))

            arbitra = competition.is_creator(user_id)
            los_dos_dentro = bool(
                sobre_a and sobre_a.is_submitted() and sobre_b and sobre_b.is_submitted()
            )
            return EnvelopesViewDTO(
                round_id=ronda.id.value,
                revealed=abiertos,
                team_a_submitted=bool(sobre_a and sobre_a.is_submitted()),
                team_b_submitted=bool(sobre_b and sobre_b.is_submitted()),
                # Lo que rellena la aplicacion cuenta como «hay algo dentro»,
                # pero NO como que el capitan entrego: sin esto la pantalla
                # diria que entregaron los dos y seria mentira
                team_a_automatic=bool(sobre_a and sobre_a.automatic),
                team_b_automatic=bool(sobre_b and sobre_b.automatic),
                mine=_a_dto(mio) if mio and mio.is_submitted() else None,
                # El del rival SOLO cuando ya estan abiertos
                rival=_a_dto(rival) if abiertos and rival else None,
                rival_submitted=bool(rival and rival.is_submitted()),
                can_reveal=(not abiertos)
                and (arbitra or (mi_equipo is not None and los_dos_dentro)),
                matchups=_cruzados(sobre_a, sobre_b) if abiertos else [],
                my_players=[
                    EnvelopePlayerDTO(
                        user_id=uid.value,
                        name=nombres.get(uid, ""),
                        handicap=handicaps.get(uid),
                    )
                    for uid in mis_jugadores
                ],
                player_names={str(uid.value): nombre for uid, nombre in nombres.items()},
            )


def _cruzados(sobre_a: Envelope, sobre_b: Envelope) -> list[list[list[UUID]]]:
    """Los enfrentamientos, cruzados por posicion."""
    return [
        [[uid.value for uid in fila_a], [uid.value for uid in fila_b]]
        for fila_a, fila_b in Envelope.pair_up(sobre_a, sobre_b)
    ]
