"""El vigilante que lanza el refresco de las 3:00 cada 15 minutos (BE #502)."""

import asyncio

import pytest

from src.modules.competition.infrastructure.jobs.vigilante_de_handicaps import (
    INTERVALO_SEGUNDOS,
    VigilanteDeHandicaps,
    debe_vigilar,
)


class _Vueltas:
    """Cuenta las vueltas y puede fallar en alguna."""

    def __init__(self, fallos: set[int] | None = None, hasta: int = 3):
        self.hechas = 0
        self._fallos = fallos or set()
        self._hasta = hasta
        self.esperas: list[float] = []

    async def vuelta(self) -> int:
        self.hechas += 1
        if self.hechas in self._fallos:
            raise RuntimeError("la base de datos no responde")
        return 0

    async def esperar(self, segundos: float) -> None:
        self.esperas.append(segundos)
        if len(self.esperas) >= self._hasta:
            raise asyncio.CancelledError


@pytest.mark.asyncio
class TestLaVigilancia:
    async def test_da_una_vuelta_cada_quince_minutos(self):
        vueltas = _Vueltas()

        with pytest.raises(asyncio.CancelledError):
            await VigilanteDeHandicaps(vueltas.vuelta, vueltas.esperar).vigilar()

        assert vueltas.hechas == 3
        assert vueltas.esperas == [INTERVALO_SEGUNDOS] * 3
        assert INTERVALO_SEGUNDOS == 15 * 60

    async def test_una_vuelta_que_falla_no_para_las_siguientes(self):
        vueltas = _Vueltas(fallos={1})

        with pytest.raises(asyncio.CancelledError):
            await VigilanteDeHandicaps(vueltas.vuelta, vueltas.esperar).vigilar()

        assert vueltas.hechas == 3


class TestCuandoSeEnciende:
    """Solo en producción: el Kind y el entorno local no preguntan a la RFEG real."""

    def test_apagado_por_defecto(self):
        assert not debe_vigilar({})

    def test_apagado_en_los_tests_aunque_se_encienda(self):
        assert not debe_vigilar({"TESTING": "true", "HANDICAP_REFRESH_ENABLED": "true"})

    @pytest.mark.parametrize("valor", ["false", "0", "no", "False"])
    def test_apagado_con_la_variable(self, valor):
        assert not debe_vigilar({"HANDICAP_REFRESH_ENABLED": valor})

    @pytest.mark.parametrize("valor", ["true", "True", "1", "yes"])
    def test_encendido_con_la_variable(self, valor):
        assert debe_vigilar({"HANDICAP_REFRESH_ENABLED": valor})
