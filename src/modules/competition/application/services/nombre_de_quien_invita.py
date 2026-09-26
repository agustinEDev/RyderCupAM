"""
El nombre de quien invita es el que usa en ESA competición (#710).

Desde la BE #254 una competición enseña el nombre legal salvo que el jugador
pida su alias para ella. Las invitaciones seguían con el alias de la BE #239:
quien solo conocía al organizador por su nombre recibía una invitación de
«Trinx», también en el correo. Aquí se decide una vez, para los cuatro sitios
que lo pintan: enviarla por usuario, por email, «Mis invitaciones» y la lista
de la competición.
"""

from collections import defaultdict
from collections.abc import Iterable

from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId


async def quieren_su_nombre_legal(
    uow: CompetitionUnitOfWorkInterface, pares: Iterable[tuple[CompetitionId, UserId]]
) -> set[tuple[CompetitionId, UserId]]:
    """De cada (competición, quien invita), si en ella pidió su nombre legal.

    Se llama dentro de la transacción de la competición. Quien no está
    inscrito en ella no ha pedido nada: sale con su nombre de siempre.
    """
    # Una consulta por competición y no por invitación: una página puede traer
    # cien (CodeRabbit en la #381)
    por_competicion: dict[CompetitionId, set[UserId]] = defaultdict(set)
    for competition_id, inviter_id in pares:
        por_competicion[competition_id].add(inviter_id)
    legales: set[tuple[CompetitionId, UserId]] = set()
    for competition_id, invitan in por_competicion.items():
        for inscripcion in await uow.enrollments.find_by_user_ids_and_competition(
            list(invitan), competition_id
        ):
            if inscripcion.use_real_name:
                legales.add((competition_id, inscripcion.user_id))
    return legales


def nombre_de_quien_invita(usuario, quiere_su_nombre_legal: bool) -> str:
    """El nombre con el que se le enseña, o «Unknown» si ya no existe."""
    if usuario is None:
        return "Unknown"
    return usuario.display_name_or_legal(quiere_su_nombre_legal)
