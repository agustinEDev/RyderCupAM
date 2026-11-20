"""
Las barras que se pueden elegir para una inscripción (BE #912, 20 nov 2026).

El front no conoce el género de los demás inscritos: al organizador o al capitán
el selector solo podía ofrecer mixtas. El back calcula la lista con la MISMA
regla que aplica el cambio (`PUT /enrollments/{id}/tee`):

| Caso                                              | Respuesta                                  |
|---------------------------------------------------|--------------------------------------------|
| Jugadora en Aldeamayor (azules y rojas de mujer)  | tees [RED, BLUE], default RED, current None |
| Ya eligió azules                                  | current BLUE                               |
| Sin género en el perfil                           | solo mixtas                                |
| SCRATCH con barras solo con tarjeta               | también esas                               |
| Sin campos                                        | []                                         |
| Usuario que ya no existe                          | solo mixtas, default None                  |
| Otro jugador / capitán del otro equipo            | 403                                        |
| Organizador, admin, capitán de su equipo, ella    | como el cambio                             |
| En curso: la propia jugadora                      | 403                                        |
| Terminada o cancelada (a quien podría)            | 409 TEE_CHANGE_CLOSED                      |
| Inscripción no aprobada                           | 409 ENROLLMENT_NOT_APPROVED                |
| Inscripción que no existe                         | 404                                        |
| Para cada barra: en la lista ⇔ el cambio la acepta | la misma regla                             |
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.enrollment_dto import (
    ChangeEnrollmentTeeRequestDTO,
)
from src.modules.competition.application.exceptions import (
    EnrollmentNotFoundError,
    NotCompetitionCreatorError,
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

pytestmark = pytest.mark.asyncio


async def _barras(mundo, quien=None, is_admin=False, de=None, inscripcion=None):
    inscripcion = inscripcion or (mundo.inscripciones[de] if de else mundo.inscripcion)
    return await GetEnrollmentTeesUseCase(
        mundo.uow, golf_course_repository=mundo.campos, user_repository=mundo.usuarios
    ).execute(inscripcion.id.value, quien or mundo.jugadora, is_admin=is_admin)


class TestQueBarras:
    async def test_get_tees_of_a_player_lists_her_rated_tees_and_her_default(self):
        """
        Given la jugadora en Aldeamayor (amarillas de hombre, azules y rojas de mujer)
        When pide sus barras
        Then le salen rojas y azules, en el orden de los colores (`TeeColor`); por defecto, rojas; sin
            elegir todavía
        """
        mundo = await _Mundo().montar()

        respuesta = await _barras(mundo)

        assert respuesta.tees == ["RED", "BLUE"]
        assert respuesta.default_tee == "RED"
        assert respuesta.current_tee is None

    async def test_get_tees_after_choosing_shows_the_current_one(self):
        """
        Given la jugadora, que ya eligió azules
        When pide sus barras
        Then la actual es azules
        """
        mundo = await _Mundo().montar()
        await mundo.cambiar(TeeColor.BLUE)

        assert (await _barras(mundo)).current_tee == "BLUE"

    async def test_get_tees_of_a_player_without_gender_lists_only_mixed_tees(self):
        """
        Given un campo con blancas mixtas y rojas de mujer, y un jugador sin género
        When se piden sus barras
        Then solo las mixtas; por defecto, amarillas como siempre
        """
        mundo = await _Mundo().montar(
            campos=([(TeeColor.WHITE, None), (TeeColor.RED, Gender.FEMALE)],)
        )
        mundo.usuarios.poner(mundo.jugadora, None)

        respuesta = await _barras(mundo)

        assert respuesta.tees == ["WHITE"]
        assert respuesta.default_tee == "YELLOW"

    async def test_get_tees_of_an_unknown_user_lists_only_mixed_and_no_default(self):
        """
        Given una inscripción cuyo usuario ya no se encuentra
        When el organizador pide sus barras
        Then solo mixtas, y sin barra por defecto: no se sabe cuál tendría
        """
        mundo = await _Mundo().montar(campos=([(TeeColor.WHITE, None), *ALDEAMAYOR],))
        mundo.usuarios.quitar(mundo.jugadora)

        respuesta = await _barras(mundo, quien=mundo.organizador)

        assert respuesta.tees == ["WHITE"]
        assert respuesta.default_tee is None

    async def test_get_tees_in_scratch_includes_tees_with_only_a_card(self):
        """
        Given una competición SCRATCH con blancas de mujer que solo tienen tarjeta
        When la jugadora pide sus barras
        Then también salen las blancas
        """
        mundo = await _Mundo().montar(
            campos=([*ALDEAMAYOR, (TeeColor.WHITE, Gender.FEMALE, SOLO_TARJETA)],),
            play_mode="SCRATCH",
        )

        assert (await _barras(mundo)).tees == ["RED", "BLUE", "WHITE"]

    async def test_get_tees_with_handicap_leaves_out_tees_with_only_a_card(self):
        """
        Given la misma competición con hándicap
        When la jugadora pide sus barras
        Then las blancas sin valorar no salen
        """
        mundo = await _Mundo().montar(
            campos=([*ALDEAMAYOR, (TeeColor.WHITE, Gender.FEMALE, SOLO_TARJETA)],)
        )

        assert (await _barras(mundo)).tees == ["RED", "BLUE"]

    async def test_get_tees_without_courses_is_an_empty_list(self):
        """
        Given una competición sin campos
        When la jugadora pide sus barras
        Then la lista está vacía
        """
        mundo = await _Mundo().montar(campos=())

        assert (await _barras(mundo)).tees == []

    async def test_get_tees_does_not_lock_anything(self):
        """
        Given la jugadora inscrita
        When pide sus barras
        Then no se bloquea nada: es una lectura
        """
        mundo = await _Mundo().montar()
        mundo.uow.competitions.find_by_id_for_update = AsyncMock(
            wraps=mundo.uow.competitions.find_by_id_for_update
        )

        await _barras(mundo)

        mundo.uow.competitions.find_by_id_for_update.assert_not_awaited()


class TestLaMismaReglaQueElCambio:
    @pytest.mark.parametrize(
        ("campos", "play_mode", "genero"),
        [
            ((ALDEAMAYOR,), "HANDICAP", Gender.FEMALE),
            ((ALDEAMAYOR,), "HANDICAP", None),
            (([*ALDEAMAYOR, (TeeColor.WHITE, None)],), "HANDICAP", Gender.MALE),
            (
                ([*ALDEAMAYOR, (TeeColor.WHITE, Gender.FEMALE, SOLO_TARJETA)],),
                "SCRATCH",
                Gender.FEMALE,
            ),
            (
                (ALDEAMAYOR, [(TeeColor.BLACK, Gender.FEMALE), (TeeColor.GREEN, None)]),
                "HANDICAP",
                Gender.FEMALE,
            ),
        ],
    )
    async def test_get_tees_lists_exactly_what_the_change_accepts(self, campos, play_mode, genero):
        """
        Given una competición y una jugadora (con o sin género)
        When se comparan sus barras con lo que acepta el cambio, color a color
        Then una barra está en la lista si y solo si el cambio la acepta
        """
        mundo = await _Mundo().montar(campos=campos, play_mode=play_mode)
        mundo.usuarios.poner(mundo.jugadora, genero)

        ofrecidas = set((await _barras(mundo, quien=mundo.organizador)).tees)

        for color in TeeColor:
            try:
                await mundo.caso().execute(
                    ChangeEnrollmentTeeRequestDTO(
                        enrollment_id=mundo.inscripcion.id.value, tee_color=color
                    ),
                    mundo.organizador,
                )
                aceptada = True
            except TeeNotAvailableError:
                aceptada = False
            assert (color.value in ofrecidas) == aceptada, color


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

        assert (await _barras(mundo, quien=user_id, is_admin=is_admin)).tees == ["RED", "BLUE"]

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
