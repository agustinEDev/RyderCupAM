"""
La barra de un campo para todos los de un género (R2, 20 nov 2026).

`PUT /competitions/{id}/courses/{golf_course_id}/tee` con `{gender, tee_color}`.
Solo el organizador o un admin, también con la competición en curso:

| Caso                                                     | Resultado                               |
|----------------------------------------------------------|-----------------------------------------|
| Azules para las mujeres en el segundo campo              | Guardado                                |
| Un fourball con las dos mujeres                          | Las dos en azules, en el mismo partido  |
| Una mujer con cambio propio en ese campo                 | No cambia (R1 gana)                     |
| Los hombres                                              | No cambian                              |
| null                                                     | Se quita; vuelven a su general          |
| Una barra que ese campo no tiene para ese género         | 422 TEE_NOT_AVAILABLE                   |
| Un campo que no es de la competición                     | 404                                     |
| Una jugadora o una capitana                              | 403                                     |
| En curso                                                 | Sí                                      |
| Terminada                                                | 409 TEE_CHANGE_CLOSED                   |
| Uno que no se puede rehacer                              | 409, y no cambia nada de nadie          |
| El log                                                   | ids, sin nombres                        |
"""

import logging
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    SetCompetitionCourseTeeRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CourseNotInCompetitionError,
    NotCompetitionCreatorError,
    PendingGameNotRecalculableError,
    TeeChangeClosedError,
    TeeNotAvailableError,
)
from src.modules.competition.application.use_cases.set_competition_course_tee_use_case import (
    SetCompetitionCourseTeeUseCase,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from tests.unit.modules.competition.application.use_cases.test_change_enrollment_course_tee_use_case import (
    SIN_ROJAS,
    _fijar,
)
from tests.unit.modules.competition.application.use_cases.test_change_enrollment_tee_use_case import (
    ALDEAMAYOR,
    _Mundo,
)

pytestmark = pytest.mark.asyncio


async def _para_todas(mundo, campo, color, genero=Gender.FEMALE, quien=None, is_admin=False):
    return await SetCompetitionCourseTeeUseCase(
        mundo.uow, golf_course_repository=mundo.campos, user_repository=mundo.usuarios
    ).execute(
        SetCompetitionCourseTeeRequestDTO(
            competition_id=mundo.competition_id.value,
            golf_course_id=campo.value,
            gender=genero,
            tee_color=color,
        ),
        quien or mundo.organizador,
        is_admin=is_admin,
    )


async def _del_campo(mundo, campo):
    return (await mundo.uow.barras_por_campo.del_campo(mundo.competition_id, campo)).por_genero


async def _con_fourball():
    """Fourball en el segundo campo: jugadora y capitana (mujeres) contra dos hombres."""
    mundo = await _Mundo().montar(campos=(ALDEAMAYOR, SIN_ROJAS))
    segundo = list(mundo.campos.por_id)[1]
    partido = await mundo.partido(
        [mundo.jugadora, mundo.capitana],
        [mundo.capitan_b, mundo.otro],
        formato=MatchFormat.FOURBALL,
        campo=1,
    )
    return mundo, segundo, partido


class TestLaBarraDelCampo:
    async def test_course_tee_for_women_rebuilds_both_women_in_the_same_match(self):
        """
        Given un fourball en el segundo campo con las dos mujeres en el mismo bando
        When el organizador fija azules allí para las mujeres
        Then se guarda, y en ese partido las dos juegan azules de mujer
        """
        mundo, segundo, partido = await _con_fourball()

        respuesta = await _para_todas(mundo, segundo, TeeColor.BLUE)

        assert (respuesta.gender, respuesta.tee_color) == ("FEMALE", "BLUE")
        assert await _del_campo(mundo, segundo) == {Gender.FEMALE: TeeColor.BLUE}
        rehecho = await mundo.el_partido(partido)
        for mujer in (mundo.jugadora, mundo.capitana):
            foto = rehecho.find_player(mujer)
            assert (foto.tee_color, foto.tee_gender) == (TeeColor.BLUE, Gender.FEMALE)

    async def test_course_tee_for_women_leaves_men_and_own_changes_alone(self):
        """
        Given un segundo campo con azules y blancas de mujer, el fourball de las dos
            mujeres allí, y la jugadora con su cambio propio a BLANCAS en ese campo
        When el organizador fija AZULES allí para las mujeres
        Then la jugadora sigue en blancas (R1 gana a R2, aunque sea otro color), la
            capitana pasa a azules y los hombres siguen en sus amarillas
        """
        mundo = await _Mundo().montar(
            campos=(ALDEAMAYOR, [*SIN_ROJAS, (TeeColor.WHITE, Gender.FEMALE)])
        )
        segundo = list(mundo.campos.por_id)[1]
        partido = await mundo.partido(
            [mundo.jugadora, mundo.capitana],
            [mundo.capitan_b, mundo.otro],
            formato=MatchFormat.FOURBALL,
            campo=1,
        )
        await _fijar(mundo, segundo, TeeColor.WHITE)

        await _para_todas(mundo, segundo, TeeColor.BLUE)

        rehecho = await mundo.el_partido(partido)
        assert rehecho.find_player(mundo.jugadora).tee_color == TeeColor.WHITE
        assert rehecho.find_player(mundo.capitana).tee_color == TeeColor.BLUE
        for hombre in (mundo.capitan_b, mundo.otro):
            assert rehecho.find_player(hombre).tee_color == TeeColor.YELLOW

    async def test_course_tee_null_removes_it_and_goes_back_to_the_general_tee(self):
        """
        Given azules para las mujeres en el segundo campo
        When el organizador la quita (null)
        Then ya no hay barra del campo para ellas, y su partido vuelve a su general
            (rojas, que ese campo no tiene: 422)
        """
        mundo, segundo, _ = await _con_fourball()
        await _para_todas(mundo, segundo, TeeColor.BLUE)

        with pytest.raises(TeeNotAvailableError):
            await _para_todas(mundo, segundo, None)

        assert await _del_campo(mundo, segundo) == {Gender.FEMALE: TeeColor.BLUE}

    async def test_course_tee_not_rated_for_that_gender_is_rejected(self):
        """
        Given el segundo campo sin rojas de mujer
        When el organizador fija rojas allí para las mujeres
        Then 422 y nada cambia
        """
        mundo, segundo, _ = await _con_fourball()

        with pytest.raises(TeeNotAvailableError):
            await _para_todas(mundo, segundo, TeeColor.RED)

        assert await _del_campo(mundo, segundo) == {}

    async def test_course_tee_not_rated_for_that_gender_without_games_is_rejected(self):
        """
        Given el segundo campo sin rojas de mujer y nada generado todavía
        When el organizador fija rojas allí para las mujeres
        Then 422 igualmente: el campo no las tiene, aunque no haya nada que rehacer
        """
        mundo = await _Mundo().montar(campos=(ALDEAMAYOR, SIN_ROJAS))
        segundo = list(mundo.campos.por_id)[1]

        with pytest.raises(TeeNotAvailableError):
            await _para_todas(mundo, segundo, TeeColor.RED)

        assert await _del_campo(mundo, segundo) == {}

    async def test_course_tee_on_a_course_of_another_competition_is_not_found(self):
        """
        Given un campo que no es de la competición
        When el organizador fija una barra en él
        Then 404
        """
        mundo, _, _ = await _con_fourball()

        with pytest.raises(CourseNotInCompetitionError):
            await _para_todas(mundo, GolfCourseId(uuid4()), TeeColor.BLUE)

    async def test_course_tee_that_cannot_rebuild_someone_changes_nothing(self):
        """
        Given el fourball de las dos mujeres y, aparte, un individual de la capitana
            en el segundo campo con un rival en blancas que el campo ya no tiene
        When el organizador fija azules allí para las mujeres
        Then 409 PENDING_GAME_NOT_RECALCULABLE, y no cambia nada de nadie
        """
        mundo, segundo, partido = await _con_fourball()
        await mundo.partido(
            [mundo.capitana],
            [mundo.capitan_b],
            campo=1,
            barras={mundo.capitan_b: (TeeColor.WHITE, Gender.MALE)},
        )

        with pytest.raises(PendingGameNotRecalculableError):
            await _para_todas(mundo, segundo, TeeColor.BLUE)

        assert await _del_campo(mundo, segundo) == {}
        assert (await mundo.el_partido(partido)).find_player(mundo.jugadora).tee_color == (
            TeeColor.YELLOW
        )

    async def test_course_tee_logs_who_where_and_how_many(self, caplog):
        """
        Given el fourball de las dos mujeres en el segundo campo
        When el organizador fija azules allí para las mujeres
        Then queda en el log quién, la competición, el campo, el género, la barra y
            cuántos partidos se rehicieron
        """
        mundo, segundo, _ = await _con_fourball()

        with caplog.at_level(logging.INFO):
            await _para_todas(mundo, segundo, TeeColor.BLUE)

        [registro] = [r for r in caplog.records if "Course tee for gender" in r.getMessage()]
        mensaje = registro.getMessage()
        for trozo in (
            str(mundo.organizador.value),
            str(mundo.competition_id.value),
            str(segundo.value),
            "gender=FEMALE",
            "to=BLUE",
            "matches=1",
        ):
            assert trozo in mensaje


class TestQuien:
    @pytest.mark.parametrize("quien", ["jugadora", "capitana"])
    async def test_course_tee_by_a_player_or_a_captain_is_forbidden(self, quien):
        """
        Given equipos formados
        When una jugadora o una capitana fijan la barra del campo para las mujeres
        Then 403: solo el organizador o un admin
        """
        mundo = await (await _Mundo().montar(campos=(ALDEAMAYOR, SIN_ROJAS))).con_equipos()
        segundo = list(mundo.campos.por_id)[1]

        with pytest.raises(NotCompetitionCreatorError):
            await _para_todas(mundo, segundo, TeeColor.BLUE, quien=getattr(mundo, quien))

    async def test_course_tee_by_an_admin_in_progress_is_allowed(self):
        """
        Given la competición en curso
        When un admin fija azules para las mujeres en el segundo campo
        Then se guarda
        """
        mundo = await (await _Mundo().montar(campos=(ALDEAMAYOR, SIN_ROJAS))).con_equipos()
        segundo = list(mundo.campos.por_id)[1]
        await mundo.empezar()

        await _para_todas(mundo, segundo, TeeColor.BLUE, quien=UserId(uuid4()), is_admin=True)

        assert await _del_campo(mundo, segundo) == {Gender.FEMALE: TeeColor.BLUE}

    async def test_course_tee_once_finished_is_closed(self):
        """
        Given una competición terminada
        When el organizador fija una barra del campo
        Then 409 TEE_CHANGE_CLOSED
        """
        mundo = await (await _Mundo().montar(campos=(ALDEAMAYOR, SIN_ROJAS))).con_equipos()
        segundo = list(mundo.campos.por_id)[1]
        await mundo.empezar()
        await mundo.terminar()

        with pytest.raises(TeeChangeClosedError):
            await _para_todas(mundo, segundo, TeeColor.BLUE)
