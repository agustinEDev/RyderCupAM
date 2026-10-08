"""
Las reglas para coger plaza en una franja (#251, decididas el 6-8 oct 2026).

| Caso                                              | Resultado                               |
|---------------------------------------------------|-----------------------------------------|
| Hay sitio, primera franja                         | Vale                                    |
| La franja está llena                              | No: «llena»                             |
| Ya está en esa franja                             | No                                      |
| Ya tiene otra franja ese día                      | No: una por jornada                     |
| Cambiarse a otra del mismo día (en lugar de)      | Vale                                    |
| «En lugar de» una que no es suya                  | No                                      |
| Cupo de jornadas: 1 y ya juega otro día           | No: «jornadas»                          |
| Cupo de jornadas: 2 y juega otro día              | Vale                                    |
| Cambiarse de día con el cupo lleno (en lugar de)  | Vale: no suma jornada                   |
| Una sesión sin hoja (Ryder)                       | No                                      |
"""

from datetime import date, time

import pytest

from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.services.plazas_en_franjas import (
    PlazaNoPosibleError,
    PlazasEnFranjas,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.shared.domain.value_objects.match_format import MatchFormat

VIERNES = date(2030, 10, 11)
SABADO = date(2030, 10, 12)
COMPETICION = CompetitionId.generate()


def _franja(dia=VIERNES, sesion=SessionType.MORNING, salidas=2) -> Round:
    # 9:00 y 9:10 de 3: cupo 6 con dos salidas
    ultima = time(9, 0) if salidas == 1 else time(9, 10)
    return Round.create_franja(
        competition_id=COMPETICION,
        golf_course_id=GolfCourseId.generate(),
        round_date=dia,
        session_type=sesion,
        hoja_de_salidas=HojaDeSalidas(time(9, 0), ultima, 10, 3),
    )


def _coger(franja, suyas=(), ocupadas=0, max_jornadas=1, en_lugar_de=None):
    PlazasEnFranjas.comprobar(
        franja=franja,
        suyas=list(suyas),
        ocupadas=ocupadas,
        max_jornadas=max_jornadas,
        en_lugar_de=en_lugar_de,
    )


class TestCogerPlaza:
    def test_con_sitio_vale(self):
        _coger(_franja())

    def test_llena_no(self):
        with pytest.raises(PlazaNoPosibleError, match="llena"):
            _coger(_franja(), ocupadas=6)

    def test_casi_llena_vale(self):
        _coger(_franja(), ocupadas=5)

    def test_ya_esta_en_esa_no(self):
        franja = _franja()

        with pytest.raises(PlazaNoPosibleError, match="Ya"):
            _coger(franja, suyas=[franja])

    def test_otra_el_mismo_dia_no(self):
        with pytest.raises(PlazaNoPosibleError, match="una franja por jornada"):
            _coger(_franja(sesion=SessionType.AFTERNOON), suyas=[_franja()])

    def test_cambiarse_a_otra_del_mismo_dia_vale(self):
        manana = _franja()

        _coger(_franja(sesion=SessionType.AFTERNOON), suyas=[manana], en_lugar_de=manana.id)

    def test_en_lugar_de_una_que_no_es_suya_no(self):
        with pytest.raises(PlazaNoPosibleError, match="no tiene"):
            _coger(_franja(), en_lugar_de=_franja(dia=SABADO).id)


class TestCupoDeJornadas:
    def test_con_cupo_1_y_otro_dia_no(self):
        with pytest.raises(PlazaNoPosibleError, match="jornadas"):
            _coger(_franja(dia=SABADO), suyas=[_franja()], max_jornadas=1)

    def test_con_cupo_2_y_otro_dia_vale(self):
        _coger(_franja(dia=SABADO), suyas=[_franja()], max_jornadas=2)

    def test_cambiarse_de_dia_con_el_cupo_lleno_vale(self):
        viernes = _franja()

        _coger(_franja(dia=SABADO), suyas=[viernes], max_jornadas=1, en_lugar_de=viernes.id)


class TestSoloFranjas:
    def test_una_sesion_de_ryder_no(self):
        sesion = Round.create(
            competition_id=COMPETICION,
            golf_course_id=GolfCourseId.generate(),
            round_date=VIERNES,
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )

        with pytest.raises(PlazaNoPosibleError, match="franja"):
            _coger(sesion)
