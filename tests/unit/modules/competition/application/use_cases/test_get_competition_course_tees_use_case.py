"""
Lo fijado por campo en una competición (barras por campo, tabla del 21 nov 2026, A).

`GET /competitions/{id}/course-tees`: la barra que el organizador fijó en cada
campo para cada género (R2), para que su pantalla la enseñe.

| Caso                                              | Resultado                          |
|---------------------------------------------------|------------------------------------|
| A1 Organizador o admin                            | [{golf_course_id, gender, tee}]    |
| A2 Nada fijado                                    | []                                 |
| A3 Jugador, capitán o ajeno                       | NotCompetitionCreatorError (403)   |
| A4 Competición que no existe                      | CompetitionNotFoundError (404)     |
| A5 Cualquier estado, también terminada/cancelada  | se lee                             |
| Lo propio de un jugador (R1)                      | no sale: no es del campo           |
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    GetCompetitionCourseTeesRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.use_cases.get_competition_course_tees_use_case import (
    GetCompetitionCourseTeesUseCase,
)
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.competition.application.use_cases.test_change_enrollment_tee_use_case import (
    ALDEAMAYOR,
    _Mundo,
)

pytestmark = pytest.mark.asyncio


async def _fijadas(mundo, quien=None, is_admin=False, competition_id=None):
    return await GetCompetitionCourseTeesUseCase(mundo.uow).execute(
        GetCompetitionCourseTeesRequestDTO(
            competition_id=competition_id or mundo.competition_id.value
        ),
        quien or mundo.organizador,
        is_admin=is_admin,
    )


async def _fijar(mundo, campo, genero, color):
    await mundo.uow.barras_por_campo.fijar_del_campo(mundo.competition_id, campo, genero, color)


def _filas(respuesta):
    return [(f.golf_course_id, f.gender, f.tee_color) for f in respuesta]


class TestLoFijado:
    async def test_course_tees_by_the_organizer_lists_each_course_and_gender(self):
        """
        Given dos campos: en el primero azules para las mujeres y blancas para los
            hombres; en el segundo, rojas para las mujeres
        When el organizador lo pide
        Then sale cada uno, en el orden de los campos y por género
        """
        mundo = await _Mundo().montar(campos=(ALDEAMAYOR, ALDEAMAYOR))
        primero, segundo = list(mundo.campos.por_id)
        await _fijar(mundo, segundo, Gender.FEMALE, TeeColor.RED)
        await _fijar(mundo, primero, Gender.FEMALE, TeeColor.BLUE)
        await _fijar(mundo, primero, Gender.MALE, TeeColor.WHITE)

        respuesta = await _fijadas(mundo)

        assert _filas(respuesta) == [
            (primero.value, "MALE", "WHITE"),
            (primero.value, "FEMALE", "BLUE"),
            (segundo.value, "FEMALE", "RED"),
        ]

    async def test_course_tees_by_an_admin_lists_them(self):
        """
        Given azules para las mujeres en el campo
        When un admin, que no es el organizador, lo pide
        Then lo ve
        """
        mundo = await _Mundo().montar()
        (campo,) = list(mundo.campos.por_id)
        await _fijar(mundo, campo, Gender.FEMALE, TeeColor.BLUE)

        respuesta = await _fijadas(mundo, quien=UserId(uuid4()), is_admin=True)

        assert _filas(respuesta) == [(campo.value, "FEMALE", "BLUE")]

    async def test_course_tees_with_nothing_set_is_empty(self):
        """
        Given una competición con campo y sin nada fijado
        When el organizador lo pide
        Then la lista viene vacía
        """
        mundo = await _Mundo().montar()

        assert await _fijadas(mundo) == []

    async def test_course_tees_leaves_out_a_player_own_change(self):
        """
        Given solo el cambio propio de la jugadora en el campo (R1)
        When el organizador lo pide
        Then no sale: no es lo fijado para el campo
        """
        mundo = await _Mundo().montar()
        (campo,) = list(mundo.campos.por_id)
        await mundo.uow.barras_por_campo.fijar_propia(mundo.inscripcion, campo, TeeColor.BLUE)

        assert await _fijadas(mundo) == []


class TestQuien:
    @pytest.mark.parametrize("quien", ["jugadora", "capitana", "ajeno"])
    async def test_course_tees_by_anyone_else_is_forbidden(self, quien):
        """
        Given una competición con equipos y azules fijadas para las mujeres
        When lo pide la jugadora, su capitana o alguien ajeno
        Then NotCompetitionCreatorError (403), sin leer lo fijado
        """
        mundo = await _Mundo().montar()
        await mundo.con_equipos()
        (campo,) = list(mundo.campos.por_id)
        await _fijar(mundo, campo, Gender.FEMALE, TeeColor.BLUE)
        mundo.ajeno = UserId(uuid4())
        mundo.uow.barras_por_campo.del_campo = AsyncMock(wraps=mundo.uow.barras_por_campo.del_campo)

        with pytest.raises(NotCompetitionCreatorError):
            await _fijadas(mundo, quien=getattr(mundo, quien))
        mundo.uow.barras_por_campo.del_campo.assert_not_awaited()

    async def test_course_tees_of_a_missing_competition_is_not_found(self):
        """
        Given una competición que no existe
        When el organizador (o un admin) la pide
        Then CompetitionNotFoundError (404)
        """
        mundo = await _Mundo().montar()

        with pytest.raises(CompetitionNotFoundError):
            await _fijadas(mundo, competition_id=uuid4(), is_admin=True)


class TestCualquierEstado:
    @pytest.mark.parametrize("estado", ["cerrada", "en_curso", "terminada", "cancelada"])
    async def test_course_tees_is_read_in_any_status(self, estado):
        """
        Given azules fijadas para las mujeres, y la competición cerrada, en curso,
            terminada o cancelada
        When el organizador lo pide
        Then lo ve, y no bloquea nada: es una lectura
        """
        mundo = await _Mundo().montar()
        (campo,) = list(mundo.campos.por_id)
        await _fijar(mundo, campo, Gender.FEMALE, TeeColor.BLUE)
        await mundo.cerrar()
        if estado in ("en_curso", "terminada"):
            await mundo.empezar()
        if estado == "terminada":
            await mundo.terminar()
        if estado == "cancelada":
            await mundo.cancelar()
        mundo.uow.competitions.find_by_id_for_update = AsyncMock(
            wraps=mundo.uow.competitions.find_by_id_for_update
        )

        respuesta = await _fijadas(mundo)

        assert _filas(respuesta) == [(campo.value, "FEMALE", "BLUE")]
        mundo.uow.competitions.find_by_id_for_update.assert_not_awaited()
