"""
Tests del turno único para procesar imágenes (SB-01).

Decodificar una foto grande se lleva cientos de megas de memoria. Avatar y fotos
de la galería pasan por un único turno en todo el proceso: se procesan de una en
una, la que llega mientras otra está en marcha espera, y si la espera pasa del
tope se devuelve un error controlado en vez de dejarla colgada.
"""

import asyncio
import io
import threading

import pytest
from PIL import Image

from src.modules.user.domain.errors.user_errors import ImageProcessingBusyError
from src.modules.user.infrastructure.external import turno_de_imagenes
from src.modules.user.infrastructure.external.pillow_image_processor import PillowImageProcessor
from src.modules.user.infrastructure.external.turno_de_imagenes import en_su_turno


def _jpeg(width: int = 64, height: int = 48) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (34, 139, 34)).save(buffer, "JPEG")
    return buffer.getvalue()


class _Ocupado:
    """Un trabajo que no acaba hasta que el test lo suelta, y avisa al empezar."""

    def __init__(self) -> None:
        self.empezado = threading.Event()
        self.soltar = threading.Event()

    def __call__(self) -> str:
        self.empezado.set()
        assert self.soltar.wait(timeout=10), "el test no soltó el trabajo"
        return "hecho"


async def _esperar_a_que_empiece(ocupado: _Ocupado) -> None:
    assert await asyncio.to_thread(ocupado.empezado.wait, 10)


async def test_dos_imagenes_a_la_vez_se_procesan_de_una_en_una():
    """
    Given cinco imágenes que llegan a la vez
    When se procesan
    Then nunca hay más de una decodificándose al mismo tiempo, y acaban todas
    """
    en_marcha = 0
    maximo = 0
    cerrojo = threading.Lock()

    def trabajo() -> int:
        nonlocal en_marcha, maximo
        with cerrojo:
            en_marcha += 1
            maximo = max(maximo, en_marcha)
        threading.Event().wait(0.05)
        with cerrojo:
            en_marcha -= 1
        return 1

    resultados = await asyncio.gather(*(en_su_turno(trabajo) for _ in range(5)))

    assert resultados == [1, 1, 1, 1, 1]
    assert maximo == 1


def test_tambien_es_una_a_la_vez_entre_event_loops_distintos():
    """
    Given dos event loops a la vez (en producción hay uno, pero el turno es del proceso)
    When cada uno procesa imágenes
    Then sigue sin haber dos decodificándose al mismo tiempo: lo garantiza el hilo único
    """
    en_marcha = 0
    maximo = 0
    cerrojo = threading.Lock()

    def trabajo() -> None:
        nonlocal en_marcha, maximo
        with cerrojo:
            en_marcha += 1
            maximo = max(maximo, en_marcha)
        threading.Event().wait(0.05)
        with cerrojo:
            en_marcha -= 1

    async def tres() -> None:
        await asyncio.gather(*(en_su_turno(trabajo) for _ in range(3)))

    hilos = [threading.Thread(target=asyncio.run, args=(tres(),)) for _ in range(2)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=10)

    assert maximo == 1


async def test_la_que_llega_mientras_otra_se_procesa_espera_su_turno_y_entra():
    """
    Given una imagen procesándose
    When llega otra y la primera acaba dentro del tiempo máximo de espera
    Then la segunda no se rechaza: espera y se procesa
    """
    ocupado = _Ocupado()
    primera = asyncio.create_task(en_su_turno(ocupado))
    await _esperar_a_que_empiece(ocupado)

    segunda = asyncio.create_task(en_su_turno(lambda: "segunda"))
    await asyncio.sleep(0.05)
    assert not segunda.done(), "la segunda tiene que esperar a que acabe la primera"

    ocupado.soltar.set()

    assert await primera == "hecho"
    assert await segunda == "segunda"


async def test_si_la_espera_pasa_del_tope_se_devuelve_un_error_controlado(monkeypatch):
    """
    Given una imagen que tarda más que el tiempo máximo de espera
    When llega otra
    Then la segunda recibe ImageProcessingBusyError y no se procesa
    """
    monkeypatch.setattr(turno_de_imagenes, "TIEMPO_MAXIMO_DE_ESPERA_S", 0.05)
    ocupado = _Ocupado()
    primera = asyncio.create_task(en_su_turno(ocupado))
    await _esperar_a_que_empiece(ocupado)
    llamadas: list[str] = []

    try:
        with pytest.raises(ImageProcessingBusyError) as error:
            await en_su_turno(lambda: llamadas.append("no debería correr"))
        assert str(error.value) == (
            "Ahora mismo se están procesando otras imágenes. Inténtalo de nuevo en unos segundos."
        )
        assert error.value.error_code == "IMAGES_BUSY"
    finally:
        ocupado.soltar.set()
        await primera

    assert llamadas == []


async def test_el_avatar_y_la_galeria_comparten_el_mismo_turno(monkeypatch):
    """
    Given una imagen ocupando el turno
    When llegan un avatar y una foto de galería con un tiempo de espera corto
    Then los dos esperan a ese mismo turno (y aquí se cansan): es uno para todo
    """
    monkeypatch.setattr(turno_de_imagenes, "TIEMPO_MAXIMO_DE_ESPERA_S", 0.05)
    procesador = PillowImageProcessor()
    ocupado = _Ocupado()
    primera = asyncio.create_task(en_su_turno(ocupado))
    await _esperar_a_que_empiece(ocupado)

    try:
        with pytest.raises(ImageProcessingBusyError):
            await procesador.process_avatar_image(_jpeg())
        with pytest.raises(ImageProcessingBusyError):
            await procesador.process_gallery_image(_jpeg())
    finally:
        ocupado.soltar.set()
        await primera


async def test_una_peticion_cancelada_no_suelta_el_turno_hasta_que_acaba_su_hilo(monkeypatch):
    """
    Given una imagen procesándose cuya petición se cancela (el cliente se va)
    When llega otra
    Then la otra sigue esperando: el hilo de la primera continúa decodificando y
    soltar el turno antes dejaría dos imágenes en memoria a la vez
    """
    monkeypatch.setattr(turno_de_imagenes, "TIEMPO_MAXIMO_DE_ESPERA_S", 0.1)
    ocupado = _Ocupado()
    primera = asyncio.create_task(en_su_turno(ocupado))
    await _esperar_a_que_empiece(ocupado)
    primera.cancel()
    with pytest.raises(asyncio.CancelledError):
        await primera

    try:
        with pytest.raises(ImageProcessingBusyError):
            await en_su_turno(lambda: "segunda")
    finally:
        ocupado.soltar.set()

    monkeypatch.setattr(turno_de_imagenes, "TIEMPO_MAXIMO_DE_ESPERA_S", 5)
    assert await en_su_turno(lambda: "tercera") == "tercera"


async def test_un_error_al_procesar_suelta_el_turno():
    """
    Given una imagen que falla al procesarse
    When llega la siguiente
    Then entra sin esperar: el error no deja el turno cogido
    """

    def falla() -> None:
        raise ValueError("imagen rota")

    with pytest.raises(ValueError, match="imagen rota"):
        await en_su_turno(falla)

    assert await asyncio.wait_for(en_su_turno(lambda: "siguiente"), timeout=1) == "siguiente"


def test_dos_primeras_imagenes_a_la_vez_desde_hilos_distintos_comparten_un_solo_pool(
    monkeypatch,
):
    """
    Given el proceso sin pool todavía (arranque en frío)
    When dos loops de hilos distintos piden el pool exactamente a la vez
    Then los dos reciben el mismo: con dos pools habría dos decodificaciones a la vez
    """
    monkeypatch.setattr(turno_de_imagenes, "_pool", None)
    salida = threading.Barrier(8)
    pools: list[object] = []

    def pide() -> None:
        salida.wait()
        pools.append(turno_de_imagenes._el_pool())

    hilos = [threading.Thread(target=pide) for _ in range(8)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    assert len({id(pool) for pool in pools}) == 1
    turno_de_imagenes._el_pool().shutdown(wait=False)
