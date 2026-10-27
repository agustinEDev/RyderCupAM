"""
Casos de Uso: Las clasificaciones de un stroke play (#251, PR 5).

- **La de la franja** (pestaña 2 de anotar): una tarjeta por jugador, solo hoyos
  validados, con «tras N» y filtro de categoría.
- **La general** (la ficha): la neta, con la regla que eligió el organizador
  (acumulado o mejor tarjeta) y filtro de categoría.
- **La scratch**: sin categorías, con la misma regla (P14), cortada en 25 más los
  empatados, y la fila de quien mira debajo si queda fuera (decisión 4).

Las reglas de orden, empates, NR y demás viven en `Clasificacion` (dominio).
Las ve cualquiera con sesión, como las partidas (D8).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from src.modules.competition.application.dto.partidas_dto import (
    StandingRowDTO,
    StandingsResponseDTO,
)
from src.modules.competition.application.exceptions import PartidasError
from src.modules.competition.application.ports.eventos_de_amigos_interface import (
    EventosDeAmigosInterface,
)
from src.modules.competition.application.services.lo_jugado_de_una_privada import (
    esta_dentro,
    exigir_la_clasificacion,
)
from src.modules.competition.application.services.participantes_de_la_clasificacion import (
    participantes_de,
)
from src.modules.competition.application.services.player_names import PlayerNames
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.clasificacion import (
    Clasificacion,
    Escala,
    Fila,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.overall_standing import OverallStanding
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

# Lo que se enseña del scratch (decisión 4 de la #251): se calcula entero
CORTE_DEL_SCRATCH = 25
_SOLO_STROKE_PLAY = "Solo hay clasificación en un Stableford o un Medal."


@dataclass(frozen=True)
class _Personas:
    """Lo de cada jugador que no es de la tabla: su nombre y el género de sus barras."""

    nombres: dict[UserId, str]
    generos: dict[UserId, str | None]


class _Clasificaciones:
    """Lo que comparten las tres: leer la competición y montar la tabla."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_repository: UserRepositoryInterface,
        eventos: EventosDeAmigosInterface | None = None,
    ):
        self._uow = uow
        self._usuarios = user_repository
        # La llave de quien está fuera de una privada (27 oct 2026)
        self._eventos = eventos

    async def _puede_verla(
        self, competicion: Competition, quien: UserId | None, es_admin: bool
    ) -> bool:
        """Con el `uow` abierto: si quien mira está dentro (sin decir quién, sí)."""
        if quien is None:
            return True
        return await esta_dentro(self._uow, competicion, quien, es_admin=es_admin)

    async def _exigir(self, dentro: bool, competicion: Competition, quien: UserId | None) -> None:
        """
        Fuera del `uow`: quien está fuera de una privada, con la llave.

        Raises:
            NoPuedeVerloError: Sin estar dentro ni tener la llave
        """
        if not dentro and quien is not None:
            await exigir_la_clasificacion(False, competicion.id, quien, self._eventos)

    async def _stroke_play(self, competition_id: CompetitionId) -> Competition:
        competicion = await self._uow.competitions.find_by_id(competition_id)
        if competicion is None or competicion.stroke_play is None:
            raise PartidasError(_SOLO_STROKE_PLAY)
        return competicion

    async def _de_la_competicion(
        self, competicion: Competition, escala: Escala, categoria: int | None
    ) -> tuple[OverallStanding, list[Fila], _Personas]:
        if competicion.stroke_play is None:
            raise PartidasError(_SOLO_STROKE_PLAY)
        regla = competicion.stroke_play.overall_standing
        partidas = await self._uow.partidas.de_la_competicion(competicion.id)
        golpes = await self._uow.golpes_de_partida.de_la_competicion(competicion.id)
        filas, personas = await self._tabla(competicion, partidas, golpes, escala, regla, categoria)
        return regla, filas, personas

    async def _tabla(
        self,
        competicion: Competition,
        partidas: Sequence[Partida],
        golpes: Sequence[GolpeDePartida],
        escala: Escala,
        regla: OverallStanding,
        categoria: int | None,
    ) -> tuple[list[Fila], _Personas]:
        user_ids = list({u for p in partidas for u in p.user_ids})
        categorias = {
            e.user_id: e.fixed_category
            for e in await self._uow.enrollments.find_by_user_ids_and_competition(
                user_ids, competicion.id
            )
        }
        franjas = {f.id: f for f in await self._uow.rounds.find_by_competition(competicion.id)}
        participantes, generos = participantes_de(partidas, golpes, franjas, categorias)
        filas = Clasificacion.de(
            participantes, competicion.tournament_type, escala, regla, categoria
        )
        nombres = await PlayerNames.de_la_competicion(
            [f.user_id for f in filas], competicion.id, self._usuarios, self._uow
        )
        return filas, _Personas(nombres, generos)


class ClasificacionDeLaFranjaUseCase(_Clasificaciones):
    """La de la franja: una tarjeta por jugador."""

    async def execute(
        self,
        round_id: UUID,
        categoria: int | None = None,
        *,
        quien: UserId | None = None,
        es_admin: bool = False,
    ) -> StandingsResponseDTO:
        """
        Raises:
            PartidasError: Si no es una franja de un stroke play
            NoPuedeVerloError: Si es de una privada en la que no está, sin llave
        """
        async with self._uow:
            franja = await self._uow.rounds.find_by_id(RoundId(round_id))
            if franja is None or franja.hoja_de_salidas is None:
                raise PartidasError(
                    "Solo hay clasificación en las franjas de un Stableford o un Medal."
                )
            competicion = await self._stroke_play(franja.competition_id)
            dentro = await self._puede_verla(competicion, quien, es_admin)
        await self._exigir(dentro, competicion, quien)
        async with self._uow:
            partidas = await self._uow.partidas.de_la_franja(franja.id)
            golpes = await self._uow.golpes_de_partida.de_la_franja(franja.id)
            regla = OverallStanding.ACCUMULATED
            filas, personas = await self._tabla(
                competicion, partidas, golpes, Escala.NETA, regla, categoria
            )
        return _respuesta(competicion, Escala.NETA, regla, categoria, filas, personas)


class ClasificacionGeneralUseCase(_Clasificaciones):
    """La general neta, con la regla de la competición."""

    async def execute(
        self,
        competition_id: UUID,
        categoria: int | None = None,
        *,
        quien: UserId | None = None,
        es_admin: bool = False,
    ) -> StandingsResponseDTO:
        """
        Raises:
            PartidasError: Si no es un stroke play
            NoPuedeVerloError: Si es una privada en la que no está, sin llave
        """
        async with self._uow:
            competicion = await self._stroke_play(CompetitionId(competition_id))
            dentro = await self._puede_verla(competicion, quien, es_admin)
        await self._exigir(dentro, competicion, quien)
        async with self._uow:
            regla, filas, personas = await self._de_la_competicion(
                competicion, Escala.NETA, categoria
            )
        return _respuesta(competicion, Escala.NETA, regla, categoria, filas, personas)


class ClasificacionScratchUseCase(_Clasificaciones):
    """La scratch, cortada, con la fila de quien mira."""

    async def execute(
        self, competition_id: UUID, quien: UserId, *, es_admin: bool = False
    ) -> StandingsResponseDTO:
        """
        Raises:
            PartidasError: Si no es un stroke play
            NoPuedeVerloError: Si es una privada en la que no está, sin llave
        """
        async with self._uow:
            competicion = await self._stroke_play(CompetitionId(competition_id))
            dentro = await self._puede_verla(competicion, quien, es_admin)
        await self._exigir(dentro, competicion, quien)
        async with self._uow:
            regla, filas, personas = await self._de_la_competicion(
                competicion, Escala.SCRATCH, None
            )
        visibles, mia = Clasificacion.cortar(filas, CORTE_DEL_SCRATCH, quien)
        return _respuesta(competicion, Escala.SCRATCH, regla, None, visibles, personas, mia)


def _fila(fila: Fila, personas: _Personas) -> StandingRowDTO:
    return StandingRowDTO(
        position=fila.puesto,
        tied=fila.empatado,
        user_id=fila.user_id.value,
        name=personas.nombres.get(fila.user_id, ""),
        category=fila.categoria,
        handicap=fila.handicap,
        value=fila.valor,
        cards=fila.tarjetas,
        thru=fila.tras,
        status=fila.estado.value,
        retired=fila.retirado,
        tee_gender=personas.generos.get(fila.user_id),
    )


def _respuesta(
    competicion: Competition,
    escala: Escala,
    regla: OverallStanding,
    categoria: int | None,
    filas: Sequence[Fila],
    personas: _Personas,
    mia: Fila | None = None,
) -> StandingsResponseDTO:
    return StandingsResponseDTO(
        tournament_type=competicion.tournament_type.value,
        scale=escala.value,
        rule=regla.value,
        category=categoria,
        rows=[_fila(f, personas) for f in filas],
        me=_fila(mia, personas) if mia else None,
    )
