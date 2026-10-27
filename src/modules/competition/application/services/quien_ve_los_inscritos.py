"""
Quién ve a los inscritos de una competición (release social 2, 27 oct 2026).

La regla de Agustín: la lista de inscritos y las solicitudes son del
organizador. Los demás ven las partidas cuando se publican; antes, solo a sus
amigos inscritos. En una privada, quien no está dentro no ve a nadie; el
invitado, a sus amigos; quien aceptó, a todos. Los capitanes (y sus vices) ven
a todos desde el principio: les hace falta para el draft.

«Publicada» no es un estado nuevo: es que ya hay partidas generadas (stroke
play) o equipos formados (Ryder), que es cuando sale el aviso de la salida.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from src.modules.competition.application.ports.amigos_interface import AmigosInterface
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.user.domain.value_objects.user_id import UserId


class Alcance(Enum):
    """Hasta dónde llega lo que ve de los inscritos."""

    # Todas las filas, en cualquier estado, con sus correos
    TODO = "TODO"
    # Todos los aprobados
    APROBADOS = "APROBADOS"
    # Sus amigos aprobados
    AMIGOS = "AMIGOS"
    # Nadie más que él
    NADA = "NADA"


@dataclass(frozen=True)
class LoQueVe:
    """A quién de los inscritos ve quien mira; a sí mismo, siempre."""

    alcance: Alcance
    quien: UserId
    amigos: frozenset[UserId] = field(default_factory=frozenset)

    @property
    def completa(self) -> bool:
        """Si ve a todos los aprobados (y entonces la agenda va entera)."""
        return self.alcance in (Alcance.TODO, Alcance.APROBADOS)

    def ve_a(self, user_id: UserId) -> bool:
        """Si ve a ese jugador (aprobado): su nombre, su fila, su sitio en la franja."""
        if user_id == self.quien or self.completa:
            return True
        return self.alcance is Alcance.AMIGOS and user_id in self.amigos


def _es_capitan(competition: Competition, quien: UserId) -> bool:
    return competition.ryder_cup is not None and competition.ryder_cup.tiene_cargo(quien)


def alcance(
    competition: Competition,
    quien: UserId,
    *,
    es_admin: bool,
    aprobado: bool,
    invitado: bool,
    publicada: bool,
) -> Alcance:
    """La regla, sin leer nada: con lo que se sabe de quien mira."""
    if es_admin or competition.is_creator(quien):
        return Alcance.TODO
    # El cargo se queda en la Ryder aunque se retire: cuenta si sigue dentro (revisor)
    if publicada or (aprobado and _es_capitan(competition, quien)):
        return Alcance.APROBADOS
    if competition.visibility is Visibility.PRIVATE:
        if aprobado:
            return Alcance.APROBADOS
        return Alcance.AMIGOS if invitado else Alcance.NADA
    return Alcance.AMIGOS


async def _publicada(uow: CompetitionUnitOfWorkInterface, competition: Competition) -> bool:
    if competition.stroke_play is not None:
        return bool(await uow.partidas.de_la_competicion(competition.id))
    return await uow.team_assignments.find_by_competition(competition.id) is not None


async def alcance_de(
    uow: CompetitionUnitOfWorkInterface,
    competition: Competition,
    quien: UserId,
    *,
    es_admin: bool = False,
    email: str | None = None,
    ahora: datetime | None = None,
) -> Alcance:
    """
    La regla con lo que hay que leer para aplicarla. Con el `uow` ya abierto.

    El reloj de la invitación es el suyo (`Invitation.is_expired`, hora local
    sin zona): con otro, se vería caducada aquí y viva al aceptarla.
    """
    if es_admin or competition.is_creator(quien):
        return Alcance.TODO
    aprobados = await uow.enrollments.find_by_competition_and_status(
        competition.id, EnrollmentStatus.APPROVED
    )
    invitado = competition.id in await uow.invitations.competiciones_con_invitacion_pendiente(
        quien, email, ahora or datetime.now()
    )
    return alcance(
        competition,
        quien,
        es_admin=False,
        aprobado=any(e.user_id == quien for e in aprobados),
        invitado=invitado,
        publicada=await _publicada(uow, competition),
    )


async def lo_que_ve(a: Alcance, quien: UserId, amigos: AmigosInterface | None) -> LoQueVe:
    """
    Con sus amigos, si le hacen falta. Fuera del `uow` de competiciones: los
    amigos se leen con el suyo. Sin puerto, ningún amigo.
    """
    if a is not Alcance.AMIGOS or amigos is None:
        return LoQueVe(a, quien)
    return LoQueVe(a, quien, await amigos.ids_de_los_amigos(quien))
