"""
Casos de Uso: Las partidas de una franja de stroke play (#251, PR 4).

Decidido con Agustín el 6-9 oct 2026:

- Las genera **el organizador** (o un admin), franja a franja, **del cierre de
  inscripciones a la primera salida** y mientras no haya salido ninguna (D11).
- Entran quienes tienen plaza en la franja y la inscripción aprobada.
- Por hándicap fijado, en el orden que elija; a igual hándicap, quien cogió antes
  la plaza; si sobrara uno, la penúltima cede uno (D6).
- Sin zona horaria en el campo no se sabe cuándo sale nadie: no se generan (D10).
- Mover, reordenar, cambiar marcadores y borrar, con el mismo plazo (D11) y las
  reglas de `MovimientosDePartidas` (D13, M1-M3).

Con la competición bloqueada, como las plazas: dos a la vez, una sola.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.modules.competition.application.dto.partidas_dto import (
    GenerateTeeGroupsRequestDTO,
    MyTeeGroupDTO,
    MyTeeGroupsResponseDTO,
    TeeGroupsResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
    PartidaNotFoundError,
    PartidasError,
    RoundNotFoundError,
)
from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.application.services.jugadores_de_la_partida import (
    JugadoresDeLaPartida,
)
from src.modules.competition.application.services.player_names import PlayerNames
from src.modules.competition.application.services.vista_de_la_franja import (
    con_plaza_y_aprobados,
    partida_dto,
    primera_salida,
    vista_de_la_franja,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.marcadores_en_cadena import (
    MarcadoresInvalidosError,
)
from src.modules.competition.domain.services.movimientos_de_partidas import (
    MovimientoImposibleError,
    MovimientosDePartidas,
)
from src.modules.competition.domain.services.plazo_de_partidas import PlazoDePartidas
from src.modules.competition.domain.services.reparto_de_partidas import (
    ParaRepartir,
    RepartoDePartidas,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

SOLO_EN_FRANJAS = "Solo hay partidas en las franjas de un Stableford o un Medal."


async def _franja_del_organizador(
    uow: CompetitionUnitOfWorkInterface, round_id: RoundId, quien: UserId, is_admin: bool
) -> tuple[Round, Competition, HojaDeSalidas]:
    """La franja, su competición (bloqueada) y su hoja, si quien pide la organiza."""
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
        raise PartidasError(SOLO_EN_FRANJAS)
    return franja, competicion, franja.hoja_de_salidas


@dataclass
class _Abierta:
    """La franja, su competición bloqueada, sus partidas y el momento, dentro de plazo."""

    franja: Round
    competicion: Competition
    hoja: HojaDeSalidas
    partidas: list[Partida]
    ahora: datetime


class _ConLaFranja:
    """Lo común: el organizador, dentro de plazo, y la vista al terminar."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        zonas: ICompetitionTimezone,
        user_repository: UserRepositoryInterface,
        reloj: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._uow = uow
        self._zonas = zonas
        self._usuarios = user_repository
        self._reloj = reloj

    async def _abrir(self, round_id: RoundId, quien: UserId, is_admin: bool) -> _Abierta:
        """
        Raises:
            RoundNotFoundError, CompetitionNotFoundError, NotCompetitionCreatorError,
            PartidasError, ZonaDesconocidaError, PlazoCerradoError, PartidaEmpezadaError
        """
        franja, competicion, hoja = await _franja_del_organizador(
            self._uow, round_id, quien, is_admin
        )
        ahora = self._reloj()
        partidas = await self._uow.partidas.de_la_franja(franja.id)
        PlazoDePartidas.comprobar(
            competicion.status, await primera_salida(franja, self._zonas), ahora, partidas
        )
        return _Abierta(franja, competicion, hoja, partidas, ahora)

    async def _vista(
        self, abierta: _Abierta, partidas: list[Partida], plazas: list | None = None
    ) -> TeeGroupsResponseDTO:
        return await vista_de_la_franja(
            self._uow,
            abierta.competicion,
            abierta.franja,
            partidas,
            self._zonas,
            self._usuarios,
            abierta.ahora,
            plazas,
        )


class GenerarPartidasUseCase(_ConLaFranja):
    """El organizador reparte una franja en partidas (y reemplaza las que hubiera)."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        jugadores: JugadoresDeLaPartida,
        zonas: ICompetitionTimezone,
        user_repository: UserRepositoryInterface,
        reloj: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        super().__init__(uow, zonas, user_repository, reloj)
        self._jugadores = jugadores

    async def execute(
        self,
        round_id: UUID,
        request: GenerateTeeGroupsRequestDTO,
        quien: UserId,
        is_admin: bool,
    ) -> TeeGroupsResponseDTO:
        """
        Raises:
            Los de `_abrir`, y además:
            RepartoImposibleError: Con un solo jugador
            JugadoresSinHandicapError, JugadoresSinBarraError: Con todos los afectados
        """
        async with self._uow:
            abierta = await self._abrir(RoundId(round_id), quien, is_admin)
            plazas = await con_plaza_y_aprobados(self._uow, abierta.franja)
            fotos = await self._jugadores.construir(
                self._uow, abierta.competicion, abierta.franja, [p.user_id for p in plazas]
            )
            grupos = RepartoDePartidas.repartir(
                [ParaRepartir(p.user_id, fotos[p.user_id].handicap, p.creada) for p in plazas],
                abierta.hoja.jugadores_por_partida,
                request.order,
            )
            partidas = [
                Partida.crear(
                    abierta.competicion.id, abierta.franja.id, numero, [fotos[u] for u in grupo]
                )
                for numero, grupo in enumerate(grupos, start=1)
            ]
            await self._uow.partidas.reemplazar_franja(abierta.franja.id, partidas)
            vista = await self._vista(abierta, partidas)
            await self._uow.commit()
        return vista


class MoverJugadorUseCase(_ConLaFranja):
    """El organizador mueve a un jugador a otra partida, intercambiando o a una nueva."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        jugadores: JugadoresDeLaPartida,
        zonas: ICompetitionTimezone,
        user_repository: UserRepositoryInterface,
        reloj: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        super().__init__(uow, zonas, user_repository, reloj)
        self._jugadores = jugadores

    async def execute(
        self,
        round_id: UUID,
        user_id: UUID,
        group_id: UUID | None,
        swap_with_user_id: UUID | None,
        quien: UserId,
        is_admin: bool,
    ) -> TeeGroupsResponseDTO:
        """
        Args:
            group_id: La partida de destino; None, una nueva al final (M1)
            swap_with_user_id: Con quién de la de destino se intercambia

        Raises:
            Los de `_abrir`, y además:
            MovimientoImposibleError: Con la clave del motivo
        """
        async with self._uow:
            abierta = await self._abrir(RoundId(round_id), quien, is_admin)
            jugador = UserId(user_id)
            plazas = await con_plaza_y_aprobados(self._uow, abierta.franja)
            if jugador not in {p.user_id for p in plazas}:
                raise MovimientoImposibleError(
                    "PLAYER_NOT_IN_WINDOW", "Ese jugador no tiene plaza en esta franja."
                )
            foto = next(
                (j for p in abierta.partidas for j in p.jugadores if j.user_id == jugador), None
            )
            if foto is None:
                # Sin partida (cambió de franja, o cogió plaza después): su foto, de ahora
                fotos = await self._jugadores.construir(
                    self._uow, abierta.competicion, abierta.franja, [jugador]
                )
                foto = fotos[jugador]
            cambios = MovimientosDePartidas.mover(
                abierta.partidas,
                foto,
                PartidaId(group_id) if group_id else None,
                UserId(swap_with_user_id) if swap_with_user_id else None,
                abierta.hoja,
                abierta.competicion.id,
                abierta.franja.id,
            )
            await self._uow.partidas.borrar(cambios.borrar)
            await self._uow.partidas.guardar(cambios.guardar)
            await self._uow.partidas.anadir(cambios.crear)
            quedan = [p for p in abierta.partidas if p not in cambios.borrar] + cambios.crear
            vista = await self._vista(abierta, quedan, plazas)
            await self._uow.commit()
        return vista


class ReordenarPartidasUseCase(_ConLaFranja):
    """El organizador cambia el orden de salida de las partidas."""

    async def execute(
        self, round_id: UUID, group_ids: list[UUID], quien: UserId, is_admin: bool
    ) -> TeeGroupsResponseDTO:
        """
        Raises:
            Los de `_abrir`, y además:
            MovimientoImposibleError: INVALID_GROUP_ORDER, si no van todas una vez
        """
        async with self._uow:
            abierta = await self._abrir(RoundId(round_id), quien, is_admin)
            partidas = MovimientosDePartidas.reordenar(
                abierta.partidas, [PartidaId(g) for g in group_ids]
            )
            await self._uow.partidas.guardar(partidas)
            vista = await self._vista(abierta, partidas)
            await self._uow.commit()
        return vista


class CambiarMarcadoresUseCase(_ConLaFranja):
    """El organizador cambia quién marca a quién en una partida (D12)."""

    async def execute(
        self,
        group_id: UUID,
        markers: list[tuple[UUID, UUID]],
        quien: UserId,
        is_admin: bool,
    ) -> TeeGroupsResponseDTO:
        """
        Args:
            markers: (marcador, marcado), uno por cada jugador de la partida

        Raises:
            PartidaNotFoundError: Si no existe
            Los de `_abrir`, y además:
            MarcadoresInvalidosError: Si alguien se marca a sí mismo, o no es biyección
        """
        async with self._uow:
            encontrada = await self._uow.partidas.find_by_id(PartidaId(group_id))
            if encontrada is None:
                raise PartidaNotFoundError(f"No existe la partida {group_id}")
            abierta = await self._abrir(encontrada.round_id, quien, is_admin)
            # Releída con el candado: si otra petición la borró mientras, no existe
            partida = next((p for p in abierta.partidas if p.id == encontrada.id), None)
            if partida is None:
                raise PartidaNotFoundError(f"No existe la partida {group_id}")
            marcadores = {UserId(a): UserId(b) for a, b in markers}
            if len(marcadores) != len(markers):
                raise MarcadoresInvalidosError("Cada jugador marca a uno solo.")
            partida.cambiar_marcadores(marcadores)
            await self._uow.partidas.guardar([partida])
            vista = await self._vista(abierta, abierta.partidas)
            await self._uow.commit()
        return vista


class BorrarPartidasUseCase(_ConLaFranja):
    """El organizador borra las partidas de una franja, para empezar de cero (D9)."""

    async def execute(self, round_id: UUID, quien: UserId, is_admin: bool) -> None:
        """
        Raises:
            Los de `_abrir`
        """
        async with self._uow:
            abierta = await self._abrir(RoundId(round_id), quien, is_admin)
            await self._uow.partidas.borrar(abierta.partidas)
            await self._uow.commit()


class VerPartidasUseCase:
    """Las partidas de una franja: cualquiera con sesión las ve, como la Ryder (D8)."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        zonas: ICompetitionTimezone,
        user_repository: UserRepositoryInterface,
        reloj: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._uow = uow
        self._zonas = zonas
        self._usuarios = user_repository
        self._reloj = reloj

    async def execute(self, round_id: UUID) -> TeeGroupsResponseDTO:
        """
        Raises:
            RoundNotFoundError, CompetitionNotFoundError: Si no existen
            PartidasError: Si no es una franja de stroke play
        """
        async with self._uow:
            franja = await self._uow.rounds.find_by_id(RoundId(round_id))
            if franja is None:
                raise RoundNotFoundError(f"No existe la franja {round_id}")
            if franja.hoja_de_salidas is None:
                raise PartidasError(SOLO_EN_FRANJAS)
            competicion = await self._uow.competitions.find_by_id(franja.competition_id)
            if competicion is None:
                raise CompetitionNotFoundError(f"No existe la competición {franja.competition_id}")
            partidas = await self._uow.partidas.de_la_franja(franja.id)
            return await vista_de_la_franja(
                self._uow, competicion, franja, partidas, self._zonas, self._usuarios, self._reloj()
            )


class MisPartidasUseCase:
    """Las partidas de quien pregunta en una competición, por día y hora de salida."""

    def __init__(
        self, uow: CompetitionUnitOfWorkInterface, user_repository: UserRepositoryInterface
    ):
        self._uow = uow
        self._usuarios = user_repository

    async def execute(self, competition_id: UUID, quien: UserId) -> MyTeeGroupsResponseDTO:
        """
        Args:
            competition_id: La competición
            quien: Quien pregunta: sus partidas, con sus compañeros

        Returns:
            Sus partidas por día y hora de salida; vacío si no juega ninguna
        """
        async with self._uow:
            competicion_id = CompetitionId(competition_id)
            partidas = await self._uow.partidas.del_jugador(competicion_id, quien)
            franjas: dict[RoundId, tuple[Round, HojaDeSalidas]] = {}
            for partida in partidas:
                if partida.round_id not in franjas:
                    franja = await self._uow.rounds.find_by_id(partida.round_id)
                    if franja is not None and franja.hoja_de_salidas is not None:
                        franjas[partida.round_id] = (franja, franja.hoja_de_salidas)
            nombres = await PlayerNames.de_la_competicion(
                list({u for p in partidas for u in p.user_ids}),
                competicion_id,
                self._usuarios,
                self._uow,
            )
            mias = []
            for partida in partidas:
                if partida.round_id not in franjas:
                    continue
                franja, hoja = franjas[partida.round_id]
                mias.append(
                    (
                        (franja.round_date, hoja.hora_de(partida.numero)),
                        MyTeeGroupDTO(
                            round_id=franja.id.value,
                            round_date=franja.round_date,
                            session_type=franja.session_type.value,
                            group=partida_dto(partida, hoja, nombres),
                        ),
                    )
                )
        return MyTeeGroupsResponseDTO(groups=[dto for _, dto in sorted(mias, key=lambda m: m[0])])
