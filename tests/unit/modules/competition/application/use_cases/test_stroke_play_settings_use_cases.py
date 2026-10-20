"""Los ajustes del stroke play al crear la competición y al cambiarlos (#251).

Al crear viajan en el `POST` de siempre, dentro de `stroke_play`. Para
cambiarlos hay un caso de uso propio, porque se pueden tocar hasta que la
competición empieza (también en CLOSED), y la edición general solo deja hasta
ACTIVE.
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
    StrokePlaySettingsDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.update_stroke_play_settings_use_case import (
    UpdateStrokePlaySettingsUseCase,
)
from src.modules.competition.domain.entities.competition import (
    CompetitionStateError,
    TournamentTypeError,
)
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.stroke_play_setup import (
    StrokePlaySettingsError,
)
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.helpers import USUARIOS_CON_GENERO

pytestmark = pytest.mark.asyncio

CREADOR = UserId(uuid4())


def _peticion(tipo=TournamentType.STABLEFORD, stroke_play=None, **extra):
    datos = {
        "name": "Medal de octubre",
        "start_date": date(2030, 10, 10),
        "end_date": date(2030, 10, 11),
        "main_country": "ES",
        "play_mode": "HANDICAP",
        "tournament_type": tipo,
        "stroke_play": stroke_play,
    }
    datos.update(extra)
    return CreateCompetitionRequestDTO(**datos)


async def _crear(uow, **kwargs):
    caso = CreateCompetitionUseCase(uow, LocationBuilder(uow.countries), USUARIOS_CON_GENERO)
    return await caso.execute(_peticion(**kwargs), CREADOR)


class TestAlCrear:
    async def test_un_stableford_con_sus_ajustes(self):
        respuesta = await _crear(
            InMemoryUnitOfWork(),
            stroke_play=StrokePlaySettingsDTO(
                category_limits=[Decimal("12.0"), Decimal("26.0")],
                max_matchdays_per_player=2,
                overall_standing="BEST_CARD",
            ),
        )

        assert respuesta.stroke_play is not None
        assert respuesta.stroke_play.category_limits == [Decimal("12.0"), Decimal("26.0")]
        assert respuesta.stroke_play.max_matchdays_per_player == 2
        assert respuesta.stroke_play.overall_standing == "BEST_CARD"

    async def test_un_medal_sin_ajustes_tiene_los_de_por_defecto(self):
        respuesta = await _crear(InMemoryUnitOfWork(), tipo=TournamentType.MEDAL)

        assert respuesta.stroke_play.category_limits == []
        assert respuesta.stroke_play.max_matchdays_per_player == 1
        assert respuesta.stroke_play.overall_standing == "ACCUMULATED"

    async def test_una_ryder_no_los_trae(self):
        respuesta = await _crear(InMemoryUnitOfWork(), tipo=TournamentType.RYDER_CUP)

        assert respuesta.stroke_play is None

    async def test_una_ryder_con_ajustes_de_stroke_play_se_rechaza(self):
        with pytest.raises(TournamentTypeError):
            await _crear(
                InMemoryUnitOfWork(),
                tipo=TournamentType.RYDER_CUP,
                stroke_play=StrokePlaySettingsDTO(category_limits=[Decimal("12.0")]),
            )

    async def test_mas_jornadas_que_dias_se_rechaza(self):
        with pytest.raises(StrokePlaySettingsError):
            await _crear(
                InMemoryUnitOfWork(), stroke_play=StrokePlaySettingsDTO(max_matchdays_per_player=3)
            )


class TestAlCambiar:
    async def _stableford(self, uow, **kwargs) -> CompetitionId:
        respuesta = await _crear(uow, **kwargs)
        return CompetitionId(respuesta.id)

    async def test_el_creador_los_cambia_y_quedan_guardados(self):
        uow = InMemoryUnitOfWork()
        competicion = await self._stableford(uow)

        respuesta = await UpdateStrokePlaySettingsUseCase(uow).execute(
            competicion.value,
            StrokePlaySettingsDTO(category_limits=[Decimal("18.0")]),
            CREADOR,
        )

        assert respuesta.category_limits == [Decimal("18.0")]
        guardada = await uow.competitions.find_by_id(competicion)
        assert guardada.stroke_play.category_limits == (Decimal("18.0"),)

    async def test_un_admin_tambien(self):
        uow = InMemoryUnitOfWork()
        competicion = await self._stableford(uow)

        respuesta = await UpdateStrokePlaySettingsUseCase(uow).execute(
            competicion.value,
            StrokePlaySettingsDTO(overall_standing="BEST_CARD"),
            UserId(uuid4()),
            is_admin=True,
        )

        assert respuesta.overall_standing == "BEST_CARD"

    async def test_otro_jugador_no(self):
        uow = InMemoryUnitOfWork()
        competicion = await self._stableford(uow)

        with pytest.raises(NotCompetitionCreatorError):
            await UpdateStrokePlaySettingsUseCase(uow).execute(
                competicion.value, StrokePlaySettingsDTO(category_limits=[]), UserId(uuid4())
            )

    async def test_una_competicion_que_no_existe(self):
        with pytest.raises(CompetitionNotFoundError):
            await UpdateStrokePlaySettingsUseCase(InMemoryUnitOfWork()).execute(
                uuid4(), StrokePlaySettingsDTO(category_limits=[]), CREADOR
            )

    async def test_en_cerrada_ya_no(self):
        """Al cerrar se fija el hándicap de cada uno y su categoría (7 oct 2026)."""
        uow = InMemoryUnitOfWork()
        competicion_id = await self._stableford(uow)
        async with uow:
            competicion = await uow.competitions.find_by_id(competicion_id)
            competicion.close_enrollments()
            await uow.competitions.update(competicion)

        with pytest.raises(CompetitionStateError):
            await UpdateStrokePlaySettingsUseCase(uow).execute(
                competicion_id.value, StrokePlaySettingsDTO(max_matchdays_per_player=2), CREADOR
            )

    async def test_empezada_ya_no(self):
        uow = InMemoryUnitOfWork()
        competicion_id = await self._stableford(uow)
        async with uow:
            competicion = await uow.competitions.find_by_id(competicion_id)
            competicion.close_enrollments()
            competicion.start()
            await uow.competitions.update(competicion)

        with pytest.raises(CompetitionStateError):
            await UpdateStrokePlaySettingsUseCase(uow).execute(
                competicion_id.value, StrokePlaySettingsDTO(category_limits=[]), CREADOR
            )

    async def test_a_una_ryder_no(self):
        uow = InMemoryUnitOfWork()
        competicion = await self._stableford(uow, tipo=TournamentType.RYDER_CUP)

        with pytest.raises(TournamentTypeError):
            await UpdateStrokePlaySettingsUseCase(uow).execute(
                competicion.value, StrokePlaySettingsDTO(category_limits=[]), CREADOR
            )

    async def test_solo_cambia_lo_que_llega(self):
        uow = InMemoryUnitOfWork()
        competicion = await self._stableford(
            uow,
            stroke_play=StrokePlaySettingsDTO(
                category_limits=[Decimal("12.0")], overall_standing="BEST_CARD"
            ),
        )

        respuesta = await UpdateStrokePlaySettingsUseCase(uow).execute(
            competicion.value, StrokePlaySettingsDTO(max_matchdays_per_player=2), CREADOR
        )

        assert respuesta.category_limits == [Decimal("12.0")]
        assert respuesta.overall_standing == "BEST_CARD"


class TestConElArranque:
    async def test_lee_la_competicion_bloqueada_para_no_cruzarse_con_el_arranque(self):
        """
        El primer golpe arranca la competición con su fila bloqueada, y al
        arrancar se fijan las categorías. Si los ajustes se cambiaran a la vez,
        los límites se moverían con las categorías ya fijadas.
        """
        uow = InMemoryUnitOfWork()
        respuesta = await _crear(uow)

        async def sin_bloquear(_competition_id):
            raise AssertionError("Los ajustes se leen con la fila bloqueada")

        uow.competitions.find_by_id = sin_bloquear

        ajustes = await UpdateStrokePlaySettingsUseCase(uow).execute(
            respuesta.id, StrokePlaySettingsDTO(category_limits=[Decimal("18.0")]), CREADOR
        )

        assert ajustes.category_limits == [Decimal("18.0")]


class TestLaPeticion:
    async def test_una_ryder_con_stroke_play_vacio_tambien_se_rechaza(self):
        """Mandar `stroke_play` ya es pedir algo que una Ryder no tiene."""
        with pytest.raises(TournamentTypeError):
            await _crear(
                InMemoryUnitOfWork(),
                tipo=TournamentType.RYDER_CUP,
                stroke_play=StrokePlaySettingsDTO(),
            )


class TestCategoriasIguales:
    """Pedir N categorías iguales en vez de los límites (10 oct 2026)."""

    async def test_al_crear_se_guarda_el_contador_sin_limites(self):
        respuesta = await _crear(
            InMemoryUnitOfWork(), stroke_play=StrokePlaySettingsDTO(category_count=3)
        )

        assert respuesta.stroke_play.category_count == 3
        assert respuesta.stroke_play.category_limits == []

    async def test_a_mano_el_contador_sale_vacio(self):
        respuesta = await _crear(
            InMemoryUnitOfWork(),
            stroke_play=StrokePlaySettingsDTO(category_limits=[Decimal("12.0")]),
        )

        assert respuesta.stroke_play.category_count is None

    async def test_al_cambiar_a_iguales_se_borran_los_limites(self):
        uow = InMemoryUnitOfWork()
        competicion = CompetitionId(
            (
                await _crear(
                    uow, stroke_play=StrokePlaySettingsDTO(category_limits=[Decimal("12.0")])
                )
            ).id
        )

        respuesta = await UpdateStrokePlaySettingsUseCase(uow).execute(
            competicion.value, StrokePlaySettingsDTO(category_count=4), CREADOR
        )

        assert respuesta.category_count == 4
        assert respuesta.category_limits == []
        guardada = await uow.competitions.find_by_id(competicion)
        assert guardada.stroke_play.category_count == 4

    async def test_los_dos_a_la_vez_se_rechazan(self):
        with pytest.raises(StrokePlaySettingsError, match="a la vez"):
            await _crear(
                InMemoryUnitOfWork(),
                stroke_play=StrokePlaySettingsDTO(
                    category_limits=[Decimal("12.0")], category_count=3
                ),
            )

    async def test_fuera_de_rango_lo_dice_el_dominio(self):
        with pytest.raises(StrokePlaySettingsError, match="entre 2 y 5"):
            await _crear(InMemoryUnitOfWork(), stroke_play=StrokePlaySettingsDTO(category_count=6))

    async def test_a_una_ryder_con_contador_se_rechaza(self):
        with pytest.raises(TournamentTypeError):
            await _crear(
                InMemoryUnitOfWork(),
                tipo=TournamentType.RYDER_CUP,
                stroke_play=StrokePlaySettingsDTO(category_count=3),
            )
