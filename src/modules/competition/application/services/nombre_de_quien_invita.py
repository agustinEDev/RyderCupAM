"""
El nombre de quien invita es el que usa en ESA competición (#710).

Desde la BE #254 una competición enseña el nombre legal salvo que el jugador
pida su alias para ella. Las invitaciones seguían con el alias de la BE #239:
quien solo conocía al organizador por su nombre recibía una invitación de
«Trinx», también en el correo. Aquí se decide una vez, para los cuatro sitios
que lo pintan: enviarla por usuario, por email, «Mis invitaciones» y la lista
de la competición.
"""

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
    legales: set[tuple[CompetitionId, UserId]] = set()
    for competition_id, inviter_id in set(pares):
        inscripcion = await uow.enrollments.find_by_user_and_competition(inviter_id, competition_id)
        if inscripcion is not None and inscripcion.use_real_name:
            legales.add((competition_id, inviter_id))
    return legales


def nombre_de_quien_invita(usuario, quiere_su_nombre_legal: bool) -> str:
    """El nombre con el que se le enseña, o «Unknown» si ya no existe."""
    if usuario is None:
        return "Unknown"
    return usuario.display_name_or_legal(quiere_su_nombre_legal)
