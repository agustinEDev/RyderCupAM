"""
Turno único para procesar imágenes: de una en una en todo el proceso (SB-01).

Decodificar una foto se lleva varias veces su tamaño en píxeles: un PNG de pocos KB
que declara 40 MP subía la memoria del proceso más de 300 MB. Con el procesado
lanzado a `asyncio.to_thread` sin más, diez subidas a la vez eran diez decodificaciones
a la vez, y el contenedor se quedaba sin memoria: el reinicio se llevaba además todos
los frenos y límites, que viven en memoria.

Avatar y fotos de la galería comparten este turno, así que en todo el proceso hay como
mucho UNA imagen decodificándose. Va en dos mitades, como `run_bcrypt`:

1. Un pool PROPIO de un solo hilo, que es lo que garantiza que no corren dos a la vez,
   y que no le quita hilos al pool del runtime (por ahí van, entre otras cosas, las
   resoluciones DNS).
2. Un semáforo de un permiso en el event loop, donde se ESPERA el turno. Esperar ahí es
   barato y permite poner un tope: quien lleva más de `TIEMPO_MAXIMO_DE_ESPERA_S`
   esperando recibe `ImageProcessingBusyError` (503) en vez de quedarse colgado.

El permiso se suelta cuando acaba el HILO, no cuando acaba la petición: si el cliente
se va a mitad, el hilo sigue decodificando y soltarlo antes dejaría dos imágenes en
memoria a la vez.
"""

import asyncio
import concurrent.futures
import contextlib
import contextvars
import functools
import weakref
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import ParamSpec, TypeVar

from src.modules.user.domain.errors.user_errors import ImageProcessingBusyError

P = ParamSpec("P")
T = TypeVar("T")

# Lo más que espera una imagen a que le toque. La peor que se acepta (un JPEG de 40 MP
# o un PNG de 25 MP) tarda en torno a medio segundo, así que 20 s dan para una cola de
# decenas de subidas a la vez, más que cualquier pico real; pasado eso es mejor decir
# «inténtalo en un momento» que dejar la petición colgada hasta que corte el cliente.
TIEMPO_MAXIMO_DE_ESPERA_S = 20.0

# Un hilo, creado con la primera imagen y no al importar el módulo
_pool: ThreadPoolExecutor | None = None

# Un semáforo por event loop: `asyncio.Semaphore` se ata al loop en el que se usa por
# primera vez (los tests crean uno por test). Débil, para no retener loops cerrados.
_turnos: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = (
    weakref.WeakKeyDictionary()
)


def _el_pool() -> ThreadPoolExecutor:
    global _pool  # noqa: PLW0603 - estado del proceso, creado al primer uso
    if _pool is None:
        _pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="imagenes")
    return _pool


def _el_turno(loop: asyncio.AbstractEventLoop) -> asyncio.Semaphore:
    turno = _turnos.get(loop)
    if turno is None:
        turno = asyncio.Semaphore(1)
        _turnos[loop] = turno
    return turno


def _soltar_desde_el_hilo(
    loop: asyncio.AbstractEventLoop, turno: asyncio.Semaphore, _futuro: object
) -> None:
    """Devuelve el permiso al loop cuando acaba el hilo (o se cancela sin empezar)."""
    # Si el loop ya se cerró, su semáforo se va con él
    with contextlib.suppress(RuntimeError):
        loop.call_soon_threadsafe(turno.release)


async def en_su_turno(func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    """
    Ejecuta `func` en el hilo de las imágenes cuando le toque.

    Raises:
        ImageProcessingBusyError: si la espera pasa de `TIEMPO_MAXIMO_DE_ESPERA_S`.
        Lo que lance `func`, sin envolver.
    """
    loop = asyncio.get_running_loop()
    turno = _el_turno(loop)
    try:
        async with asyncio.timeout(TIEMPO_MAXIMO_DE_ESPERA_S):
            await turno.acquire()
    except TimeoutError as exc:
        raise ImageProcessingBusyError(
            "Ahora mismo se están procesando otras imágenes. Inténtalo de nuevo en unos segundos."
        ) from exc

    # Se copia el contexto como hace `asyncio.to_thread`, para que el correlation-id y
    # demás contextvars sigan en los logs que salgan desde el hilo
    contexto = contextvars.copy_context()
    llamada = functools.partial(contexto.run, functools.partial(func, *args, **kwargs))
    try:
        futuro: concurrent.futures.Future[T] = _el_pool().submit(llamada)
    except BaseException:
        turno.release()
        raise
    futuro.add_done_callback(functools.partial(_soltar_desde_el_hilo, loop, turno))
    return await asyncio.wrap_future(futuro)
