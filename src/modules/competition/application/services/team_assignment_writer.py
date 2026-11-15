"""
TeamAssignmentWriter - Dejar los equipos guardados (BE #320, FE #653).

Los equipos se pueden repartir de tres maneras —la aplicacion sola, a mano, o
eligiendo los capitanes en la sala de draft— pero guardarlos es siempre lo
mismo: sustituir el reparto anterior, avisar a la competicion de que sus
equipos cambiaron y soltar las rondas que estaban esperandolos.

Esta en un solo sitio a proposito: la sala de draft que se olvidara de mover
las rondas dejaria la agenda atascada sin decir por que, y el olvido no lo ve
ningun test de la otra ruta.
"""

from dataclasses import dataclass

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.team_assignment_mode import TeamAssignmentMode
from src.modules.user.domain.value_objects.user_id import UserId


@dataclass(frozen=True)
class Deshacible:
    """Los equipos formados que aún se pueden deshacer, con sus sesiones."""

    reparto: TeamAssignment
    sesiones: list[Round]


class TeamAssignmentWriter:
    """Guarda un reparto de equipos, venga de donde venga."""

    @staticmethod
    async def guardar(
        uow: CompetitionUnitOfWorkInterface,
        competition: Competition,
        mode: TeamAssignmentMode,
        team_a_player_ids: list[UserId],
        team_b_player_ids: list[UserId],
    ) -> TeamAssignment:
        """
        Args:
            uow: Unit of Work ya abierto por el caso de uso
            competition: La competicion, con su fila bloqueada
            mode: Como se repartieron
            team_a_player_ids: Los del equipo A
            team_b_player_ids: Los del equipo B

        Returns:
            El reparto guardado
        """
        # Defensivo: desde el 29 oct 2026 no se forman equipos encima de otros
        # (TEAMS_FORMED), pero si quedara uno, dos repartos no conviven
        anterior = await uow.team_assignments.find_by_competition(competition.id)
        if anterior:
            await uow.team_assignments.delete(anterior.id)

        assignment = TeamAssignment.create(
            competition_id=competition.id,
            mode=mode,
            team_a_player_ids=team_a_player_ids,
            team_b_player_ids=team_b_player_ids,
        )
        await uow.team_assignments.add(assignment)

        # Los subcapitanes se eligen dentro de cada equipo, y el equipo ha
        # cambiado (BE #320)
        competition.teams_reassigned()
        await uow.competitions.update(competition)

        for round_entity in await uow.rounds.find_by_competition(competition.id):
            if round_entity.status == RoundStatus.PENDING_TEAMS:
                round_entity.mark_teams_assigned()
                await uow.rounds.update(round_entity)

        return assignment

    @staticmethod
    async def deshacible(
        uow: CompetitionUnitOfWorkInterface, competition: Competition
    ) -> Deshacible | None:
        """
        Los equipos formados, si aún se pueden deshacer: sin empezar y sin partidos.
        Sin tocar nada: para invitar con los equipos formados (B3, 15 nov 2026), y lo
        que lee lo usa `deshacer` sin volver a pedirlo.
        """
        # Solo antes de empezar: en juego, o con partidos, el reparto ya es lo jugado
        if competition.status not in (CompetitionStatus.ACTIVE, CompetitionStatus.CLOSED):
            return None
        # Un reparto es de una Ryder: sin su pieza, nada que deshacer (revisor)
        if competition.ryder_cup is None:
            return None
        reparto = await uow.team_assignments.find_by_competition(competition.id)
        if reparto is None:
            return None
        sesiones = await uow.rounds.find_by_competition(competition.id)
        for sesion in sesiones:
            if sesion.status not in (RoundStatus.PENDING_TEAMS, RoundStatus.PENDING_MATCHES):
                return None
            if await uow.matches.find_by_round(sesion.id):
                return None
        return Deshacible(reparto, sesiones)

    @staticmethod
    async def deshacer(uow: CompetitionUnitOfWorkInterface, competition: Competition) -> bool:
        """
        Deshace los equipos: vuelve a como estaba antes de formarlos (release
        social 2, decidido el 27 oct 2026).

        Cuando sale un jugador de un equipo formado, los equipos quedaban
        descompensados y al generar partidos uno se quedaba sin jugar sin que
        nadie avisara. Solo sin partidos: con alguno ya generado no se toca.
        Los capitanes se quedan (se nombran antes de repartir); los
        subcapitanes, la sala de draft y los sobres se van, y las sesiones
        vuelven a esperar equipos.

        Args:
            uow: Unit of Work ya abierto por el caso de uso
            competition: La competicion, con su fila bloqueada

        Returns:
            Si se deshicieron (False: no habia reparto, o ya hay partidos)
        """
        deshacible = await TeamAssignmentWriter.deshacible(uow, competition)
        if deshacible is None:
            return False
        sesiones = deshacible.sesiones

        await uow.team_assignments.delete(deshacible.reparto.id)
        # Los subcapitanes se eligen dentro de cada equipo (BE #320)
        competition.teams_reassigned()
        await uow.competitions.update(competition)
        await uow.drafts.delete_by_competition(competition.id)
        for sesion in sesiones:
            await uow.envelopes.delete_by_round(sesion.id)
            if sesion.status == RoundStatus.PENDING_MATCHES:
                sesion.mark_teams_unassigned()
                await uow.rounds.update(sesion)
        return True
