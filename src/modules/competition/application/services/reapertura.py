"""
Reabrir las inscripciones, en un solo sitio (15 nov 2026).

Lo hace el organizador con su botón, y también mover el torneo cuando lo había
cerrado el plazo y el plazo nuevo está en el futuro (R3). Los dos tienen que
hacer lo mismo: la entidad vuelve a ACTIVE (y olvida el reparto de categorías),
la actualización de hándicaps a medias se corta, las partidas que no han
salido se borran, con sus avisos de salida retirados, y las invitaciones que
esperaban vuelven a pendientes, con su «ya puedes aceptar» (P2).
"""

import logging
from collections.abc import Callable
from datetime import datetime

from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.application.ports.invitation_email_service_interface import (
    IInvitationEmailService,
)
from src.modules.competition.application.services.actualizaciones_de_handicaps import (
    ActualizacionesDeHandicaps,
)
from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.application.services.baja_de_la_competicion import (
    exigir_sin_draft_abierto,
)
from src.modules.competition.application.services.invitaciones_al_cerrar import (
    AlReabrir,
    al_reabrir,
)
from src.modules.competition.application.services.nombre_de_quien_invita import (
    nombre_de_quien_invita,
    quieren_su_nombre_legal,
)
from src.modules.competition.application.services.partidas_del_jugador import (
    salidas_por_hora,
)
from src.modules.competition.application.services.salidas_de_la_ronda import (
    Salidas,
    de_las_partidas,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)


class Reapertura:
    """Reabre una competición cerrada, con todo lo que eso arrastra."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        zonas: ICompetitionTimezone | None,
        reloj: Callable[[], datetime],
        actividad: AvisosDeActividad,
        correos: IInvitationEmailService | None = None,
        user_uow: UserUnitOfWorkInterface | None = None,
    ):
        """
        Args:
            zonas: Para no borrar las partidas que ya salieron por su hora (#251).
                Sin ellas, solo cuenta el estado de la partida
            actividad: Para retirar los avisos de salida de las partidas que se
                borran (G4)
            correos: Para reenviar la invitación a quien no tiene cuenta (O2); sin
                él, no se reenvía
            user_uow: Para el nombre de quien invita en ese correo
        """
        self._correos = correos
        self._user_uow = user_uow
        self._uow = uow
        self._zonas = zonas
        self._reloj = reloj
        self._actividad = actividad
        # Los aprobados al reabrir: sus avisos de hándicaps con la RFEG se retiran
        self._inscritos: list[UserId] = []
        # Las invitaciones que esperaban: las que vuelven y las que se quedan sin
        # plaza, para avisar ya guardado (P2, O1, C1)
        self._invitaciones = AlReabrir()

    async def reabrir(self, competition: Competition) -> dict[RoundId, Salidas]:
        """
        Dentro de la transacción de quien llama, con la competición bloqueada.

        Returns:
            Por franja, las salidas de las partidas borradas: para `avisar`

        Raises:
            CompetitionStateError: Si no está cerrada
            DraftInProgressError: Con la sala de draft abierta: se acaba antes (O1)
        """
        # Con la sala de draft abierta no se reabre: la sala no se enteraría de
        # quien entrase (Agustín, 15 nov 2026)
        await exigir_sin_draft_abierto(self._uow, competition.id)
        # Con la hora: reabierta pasado el plazo, ya no se cierra sola (R1)
        competition.reopen_enrollments(now=self._reloj())

        # La actualización de hándicaps que esté a medias se corta: al volver
        # a cerrar empieza otra (#251)
        await ActualizacionesDeHandicaps(self._uow, None).cortar(competition.id)

        # Las invitaciones que esperaban vuelven a pendientes, todas, si queda sitio; si
        # no, sin plaza (P2, O1, C1, C2: 15 nov 2026). Sin ninguna, ni se mira el sitio
        esperan = await self._uow.invitations.find_by_competition_and_status_for_update(
            competition.id, InvitationStatus.ON_HOLD
        )
        if esperan:
            self._invitaciones = await al_reabrir(
                self._uow,
                competition.id,
                esperan,
                sin_sitio=await self._sin_sitio(competition),
            )

        # Las partidas que no han salido se borran: pueden entrar y salir
        # jugadores, y se vuelven a generar al cerrar. Las que salieron (por su
        # estado o por su hora: hasta la PR 5 nadie las pasa a IN_PROGRESS) se
        # quedan: lo jugado no se borra (D1, #251)
        borradas = await self._borrar_las_que_no_salieron(competition.id)

        # Sus avisos de hándicaps con la RFEG dejan de ser ciertos (CodeRabbit, #864)
        self._inscritos = [
            i.user_id
            for i in await self._uow.enrollments.find_by_competition_and_status(
                competition.id, EnrollmentStatus.APPROVED
            )
        ]
        return borradas

    async def avisar(self, competition: Competition, borradas: dict[RoundId, Salidas]) -> None:
        """
        Ya guardada: sin partida no hay salida, y se retiran sus avisos (G4); y
        los de hándicaps con la RFEG, que dejan de ser ciertos (#864); y a cada
        invitado que esperaba, «ya puedes aceptar» (P2).
        """
        for round_id, salidas in borradas.items():
            await self._actividad.salidas_cambiadas(competition, round_id, salidas, {})
        await self.avisar_handicaps(competition)
        await self.avisar_a_los_invitados(competition)

    async def avisar_handicaps(self, competition: Competition) -> None:
        """Los avisos de hándicaps con la RFEG de la competición reabierta se retiran (#864)."""
        await self._actividad.handicaps_not_updated_withdrawn(competition)
        await self._actividad.handicap_not_found_withdrawn(competition, self._inscritos)

    async def avisar_a_los_invitados(self, competition: Competition) -> None:
        """
        Ya guardada: a cada invitado que vuelve, «ya puedes aceptar» (P2), y a quien
        no tiene cuenta, el correo de invitación otra vez (O2); a quien se quedó sin
        plaza, «no hubo plaza» (O1, C1).
        """
        vuelven = self._invitaciones.vuelven
        await self._actividad.invitations_acceptable_again(competition, vuelven)
        await self._actividad.invitations_no_place(competition, self._invitaciones.sin_plaza)
        await self._reenviar(competition, [i for i in vuelven if i.invitee_user_id is None])

    async def _reenviar(self, competition: Competition, sin_cuenta: list[Invitation]) -> None:
        """El correo de invitación de siempre, con la caducidad nueva (O2). Lo que falle
        —leer quién invita o mandarlo— se apunta y se sigue: la reapertura ya está hecha."""
        if self._correos is None or not sin_cuenta:
            return
        try:
            nombres = await self._nombres_de_quien_invita(competition, sin_cuenta)
            for invitacion in sin_cuenta:
                await self._correos.send_invitation_email(
                    to_email=invitacion.invitee_email,
                    invitee_name=None,
                    inviter_name=nombres[invitacion.inviter_id],
                    competition_name=str(competition.name),
                    personal_message=invitacion.personal_message,
                    expires_at=invitacion.expires_at,
                )
        except Exception:
            logger.warning(
                "Could not resend the invitation emails of competition %s",
                competition.id.value,
                exc_info=True,
            )

    async def _nombres_de_quien_invita(
        self, competition: Competition, sin_cuenta: list[Invitation]
    ) -> dict[UserId, str]:
        """El nombre que usa cada uno en ESTA competición (#710), como al invitar: una
        lectura de los nombres legales y una de usuarios, para todos."""
        quienes = list(dict.fromkeys(i.inviter_id for i in sin_cuenta))
        async with self._uow:
            legales = await quieren_su_nombre_legal(
                self._uow, [(competition.id, quien) for quien in quienes]
            )
        usuarios = {}
        if self._user_uow is not None:
            async with self._user_uow:
                usuarios = {u.id: u for u in await self._user_uow.users.find_by_ids(quienes)}
        return {
            quien: nombre_de_quien_invita(usuarios.get(quien), (competition.id, quien) in legales)
            for quien in quienes
        }

    async def _sin_sitio(self, competition: Competition) -> bool:
        """
        Si no cabe nadie más (O1, C1): con partidos ya generados (solo los tiene una
        Ryder), o sin ninguna plaza libre del máximo. Con franjas el cupo son sus
        plazas, y por ese número no se llena. Las sesiones, leídas una vez.
        """
        sesiones = await self._uow.rounds.find_by_competition(competition.id)
        for sesion in sesiones:
            if await self._uow.matches.find_by_round(sesion.id):
                return True
        if any(s.hoja_de_salidas is not None for s in sesiones):
            return False
        aprobadas = await self._uow.enrollments.count_approved_by_competition(competition.id)
        return aprobadas >= competition.max_players

    async def _borrar_las_que_no_salieron(
        self, competition_id: CompetitionId
    ) -> dict[RoundId, Salidas]:
        """
        Returns:
            Por franja, las salidas de los jugadores de las partidas borradas
        """
        partidas = await self._uow.partidas.de_la_competicion(competition_id)
        ahora = self._reloj()
        salidas: set[PartidaId] = set()
        franjas: dict[RoundId, Round] = {}
        for round_id in {p.round_id for p in partidas}:
            franja = await self._uow.rounds.find_by_id(round_id)
            if franja is not None:
                franjas[round_id] = franja
                de_la_franja = [p for p in partidas if p.round_id == round_id]
                salidas |= await salidas_por_hora(franja, de_la_franja, self._zonas, ahora)
        borrar = [p for p in partidas if not p.empezada and p.id not in salidas]
        await self._uow.partidas.borrar(borrar)
        return {
            round_id: de_las_partidas(franja, [p for p in borrar if p.round_id == round_id])
            for round_id, franja in franjas.items()
            if any(p.round_id == round_id for p in borrar)
        }
