"""
VistaDeLaFranja - Las partidas de una franja tal como las ve la pantalla (#251, PR 4).

La misma para quien genera y para quien consulta: cada partida con su hora (que
sale de la hoja, no se guarda), sus jugadores con nombre, quién marca a quién, si
el organizador aún puede tocarlas y quién tiene plaza pero no partida.
"""

from collections.abc import Sequence
from datetime import datetime

from src.modules.competition.application.dto.partidas_dto import (
    TeeGroupDTO,
    TeeGroupPlayerDTO,
    TeeGroupsResponseDTO,
)
from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.application.services.jornadas_de_la_competicion import (
    JornadasDeLaCompeticion,
    ZonaDesconocidaError,
)
from src.modules.competition.application.services.player_names import PlayerNames
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.partida import Partida, PartidaEmpezadaError
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.plazo_de_partidas import (
    PlazoCerradoError,
    PlazoDePartidas,
)
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


async def primera_salida(franja: Round, zonas: ICompetitionTimezone) -> datetime:
    """
    El instante de la primera salida de la franja, en UTC.

    Raises:
        ZonaDesconocidaError: Si el campo no tiene zona horaria (D10)
    """
    return (await JornadasDeLaCompeticion.de([franja], zonas))[0].primera_salida


async def con_plaza_y_aprobados(uow: CompetitionUnitOfWorkInterface, franja: Round) -> list:
    """Las plazas de la franja de quien sigue aprobado, por orden de llegada.

    Un retirado con la competición iniciada conserva su plaza: no juega.
    """
    aprobados = {
        e.user_id
        for e in await uow.enrollments.find_by_competition_and_status(
            franja.competition_id, EnrollmentStatus.APPROVED
        )
    }
    return [p for p in await uow.plazas.de_la_franja(franja.id) if p.user_id in aprobados]


async def vista_de_la_franja(
    uow: CompetitionUnitOfWorkInterface,
    competicion: Competition,
    franja: Round,
    partidas: Sequence[Partida],
    zonas: ICompetitionTimezone,
    usuarios: UserRepositoryInterface,
    ahora: datetime,
) -> TeeGroupsResponseDTO:
    """La franja con sus partidas, para la pantalla."""
    hoja = franja.hoja_de_salidas
    if hoja is None:
        raise ValueError(f"La sesión {franja.id} no es una franja de stroke play")
    en_partida = {u for p in partidas for u in p.user_ids}
    sin_partida = [
        p.user_id for p in await con_plaza_y_aprobados(uow, franja) if p.user_id not in en_partida
    ]
    nombres = await PlayerNames.de_la_competicion(
        [*en_partida, *sin_partida], competicion.id, usuarios, uow
    )
    return TeeGroupsResponseDTO(
        round_id=franja.id.value,
        editable=await _editable(competicion, franja, partidas, zonas, ahora),
        unassigned_player_ids=[u.value for u in sin_partida],
        groups=[
            TeeGroupDTO(
                id=partida.id.value,
                number=partida.numero,
                tee_time=hoja.hora_de(partida.numero).strftime("%H:%M"),
                status=partida.estado.value,
                incomplete=partida.incompleta,
                players=[_jugador(j, partida, nombres) for j in partida.jugadores],
            )
            for partida in sorted(partidas, key=lambda p: p.numero)
        ],
    )


async def _editable(competicion, franja, partidas, zonas, ahora) -> bool:
    try:
        PlazoDePartidas.comprobar(
            competicion.status, await primera_salida(franja, zonas), ahora, partidas
        )
    except (PlazoCerradoError, PartidaEmpezadaError, ZonaDesconocidaError):
        return False
    return True


def _jugador(jugador, partida: Partida, nombres: dict[UserId, str]) -> TeeGroupPlayerDTO:
    marca = partida.marcadores.get(jugador.user_id)
    return TeeGroupPlayerDTO(
        user_id=jugador.user_id.value,
        name=nombres.get(jugador.user_id, ""),
        handicap=jugador.handicap,
        playing_handicap=jugador.playing_handicap,
        tee_color=jugador.tee_color.value,
        tee_gender=jugador.tee_gender.value if jugador.tee_gender else None,
        strokes_by_hole=list(jugador.golpes_por_hoyo),
        marks_user_id=marca.value if marca else None,
    )
