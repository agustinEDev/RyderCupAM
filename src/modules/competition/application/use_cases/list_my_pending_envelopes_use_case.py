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
from datetime import date

from src.modules.competition.application.dto.envelope_dto import PendingEnvelopeDTO
from src.modules.competition.application.services.envelope_desk import EnvelopeDesk
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.user.domain.value_objects.user_id import UserId


class ListMyPendingEnvelopesUseCase:
    """Caso de uso para listar los sobres que un capitan tiene sin entregar."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        today: Callable[[], date] | None = None,
    ):
        """
        Args:
            uow: Unit of Work del modulo
            today: El dia de hoy segun el SERVIDOR. Se inyecta para poder
                moverlo en los tests, nunca para que lo ponga el cliente: con
                la fecha del movil, un telefono atrasado resucitaria avisos de
                sesiones ya jugadas
        """
        self._uow = uow
        self._today = today or date.today

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
            hoy = self._today()
            pendientes: list[PendingEnvelopeDTO] = []
            for competition in await self._mis_competiciones(user_id):
                equipo = EnvelopeDesk.equipo_de(competition, user_id)
                if equipo is None:
                    continue
                for ronda in await self._uow.rounds.find_by_competition(competition.id):
                    if await self._toca_entregarlo(ronda, equipo, hoy):
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
            # Lo primero que hay que atender va primero: la sesion mas proxima
            return sorted(pendientes, key=lambda p: (p.round_date, p.session_type))

    async def _mis_competiciones(self, user_id: UserId) -> list[Competition]:
        """Las competiciones en las que participa, por sus inscripciones.

        Un capitan siempre esta inscrito: nombrarlo lo fija en su equipo
        (RyderCupAm#320), y el organizador que capitanea tambien se inscribe.
        """
        competiciones = []
        for inscripcion in await self._uow.enrollments.find_by_user(user_id):
            if inscripcion.status != EnrollmentStatus.APPROVED:
                continue
            competition = await self._uow.competitions.find_by_id(inscripcion.competition_id)
            if competition is not None:
                competiciones.append(competition)
        return competiciones

    async def _toca_entregarlo(self, ronda: Round, equipo: str, hoy: date) -> bool:
        """Si esa sesion tiene un sobre que ese equipo pueda entregar hoy.

        - Con los partidos ya generados no hay nada que decidir: el sobre ya
          dijo lo suyo, o la sesion no fue por sobres.
        - Sin equipos repartidos todavia no hay sobre posible.
        - Una sesion pasada no se atiende: su plazo vencio y la aplicacion
          relleno lo que faltara. El DIA de la sesion todavia cuenta, que hasta
          que se abren se puede corregir.
        """
        if ronda.status != RoundStatus.PENDING_MATCHES:
            return False
        if ronda.round_date < hoy:
            return False
        sobres = {s.team: s for s in await self._uow.envelopes.find_by_round(ronda.id)}
        # Abiertos ya no se tocan, ni el propio ni el del rival
        if any(not sobre.is_sealed() for sobre in sobres.values()):
            return False
        mio = sobres.get(equipo)
        return mio is None or not mio.is_submitted()
