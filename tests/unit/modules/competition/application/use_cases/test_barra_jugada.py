"""
La barra jugada (barras por campo, tabla del 21 nov 2026, B).

`GET /enrollments/{id}/tees` con la competición terminada o cancelada: en un
campo donde jugó, la barra de la foto guardada en su partido (Ryder) o su partida
(stroke play), con origen PLAYED. Jugó = su partido o su partida empezaron.

| Caso                                                      | Ese campo                       |
|-----------------------------------------------------------|---------------------------------|
| B6 Ryder terminada, su partido empezado en azules         | BLUE, PLAYED                    |
| B6 Stroke play terminado, su partida empezada en amarillas | YELLOW, PLAYED                 |
| B7 Dos rondas en el campo con barras distintas            | la de la última (fecha, sesión) |
| B8 Cancelada, campo donde no llegó a jugar                | la configuración, como ahora    |
| B8 Cancelada, su partido generado sin empezar             | la configuración, como ahora    |
| B9 En curso, con su partido empezado                      | nada cambia                     |
| B10 Terminada o cancelada                                 | options vacío en todos          |
"""

from datetime import date, time
from decimal import Decimal

import pytest

from src.modules.competition.application.use_cases.get_enrollment_tees_use_case import (
    GetEnrollmentTeesUseCase,
)
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.jugador_de_partida import JugadorDePartida
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from tests.unit.modules.competition.application.use_cases.test_change_enrollment_tee_use_case import (
    ALDEAMAYOR,
    _Mundo,
)

pytestmark = pytest.mark.asyncio


def _jugador(user_id, color):
    return JugadorDePartida(
        user_id=user_id,
        handicap=Decimal("18.0"),
        playing_handicap=10,
        tee_color=color,
        tee_gender=Gender.FEMALE,
        golpes_por_hoyo=(1,) * 10 + (0,) * 8,
        par_por_hoyo=(4,) * 18,
    )


AZULES = (TeeColor.BLUE, Gender.FEMALE)
ROJAS = (TeeColor.RED, Gender.FEMALE)


async def _barras(mundo):
    return await GetEnrollmentTeesUseCase(
        mundo.uow, golf_course_repository=mundo.campos, user_repository=mundo.usuarios
    ).execute(mundo.inscripcion.id.value, mundo.jugadora)


def _campos(respuesta):
    return [(c.tee, c.source, c.options) for c in respuesta.courses]


async def _acabar(mundo, como):
    await mundo.cerrar()
    if como == "terminada":
        await mundo.empezar()
        await mundo.terminar()
    else:
        await mundo.cancelar()


async def _ronda(mundo, dia, sesion, campo=0):
    ronda = Round.create(
        competition_id=mundo.competition_id,
        golf_course_id=list(mundo.campos.por_id)[campo],
        round_date=dia,
        session_type=sesion,
        match_format=MatchFormat.SINGLES,
    )
    async with mundo.uow:
        await mundo.uow.rounds.add(ronda)
        await mundo.uow.commit()
    return ronda


class TestRyder:
    @pytest.mark.parametrize("como", ["terminada", "cancelada"])
    async def test_played_course_gives_the_tee_of_her_match(self, como):
        """
        Given su partido empezado en azules en Aldeamayor, y la Ryder terminada o cancelada
        When pide sus barras
        Then allí azules, de origen PLAYED, sin opciones
        """
        mundo = await _Mundo().montar()
        await mundo.partido(
            [mundo.jugadora], [mundo.otro], empezado=True, barras={mundo.jugadora: AZULES}
        )
        await _acabar(mundo, como)

        assert _campos(await _barras(mundo)) == [("BLUE", "PLAYED", [])]

    async def test_several_rounds_on_the_course_give_the_last_one(self):
        """
        Given en el mismo campo: el 2 jun por la mañana en rojas, el 1 jun por la tarde
            y el 1 jun por la mañana en azules (guardadas sin orden)
        When pide sus barras con la Ryder terminada
        Then rojas: la de la última ronda, por fecha y sesión
        """
        mundo = await _Mundo().montar()
        tarde = await _ronda(mundo, date(2026, 6, 1), SessionType.AFTERNOON)
        ultima = await _ronda(mundo, date(2026, 6, 2), SessionType.MORNING)
        manana = await _ronda(mundo, date(2026, 6, 1), SessionType.MORNING)
        for ronda, barra in ((tarde, AZULES), (ultima, ROJAS), (manana, AZULES)):
            await mundo.partido(
                [mundo.jugadora],
                [mundo.otro],
                empezado=True,
                barras={mundo.jugadora: barra},
                ronda=ronda,
            )
        await _acabar(mundo, "terminada")

        assert _campos(await _barras(mundo)) == [("RED", "PLAYED", [])]

    async def test_the_same_day_the_evening_is_after_the_afternoon(self):
        """
        Given en el mismo campo y día: por la noche en rojas y por la tarde en azules
        When pide sus barras con la Ryder terminada
        Then rojas: la noche va después de la tarde, aunque por letra no
        """
        mundo = await _Mundo().montar()
        noche = await _ronda(mundo, date(2026, 6, 1), SessionType.EVENING)
        tarde = await _ronda(mundo, date(2026, 6, 1), SessionType.AFTERNOON)
        for ronda, barra in ((noche, ROJAS), (tarde, AZULES)):
            await mundo.partido(
                [mundo.jugadora],
                [mundo.otro],
                empezado=True,
                barras={mundo.jugadora: barra},
                ronda=ronda,
            )
        await _acabar(mundo, "terminada")

        assert _campos(await _barras(mundo)) == [("RED", "PLAYED", [])]

    async def test_a_course_where_she_did_not_play_gives_the_current_setup(self):
        """
        Given dos campos, su partido empezado en azules solo en el primero, y la
            Ryder cancelada
        When pide sus barras
        Then el primero PLAYED; el segundo, rojas por defecto como ahora, sin opciones
        """
        mundo = await _Mundo().montar(campos=(ALDEAMAYOR, ALDEAMAYOR))
        await mundo.partido(
            [mundo.jugadora], [mundo.otro], empezado=True, barras={mundo.jugadora: AZULES}
        )
        await _acabar(mundo, "cancelada")

        assert _campos(await _barras(mundo)) == [
            ("BLUE", "PLAYED", []),
            ("RED", "DEFAULT", []),
        ]

    async def test_a_match_generated_but_not_started_gives_the_current_setup(self):
        """
        Given su partido generado en azules que no llegó a empezar, y la Ryder cancelada
        When pide sus barras
        Then la configuración actual (rojas por defecto), no la del partido
        """
        mundo = await _Mundo().montar()
        await mundo.partido([mundo.jugadora], [mundo.otro], barras={mundo.jugadora: AZULES})
        await _acabar(mundo, "cancelada")

        assert _campos(await _barras(mundo)) == [("RED", "DEFAULT", [])]

    async def test_a_match_of_others_does_not_count(self):
        """
        Given un partido empezado de otros dos en azules, y la Ryder terminada
        When la jugadora pide sus barras
        Then la configuración actual: ella no jugó
        """
        mundo = await _Mundo().montar()
        await mundo.partido(
            [mundo.capitana], [mundo.otro], empezado=True, barras={mundo.capitana: AZULES}
        )
        await _acabar(mundo, "terminada")

        assert _campos(await _barras(mundo)) == [("RED", "DEFAULT", [])]

    async def test_in_progress_nothing_changes(self):
        """
        Given su partido empezado en azules y la Ryder en curso
        When pide sus barras
        Then como hoy: rojas por defecto, con sus opciones
        """
        mundo = await _Mundo().montar()
        await mundo.partido(
            [mundo.jugadora], [mundo.otro], empezado=True, barras={mundo.jugadora: AZULES}
        )
        await mundo.cerrar()
        await mundo.empezar()

        assert _campos(await _barras(mundo)) == [("RED", "DEFAULT", ["RED", "BLUE"])]


class TestStrokePlay:
    async def test_played_course_gives_the_tee_of_her_group(self):
        """
        Given un Stableford con su partida empezada en amarillas, y terminado
        When pide sus barras
        Then allí amarillas, de origen PLAYED, sin opciones
        """
        mundo = await _Mundo().montar(tipo=TournamentType.STABLEFORD)
        await mundo.partida_con(mundo.jugadora, empezada=True)
        await _acabar(mundo, "terminada")

        assert _campos(await _barras(mundo)) == [("YELLOW", "PLAYED", [])]

    async def test_in_a_group_of_several_her_own_tee_counts(self):
        """
        Given un Stableford con una partida empezada de ella en rojas y otra
            jugadora en azules, y terminado
        When pide sus barras
        Then rojas: la suya, no la de su compañera
        """
        mundo = await _Mundo().montar(tipo=TournamentType.STABLEFORD)
        franja = Round.create_franja(
            competition_id=mundo.competition_id,
            golf_course_id=next(iter(mundo.campos.por_id)),
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            hoja_de_salidas=HojaDeSalidas(time(9, 0), time(11, 0), 10, 4),
        )
        partida = Partida.crear(
            mundo.competition_id,
            franja.id,
            1,
            [_jugador(mundo.jugadora, TeeColor.RED), _jugador(mundo.capitana, TeeColor.BLUE)],
        )
        partida.empezar()
        async with mundo.uow:
            await mundo.uow.rounds.add(franja)
            await mundo.uow.partidas.anadir([partida])
            await mundo.uow.commit()
        await _acabar(mundo, "terminada")

        assert _campos(await _barras(mundo)) == [("RED", "PLAYED", [])]

    async def test_a_group_not_started_gives_the_current_setup(self):
        """
        Given un Stableford con su partida generada sin empezar, y cancelado
        When pide sus barras
        Then la configuración actual (rojas por defecto), sin opciones
        """
        mundo = await _Mundo().montar(tipo=TournamentType.STABLEFORD)
        await mundo.partida_con(mundo.jugadora)
        await _acabar(mundo, "cancelada")

        assert _campos(await _barras(mundo)) == [("RED", "DEFAULT", [])]
