"""
Al apagar, la API espera a los correos en segundo plano, con un límite (fase 5, lifespan).

Los avisos de seguridad y los correos de verificación se lanzan sin esperarlos para que el
login y el registro contesten rápido. Hasta ahora, en un reinicio (cada despliegue de
Render) se perdían los que estuvieran saliendo. Decidido el 13 nov: al apagar se esperan
como mucho unos segundos; lo que no acabe se cancela (L1-L5).
"""

import asyncio
import contextlib
import logging

import pytest

from src.config import aviso_en_segundo_plano as avisos
from src.config.aviso_en_segundo_plano import TOPE_AL_APAGAR_S, drena_al_apagar

pytestmark = pytest.mark.asyncio


def _lanza(coro, nombre: str) -> asyncio.Task[None]:
    """Una tarea en el registro de los avisos, como la lanzan los avisos de verdad."""
    tarea = asyncio.create_task(coro, name=nombre)
    avisos._PENDIENTES.add(tarea)
    tarea.add_done_callback(avisos._PENDIENTES.discard)
    return tarea


async def test_l1_un_aviso_que_acaba_a_tiempo_se_espera_y_sale():
    """Given un aviso a medio enviar, When la API se apaga, Then lo espera y el correo sale."""
    enviados = []

    async def envia():
        await asyncio.sleep(0.05)
        enviados.append("aviso")

    _lanza(envia(), "aviso-de-nuevo-inicio")

    await drena_al_apagar(tope_s=1)

    assert enviados == ["aviso"]


async def test_l2_lo_que_no_acaba_en_el_tope_se_cancela_y_el_apagado_no_se_cuelga(caplog):
    """Given una tarea que no acaba, When la API se apaga, Then se cancela al cumplirse el tope."""
    colgada = _lanza(asyncio.sleep(3600), "aviso-colgado")
    bucle = asyncio.get_running_loop()
    inicio = bucle.time()

    with caplog.at_level(logging.WARNING):
        # Con su propio límite: si no cancelara, la prueba fallaría en vez de colgarse
        await asyncio.wait_for(drena_al_apagar(tope_s=0.1), timeout=2)

    assert colgada.cancelled()
    assert bucle.time() - inicio < 1
    assert "aviso-colgado" in caplog.text


async def test_l3_una_tarea_que_falla_no_para_el_apagado_y_queda_registrada(caplog):
    """Given una tarea que falla al acabar, When la API se apaga, Then sigue y deja el fallo en el log."""

    async def falla():
        await asyncio.sleep(0.01)
        raise RuntimeError("no responde para ana@example.com")

    _lanza(falla(), "aviso-que-falla")

    with caplog.at_level(logging.ERROR):
        await drena_al_apagar(tope_s=1)

    assert "aviso-que-falla" in caplog.text
    assert "RuntimeError" in caplog.text
    # Ni el mensaje ni la traza: pueden llevar el correo (A09)
    assert "ana@example.com" not in caplog.text


async def test_l4_las_tareas_acabadas_salen_solas_del_registro():
    """Given avisos que acaban, When se apaga, Then el registro queda vacío (no se acumulan)."""

    async def rapido():
        await asyncio.sleep(0)

    _lanza(rapido(), "uno")
    _lanza(rapido(), "dos")

    await drena_al_apagar(tope_s=1)

    assert not [t for t in avisos._PENDIENTES if t.get_loop() is asyncio.get_running_loop()]


async def test_l5_tambien_espera_las_tareas_del_lanzador_de_handicaps():
    """Given una actualización de hándicaps en marcha, When se apaga, Then también se espera."""
    hechas = []

    async def actualiza():
        await asyncio.sleep(0.05)
        hechas.append("hándicaps")

    tarea = asyncio.create_task(actualiza(), name="actualizacion-de-handicaps")

    await drena_al_apagar([tarea], tope_s=1)

    assert hechas == ["hándicaps"]


async def test_el_tope_cabe_en_el_margen_de_render():
    """Given los ~30 s que da Render al apagar, When se fija el tope, Then deja margen."""
    assert 0 < TOPE_AL_APAGAR_S <= 15


async def test_el_lifespan_drena_al_apagar(monkeypatch):
    """Given la app arrancada, When se apaga, Then llama a drena_al_apagar una vez."""
    import main

    llamadas = []

    async def drena_espia(otras=(), tope_s=TOPE_AL_APAGAR_S):
        llamadas.append((list(otras), tope_s))

    _aisla_el_arranque(monkeypatch, main)
    monkeypatch.setattr(main, "drena_al_apagar", drena_espia)

    async with main.lifespan(main.app):
        assert llamadas == []

    assert len(llamadas) == 1
    assert llamadas[0][1] == TOPE_AL_APAGAR_S


def _aisla_el_arranque(monkeypatch, main) -> None:
    """Sin Sentry de verdad, sin parar el log de seguridad real ni mirar el correo del entorno."""
    from unittest.mock import Mock

    monkeypatch.setattr(main, "get_security_logger", Mock)
    monkeypatch.setattr(main, "comprueba_el_envio_de_correo", lambda _entorno: None)
    monkeypatch.setattr(main.settings, "SENTRY_DSN", "")


async def test_el_lifespan_drena_las_actualizaciones_de_handicaps_tras_parar_los_vigilantes(
    monkeypatch,
):
    """
    Given el lanzador de hándicaps de producción con una actualización en marcha,
    When la app se apaga, Then se drena esa tarea, y después de cancelar los vigilantes.
    """
    import main
    from src.config import refresco_de_handicaps as refresco

    orden = []
    en_marcha = asyncio.create_task(asyncio.sleep(0), name="actualizacion")

    class LanzadorFalso(refresco.LanzadorEnSegundoPlano):
        def __init__(self):
            pass

        def tareas_en_marcha(self):
            orden.append("tareas")
            return [en_marcha]

    class VigilanteFalso:
        def __init__(self, _lanzador):
            pass

        async def vigilar(self):
            try:
                await asyncio.sleep(3600)
            finally:
                orden.append("vigilante parado")

    async def drena_espia(otras=(), tope_s=TOPE_AL_APAGAR_S):
        orden.append(("drena", list(otras)))

    _aisla_el_arranque(monkeypatch, main)
    monkeypatch.setattr(main, "get_lanzador_de_actualizaciones", LanzadorFalso)
    monkeypatch.setattr(main, "VigilanteDeActualizaciones", VigilanteFalso)
    monkeypatch.setattr(main, "drena_al_apagar", drena_espia)

    async with main.lifespan(main.app):
        await asyncio.sleep(0)

    assert orden == ["vigilante parado", "tareas", ("drena", [en_marcha])]
    await en_marcha


async def test_tareas_en_marcha_solo_devuelve_las_que_no_han_acabado():
    """Given una actualización acabada y otra en marcha, When se piden, Then solo la segunda."""
    from src.config.refresco_de_handicaps import LanzadorEnSegundoPlano

    lanzador = LanzadorEnSegundoPlano.__new__(LanzadorEnSegundoPlano)
    acabada = asyncio.create_task(asyncio.sleep(0))
    await acabada
    corriendo = asyncio.create_task(asyncio.sleep(3600))
    lanzador._tareas = {acabada, corriendo}

    assert lanzador.tareas_en_marcha() == [corriendo]
    corriendo.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await corriendo


async def test_el_log_de_seguridad_se_para_aunque_el_drenaje_falle(monkeypatch):
    """Given un drenaje que falla al apagar, When la app se apaga, Then el log se para igual."""
    from unittest.mock import Mock

    import main

    registro = Mock()
    _aisla_el_arranque(monkeypatch, main)
    monkeypatch.setattr(main, "get_security_logger", lambda: registro)

    async def drena_que_falla(otras=(), tope_s=TOPE_AL_APAGAR_S):
        raise RuntimeError("fallo al drenar")

    monkeypatch.setattr(main, "drena_al_apagar", drena_que_falla)

    with pytest.raises(RuntimeError):
        async with main.lifespan(main.app):
            pass

    registro.para.assert_called_once_with()


async def test_un_fallo_al_cancelar_tambien_queda_registrado(caplog):
    """Given una tarea que falla al cancelarla, When se apaga, Then el fallo queda en el log."""

    async def falla_al_cancelar():
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise ConnectionError("no cierra para ana@example.com") from None

    _lanza(falla_al_cancelar(), "aviso-que-falla-al-cancelar")

    with caplog.at_level(logging.ERROR):
        await asyncio.wait_for(drena_al_apagar(tope_s=0.05), timeout=3)

    assert "aviso-que-falla-al-cancelar" in caplog.text
    assert "ConnectionError" in caplog.text
    assert "ana@example.com" not in caplog.text
