"""
Los equipos de una Ryder cambian sin deshacerse (release social 3, tabla del 28 oct 2026).

Cambia lo decidido el 27 oct (deshacer el reparto al entrar o salir alguien):

- **T1** Quien entra con los equipos formados queda sin equipo; el organizador
  le pone en uno.
- **T2** Quien sale (se retira o le quitan) sale solo de su equipo. Si era
  capitán sube su subcapitán; si era subcapitán, el puesto queda vacío (eso lo
  hace `Competition.handle_withdrawal`, antes).
- **T3** El organizador o un admin mete a un jugador en A o en B, o le mueve:
  nunca a un capitán; un subcapitán movido pierde el puesto.
- **T4** Cualquier cambio devuelve a borrador los dos sobres entregados, y a los
  dos capitanes se les avisa.
- **T5** Para generar partidos, nadie sin equipo y A = B (contando solo a los
  inscritos), mientras los equipos se puedan tocar: con partidos ya no se mueve
  a nadie, y quien no tenga equipo no juega, como antes.
- **A1** Volver a formar los equipos (AssignTeams) es otro cambio: los sobres,
  también los revelados, a borrador y aviso a los capitanes (29 oct 2026).
- Con partidos generados en alguna sesión, el reparto ya es lo jugado: no se toca.

Va dentro de la transacción de quien llama, con la competición bloqueada.
"""

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.user.domain.value_objects.user_id import UserId

# A = B para generar, como dice la tabla aprobada: formar equipos ya exige un
# número par, y con uno de diferencia las sesiones por parejas no se rellenan
DIFERENCIA_MAXIMA = 0


class CaptainCannotMoveError(Exception):
    """A un capitán no se le saca de su equipo (T3)."""

    error_code = "CAPTAIN_CANNOT_MOVE"


class TeamsLockedError(Exception):
    """Los equipos no se pueden tocar: sin formar, con partidos, empezada o sin ese jugador."""

    error_code = "TEAMS_LOCKED"


class PlayersWithoutTeamError(Exception):
    """Para generar partidos, nadie puede quedar sin equipo (T5)."""

    error_code = "PLAYERS_WITHOUT_TEAM"


class TeamsUnbalancedError(Exception):
    """Para generar partidos, A y B con los mismos jugadores (T5)."""

    error_code = "TEAMS_UNBALANCED"


async def _sesiones_sin_partidos(
    uow: CompetitionUnitOfWorkInterface, competition: Competition
) -> list[Round] | None:
    """Sus sesiones, si en ninguna hay partidos todavía; si los hay, None."""
    sesiones = await uow.rounds.find_by_competition(competition.id)
    for sesion in sesiones:
        if await uow.matches.find_by_round(sesion.id):
            return None
    return sesiones


async def _reparto_que_se_toca(
    uow: CompetitionUnitOfWorkInterface, competition: Competition
) -> tuple[TeamAssignment, list[Round]] | None:
    """El reparto y sus sesiones, si se puede tocar: Ryder abierta o cerrada, sin partidos."""
    if competition.ryder_cup is None:
        return None
    if competition.status not in (CompetitionStatus.ACTIVE, CompetitionStatus.CLOSED):
        return None
    reparto = await uow.team_assignments.find_by_competition(competition.id)
    if reparto is None:
        return None
    sesiones = await _sesiones_sin_partidos(uow, competition)
    if sesiones is None:
        return None
    return reparto, sesiones


async def _reabrir_los_sobres(uow: CompetitionUnitOfWorkInterface, sesiones: list[Round]) -> bool:
    """Los sobres entregados, a borrador (T4). Si se reabrió alguno."""
    alguno = False
    for sesion in sesiones:
        for sobre in await uow.envelopes.find_by_round(sesion.id):
            if sobre.reabrir():
                await uow.envelopes.update(sobre)
                alguno = True
    return alguno


def _capitanes(competition: Competition) -> tuple[UserId, ...]:
    """Los dos capitanes que haya, a quienes se avisa de que sus equipos cambiaron."""
    ryder_cup = competition.require_ryder_cup()
    return tuple(c for c in (ryder_cup.captain("A"), ryder_cup.captain("B")) if c is not None)


async def al_salir(
    uow: CompetitionUnitOfWorkInterface, competition: Competition, user_id: UserId
) -> tuple[UserId, ...]:
    """
    Sale de su equipo; los demás se quedan (T2). La capitanía ya la resolvió
    `handle_withdrawal`.

    Returns:
        Los capitanes a avisar (T4); vacío si no cambió nada
    """
    tocable = await _reparto_que_se_toca(uow, competition)
    if tocable is None:
        return ()
    reparto, sesiones = tocable
    if not reparto.quitar(user_id):
        return ()
    await uow.team_assignments.update(reparto)
    await _reabrir_los_sobres(uow, sesiones)
    return _capitanes(competition)


async def al_entrar(
    uow: CompetitionUnitOfWorkInterface, competition: Competition
) -> tuple[UserId, ...]:
    """
    Entra alguien con los equipos formados: queda sin equipo (T1) y los sobres,
    a borrador (T4).

    Returns:
        Los capitanes a avisar; vacío si no había equipos que tocar
    """
    return await _sobres_a_borrador(uow, competition)


async def al_formarlos_de_nuevo(
    uow: CompetitionUnitOfWorkInterface, competition: Competition
) -> tuple[UserId, ...]:
    """
    Se forman otros equipos encima de los que había (A1): los sobres, a borrador
    (T4). Se llama con el reparto nuevo ya guardado.

    Returns:
        Los capitanes a avisar; vacío si ya hay partidos
    """
    return await _sobres_a_borrador(uow, competition)


async def _sobres_a_borrador(
    uow: CompetitionUnitOfWorkInterface, competition: Competition
) -> tuple[UserId, ...]:
    """Los sobres a borrador y los capitanes a avisar, si los equipos se pueden tocar."""
    tocable = await _reparto_que_se_toca(uow, competition)
    if tocable is None:
        return ()
    _, sesiones = tocable
    await _reabrir_los_sobres(uow, sesiones)
    return _capitanes(competition)


async def mover(
    uow: CompetitionUnitOfWorkInterface, competition: Competition, user_id: UserId, equipo: str
) -> tuple[UserId, ...]:
    """
    El organizador mete a un jugador en un equipo o le cambia de uno a otro (T3).

    Returns:
        Los capitanes a avisar; vacío si ya estaba en ese equipo

    Raises:
        TeamsLockedError: Sin equipos, con partidos, fuera de plazo o sin ese inscrito
        CaptainCannotMoveError: Si es capitán
        ValueError: Si el equipo no es A ni B
    """
    tocable = await _reparto_que_se_toca(uow, competition)
    if tocable is None:
        raise TeamsLockedError(
            "Los equipos solo se cambian formados, sin partidos y antes de empezar."
        )
    reparto, sesiones = tocable
    inscripcion = await uow.enrollments.find_by_user_and_competition(user_id, competition.id)
    if inscripcion is None or inscripcion.status is not EnrollmentStatus.APPROVED:
        raise TeamsLockedError("Solo se coloca en un equipo a un inscrito.")
    if user_id in _capitanes(competition):
        raise CaptainCannotMoveError("A un capitán no se le cambia de equipo.")
    if reparto.get_player_team(user_id) == equipo:
        return ()
    reparto.poner(user_id, equipo)
    await uow.team_assignments.update(reparto)
    # Un subcapitán movido deja su puesto (T3)
    if competition.handle_withdrawal(user_id):
        await uow.competitions.update(competition)
    await _reabrir_los_sobres(uow, sesiones)
    return _capitanes(competition)


async def exigir_equipos_completos(
    uow: CompetitionUnitOfWorkInterface, competition: Competition, reparto: TeamAssignment
) -> None:
    """
    Antes de generar partidos (T5). Solo mientras los equipos se pueden tocar:
    con partidos en alguna sesión ya no se mueve a nadie, y exigirlo dejaría la
    siguiente sesión bloqueada para siempre (revisor, 28 oct 2026).

    Raises:
        PlayersWithoutTeamError: Si un inscrito no está en ningún equipo
        TeamsUnbalancedError: Si A y B no tienen los mismos inscritos
    """
    if await _reparto_que_se_toca(uow, competition) is None:
        return
    aprobados = {
        i.user_id
        for i in await uow.enrollments.find_by_competition_and_status(
            competition.id, EnrollmentStatus.APPROVED
        )
    }
    sin_equipo = [u for u in aprobados if reparto.get_player_team(u) is None]
    if sin_equipo:
        raise PlayersWithoutTeamError(
            f"Hay {len(sin_equipo)} inscritos sin equipo: ponlos en uno antes de generar."
        )
    # Solo los inscritos: el reparto puede guardar a quien se retiró (revisor)
    en_a = sum(1 for u in reparto.team_a_player_ids if u in aprobados)
    en_b = sum(1 for u in reparto.team_b_player_ids if u in aprobados)
    if abs(en_a - en_b) > DIFERENCIA_MAXIMA:
        raise TeamsUnbalancedError("Los equipos no tienen los mismos jugadores: iguálalos.")
