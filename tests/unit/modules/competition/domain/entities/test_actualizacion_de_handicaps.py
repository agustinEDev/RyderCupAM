"""
Una actualización de hándicaps de una competición (#251, 7 oct 2026).

Se crea al cerrar las inscripciones (y en la PR siguiente, con el botón o
programada) y pasa por estos estados:

| Desde       | Qué pasa                         | Queda en    |
|-------------|----------------------------------|-------------|
| En curso    | Termina sin nadie pendiente      | Completa    |
| En curso    | Termina con alguien pendiente    | Incompleta  |
| En curso    | La competición empieza o se cierra de nuevo | Cortada |
| Incompleta  | La competición empieza o se cierra de nuevo | Cortada |
| Completa    | La competición empieza           | Completa    |
| Cortada     | Termina (la pasada iba por detrás) | Cortada   |
"""

from datetime import UTC, datetime

from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    ActualizacionDeHandicaps,
    EstadoActualizacion,
    OrigenActualizacion,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId

MOMENTO = datetime(2030, 10, 10, 18, 0, tzinfo=UTC)
LUEGO = datetime(2030, 10, 10, 18, 5, tzinfo=UTC)


def _nueva() -> ActualizacionDeHandicaps:
    return ActualizacionDeHandicaps.crear(
        CompetitionId.generate(), OrigenActualizacion.CIERRE, MOMENTO
    )


class TestActualizacion:
    def test_nace_en_curso(self):
        actualizacion = _nueva()

        assert actualizacion.estado is EstadoActualizacion.EN_CURSO
        assert actualizacion.sigue()
        assert actualizacion.creada == MOMENTO
        assert actualizacion.terminada is None

    def test_sin_pendientes_queda_completa(self):
        actualizacion = _nueva()

        actualizacion.terminar(pendientes=0, momento=LUEGO)

        assert actualizacion.estado is EstadoActualizacion.COMPLETA
        assert actualizacion.terminada == LUEGO
        assert not actualizacion.sigue()

    def test_con_pendientes_queda_incompleta(self):
        actualizacion = _nueva()

        actualizacion.terminar(pendientes=2, momento=LUEGO)

        assert actualizacion.estado is EstadoActualizacion.INCOMPLETA

    def test_en_curso_o_incompleta_se_corta(self):
        en_curso, incompleta = _nueva(), _nueva()
        incompleta.terminar(pendientes=1, momento=MOMENTO)

        en_curso.cortar(LUEGO)
        incompleta.cortar(LUEGO)

        assert en_curso.estado is incompleta.estado is EstadoActualizacion.CORTADA
        assert en_curso.terminada == LUEGO

    def test_completa_no_se_corta(self):
        actualizacion = _nueva()
        actualizacion.terminar(pendientes=0, momento=MOMENTO)

        actualizacion.cortar(LUEGO)

        assert actualizacion.estado is EstadoActualizacion.COMPLETA
        assert actualizacion.terminada == MOMENTO

    def test_cortada_no_vuelve_a_terminar(self):
        actualizacion = _nueva()
        actualizacion.cortar(MOMENTO)

        actualizacion.terminar(pendientes=0, momento=LUEGO)

        assert actualizacion.estado is EstadoActualizacion.CORTADA
        assert actualizacion.terminada == MOMENTO


class TestReanudar:
    def test_una_incompleta_vuelve_a_estar_en_curso(self):
        actualizacion = _nueva()
        actualizacion.terminar(pendientes=1, momento=LUEGO)

        actualizacion.reanudar(LUEGO)

        assert actualizacion.sigue()
        assert actualizacion.terminada is None
        assert actualizacion.reanudada == LUEGO

    def test_las_demas_no(self):
        import pytest

        en_curso, completa, cortada = _nueva(), _nueva(), _nueva()
        completa.terminar(pendientes=0, momento=LUEGO)
        cortada.cortar(LUEGO)

        for actualizacion in (en_curso, completa, cortada):
            with pytest.raises(ValueError, match="incompleta"):
                actualizacion.reanudar(LUEGO)
