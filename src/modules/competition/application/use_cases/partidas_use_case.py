"""
Casos de Uso: Las partidas de una franja de stroke play (#251, PR 4).

Decidido con Agustín el 6-9 oct 2026:

- Las genera **el organizador** (o un admin), franja a franja, **del cierre de
  inscripciones a la primera salida** y mientras no haya salido ninguna (D11).
- Entran quienes tienen plaza en la franja y la inscripción aprobada.
- Por hándicap fijado, en el orden que elija; a igual hándicap, quien cogió antes
  la plaza; si sobrara uno, la penúltima cede uno (D6).
- Sin zona horaria en el campo no se sabe cuándo sale nadie: no se generan (D10).

Con la competición bloqueada, como las plazas: dos a la vez, una sola.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from src.modules.competition.application.dto.partidas_dto import (
    GenerateTeeGroupsRequestDTO,
    TeeGroupsResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
    PartidasError,
    RoundNotFoundError,
)
from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.application.services.jugadores_de_la_partida import (
    JugadoresDeLaPartida,
)
from src.modules.competition.application.services.vista_de_la_franja import (
    con_plaza_y_aprobados,
    primera_salida,
    vista_de_la_franja,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.plazo_de_partidas import PlazoDePartidas
from src.modules.competition.domain.services.reparto_de_partidas import (
    ParaRepartir,
    RepartoDePartidas,
)
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


async def _franja_del_organizador(
    uow: CompetitionUnitOfWorkInterface, round_id: RoundId, quien: UserId, is_admin: bool
) -> tuple[Round, Competition]:
    """La franja y su competición (bloqueada), si quien pide la organiza."""
    franja = await uow.rounds.find_by_id(round_id)
    if franja is None:
        raise RoundNotFoundError(f"No existe la franja {round_id}")
    competicion = await uow.competitions.find_by_id_for_update(franja.competition_id)
    if competicion is None:
        raise CompetitionNotFoundError(f"No existe la competición {franja.competition_id}")
    # Releída con el candado: si a la vez la cambiaron, cuenta como quedó
    franja = await uow.rounds.find_by_id_for_update(round_id)
    if franja is None:
        raise RoundNotFoundError(f"No existe la franja {round_id}")
    if not (is_admin or competicion.is_creator(quien)):
        raise NotCompetitionCreatorError("Solo el organizador hace las partidas")
    if franja.hoja_de_salidas is None:
        raise PartidasError("Solo hay partidas en las franjas de un Stableford o un Medal.")
    return franja, competicion


class GenerarPartidasUseCase:
    """El organizador reparte una franja en partidas (y reemplaza las que hubiera)."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        jugadores: JugadoresDeLaPartida,
        zonas: ICompetitionTimezone,
        user_repository: UserRepositoryInterface,
        reloj: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._uow = uow
        self._jugadores = jugadores
        self._zonas = zonas
        self._usuarios = user_repository
        self._reloj = reloj

    async def execute(
        self,
        round_id: UUID,
        request: GenerateTeeGroupsRequestDTO,
        quien: UserId,
        is_admin: bool,
    ) -> TeeGroupsResponseDTO:
        """
        Raises:
            RoundNotFoundError, CompetitionNotFoundError: Si no existen
            NotCompetitionCreatorError: Si no lo pide el organizador ni un admin
            PartidasError: Si no es una franja de stroke play
            ZonaDesconocidaError: Si el campo no tiene zona horaria (D10)
            PlazoCerradoError: Fuera de plazo (D11)
            PartidaEmpezadaError: Si ya salió alguna
            RepartoImposibleError: Con un solo jugador
            JugadoresSinHandicapError, JugadoresSinBarraError: Con todos los afectados
        """
        async with self._uow:
            franja, competicion = await _franja_del_organizador(
                self._uow, RoundId(round_id), quien, is_admin
            )
            ahora = self._reloj()
            existentes = await self._uow.partidas.de_la_franja(franja.id)
            PlazoDePartidas.comprobar(
                competicion.status, await primera_salida(franja, self._zonas), ahora, existentes
            )

            plazas = await con_plaza_y_aprobados(self._uow, franja)
            fotos = await self._jugadores.construir(
                self._uow, competicion, franja, [p.user_id for p in plazas]
            )
            hoja = franja.hoja_de_salidas
            if hoja is None:  # comprobado al leer la franja: para mypy
                raise PartidasError("Solo hay partidas en las franjas de un Stableford o un Medal.")
            grupos = RepartoDePartidas.repartir(
                [ParaRepartir(p.user_id, fotos[p.user_id].handicap, p.creada) for p in plazas],
                hoja.jugadores_por_partida,
                request.order,
            )
            partidas = [
                Partida.crear(competicion.id, franja.id, numero, [fotos[u] for u in grupo])
                for numero, grupo in enumerate(grupos, start=1)
            ]
            await self._uow.partidas.reemplazar_franja(franja.id, partidas)
            vista = await vista_de_la_franja(
                self._uow, competicion, franja, partidas, self._zonas, self._usuarios, ahora
            )
            await self._uow.commit()
        return vista
