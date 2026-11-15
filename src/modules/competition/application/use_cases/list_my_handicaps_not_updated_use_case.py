"""
Caso de Uso: Mis hándicaps sin actualizar con la RFEG, para «Requiere tu Atención».

Decidido con Agustín el 15 nov 2026 (H1-H6). Al terminar una actualización de
hándicaps se avisa por correo y en Actividad; esto es lo que el panel enseña
mientras siga siendo cierto:

- **Al organizador**, cada competición suya con jugadores sin actualizar con
  la RFEG (H2).
- **Al jugador español al que la RFEG no encontró**, cada competición en la
  que le pasó (H3). Si la RFEG falló, nada (H4); a un extranjero, nunca (H6).

Se calcula al vuelo con la última actualización de cada competición: deja de
salir solo al empezar la competición o cuando la RFEG lo encuentra (H5, D1),
sin nada que borrar. No escribe nada.

Lo pide el panel de todo el mundo cada vez que se abre (T2): del organizador
se leen solo sus competiciones cerradas, por la base; cada competición se
calcula una vez; y como jugador se lee solo su propio resultado.
"""

from src.modules.competition.application.dto.competition_dto import (
    HandicapNotFoundAsPlayerDTO,
    HandicapsNotUpdatedAsOrganizerDTO,
    MyHandicapsNotUpdatedDTO,
    PendingHandicapPlayerDTO,
)
from src.modules.competition.application.services.player_names import PlayerNames
from src.modules.competition.application.services.sin_actualizar_de_la_competicion import (
    SinActualizarDeLaCompeticion,
)
from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    ActualizacionDeHandicaps,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

# Un organizador con mucho historial no puede perder el aviso por el corte por
# defecto del repositorio, que son 100 (como las sesiones sin partidos)
_TODAS_LAS_SUYAS = 1000


class ListMyHandicapsNotUpdatedUseCase:
    """Lo que «Requiere tu Atención» enseña de los hándicaps con la RFEG."""

    def __init__(
        self, uow: CompetitionUnitOfWorkInterface, user_repository: UserRepositoryInterface
    ):
        self._uow = uow
        self._users = user_repository

    async def execute(self, user_id: UserId) -> MyHandicapsNotUpdatedDTO:
        """
        Args:
            user_id: Quien pregunta

        Returns:
            Como organizador y como jugador; vacío casi siempre
        """
        async with self._uow:
            como_organizador, ya_vistas = await self._como_organizador(user_id)
            return MyHandicapsNotUpdatedDTO(
                as_organizer=como_organizador,
                as_player=await self._como_jugador(user_id, ya_vistas),
            )

    async def _como_organizador(
        self, user_id: UserId
    ) -> tuple[list[HandicapsNotUpdatedAsOrganizerDTO], dict[CompetitionId, bool]]:
        """
        Las suyas cerradas con alguien sin actualizar; y, de cada una mirada, si
        él mismo es un no encontrado, para no calcularla otra vez como jugador.
        """
        items = []
        vistas: dict[CompetitionId, bool] = {}
        for competicion in await self._uow.competitions.find_by_filters(
            creator_id=user_id, status=CompetitionStatus.CLOSED, limit=_TODAS_LAS_SUYAS
        ):
            actualizacion = await self._terminada(competicion)
            if actualizacion is None:
                continue
            hecho = await SinActualizarDeLaCompeticion.de(
                self._uow, self._users, competicion, actualizacion
            )
            vistas[competicion.id] = user_id in hecho.no_encontrados
            if not hecho.para_el_organizador:
                continue
            nombres = await PlayerNames.de_la_competicion(
                hecho.para_el_organizador, competicion.id, self._users, self._uow
            )
            items.append(
                HandicapsNotUpdatedAsOrganizerDTO(
                    competition_id=competicion.id.value,
                    competition_name=str(competicion.name),
                    count=len(hecho.para_el_organizador),
                    players=[
                        PendingHandicapPlayerDTO(user_id=u.value, name=nombres.get(u, ""))
                        for u in hecho.para_el_organizador
                    ],
                )
            )
        return items, vistas

    async def _como_jugador(
        self, user_id: UserId, ya_vistas: dict[CompetitionId, bool]
    ) -> list[HandicapNotFoundAsPlayerDTO]:
        """Donde sigue inscrito y la RFEG no lo encontró, leyendo solo lo suyo."""
        inscripciones = {
            i.competition_id: i
            for i in await self._uow.enrollments.find_by_user(user_id)
            if i.status == EnrollmentStatus.APPROVED
        }
        if not inscripciones:
            return []
        jugador = None
        items = []
        for competicion in await self._uow.competitions.find_by_ids(list(inscripciones)):
            if competicion.id in ya_vistas:
                no_encontrado = ya_vistas[competicion.id]
            else:
                actualizacion = await self._terminada(competicion)
                if actualizacion is None:
                    continue
                jugador = jugador or await self._users.find_by_id(user_id)
                if jugador is None:
                    return []
                no_encontrado = await SinActualizarDeLaCompeticion.no_encontrado(
                    self._uow, jugador, inscripciones[competicion.id], competicion, actualizacion
                )
            if no_encontrado:
                items.append(
                    HandicapNotFoundAsPlayerDTO(
                        competition_id=competicion.id.value,
                        competition_name=str(competicion.name),
                    )
                )
        return items

    async def _terminada(self, competicion: Competition) -> ActualizacionDeHandicaps | None:
        """
        La última actualización, si el panel la enseña: con la competición
        cerrada y sin empezar (al empezar desaparece, H5) y la actualización
        terminada (H1). De las demás no se lee nada más.
        """
        if competicion.status is not CompetitionStatus.CLOSED:
            return None
        actualizacion = await self._uow.handicap_updates.ultima_de(competicion.id)
        if actualizacion is None or not SinActualizarDeLaCompeticion.terminada(actualizacion):
            return None
        return actualizacion
