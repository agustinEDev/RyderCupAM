"""
Caso de Uso: Mirar los sobres de una sesion (FE #655).

Quien mira decide que se devuelve: un capitan ve el SUYO y, del rival, solo si
ya lo entrego —nunca su contenido, que verlo antes de tiempo es el juego
entero—. Abiertos, los ve todo el mundo con sus enfrentamientos.
"""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from src.modules.competition.application.dto.envelope_dto import (
    EnvelopePlayerDTO,
    EnvelopesViewDTO,
    envelope_to_dto,
    matchups_to_dto,
)
from src.modules.competition.application.dto.match_generation_block_dto import block_to_dto
from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.application.services.envelope_desk import (
    EnvelopeDesk,
    GeneradorDePartidos,
)
from src.modules.competition.application.services.player_names import PlayerNames
from src.modules.competition.domain.entities.envelope import Envelope
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.value_objects.user_id import UserId


class GetEnvelopesUseCase:
    """Caso de uso para consultar los sobres de una sesion."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_repository: UserRepositoryInterface,
        clock: Callable[[], datetime] | None = None,
        timezone_service: ICompetitionTimezone | None = None,
        generador: GeneradorDePartidos | None = None,
    ):
        """
        Args:
            uow: Unit of Work del modulo
            user_repository: Lo pide la mesa de sobres para los handicaps
            clock: El reloj del servidor, para el revelado del plazo
            timezone_service: La zona del campo donde se juega
            generador: Crea los partidos si mirar es lo que los abre (BE #361)
        """
        self._uow = uow
        self._desk = EnvelopeDesk(uow, user_repository, clock, timezone_service, generador)

    async def execute(
        self, round_id: UUID, user_id: UserId, is_admin: bool = False
    ) -> EnvelopesViewDTO:
        """
        Devuelve lo que puede ver quien pregunta.

        Args:
            round_id: La sesion
            user_id: Quien mira
            is_admin: Si es administrador: los ve aunque no juegue ni organice, y
                tambien puede abrirlos

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
            await self._desk.comprobar_que_es_de_la_competicion(
                competition, user_id, is_admin=is_admin
            )
            sobres = {s.team: s for s in await self._uow.envelopes.find_by_round(ronda.id)}
            # Mirarlos es lo que los abre cuando llega su hora: no hay ningun
            # proceso de fondo con el reloj, igual que la anotacion (BE #305)
            # El id antes de abrir: si crear los partidos falla, la ronda puede
            # quedar caducada, y leerle un atributo revienta en asincrono
            id_de_la_ronda = ronda.id
            await self._desk.revelar_si_toca(ronda, competition, sobres)
            # Abrir puede haber creado los partidos o apuntado por que no: la
            # sesion se vuelve a leer para contar lo que hay de verdad
            ronda = await self._uow.rounds.find_by_id(id_de_la_ronda) or ronda
            mi_equipo = self._desk.equipo_de(competition, user_id)
            mis_jugadores = (
                await self._desk.jugadores_de(competition, mi_equipo) if mi_equipo else []
            )
            nombres = await PlayerNames.de_la_competicion(
                _aparecen(mis_jugadores, sobres),
                competition.id,
                self._desk.user_repository,
                self._uow,
                competition.visibility,
            )
            handicaps = dict(await self._desk.handicaps_de(competition, mis_jugadores))
            programado = await self._desk.programado_para(ronda, competition)
            por_fila = Envelope.players_per_row_for(ronda.match_format)
            cuadran = await self._desk.los_equipos_cuadran(competition, por_fila)
            # La regla vive en un solo sitio: aqui solo se pregunta
            puede_abrirlos = self._desk.puede_abrirlos(
                competition,
                user_id,
                sobres,
                ronda=ronda,
                is_admin=is_admin,
                sin_plazo=self._desk.sin_plazo_que_vencer(programado),
            )

            vista = _vista(
                ronda,
                sobres,
                mi_equipo,
                players_per_row=por_fila,
                teams_fit_format=cuadran,
                can_reveal=puede_abrirlos,
                reveal_scheduled_at=programado,
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
        # Ya guardado: los avisos de los partidos que haya creado abrirlos (G2)
        await self._desk.avisar_salidas()
        return vista


def _aparecen(mis_jugadores: list[UserId], sobres: dict[str, Envelope]) -> list[UserId]:
    """Los que salen en la vista, sin repetir: los míos y los de los sobres abiertos."""
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
    return list(dict.fromkeys(aparecen))


def _vista(
    ronda: Round,
    sobres: dict[str, Envelope],
    mi_equipo: str | None,
    *,
    players_per_row: int,
    teams_fit_format: bool,
    can_reveal: bool,
    reveal_scheduled_at: datetime | None,
    my_players: list[EnvelopePlayerDTO],
    player_names: dict[str, str],
) -> EnvelopesViewDTO:
    """Lo que ve quien mira: del rival, su contenido solo cuando ya están abiertos."""
    sobre_a, sobre_b = sobres.get("A"), sobres.get("B")
    abiertos = _abiertos(sobre_a, sobre_b)
    mio = sobres.get(mi_equipo) if mi_equipo else None
    rival = sobres.get("B" if mi_equipo == "A" else "A") if mi_equipo else None
    return EnvelopesViewDTO(
        round_id=ronda.id.value,
        revealed=abiertos,
        team_a_submitted=_entregado(sobre_a),
        team_b_submitted=_entregado(sobre_b),
        # Lo que rellena la aplicacion cuenta como «hay algo dentro»,
        # pero NO como que el capitan entrego: sin esto la pantalla
        # diria que entregaron los dos y seria mentira
        team_a_automatic=bool(sobre_a and sobre_a.automatic),
        team_b_automatic=bool(sobre_b and sobre_b.automatic),
        mine=envelope_to_dto(mio) if mio and _entregado(mio) else None,
        # El del rival SOLO cuando ya estan abiertos
        rival=envelope_to_dto(rival) if abiertos and rival else None,
        rival_submitted=_entregado(rival),
        rival_wants_early=bool(rival and rival.reveal_when_both_ready),
        players_per_row=players_per_row,
        teams_fit_format=teams_fit_format,
        can_reveal=can_reveal,
        reveal_scheduled_at=reveal_scheduled_at,
        matchups=_enfrentamientos(sobre_a, sobre_b) if abiertos else [],
        my_players=my_players,
        player_names=player_names,
        match_generation_block=block_to_dto(ronda.match_generation_block),
    )


def _abiertos(sobre_a: Envelope | None, sobre_b: Envelope | None) -> bool:
    """Si están los dos y ninguno sigue sellado."""
    return bool(sobre_a and sobre_b and not sobre_a.is_sealed() and not sobre_b.is_sealed())


def _entregado(sobre: Envelope | None) -> bool:
    """Si ese sobre existe y su capitán lo entregó."""
    return bool(sobre and sobre.is_submitted())


def _enfrentamientos(sobre_a: Envelope | None, sobre_b: Envelope | None) -> list[list[list[UUID]]]:
    """Los cruces de los dos sobres, si están los dos."""
    return matchups_to_dto(sobre_a, sobre_b) if sobre_a and sobre_b else []
