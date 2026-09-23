"""
Caso de Uso: los sobres que me faltan por entregar (FE #655).

Un capitan no puede enterarse de que tiene un sobre pendiente entrando sesion
por sesion en la agenda de cada competicion: el plazo le vence sin saberlo y la
aplicacion rellena su lista por handicap. Esto alimenta el bloque «Requiere tu
Atencion» del panel, que es donde el producto avisa de lo que hay que hacer: no
hay notificaciones push en ninguna parte.

Solo lo que se puede hacer AHORA: un sobre entregado, uno ya abierto o una
sesion con los partidos hechos no son nada que atender.
"""

from collections.abc import Callable
from datetime import UTC, datetime

from src.modules.competition.application.dto.envelope_dto import PendingEnvelopeDTO
from src.modules.competition.application.ports.competition_timezone import (
    ICompetitionTimezone,
)
from src.modules.competition.application.services.envelope_desk import (
    ORDEN_DE_SESION,
    EnvelopeDesk,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.setup_mode import SetupMode
from src.modules.user.domain.value_objects.user_id import UserId

# La misma tabla, por el nombre de la franja que viaja en el DTO
ORDEN_DE_SESION_POR_NOMBRE = {tipo.value: orden for tipo, orden in ORDEN_DE_SESION.items()}

# Un jugador veterano acumula filas de inscripcion —rechazos, retiros, altas de
# nuevo—, y el filtro de APROBADAS se aplica DESPUES del corte del repositorio:
# con el limite por defecto de 100 se perderian en silencio las competiciones
# mas antiguas y el aviso no saldria nunca
_TODAS_SUS_INSCRIPCIONES = 1000


class ListMyPendingEnvelopesUseCase:
    """Caso de uso para listar los sobres que un capitan tiene sin entregar."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        clock: Callable[[], datetime] | None = None,
        timezone_service: ICompetitionTimezone | None = None,
    ):
        """
        Args:
            uow: Unit of Work del modulo
            clock: El reloj del SERVIDOR. Se inyecta para poder moverlo en los
                tests, nunca para que lo ponga el cliente: con la hora del
                movil, un telefono atrasado resucitaria avisos de sesiones ya
                jugadas
            timezone_service: La zona del campo, que es lo que convierte la
                franja en una hora. Sin ella no hay plazo que vencer
        """
        self._uow = uow
        self._clock = clock or (lambda: datetime.now(UTC))
        self._timezone = timezone_service

    async def execute(self, user_id: UserId) -> list[PendingEnvelopeDTO]:
        """
        Devuelve los sobres que esa persona tiene sin entregar.

        Args:
            user_id: Quien pregunta

        Returns:
            Uno por sesion, de la mas proxima a la mas lejana. Vacio para quien
            no capitanea nada, que es casi todo el mundo
        """
        async with self._uow:
            ahora = self._clock()
            ahora = ahora if ahora.tzinfo else ahora.replace(tzinfo=UTC)
            desk = EnvelopeDesk(self._uow, None, timezone_service=self._timezone)
            pendientes: list[PendingEnvelopeDTO] = []
            for competition in await self._mis_competiciones(user_id):
                equipo = EnvelopeDesk.equipo_de(competition, user_id)
                if equipo is None:
                    continue
                for ronda in await self._uow.rounds.find_by_competition(competition.id):
                    if await self._toca_entregarlo(ronda, equipo, ahora, desk, competition):
                        pendientes.append(
                            PendingEnvelopeDTO(
                                round_id=ronda.id.value,
                                competition_id=competition.id.value,
                                competition_name=str(competition.name),
                                round_date=ronda.round_date,
                                session_type=ronda.session_type.value,
                                team=equipo,
                            )
                        )
            # Lo primero que hay que atender va primero: la sesion mas
            # proxima. La franja ordena por HORA y no por letra, que
            # alfabeticamente la tarde va antes que la mañana
            return sorted(
                pendientes,
                key=lambda p: (p.round_date, ORDEN_DE_SESION_POR_NOMBRE.get(p.session_type, 0)),
            )

    async def _mis_competiciones(self, user_id: UserId) -> list[Competition]:
        """Las competiciones en las que participa, por sus inscripciones.

        Un capitan siempre esta inscrito: nombrarlo lo fija en su equipo
        (RyderCupAm#320), y el organizador que capitanea tambien se inscribe.
        """
        competiciones = []
        vistas = set()
        for inscripcion in await self._uow.enrollments.find_by_user(
            user_id, limit=_TODAS_SUS_INSCRIPCIONES
        ):
            if inscripcion.status != EnrollmentStatus.APPROVED:
                continue
            if inscripcion.competition_id in vistas:
                continue
            vistas.add(inscripcion.competition_id)
            competition = await self._uow.competitions.find_by_id(inscripcion.competition_id)
            if competition is None:
                continue
            # Los sobres son el camino del tipo Ryder: en automatico y en
            # manual los partidos los pone la aplicacion o el organizador, y
            # avisar alli ofrece un paso que ese torneo no tiene. Peor: si el
            # capitan pica y entrega, generar los partidos se bloquea hasta
            # que los sobres se abran
            if competition.setup_mode != SetupMode.RYDER_CUP:
                continue
            # Cancelar no toca el estado de las rondas, asi que sus sesiones se
            # quedaban avisando hasta que pasaran las fechas
            if competition.status in (CompetitionStatus.CANCELLED, CompetitionStatus.COMPLETED):
                continue
            competiciones.append(competition)
        return competiciones

    async def _toca_entregarlo(
        self,
        ronda: Round,
        equipo: str,
        ahora: datetime,
        desk: EnvelopeDesk,
        competition: Competition,
    ) -> bool:
        """Si esa sesion tiene un sobre que ese equipo pueda entregar ahora.

        - Con los partidos ya generados no hay nada que decidir: el sobre ya
          dijo lo suyo, o la sesion no fue por sobres.
        - Sin equipos repartidos todavia no hay sobre posible.
        - Pasado el PLAZO tampoco: a esa hora los sobres se abren solos en
          cuanto alguien mire, asi que avisar manda al capitan a una pantalla
          que le rellena la lista por handicap delante. El plazo es una hora
          —6 h antes del comienzo—, no un dia: el de una sesion de mañana
          vence a las 00:00 de ESE mismo dia.
        - Sin zona del campo no hay plazo que vencer: esos sobres no se abren
          solos nunca, asi que siguen pendientes de verdad.
        """
        if ronda.status != RoundStatus.PENDING_MATCHES:
            return False
        plazo = await desk.programado_para(ronda, competition)
        if plazo is not None and ahora >= plazo:
            return False
        sobres = {s.team: s for s in await self._uow.envelopes.find_by_round(ronda.id)}
        # Abiertos ya no se tocan, ni el propio ni el del rival
        if any(not sobre.is_sealed() for sobre in sobres.values()):
            return False
        mio = sobres.get(equipo)
        return mio is None or not mio.is_submitted()
