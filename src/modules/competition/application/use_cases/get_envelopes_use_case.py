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
    envelope_to_dto,
    matchups_to_dto,
)
from src.modules.competition.application.services.envelope_desk import EnvelopeDesk
from src.modules.competition.application.services.player_names import PlayerNames
from src.modules.competition.domain.entities.envelope import Envelope
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


class GetEnvelopesUseCase:
    """Caso de uso para consultar los sobres de una sesion."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_repository,
        clock=None,
        timezone_service=None,
    ):
        """
        Args:
            uow: Unit of Work del modulo
            user_repository: Lo pide la mesa de sobres para los handicaps
            clock: El reloj del servidor, para el revelado del plazo
            timezone_service: La zona del campo donde se juega
        """
        self._uow = uow
        self._desk = EnvelopeDesk(uow, user_repository, clock, timezone_service)

    async def execute(
        self, round_id: UUID, user_id: UserId, is_admin: bool = False
    ) -> EnvelopesViewDTO:
        """
        Devuelve lo que puede ver quien pregunta.

        Args:
            round_id: La sesion
            user_id: Quien mira
            is_admin: Si es administrador, que tambien puede abrirlos

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
            # Mirarlos es lo que los abre cuando llega su hora: no hay ningun
            # proceso de fondo con el reloj, igual que la anotacion (BE #305)
            await self._desk.revelar_si_toca(ronda, competition, sobres)
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
            programado = await self._desk.programado_para(ronda, competition)
            por_fila = Envelope.players_per_row_for(ronda.match_format)
            cuadran = await self._desk.los_equipos_cuadran(competition, por_fila)

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
                mine=envelope_to_dto(mio) if mio and mio.is_submitted() else None,
                # El del rival SOLO cuando ya estan abiertos
                rival=envelope_to_dto(rival) if abiertos and rival else None,
                rival_submitted=bool(rival and rival.is_submitted()),
                rival_wants_early=bool(rival and rival.reveal_when_both_ready),
                # La regla vive en un solo sitio: aqui solo se pregunta
                players_per_row=por_fila,
                teams_fit_format=cuadran,
                can_reveal=self._desk.puede_abrirlos(
                    competition,
                    user_id,
                    sobres,
                    ronda=ronda,
                    is_admin=is_admin,
                    sin_plazo=self._desk.sin_plazo_que_vencer(programado),
                ),
                reveal_scheduled_at=programado,
                matchups=matchups_to_dto(sobre_a, sobre_b) if abiertos else [],
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
