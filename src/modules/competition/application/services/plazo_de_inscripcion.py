"""
El plazo de inscripción, con su zona y su reloj (decidido el 15 nov 2026).

Las inscripciones cierran a las 12:00 del día anterior al torneo, a la hora del
campo. Desde ese momento nadie entra aunque la competición siga ACTIVE —manda
la hora, el estado la sigue—: ni apuntándose, ni invitado, ni aceptando una
invitación, ni aprobado por el organizador (C2). Salvo si el organizador la
abrió o reabrió ya pasado el plazo (R1, R2).

La regla vive en la entidad; aquí se le da la zona del campo y la hora de
ahora, que es lo que sabe la aplicación.
"""

from collections.abc import Callable
from datetime import date, datetime

from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.policies.enrollment_deadline import fecha_en_el_campo
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.shared.domain.services.instante_utc import ahora_en_utc


class EnrollmentDeadlinePassedError(Exception):
    """Pasado el plazo de inscripción no entra nadie (C2)."""

    error_code = "ENROLLMENT_DEADLINE_PASSED"
    MENSAJE = "La inscripción está cerrada."

    def __init__(self) -> None:
        super().__init__(self.MENSAJE)


class PlazoDeInscripcion:
    """Si el plazo de una competición ya no deja entrar a nadie, o le toca cerrarse."""

    def __init__(self, zonas: ICompetitionTimezone, reloj: Callable[[], datetime] = ahora_en_utc):
        self._zonas = zonas
        self._reloj = reloj

    def ahora(self) -> datetime:
        return self._reloj()

    @property
    def zonas(self) -> ICompetitionTimezone:
        return self._zonas

    async def queda_plazo(self, competition: Competition) -> bool:
        """Si su plazo todavía no ha llegado, con su zona (R3)."""
        zona = await self._zonas.for_competition(competition)
        return self.ahora() < competition.enrollment_deadline(zona)

    async def vencido(self, competition: Competition) -> bool:
        """
        Si ya no entra nadie por el plazo. En borrador, sin mirar la zona: quien
        la abra la abre tarde y entonces se entra (R2), y la zona cuesta una
        consulta.
        """
        if competition.status is CompetitionStatus.DRAFT:
            return False
        zona = await self._zonas.for_competition(competition)
        return competition.entries_closed_by_deadline(zona, self.ahora())

    async def le_toca_cerrarse(self, competition: Competition) -> bool:
        """Si abierta y con el plazo pasado (salvo R1/R2): la cierra el cierre automático."""
        if competition.status is not CompetitionStatus.ACTIVE:
            return False
        zona = await self._zonas.for_competition(competition)
        return competition.due_to_close(zona, self.ahora())

    async def exigir_abierto(self, competition: Competition) -> date:
        """
        Exige que el plazo deje entrar y devuelve qué día es en su campo, con una sola
        consulta de la zona para las dos cosas (F-01).

        Raises:
            EnrollmentDeadlinePassedError: Si el plazo ya no deja entrar a nadie
        """
        zona = await self._zonas.for_competition(competition)
        ahora = self.ahora()
        # La regla de la entidad, la misma que `vencido` (en borrador no cuenta, R2)
        if competition.entries_closed_by_deadline(zona, ahora):
            raise EnrollmentDeadlinePassedError()
        return fecha_en_el_campo(ahora, zona)


async def exigir_el_plazo(plazo: PlazoDeInscripcion | None, competition: Competition) -> date:
    """
    El plazo, si el caso de uso lo tiene: fuera de la API (tests, scripts) puede
    construirse sin él, como la zona de la apertura programada.

    Returns:
        Qué día es en el campo (F-01). Sin plazo, con la hora de ahora y la zona por
        defecto del plazo.

    Raises:
        EnrollmentDeadlinePassedError: Si el plazo ya no deja entrar a nadie
    """
    if plazo is not None:
        return await plazo.exigir_abierto(competition)
    return fecha_en_el_campo(ahora_en_utc(), None)
