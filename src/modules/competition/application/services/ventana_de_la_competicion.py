"""
VentanaDeLaCompeticion - La ventana para actualizar hándicaps de una competición, ahora (#251).

La usan el botón, la ficha y la propia pasada: «se corta 10 s por jugador antes
de empezar» vale para empezar una actualización y para la que esté en marcha
(Agustín, 7 oct 2026). Mira primero el estado, que no cuesta nada, y solo
después las franjas, las zonas y los inscritos.
"""

from datetime import datetime

from src.modules.competition.application.ports.competition_timezone import (
    ICompetitionTimezone,
)
from src.modules.competition.application.services.jornadas_de_la_competicion import (
    JornadasDeLaCompeticion,
    ZonaDesconocidaError,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.ventana_de_actualizacion import (
    Ventana,
    VentanaDeActualizacion,
)
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus


async def ventana_de(
    uow: CompetitionUnitOfWorkInterface,
    zonas: ICompetitionTimezone,
    competition: Competition,
    ahora: datetime,
) -> Ventana:
    """La ventana del botón para una competición, ahora."""
    stroke_play = competition.stroke_play is not None
    # Solo por el estado: sin consultas, y con su motivo
    sin_horas = VentanaDeActualizacion.calcular(
        stroke_play=stroke_play, status=competition.status, jornadas=[], jugadores=0, ahora=ahora
    )
    if not stroke_play or sin_horas.motivo == VentanaDeActualizacion.MOTIVO_ESTADO:
        return sin_horas
    try:
        jornadas = await JornadasDeLaCompeticion.de(
            await uow.rounds.find_by_competition(competition.id), zonas
        )
    except ZonaDesconocidaError as e:
        return Ventana(False, motivo=str(e))
    inscritos = await uow.enrollments.find_by_competition_and_status(
        competition.id, EnrollmentStatus.APPROVED
    )
    return VentanaDeActualizacion.calcular(
        stroke_play=True,
        status=competition.status,
        jornadas=jornadas,
        jugadores=len(inscritos),
        ahora=ahora,
    )
