"""
Las barras de una inscripción, campo a campo (barras por campo, 20 nov 2026).

El front no conoce el género de los demás inscritos: las opciones las calcula el
back con la MISMA regla que aplican los cambios. Por cada campo de la
competición: la barra que juega (o null), de dónde sale y las que se pueden elegir.

| Caso                                               | Campo                                |
|----------------------------------------------------|--------------------------------------|
| Sin cambios, con las habituales en el campo        | tee RED, source GENERAL              |
| Sin cambios, sin su barra en el campo              | tee null, source NONE (R4)           |
| Con un cambio propio                               | source OWN                           |
| Con la del campo para su género                    | source COURSE                        |
| Opciones                                           | las que valen en ESE campo           |
| Sin género / SCRATCH con tarjeta / sin campos      | solo mixtas / también esas / []      |
| Usuario que ya no existe                           | default null                         |
| Para cada campo y barra: opción ⇔ el cambio la acepta | la misma regla                    |
| Quién                                              | los mismos que pueden cambiarlas     |
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.enrollment_dto import (
    ChangeEnrollmentCourseTeeRequestDTO,
)
from src.modules.competition.application.exceptions import (
    EnrollmentNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.use_cases.change_enrollment_course_tee_use_case import (
    ChangeEnrollmentCourseTeeUseCase,
)
from src.modules.competition.application.use_cases.change_enrollment_tee_use_case import (
    EnrollmentNotApprovedError,
    TeeChangeClosedError,
    TeeNotAvailableError,
)
from src.modules.competition.application.use_cases.get_enrollment_tees_use_case import (
    GetEnrollmentTeesUseCase,
)
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.competition.application.use_cases.test_change_enrollment_tee_use_case import (
    ALDEAMAYOR,
    SOLO_TARJETA,
    _Mundo,
)

# Un segundo campo sin rojas de mujer
SIN_ROJAS = [(TeeColor.YELLOW, Gender.MALE), (TeeColor.BLUE, Gender.FEMALE)]

pytestmark = pytest.mark.asyncio


async def _barras(mundo, quien=None, is_admin=False, de=None, inscripcion=None):
    inscripcion = inscripcion or (mundo.inscripciones[de] if de else mundo.inscripcion)
    return await GetEnrollmentTeesUseCase(
        mundo.uow, golf_course_repository=mundo.campos, user_repository=mundo.usuarios
    ).execute(inscripcion.id.value, quien or mundo.jugadora, is_admin=is_admin)


def _campos(mundo):
    campos = list(mundo.campos.por_id)
    for n, campo_id in enumerate(campos, start=1):
        mundo.campos.por_id[campo_id].name = f"Campo {n}"
    return campos


def _cambio_propio(mundo):
    return ChangeEnrollmentCourseTeeUseCase(
        mundo.uow, golf_course_repository=mundo.campos, user_repository=mundo.usuarios
    )


async def _propio(mundo, campo, color, quien=None):
    return await _cambio_propio(mundo).execute(
        ChangeEnrollmentCourseTeeRequestDTO(
            enrollment_id=mundo.inscripcion.id.value, golf_course_id=campo.value, tee_color=color
        ),
        quien or mundo.jugadora,
    )


class TestCampoACampo:
    async def test_get_tees_lists_each_course_with_her_tee_its_source_and_options(self):
        """
        Given la jugadora sin barra elegida, en Aldeamayor (rojas y azules de mujer) y en
            un campo sin rojas de mujer
        When pide sus barras
        Then en Aldeamayor juega rojas (las habituales, GENERAL), en el otro ninguna
            (NONE) y solo puede elegir azules; general null y por defecto rojas
        """
        mundo = await _Mundo().montar(campos=(ALDEAMAYOR, SIN_ROJAS))
        primero, segundo = _campos(mundo)

        respuesta = await _barras(mundo)

        assert (respuesta.general_tee, respuesta.default_tee) == (None, "RED")
        assert [
            (c.golf_course_id, c.golf_course_name, c.tee, c.source, c.options)
            for c in respuesta.courses
        ] == [
            (primero.value, "Campo 1", "RED", "GENERAL", ["RED", "BLUE"]),
            (segundo.value, "Campo 2", None, "NONE", ["BLUE"]),
        ]

    async def test_get_tees_with_an_own_change_says_own(self):
        """
        Given su cambio propio a azules en el segundo campo
        When pide sus barras
        Then allí juega azules, de origen OWN
        """
        mundo = await _Mundo().montar(campos=(ALDEAMAYOR, SIN_ROJAS))
        _, segundo = _campos(mundo)
        await _propio(mundo, segundo, TeeColor.BLUE)

        campo = (await _barras(mundo)).courses[1]

        assert (campo.tee, campo.source) == ("BLUE", "OWN")

    async def test_get_tees_with_the_course_tee_for_her_gender_says_course(self):
        """
        Given azules fijadas en el segundo campo para las mujeres
        When pide sus barras
        Then allí juega azules, de origen COURSE
        """
        mundo = await _Mundo().montar(campos=(ALDEAMAYOR, SIN_ROJAS))
        _, segundo = _campos(mundo)
        await mundo.uow.barras_por_campo.fijar_del_campo(
            mundo.competition_id, segundo, Gender.FEMALE, TeeColor.BLUE
        )

        campo = (await _barras(mundo)).courses[1]

        assert (campo.tee, campo.source) == ("BLUE", "COURSE")

    async def test_get_tees_with_both_her_own_change_and_the_course_tee_says_own(self):
        """
        Given azules para las mujeres en el segundo campo y su cambio propio también
            a azules allí
        When pide sus barras
        Then de origen OWN: su cambio propio gana
        """
        mundo = await _Mundo().montar(campos=(ALDEAMAYOR, SIN_ROJAS))
        _, segundo = _campos(mundo)
        await mundo.uow.barras_por_campo.fijar_del_campo(
            mundo.competition_id, segundo, Gender.FEMALE, TeeColor.BLUE
        )
        await _propio(mundo, segundo, TeeColor.BLUE)

        assert (await _barras(mundo)).courses[1].source == "OWN"

    async def test_get_tees_after_choosing_shows_her_general_tee(self):
        """
        Given la jugadora, que eligió azules como barra general
        When pide sus barras
        Then su general es azules, y la juega en los dos campos
        """
        mundo = await _Mundo().montar(campos=(ALDEAMAYOR, SIN_ROJAS))
        _campos(mundo)
        await mundo.cambiar(TeeColor.BLUE)

        respuesta = await _barras(mundo)

        assert respuesta.general_tee == "BLUE"
        assert [c.tee for c in respuesta.courses] == ["BLUE", "BLUE"]

    async def test_get_tees_of_a_player_without_gender_offers_only_mixed_tees(self):
        """
        Given un campo con blancas mixtas y rojas de mujer, y un jugador sin género
        When se piden sus barras
        Then solo puede elegir las mixtas; por defecto, amarillas como siempre
        """
        mundo = await _Mundo().montar(
            campos=([(TeeColor.WHITE, None), (TeeColor.RED, Gender.FEMALE)],)
        )
        _campos(mundo)
        mundo.usuarios.poner(mundo.jugadora, None)

        respuesta = await _barras(mundo)

        assert respuesta.courses[0].options == ["WHITE"]
        assert respuesta.default_tee == "YELLOW"

    async def test_get_tees_of_an_unknown_user_offers_mixed_and_no_default(self):
        """
        Given una inscripción cuyo usuario ya no se encuentra
        When el organizador pide sus barras
        Then solo mixtas, y sin barra por defecto
        """
        mundo = await _Mundo().montar(campos=([(TeeColor.WHITE, None), *ALDEAMAYOR],))
        _campos(mundo)
        mundo.usuarios.quitar(mundo.jugadora)

        respuesta = await _barras(mundo, quien=mundo.organizador)

        assert respuesta.courses[0].options == ["WHITE"]
        assert respuesta.default_tee is None

    async def test_get_tees_in_scratch_offers_tees_with_only_a_card(self):
        """
        Given una competición SCRATCH con blancas de mujer que solo tienen tarjeta
        When la jugadora pide sus barras
        Then también puede elegir blancas; con hándicap, no
        """
        barras = [*ALDEAMAYOR, (TeeColor.WHITE, Gender.FEMALE, SOLO_TARJETA)]
        scratch = await _Mundo().montar(campos=(barras,), play_mode="SCRATCH")
        con_handicap = await _Mundo().montar(campos=(barras,))
        _campos(scratch)
        _campos(con_handicap)

        assert (await _barras(scratch)).courses[0].options == ["RED", "BLUE", "WHITE"]
        assert (await _barras(con_handicap)).courses[0].options == ["RED", "BLUE"]

    async def test_get_tees_without_courses_has_no_courses(self):
        """
        Given una competición sin campos
        When la jugadora pide sus barras
        Then no hay campos
        """
        mundo = await _Mundo().montar(campos=())

        assert (await _barras(mundo)).courses == []

    async def test_get_tees_does_not_lock_anything(self):
        """
        Given la jugadora inscrita
        When pide sus barras
        Then no se bloquea nada: es una lectura
        """
        mundo = await _Mundo().montar()
        _campos(mundo)
        mundo.uow.competitions.find_by_id_for_update = AsyncMock(
            wraps=mundo.uow.competitions.find_by_id_for_update
        )

        await _barras(mundo)

        mundo.uow.competitions.find_by_id_for_update.assert_not_awaited()


class TestLaMismaReglaQueElCambio:
    @pytest.mark.parametrize(
        ("campos", "play_mode", "genero"),
        [
            ((ALDEAMAYOR, SIN_ROJAS), "HANDICAP", Gender.FEMALE),
            ((ALDEAMAYOR,), "HANDICAP", None),
            (([*ALDEAMAYOR, (TeeColor.WHITE, None)],), "HANDICAP", Gender.MALE),
            (
                ([*ALDEAMAYOR, (TeeColor.WHITE, Gender.FEMALE, SOLO_TARJETA)],),
                "SCRATCH",
                Gender.FEMALE,
            ),
        ],
    )
    async def test_get_tees_offers_exactly_what_the_course_change_accepts(
        self, campos, play_mode, genero
    ):
        """
        Given una competición y una jugadora (con o sin género)
        When se comparan, campo a campo y color a color, sus opciones con lo que
            acepta su cambio propio para ese campo
        Then una barra es opción si y solo si el cambio la acepta
        """
        mundo = await _Mundo().montar(campos=campos, play_mode=play_mode)
        _campos(mundo)
        mundo.usuarios.poner(mundo.jugadora, genero)

        respuesta = await _barras(mundo, quien=mundo.organizador)

        for campo in respuesta.courses:
            for color in TeeColor:
                try:
                    await _cambio_propio(mundo).execute(
                        ChangeEnrollmentCourseTeeRequestDTO(
                            enrollment_id=mundo.inscripcion.id.value,
                            golf_course_id=campo.golf_course_id,
                            tee_color=color,
                        ),
                        mundo.organizador,
                    )
                    aceptada = True
                except TeeNotAvailableError:
                    aceptada = False
                assert (color.value in campo.options) == aceptada, (campo.golf_course_id, color)


class TestQuien:
    @pytest.mark.parametrize("quien", ["jugadora", "organizador", "admin", "capitana"])
    async def test_get_tees_by_those_who_can_change_them_answers(self, quien):
        """
        Given equipos formados y la competición sin empezar
        When la propia jugadora, el organizador, un admin o la capitana de su equipo
            piden sus barras
        Then responden
        """
        mundo = await (await _Mundo().montar()).con_equipos()
        quienes = {
            "jugadora": (mundo.jugadora, False),
            "organizador": (mundo.organizador, False),
            "admin": (UserId(uuid4()), True),
            "capitana": (mundo.capitana, False),
        }
        user_id, is_admin = quienes[quien]

        respuesta = await _barras(mundo, quien=user_id, is_admin=is_admin)

        assert respuesta.courses[0].options == ["RED", "BLUE"]

    @pytest.mark.parametrize("quien", ["otro", "capitan_b"])
    async def test_get_tees_by_another_player_or_the_other_captain_is_forbidden(self, quien):
        """
        Given equipos formados
        When otro jugador o el capitán del otro equipo piden las barras de la jugadora
        Then 403
        """
        mundo = await (await _Mundo().montar()).con_equipos()

        with pytest.raises(NotCompetitionCreatorError):
            await _barras(mundo, quien=getattr(mundo, quien))

    async def test_get_tees_in_progress_by_the_player_is_forbidden(self):
        """
        Given la competición en curso
        When la propia jugadora (no capitana) pide sus barras
        Then 403: ya no las puede cambiar
        """
        mundo = await (await _Mundo().montar()).con_equipos()
        await mundo.empezar()

        with pytest.raises(NotCompetitionCreatorError):
            await _barras(mundo)

    @pytest.mark.parametrize("final", ["terminar", "cancelar"])
    async def test_get_tees_once_finished_is_closed_for_the_organizer(self, final):
        """
        Given una competición terminada o cancelada
        When el organizador pide las barras
        Then 409 TEE_CHANGE_CLOSED
        """
        mundo = await (await _Mundo().montar()).con_equipos()
        if final == "terminar":
            await mundo.empezar()
        await getattr(mundo, final)()

        with pytest.raises(TeeChangeClosedError):
            await _barras(mundo, quien=mundo.organizador)

    async def test_get_tees_once_finished_by_the_player_is_forbidden(self):
        """
        Given una competición terminada
        When la propia jugadora pide sus barras
        Then 403, sin decirle nada del estado
        """
        mundo = await (await _Mundo().montar()).con_equipos()
        await mundo.empezar()
        await mundo.terminar()

        with pytest.raises(NotCompetitionCreatorError):
            await _barras(mundo)

    @pytest.mark.parametrize(
        "estado",
        [EnrollmentStatus.INVITED, EnrollmentStatus.REQUESTED, EnrollmentStatus.WITHDRAWN],
    )
    async def test_get_tees_of_an_enrollment_not_approved_is_rejected(self, estado):
        """
        Given una inscripción que no está aprobada
        When el organizador pide sus barras
        Then 409 ENROLLMENT_NOT_APPROVED
        """
        mundo = await _Mundo().montar()
        inscripcion = await mundo.inscripcion_en(estado)

        with pytest.raises(EnrollmentNotApprovedError):
            await _barras(mundo, quien=mundo.organizador, inscripcion=inscripcion)

    async def test_get_tees_of_an_unknown_enrollment_is_not_found(self):
        """
        Given una inscripción que no existe
        When se piden sus barras
        Then 404
        """
        mundo = await _Mundo().montar()

        with pytest.raises(EnrollmentNotFoundError):
            await GetEnrollmentTeesUseCase(
                mundo.uow, golf_course_repository=mundo.campos, user_repository=mundo.usuarios
            ).execute(uuid4(), mundo.organizador)
