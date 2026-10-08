"""
Las reglas de la lista de espera de una franja (#251, decididas el 20 sep y el 8 oct 2026).

| Caso                                              | ¿Puede esperar? / ¿Le toca? |
|---------------------------------------------------|-----------------------------|
| Franja llena, ese día no juega, cupo libre        | Espera                      |
| Franja con sitio                                  | No: que coja plaza          |
| Ya juega ese día                                  | No                          |
| Cupo de jornadas lleno                            | No                          |
| Ya espera en esa                                  | No                          |
| Ya tiene plaza en esa                             | No                          |
| Le toca: ese día ya juega (cogió otra)            | Se salta                    |
| Le toca: cupo lleno                               | Se salta                    |
| Le toca: puede                                    | Sí                          |
"""

from datetime import date, time

import pytest

from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.services.listas_de_espera import (
    EsperaNoPosibleError,
    ListasDeEspera,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId

VIERNES = date(2030, 10, 11)
SABADO = date(2030, 10, 12)
COMPETICION = CompetitionId.generate()


def _franja(dia=VIERNES, sesion=SessionType.MORNING) -> Round:
    return Round.create_franja(
        competition_id=COMPETICION,
        golf_course_id=GolfCourseId.generate(),
        round_date=dia,
        session_type=sesion,
        hoja_de_salidas=HojaDeSalidas(time(9, 0), time(9, 0), 10, 3),  # cupo 3
    )


def _esperar(franja, suyas=(), ocupadas=3, max_jornadas=1, ya_espera=False):
    ListasDeEspera.comprobar_espera(
        franja=franja,
        suyas=list(suyas),
        ocupadas=ocupadas,
        max_jornadas=max_jornadas,
        ya_espera=ya_espera,
    )


class TestEsperar:
    def test_llena_y_libre_ese_dia_espera(self):
        _esperar(_franja())

    def test_con_sitio_que_coja_plaza(self):
        with pytest.raises(EsperaNoPosibleError, match="sitio"):
            _esperar(_franja(), ocupadas=2)

    def test_ya_juega_ese_dia_no(self):
        with pytest.raises(EsperaNoPosibleError, match="ese día"):
            _esperar(_franja(sesion=SessionType.AFTERNOON), suyas=[_franja()])

    def test_con_el_cupo_lleno_no(self):
        with pytest.raises(EsperaNoPosibleError, match="jornadas"):
            _esperar(_franja(dia=SABADO), suyas=[_franja()], max_jornadas=1)

    def test_con_cupo_para_otro_dia_si(self):
        _esperar(_franja(dia=SABADO), suyas=[_franja()], max_jornadas=2)

    def test_ya_espera_en_esa_no(self):
        with pytest.raises(EsperaNoPosibleError, match="Ya espera"):
            _esperar(_franja(), ya_espera=True)

    def test_ya_tiene_plaza_en_esa_no(self):
        franja = _franja()

        with pytest.raises(EsperaNoPosibleError, match="Ya tiene plaza"):
            _esperar(franja, suyas=[franja])


class TestLeToca:
    def test_puede(self):
        assert ListasDeEspera.le_toca(_franja(), suyas=[], max_jornadas=1)

    def test_ese_dia_ya_juega_se_salta(self):
        assert not ListasDeEspera.le_toca(
            _franja(sesion=SessionType.AFTERNOON), suyas=[_franja()], max_jornadas=2
        )

    def test_con_el_cupo_lleno_se_salta(self):
        assert not ListasDeEspera.le_toca(_franja(dia=SABADO), suyas=[_franja()], max_jornadas=1)
