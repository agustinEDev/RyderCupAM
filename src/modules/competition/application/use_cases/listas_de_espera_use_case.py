"""
Casos de Uso: Las listas de espera de las franjas de stroke play (#251).

Decidido con Agustín (#251, 20 sep; y 8 oct 2026):

- **Esperar**: el propio jugador, aprobado, en una franja llena de un día en
  que no juega, mientras las inscripciones están abiertas.
- **Dejar de esperar**: él, o el organizador.
- **Requiere tu atención**: las plazas que le asignó la lista y aún no ha
  visto, hasta que pulsa «Entendido».
"""

from datetime import UTC, datetime

from src.modules.competition.application.dto.round_match_dto import AssignedPlaceDTO
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
    PlazaEnFranjaError,
    RoundNotFoundError,
)
from src.modules.competition.application.services.esperas_de_la_competicion import (
    esta_jugada,
)
from src.modules.competition.domain.entities.espera_en_franja import EsperaEnFranja
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.listas_de_espera import (
    EsperaNoPosibleError,
    ListasDeEspera,
)
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


class EsperarUseCase:
    """El jugador se apunta a la lista de espera de una franja llena."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, round_id: RoundId, jugador: UserId, quien: UserId) -> EsperaEnFranja:
        """
        Raises:
            RoundNotFoundError, CompetitionNotFoundError, NotCompetitionCreatorError,
            PlazaEnFranjaError: fuera de plazo, sin estar inscrito o por las reglas
        """
        if quien != jugador:
            raise NotCompetitionCreatorError("Cada uno se apunta a su propia lista de espera")
        async with self._uow:
            franja = await self._uow.rounds.find_by_id(round_id)
            if franja is None:
                raise RoundNotFoundError(f"No existe la franja {round_id}")
            competicion = await self._uow.competitions.find_by_id_for_update(franja.competition_id)
            if competicion is None:
                raise CompetitionNotFoundError(f"No existe la competición {franja.competition_id}")
            # Releída con el candado: si la borraron a la vez, 404 y no un 500
            franja = await self._uow.rounds.find_by_id_for_update(round_id)
            if franja is None:
                raise RoundNotFoundError(f"No existe la franja {round_id}")
            if esta_jugada(franja):
                raise PlazaEnFranjaError("La franja ya se está jugando o se jugó.")
            if competicion.stroke_play is None:
                raise PlazaEnFranjaError("Las listas de espera son de un Stableford o un Medal.")
            if competicion.status is not CompetitionStatus.ACTIVE:
                raise PlazaEnFranjaError(
                    "Las listas de espera funcionan hasta cerrar las inscripciones."
                )
            aprobados = await self._uow.enrollments.find_by_competition_and_status(
                competicion.id, EnrollmentStatus.APPROVED
            )
            if jugador not in {i.user_id for i in aprobados}:
                raise PlazaEnFranjaError("Solo esperan los inscritos aprobados en la competición.")
            plazas = await self._uow.plazas.de_la_competicion(competicion.id)
            esperas = await self._uow.esperas.de_la_competicion(competicion.id)
            sesiones = {s.id: s for s in await self._uow.rounds.find_by_competition(competicion.id)}
            try:
                ListasDeEspera.comprobar_espera(
                    franja=franja,
                    suyas=[sesiones[p.round_id] for p in plazas if p.user_id == jugador],
                    ocupadas=sum(1 for p in plazas if p.round_id == round_id),
                    max_jornadas=competicion.stroke_play.max_matchdays_per_player,
                    ya_espera=any(e.round_id == round_id and e.user_id == jugador for e in esperas),
                )
            except EsperaNoPosibleError as e:
                raise PlazaEnFranjaError(str(e)) from e
            espera = EsperaEnFranja.crear(competicion.id, round_id, jugador, datetime.now(UTC))
            await self._uow.esperas.add(espera)
        return espera


class DejarDeEsperarUseCase:
    """El jugador (o el organizador) lo saca de la lista de espera de una franja."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(
        self, round_id: RoundId, jugador: UserId, quien: UserId, is_admin: bool = False
    ) -> None:
        """
        Raises:
            RoundNotFoundError, CompetitionNotFoundError, NotCompetitionCreatorError
        """
        async with self._uow:
            franja = await self._uow.rounds.find_by_id(round_id)
            if franja is None:
                raise RoundNotFoundError(f"No existe la franja {round_id}")
            # Bloqueada: si a la vez se libera una plaza, no se le asigna a quien sale
            competicion = await self._uow.competitions.find_by_id_for_update(franja.competition_id)
            if competicion is None:
                raise CompetitionNotFoundError(f"No existe la competición {franja.competition_id}")
            if quien != jugador and not (is_admin or competicion.is_creator(quien)):
                raise NotCompetitionCreatorError(
                    "Solo el organizador saca a otro jugador de la lista de espera"
                )
            await self._uow.esperas.quitar(round_id, jugador)


class MisPlazasAsignadasUseCase:
    """«Requiere tu atención»: las plazas que te asignó la lista y aún no has visto."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, user_id: UserId) -> list[AssignedPlaceDTO]:
        """Las más antiguas primero."""
        async with self._uow:
            plazas = await self._uow.plazas.asignadas_sin_ver(user_id)
            competiciones = {}
            for competition_id in {p.competition_id for p in plazas}:
                competiciones[competition_id] = await self._uow.competitions.find_by_id(
                    competition_id
                )
            resultado = []
            for plaza in sorted(plazas, key=lambda p: p.desde_espera or p.creada):
                competicion = competiciones.get(plaza.competition_id)
                # Cancelada o terminada: ya no requiere su atención
                if competicion is None or competicion.status.is_final():
                    continue
                franja = await self._uow.rounds.find_by_id(plaza.round_id)
                if franja is None or franja.hoja_de_salidas is None:
                    continue
                resultado.append(
                    AssignedPlaceDTO(
                        competition_id=competicion.id.value,
                        competition_name=str(competicion.name),
                        round_id=franja.id.value,
                        round_date=franja.round_date,
                        session_type=franja.session_type.value,
                        first_tee_time=franja.hoja_de_salidas.primera_salida,
                        assigned_at=plaza.desde_espera or plaza.creada,
                    )
                )
        return resultado


class EntendidoUseCase:
    """El jugador ya ha visto la plaza que le asignó la lista."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, round_id: RoundId, user_id: UserId) -> None:
        """Solo la suya: se marca por jugador y franja."""
        async with self._uow:
            await self._uow.plazas.marcar_vista(round_id, user_id, datetime.now(UTC))
