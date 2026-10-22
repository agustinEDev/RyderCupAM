"""
Las salidas de cada jugador en una ronda, para avisarle cuando cambian (G1-G4).

Se saca una foto de la ronda antes de tocarla y otra despues, y se comparan:
solo se avisa a quien le cambia algo de verdad (otra hora, otros compañeros u
otros rivales), y quien sale de la ronda pierde su aviso.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace

from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    TeeTimeAssignment,
)
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId

Salidas = dict[UserId, TeeTimeAssignment]


def de_las_partidas(
    franja: Round, partidas: Sequence[Partida], hoja: HojaDeSalidas | None = None
) -> Salidas:
    """
    La salida de cada jugador de una franja de stroke play: la hora de su
    partida y sus compañeros de grupo.

    Args:
        hoja: La hoja con la que contar la hora; sin ella, la de la franja. Al
            cambiar la hoja se comparan las dos sobre las mismas partidas
    """
    hoja = hoja or franja.hoja_de_salidas
    salidas: Salidas = {}
    for partida in partidas:
        # Una partida fuera de la hoja se queda sin hora en vez de tumbar la
        # accion que avisa (CodeRabbit BE #638)
        hora = (
            hoja.hora_de(partida.numero)
            if hoja and 1 <= partida.numero <= hoja.numero_de_salidas
            else None
        )
        # El grupo asignado, falte quien falte: que alguien no se presente o se
        # retire no cambia la salida de nadie (revision final del 22 oct). El
        # que falta queda fuera de juego: su aviso no se toca
        juegan = set(partida.quedan)
        for jugador in partida.user_ids:
            salidas[jugador] = TeeTimeAssignment(
                user_id=jugador,
                round_date=franja.round_date,
                session_type=franja.session_type,
                tee_time=hora,
                partner_ids=tuple(u for u in partida.user_ids if u != jugador),
                opponent_ids=(),
                out_of_play=jugador not in juegan,
            )
    return salidas


def de_los_partidos(ronda: Round, partidos: Sequence[Match]) -> Salidas:
    """El partido de cada jugador de una sesion de Ryder: sin hora, con su compañero y rivales."""
    salidas: Salidas = {}
    for partido in partidos:
        equipo_a = tuple(p.user_id for p in partido.team_a_players)
        equipo_b = tuple(p.user_id for p in partido.team_b_players)
        for suyos, rivales in ((equipo_a, equipo_b), (equipo_b, equipo_a)):
            for jugador in suyos:
                salidas[jugador] = TeeTimeAssignment(
                    user_id=jugador,
                    round_date=ronda.round_date,
                    session_type=ronda.session_type,
                    tee_time=None,
                    partner_ids=tuple(u for u in suyos if u != jugador),
                    opponent_ids=rivales,
                    match_id=partido.id,
                )
    return salidas


def cambios(
    antes: Mapping[UserId, TeeTimeAssignment], despues: Mapping[UserId, TeeTimeAssignment]
) -> tuple[list[TeeTimeAssignment], list[UserId]]:
    """
    Las salidas que avisar y quienes pierden la suya.

    Returns:
        Las de quien entra en la ronda (`changed` False) o cambia de verdad
        (`changed` True), y quienes ya no estan en ella. A quien le queda lo
        mismo no se le dice nada, ni a quien esta fuera de juego (no se
        presento o se retiro): lo suyo ya no es una salida que avisar
    """
    avisos = [
        replace(salida, changed=True) if jugador in antes else salida
        for jugador, salida in despues.items()
        if not salida.out_of_play
        and (jugador not in antes or not salida.same_slot_as(antes[jugador]))
    ]
    fuera = [jugador for jugador in antes if jugador not in despues]
    return avisos, fuera


async def salidas_vigentes(uow: CompetitionUnitOfWorkInterface, round_id: RoundId) -> Salidas:
    """
    Las salidas que hay AHORA en la ronda, leidas en la transaccion abierta de
    quien llama (no abre ni confirma la suya): quien publica los avisos las
    relee con el torneo bloqueado, en vez de fiarse de la foto de una accion
    que puede llegar tarde (G3, revision del 22 oct 2026).

    Sin ronda —se borro— no hay salida para nadie.
    """
    ronda = await uow.rounds.find_by_id(round_id)
    if ronda is None:
        return {}
    if ronda.hoja_de_salidas is not None:
        salidas = de_las_partidas(ronda, await uow.partidas.de_la_franja(round_id))
    else:
        salidas = de_los_partidos(ronda, await uow.matches.find_by_round(round_id))
    # Solo quien sigue inscrito: quien se dio de baja de una Ryder sigue en su
    # partido hasta que lo reasignen, y no puede recuperar su aviso (revision
    # final del 22 oct). Una lectura para toda la ronda
    inscritos = {
        i.user_id
        for i in await uow.enrollments.find_by_competition_and_status(
            ronda.competition_id, EnrollmentStatus.APPROVED
        )
    }
    return {u: s for u, s in salidas.items() if u in inscritos}
