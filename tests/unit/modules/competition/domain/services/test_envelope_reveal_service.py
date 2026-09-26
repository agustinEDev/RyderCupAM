"""
Cuándo se abren solos los sobres de una sesión (FE #655).

Decidido por el dueño del producto el 23 sep: **6 horas antes de la sesión**, que
es además el plazo para entregar —lo que no esté dentro lo rellena la aplicación—,
y la hora de una sesión ya está definida en el producto —06:00 la de mañana,
12:00 la de tarde, 18:00 la de noche, en la hora local del campo— porque es la
misma a la que se abre sola la anotación (BE #305). Así que los sobres de la
sesión de mañana se abren a medianoche del mismo día.

Pero el reloj no manda solo: **nunca antes de que acabe la sesión anterior**.
El plazo a secas abriría los de la tarde a las 06:00 del mismo día, con la
sesión de mañana empezando, y se perdería lo que da sentido a esperar: elegir
con el marcador delante.

Y para que eso no se atasque, la sesión anterior se da por acabada **cuando sus
partidos terminan o cuando llega la hora de esta**, lo que ocurra primero: un
partido que nadie cierra no puede dejar la sesión siguiente sin enfrentamientos.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from src.modules.competition.domain.services.envelope_reveal_service import (
    EnvelopeRevealService,
)
from src.modules.competition.domain.value_objects.session_type import SessionType

MADRID = "Europe/Madrid"
DIA = date(2026, 6, 15)


def _en_madrid(dia, hora, minuto=0):
    return datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=ZoneInfo(MADRID))


class TestLaHoraProgramada:
    @pytest.mark.parametrize(
        ("sesion", "dia_de_apertura", "hora"),
        [
            # La de mañana empieza a las 6:00, luego se abre a las 00:00 de ese día
            (SessionType.MORNING, DIA, 0),
            # La de tarde empieza a las 12:00: a las 6:00 del mismo día
            (SessionType.AFTERNOON, DIA, 6),
            # La de noche empieza a las 18:00: a las 12:00 del mismo día
            (SessionType.EVENING, DIA, 12),
        ],
    )
    def test_seis_horas_antes_del_comienzo_de_la_sesion(self, sesion, dia_de_apertura, hora):
        programado = EnvelopeRevealService.scheduled_for(DIA, sesion, MADRID)

        assert programado == _en_madrid(dia_de_apertura, hora)

    def test_la_hora_es_la_del_campo_y_no_la_del_servidor(self):
        """Las seis de Canarias no son las seis de Madrid."""
        canarias = EnvelopeRevealService.scheduled_for(DIA, SessionType.MORNING, "Atlantic/Canary")
        madrid = EnvelopeRevealService.scheduled_for(DIA, SessionType.MORNING, MADRID)

        assert canarias != madrid
        assert (canarias - madrid).total_seconds() == 3600

    def test_sin_zona_no_hay_hora_que_calcular(self):
        """Los datos de antes de que existiera la zona no se inventan."""
        assert EnvelopeRevealService.scheduled_for(DIA, SessionType.MORNING, None) is None

    def test_ni_sin_fecha_o_sin_sesion(self):
        assert EnvelopeRevealService.scheduled_for(None, SessionType.MORNING, MADRID) is None
        assert EnvelopeRevealService.scheduled_for(DIA, None, MADRID) is None


class TestSiYaTocaAbrirlos:
    def test_antes_de_la_hora_no(self):
        programado = _en_madrid(DIA, 0)

        assert (
            EnvelopeRevealService.is_due(
                programado, la_anterior_acabo=True, ahora=_en_madrid(date(2026, 6, 14), 23, 59)
            )
            is False
        )

    def test_en_la_hora_si(self):
        programado = _en_madrid(DIA, 0)

        assert (
            EnvelopeRevealService.is_due(programado, la_anterior_acabo=True, ahora=programado)
            is True
        )

    def test_con_la_sesion_anterior_viva_no_se_abren_aunque_toque(self):
        """Elegir con el marcador delante es lo que da sentido a esperar."""
        programado = _en_madrid(DIA, 6)

        assert (
            EnvelopeRevealService.is_due(
                programado, la_anterior_acabo=False, ahora=_en_madrid(DIA, 11)
            )
            is False
        )

    def test_sin_hora_programada_nunca_se_abren_solos(self):
        """Sin zona no hay reloj: los abre el organizador a mano."""
        assert (
            EnvelopeRevealService.is_due(None, la_anterior_acabo=True, ahora=_en_madrid(DIA, 23))
            is False
        )


class TestCuandoSeDaPorAcabadaLaAnterior:
    def test_cuando_todos_sus_partidos_terminaron(self):
        assert (
            EnvelopeRevealService.previous_session_is_over(
                partidos_pendientes=0,
                comienzo_de_esta=_en_madrid(DIA, 12),
                ahora=_en_madrid(DIA, 9),
            )
            is True
        )

    def test_con_algun_partido_por_terminar_todavia_no(self):
        assert (
            EnvelopeRevealService.previous_session_is_over(
                partidos_pendientes=1,
                comienzo_de_esta=_en_madrid(DIA, 12),
                ahora=_en_madrid(DIA, 9),
            )
            is False
        )

    def test_pero_al_llegar_la_hora_de_esta_se_da_por_acabada(self):
        """Un partido que nadie cierra no puede dejar la sesión siguiente sin
        enfrentamientos para siempre."""
        assert (
            EnvelopeRevealService.previous_session_is_over(
                partidos_pendientes=3,
                comienzo_de_esta=_en_madrid(DIA, 12),
                ahora=_en_madrid(DIA, 12),
            )
            is True
        )

    def test_la_primera_sesion_del_torneo_no_tiene_anterior(self):
        """Ahí manda el reloj y nada más."""
        assert (
            EnvelopeRevealService.previous_session_is_over(
                partidos_pendientes=None,
                comienzo_de_esta=_en_madrid(DIA, 12),
                ahora=_en_madrid(DIA, 1),
            )
            is True
        )
