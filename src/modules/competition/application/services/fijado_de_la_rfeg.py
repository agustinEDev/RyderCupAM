"""
El hándicap que da la RFEG tras el cierre pasa a ser el fijado (#251; D4, 16 nov 2026).

Lo usan la pasada de una actualización y el jugador que pide su hándicap a la
RFEG desde su perfil: en un stroke play cerrado, su hándicap fijado pasa a ser
el nuevo, las categorías se rehacen y sus partidas sin salir cambian de
hándicap de juego. Quien llama decide si toca (competición bloqueada, ventana
abierta).
"""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from src.modules.competition.application.ports.competition_timezone import (
    ICompetitionTimezone,
)
from src.modules.competition.application.services.handicaps_al_cerrar import HandicapsAlCerrar
from src.modules.competition.application.services.jugadores_de_la_partida import (
    JugadoresDeLaPartida,
)
from src.modules.competition.application.services.partidas_de_la_franja import (
    recalcular_su_handicap,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.golf_course.domain.repositories.golf_course_repository import (
    IGolfCourseRepository,
)
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


@dataclass(frozen=True)
class Herramientas:
    """
    Lo que hace falta para una parte de la pasada, sobre una misma sesión.

    La competición y los usuarios TIENEN que compartir sesión: el hándicap nuevo
    del perfil se guarda con los usuarios y se confirma al cerrar la unidad de
    trabajo de la competición. Con sesiones distintas se perdería sin error
    (CodeRabbit en la #507).
    """

    competiciones: CompetitionUnitOfWorkInterface
    usuarios: UserRepositoryInterface
    # Para la ventana: la pasada se corta 10 s por jugador antes de la salida
    zonas: ICompetitionTimezone
    # Para rehacer el hándicap de juego de sus partidas al corregir el fijado (#251,
    # G1). Sin campos, las partidas no se tocan (los tests que no las usan)
    campos: IGolfCourseRepository | None = None


# Da herramientas nuevas cada vez, y las cierra al salir
FabricaDeHerramientas = Callable[[], AbstractAsyncContextManager[Herramientas]]


async def corregir_el_fijado(
    uow: CompetitionUnitOfWorkInterface,
    h: Herramientas,
    competicion: Competition,
    user_id: UserId,
    nuevo: Decimal,
    ahora: datetime,
) -> None:
    """Su fijado y las categorías, y sus partidas sin salir con su hándicap de juego (G1)."""
    await HandicapsAlCerrar(uow, h.usuarios).corregir(competicion, user_id, nuevo)
    if h.campos is not None:
        await recalcular_su_handicap(
            uow,
            JugadoresDeLaPartida(h.campos, h.usuarios),
            competicion,
            user_id,
            zonas=h.zonas,
            ahora=ahora,
        )
