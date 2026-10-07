"""
Quién se refresca con la RFEG en un día de juego, y cuándo (BE #502).

Decidido con Agustín el 7 oct 2026: a las 3:00 hora del campo de cada día de
juego, a quien juega ese día y todavía no ha empezado; lo que no responde se
reintenta hasta las 7:00, y lo que la RFEG no encuentra no se reintenta.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    Candidato,
    RefrescoDeHandicapsService,
    ResultadoRefresco,
)
from src.modules.user.domain.value_objects.user_id import UserId

MADRID = ZoneInfo("Europe/Madrid")
CANARIAS = ZoneInfo("Atlantic/Canary")
SABADO = date(2030, 10, 12)


def _a_las(hora: int, minuto: int = 0, dia: date = SABADO, zona=MADRID) -> datetime:
    return datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=zona)


def _candidato(**extra) -> Candidato:
    datos = {"user_id": UserId.generate(), "handicap_personalizado": False, "empezo_hoy": False}
    datos.update(extra)
    return Candidato(**datos)


class TestCuando:
    def test_a_las_tres_del_dia_de_juego_toca(self):
        assert RefrescoDeHandicapsService.toca(_a_las(3), SABADO)

    def test_un_minuto_antes_no(self):
        assert not RefrescoDeHandicapsService.toca(_a_las(2, 59), SABADO)

    def test_si_hoy_no_se_juega_no(self):
        assert not RefrescoDeHandicapsService.toca(_a_las(10), date(2030, 10, 13))

    def test_si_el_servidor_vuelve_tarde_tambien_toca(self):
        assert RefrescoDeHandicapsService.toca(_a_las(9), SABADO)

    def test_cada_torneo_a_las_tres_de_su_campo(self):
        """Las 3:00 en Canarias son las 4:00 en Madrid: a las 3:30 de Madrid aún no."""
        a_las_tres_y_media_en_madrid = _a_las(3, 30).astimezone(CANARIAS)

        assert not RefrescoDeHandicapsService.toca(a_las_tres_y_media_en_madrid, SABADO)
        assert RefrescoDeHandicapsService.toca(_a_las(3, zona=CANARIAS), SABADO)


class TestAQuien:
    def test_a_quien_juega_y_aun_no_tiene_resultado(self):
        jugador = _candidato()

        assert RefrescoDeHandicapsService.a_quien([jugador], {}, _a_las(3)) == [jugador.user_id]

    def test_no_a_quien_tiene_handicap_personalizado(self):
        assert (
            RefrescoDeHandicapsService.a_quien(
                [_candidato(handicap_personalizado=True)], {}, _a_las(3)
            )
            == []
        )

    @pytest.mark.parametrize("hora", [3, 9])
    def test_nunca_a_quien_ya_empezo_hoy(self, hora):
        assert (
            RefrescoDeHandicapsService.a_quien([_candidato(empezo_hoy=True)], {}, _a_las(hora))
            == []
        )

    def test_el_primer_intento_aunque_sea_tarde(self):
        jugador = _candidato()

        assert RefrescoDeHandicapsService.a_quien([jugador], {}, _a_las(9)) == [jugador.user_id]

    @pytest.mark.parametrize(
        "resultado",
        [
            ResultadoRefresco.ACTUALIZADO,
            ResultadoRefresco.NO_ENCONTRADO,
            ResultadoRefresco.SIN_LICENCIA_ESPANOLA,
        ],
    )
    def test_lo_ya_resuelto_no_se_repite(self, resultado):
        jugador = _candidato()

        assert (
            RefrescoDeHandicapsService.a_quien([jugador], {jugador.user_id: resultado}, _a_las(4))
            == []
        )

    def test_lo_fallido_se_reintenta_antes_de_las_siete(self):
        jugador = _candidato()
        fallo = {jugador.user_id: ResultadoRefresco.FALLIDO}

        assert RefrescoDeHandicapsService.a_quien([jugador], fallo, _a_las(6, 59)) == [
            jugador.user_id
        ]

    def test_lo_fallido_ya_no_se_reintenta_desde_las_siete(self):
        jugador = _candidato()
        fallo = {jugador.user_id: ResultadoRefresco.FALLIDO}

        assert RefrescoDeHandicapsService.a_quien([jugador], fallo, _a_las(7)) == []

    def test_conserva_el_orden_de_los_candidatos(self):
        candidatos = [_candidato() for _ in range(4)]

        assert RefrescoDeHandicapsService.a_quien(candidatos, {}, _a_las(3)) == [
            c.user_id for c in candidatos
        ]
