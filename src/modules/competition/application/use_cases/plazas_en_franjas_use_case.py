"""
Casos de Uso: Coger y soltar plaza en una franja de stroke play (#251).

Decidido con Agustín el 6-8 oct 2026. Primero se entra en la competición como
siempre (pedir plaza, invitación o directa) y, ya aprobado, se eligen franjas:

- **El jugador**, mientras las inscripciones están abiertas.
- **El organizador** (o un admin), hasta iniciar: coloca y mueve a cualquiera.
- Con las reglas de `PlazasEnFranjas`: sitio, una por jornada, cupo de
  jornadas, y cambiarse de golpe («en lugar de»).

Con la competición bloqueada: dos a la vez por la última plaza, una sola.
"""

from datetime import UTC, datetime

from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
    PlazaEnFranjaError,
    RoundNotFoundError,
)
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.application.services.esperas_de_la_competicion import (
    EsperasDeLaCompeticion,
)
from src.modules.competition.application.services.partidas_del_jugador import (
    sacar_de_sus_partidas,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.plaza_en_franja import PlazaEnFranja
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.plazas_en_franjas import (
    PlazaNoPosibleError,
    PlazasEnFranjas,
)
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


async def _franja_y_competicion(
    uow: CompetitionUnitOfWorkInterface,
    round_id: RoundId,
    jugador: UserId,
    quien: UserId,
    is_admin: bool,
) -> tuple[Round, Competition]:
    """La franja y su competición (bloqueada), si quien pide puede tocar esa plaza."""
    franja = await uow.rounds.find_by_id(round_id)
    if franja is None:
        raise RoundNotFoundError(f"No existe la franja {round_id}")
    competicion = await uow.competitions.find_by_id_for_update(franja.competition_id)
    if competicion is None:
        raise CompetitionNotFoundError(f"No existe la competición {franja.competition_id}")
    # Releída con el candado: si a la vez la achicaron, la movieron o la borraron,
    # cuenta como quedó (code-review de la 3a)
    franja = await uow.rounds.find_by_id_for_update(round_id)
    if franja is None:
        raise RoundNotFoundError(f"No existe la franja {round_id}")
    organiza = is_admin or competicion.is_creator(quien)
    if not organiza and quien != jugador:
        raise NotCompetitionCreatorError("Solo el organizador elige la franja de otro jugador")
    # Quien organiza va con sus reglas, también para su propia plaza: también juega
    if organiza:
        if not competicion.allows_agenda_edits():
            raise PlazaEnFranjaError(
                "El organizador coloca a los jugadores en las franjas hasta iniciar la competición."
            )
    elif competicion.status is not CompetitionStatus.ACTIVE:
        raise PlazaEnFranjaError(
            "Las franjas se eligen hasta cerrar las inscripciones: después, solo el organizador."
        )
    return franja, competicion


class CogerPlazaUseCase:
    """Un jugador coge plaza en una franja (él mismo, o el organizador por él)."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        zonas: ICompetitionTimezone | None = None,
        actividad: CompetitionActivityPublisherInterface | None = None,
    ):
        """
        Args:
            zonas: Para no sacar a nadie de una partida que ya salió por su hora (#251)
            actividad: Para retirarle el aviso de salida de la franja que deja (G3)
        """
        self._uow = uow
        self._zonas = zonas
        self._actividad = AvisosDeActividad(actividad)

    async def execute(
        self,
        round_id: RoundId,
        jugador: UserId,
        quien: UserId,
        is_admin: bool = False,
        en_lugar_de: RoundId | None = None,
    ) -> PlazaEnFranja:
        """
        Args:
            round_id: La franja
            jugador: Quién coge plaza
            quien: Quién lo pide: el propio jugador o el organizador
            en_lugar_de: Una franja suya que deja a cambio, de golpe

        Raises:
            RoundNotFoundError, CompetitionNotFoundError, NotCompetitionCreatorError,
            PlazaEnFranjaError: fuera de plazo, sin estar inscrito o por las reglas
        """
        async with self._uow:
            franja, competicion = await _franja_y_competicion(
                self._uow, round_id, jugador, quien, is_admin
            )
            if competicion.stroke_play is None:
                raise PlazaEnFranjaError("Las franjas son de un Stableford o un Medal.")
            aprobados = await self._uow.enrollments.find_by_competition_and_status(
                competicion.id, EnrollmentStatus.APPROVED
            )
            suya = next((i for i in aprobados if i.user_id == jugador), None)
            if suya is None:
                raise PlazaEnFranjaError(
                    "Solo eligen franja los inscritos aprobados en la competición."
                )
            plazas = await self._uow.plazas.de_la_competicion(competicion.id)
            sesiones = {s.id: s for s in await self._uow.rounds.find_by_competition(competicion.id)}
            suyas = [sesiones[p.round_id] for p in plazas if p.user_id == jugador]
            # Su primera plaza, si entró esperando: ya juega (A2, 28 oct 2026). Los
            # demás tuvieron su aviso al entrar
            primera = not suyas and suya.entered_waiting
            try:
                PlazasEnFranjas.comprobar(
                    franja=franja,
                    suyas=suyas,
                    ocupadas=sum(1 for p in plazas if p.round_id == franja.id),
                    max_jornadas=competicion.stroke_play.max_matchdays_per_player,
                    en_lugar_de=en_lugar_de,
                )
            except PlazaNoPosibleError as e:
                raise PlazaEnFranjaError(str(e)) from e
            ahora = datetime.now(UTC)
            # Si deja una plaza que le dio la lista y aún no ha visto, la nueva hereda el
            # aviso: si no, nunca se enteraría de que tiene plaza (code-review de la 3b)
            sin_ver = en_lugar_de is not None and any(
                p.round_id == en_lugar_de
                and p.user_id == jugador
                and p.desde_espera is not None
                and p.vista is None
                for p in plazas
            )
            fotos = {}
            if en_lugar_de is not None:
                await self._uow.plazas.quitar(en_lugar_de, jugador)
                # Y de su partida en esa franja: en la nueva queda sin partida (D3)
                fotos = await sacar_de_sus_partidas(
                    self._uow, competicion.id, jugador, en_lugar_de, self._zonas, ahora
                )
            plaza = PlazaEnFranja.crear(
                competicion.id, franja.id, jugador, ahora, desde_espera=sin_ver
            )
            await self._uow.plazas.add(plaza)
            if suya.entered_waiting:
                suya.consigue_plaza()
                await self._uow.enrollments.update(suya)
            # Fuera de las listas de ese día; y la que deja, para el primero que espera
            esperas = EsperasDeLaCompeticion(self._uow)
            await esperas.tras_coger(competicion, jugador)
            if en_lugar_de is not None:
                await esperas.rellenar(competicion, en_lugar_de, ahora)
        # Ya guardado: pierde su aviso de la franja que deja, y a quien se
        # recoloca por su salida se le dice (G3)
        for tocada, (antes, despues) in fotos.items():
            await self._actividad.salidas_cambiadas(competicion, tocada, antes, despues)
        # Y a quien la lista dio la que deja (A3)
        await self._actividad.desde_la_espera(competicion, esperas.asignadas)
        if primera:
            await self._actividad.enrolled(competicion, suya, accepted_request=False)
        return plaza


class SoltarPlazaUseCase:
    """Un jugador deja su plaza en una franja (él mismo, o el organizador por él)."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        actividad: CompetitionActivityPublisherInterface | None = None,
    ):
        """
        Args:
            actividad: Para avisar a quien la lista da la plaza que se suelta (A3)
        """
        self._uow = uow
        self._actividad = AvisosDeActividad(actividad)

    async def execute(
        self, round_id: RoundId, jugador: UserId, quien: UserId, is_admin: bool = False
    ) -> None:
        """
        Raises:
            RoundNotFoundError, CompetitionNotFoundError, NotCompetitionCreatorError,
            PlazaEnFranjaError: fuera de plazo
        """
        async with self._uow:
            _, competicion = await _franja_y_competicion(
                self._uow, round_id, jugador, quien, is_admin
            )
            # Tras el cierre nadie se queda sin franja: se le cambia de una a otra,
            # y para quitarlo del todo se le retira (8 oct 2026)
            if competicion.status is not CompetitionStatus.ACTIVE:
                raise PlazaEnFranjaError(
                    "Con las inscripciones cerradas a un jugador se le cambia de franja, pero no "
                    "se le deja sin ninguna: para quitarlo, retíralo de la competición."
                )
            await self._uow.plazas.quitar(round_id, jugador)
            # La plaza libre, para el primero que espera (#251)
            esperas = EsperasDeLaCompeticion(self._uow)
            await esperas.rellenar(competicion, round_id, datetime.now(UTC))
        await self._actividad.desde_la_espera(competicion, esperas.asignadas)
