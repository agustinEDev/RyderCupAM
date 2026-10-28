"""
Lo jugado de una privada: sus clasificaciones y sus partidas (tabla del 27 oct 2026).

La regla de Agustín: en una privada, quien no está no ve nada, tampoco
publicada. Está dentro el organizador, un admin y quien tiene su inscripción
aprobada (los capitanes lo son). La llave de quien está fuera es su Actividad:
si le sale un evento de un amigo en esa competición, ve la clasificación y la
partida de ese amigo; las demás partidas, no. Las públicas siguen abiertas.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum

from src.modules.competition.application.ports.eventos_de_amigos_interface import (
    EventosDeAmigosInterface,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.user.domain.value_objects.user_id import UserId


class Acceso(Enum):
    """Hasta dónde llega lo que ve de lo jugado."""

    # Todo: está dentro, o es pública
    ENTERO = "ENTERO"
    # La clasificación y las partidas de sus amigos con evento (la llave)
    SUS_AMIGOS = "SUS_AMIGOS"
    # Nada
    NADA = "NADA"


class NoPuedeVerloError(Exception):
    """Lo jugado de una privada en la que no está, sin llave para verlo."""


@dataclass(frozen=True)
class LoJugadoQueVe:
    """Lo que ve de lo jugado quien mira; con la llave, de qué amigos."""

    acceso: Acceso
    amigos: frozenset[UserId] = field(default_factory=frozenset)
    # Quien mira: su propia partida la ve siempre, aunque se retirara (/code-review)
    quien: UserId | None = None

    @property
    def ve_la_clasificacion(self) -> bool:
        """Si ve la clasificación: dentro, o con la llave."""
        return self.acceso is not Acceso.NADA

    def ve_la_partida(self, jugadores: Iterable[UserId]) -> bool:
        """
        Si ve una partida (o un partido): entero, la suya, o si juega en ella
        un amigo con evento.
        """
        if self.acceso is Acceso.ENTERO:
            return True
        jugadores = list(jugadores)
        if self.quien is not None and self.quien in jugadores:
            return True
        return self.acceso is Acceso.SUS_AMIGOS and any(j in self.amigos for j in jugadores)


async def esta_dentro(
    uow: CompetitionUnitOfWorkInterface,
    competition: Competition,
    quien: UserId,
    *,
    es_admin: bool = False,
) -> bool:
    """
    Si ve lo jugado entero: es pública, o la organiza, o es admin, o tiene su
    inscripción aprobada. Con el `uow` abierto y la competición ya leída: solo
    pregunta por su inscripción, y solo si hace falta.
    """
    if competition.visibility is Visibility.PUBLIC or es_admin or competition.is_creator(quien):
        return True
    suya = await uow.enrollments.find_by_user_and_competition(quien, competition.id)
    return suya is not None and suya.status == EnrollmentStatus.APPROVED


async def exigir_la_partida(
    competition_id: CompetitionId,
    quien: UserId,
    jugadores: Iterable[UserId],
    eventos: EventosDeAmigosInterface | None,
) -> None:
    """
    Fuera del `uow`, de quien está fuera: que vea esa partida (o ese partido).

    Raises:
        NoPuedeVerloError: Si no está dentro, no juega en ella ni tiene la llave
    """
    ve = await con_la_llave(False, competition_id, quien, eventos)
    if not ve.ve_la_partida(jugadores):
        raise NoPuedeVerloError


async def exigir_la_clasificacion(
    competition_id: CompetitionId,
    quien: UserId,
    eventos: EventosDeAmigosInterface | None,
) -> LoJugadoQueVe:
    """
    Fuera del `uow`, de quien está fuera: lo que ve de la clasificación, para
    filtrar los partidos.

    Raises:
        NoPuedeVerloError: Si no está dentro ni tiene la llave
    """
    ve = await con_la_llave(False, competition_id, quien, eventos)
    if not ve.ve_la_clasificacion:
        raise NoPuedeVerloError
    return ve


async def con_la_llave(
    dentro: bool,
    competition_id: CompetitionId,
    quien: UserId,
    eventos: EventosDeAmigosInterface | None,
) -> LoJugadoQueVe:
    """
    Lo que ve de lo jugado quien está dentro (o no): fuera, con la llave de su
    Actividad. Fuera del `uow` de competiciones. Sin puerto, ninguna llave.
    """
    if dentro:
        return LoJugadoQueVe(Acceso.ENTERO)
    if eventos is None:
        return LoJugadoQueVe(Acceso.NADA, quien=quien)
    amigos = await eventos.amigos_con_evento_en(quien, competition_id)
    return LoJugadoQueVe(Acceso.SUS_AMIGOS if amigos else Acceso.NADA, amigos, quien)
