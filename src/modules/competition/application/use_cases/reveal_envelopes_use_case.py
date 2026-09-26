"""
Caso de Uso: Abrir los sobres de una sesion (FE #655).

Se abren los dos a la vez y salen los enfrentamientos, cruzando las dos listas
por posicion. **El sobre que no llego lo rellena la aplicacion** —por handicap,
juntando al mejor con el peor en los formatos de dos— y **no pisa al capitan
que si entrego**: el que llego a tiempo no se queda sin su lista por culpa del
que se olvido (decidido el 20 sep).
"""

from datetime import UTC, datetime
from uuid import UUID

from src.modules.competition.application.dto.envelope_dto import (
    RevealEnvelopesResponseDTO,
    matchups_to_dto,
)
from src.modules.competition.application.exceptions import NotCompetitionCreatorError
from src.modules.competition.application.ports.competition_timezone import (
    ICompetitionTimezone,
)
from src.modules.competition.application.services.envelope_desk import (
    EnvelopeDesk,
)
from src.modules.competition.domain.entities.envelope import EnvelopeAlreadyRevealedError
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


class EarlyRevealNeedsBothCaptainsError(Exception):
    """Abrir antes de hora lo deciden los dos capitanes, no uno ni el organizador (BE #374)."""

    pass


class RevealEnvelopesUseCase:
    """Caso de uso para abrir los dos sobres de una sesion."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_repository,
        timezone_service: ICompetitionTimezone | None = None,
        generador=None,
    ):
        """
        Args:
            uow: Unit of Work del modulo
            user_repository: De donde sale el handicap para el sobre que falte
            timezone_service: La zona del campo donde se juega. Hace falta para
                saber si esta sesion llega a tener plazo: sin el, la respuesta
                es que si, y manda la regla estricta
            generador: Crea los partidos en cuanto se abren (BE #361)
        """
        self._uow = uow
        self._desk = EnvelopeDesk(
            uow, user_repository, timezone_service=timezone_service, generador=generador
        )

    async def execute(
        self, round_id: UUID, user_id: UserId, is_admin: bool = False
    ) -> RevealEnvelopesResponseDTO:
        """
        Abre los dos sobres y devuelve los enfrentamientos.

        Args:
            round_id: La sesion
            user_id: Quien los abre: el organizador o uno de los capitanes
            is_admin: Si es administrador

        Returns:
            Los enfrentamientos y que equipos llevaban sobre automatico

        Raises:
            RoundNotFoundError: Si la sesion no existe
            NotCompetitionCreatorError: Si no es el organizador ni un capitan
            EarlyRevealNeedsBothCaptainsError: Si la sesion tiene plazo: antes de
                hora solo se abren con el permiso de los dos capitanes
            EnvelopeAlreadyRevealedError: Si ya estaban abiertos
        """
        async with self._uow:
            ronda, competition = await self._desk.ronda_y_competicion(
                RoundId(round_id), bloquear=True
            )
            self._desk.comprobar_que_la_sesion_admite_sobres(ronda)
            es_capitan = self._desk.equipo_de(competition, user_id) is not None
            arbitra = is_admin or competition.is_creator(user_id)
            if not arbitra and not es_capitan:
                raise NotCompetitionCreatorError(
                    "Los sobres de esta sesión son de sus dos capitanes"
                )
            # Abrir antes de hora es decision de LOS DOS capitanes (BE #374):
            # cada uno da su permiso al entregar, y se abren cuando estan los
            # dos. Ni un capitan solo ni el organizador los abren a mano: el
            # orden de juego es de los capitanes, y el relleno automatico es
            # PREDECIBLE —por handicap—, asi que abrir por su cuenta dejaria
            # armar la lista propia para ganar todos los cruces.
            #
            # El capitan que no aparece no deja nada atascado: al vencer el
            # plazo se abren solos y la aplicacion rellena lo que falte.
            #
            # Salvo en una sesion SIN plazo —campo sin zona horaria—, que no se
            # abre sola nunca: ahi el que arbitra conserva la llave, aunque
            # falte un sobre, o la sesion se queda atascada para siempre.
            #
            # Unos sobres ya abiertos pasan por aqui —rellenar deja entradas
            # dentro—, y el error de «ya estaban abiertos» lo da el bucle
            sin_plazo = self._desk.sin_plazo_que_vencer(
                await self._desk.programado_para(ronda, competition)
            )
            sobres_ahora = {
                sobre.team: sobre for sobre in await self._uow.envelopes.find_by_round(ronda.id)
            }
            # Ya abiertos, el motivo es ese, no el permiso que faltaría
            if any(not sobre.is_sealed() for sobre in sobres_ahora.values()):
                raise EnvelopeAlreadyRevealedError("Los sobres de esta sesión ya se abrieron")
            # La misma regla que enseña la vista: vive en un solo sitio
            if not self._desk.puede_abrirlos(
                competition, user_id, sobres_ahora, is_admin=is_admin, sin_plazo=sin_plazo
            ):
                raise EarlyRevealNeedsBothCaptainsError(
                    # Sin prometer hora: hay sesiones que tardan en abrirse
                    # (la anterior sin acabar) o no se abren solas (un equipo
                    # impar en parejas), y la pantalla ya enseña el plazo
                    "Antes de hora, los sobres solo se abren si los dos "
                    "capitanes lo piden al entregar"
                )

            ahora = datetime.now(UTC).replace(tzinfo=None)
            automaticos = []
            sobres = {}
            for team in ("A", "B"):
                sobre = await self._desk.sobre_de(ronda, team, crear=True)
                if not sobre.is_sealed():
                    raise EnvelopeAlreadyRevealedError("Los sobres de esta sesión ya se abrieron")
                if not sobre.is_submitted():
                    jugadores = await self._desk.jugadores_de(competition, team)
                    sobre.fill(await self._desk.handicaps_de(competition, jugadores), ahora=ahora)
                    automaticos.append(team)
                sobre.reveal()
                await self._uow.envelopes.update(sobre)
                sobres[team] = sobre

            # Con los enfrentamientos decididos, los partidos salen ya (BE #361)
            await self._desk.generar_los_partidos(ronda, competition)

            return RevealEnvelopesResponseDTO(
                round_id=ronda.id.value,
                matchups=matchups_to_dto(sobres["A"], sobres["B"]),
                filled_automatically=automaticos,
            )
