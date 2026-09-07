"""
Ejecutor de bcrypt fuera del event loop, con la concurrencia acotada.

bcrypt con 12 rounds (`Password._hash_password`) cuesta ~200 ms de CPU, y llamarlo
directamente desde una corrutina bloquea el event loop: mientras dura, el proceso no
atiende NINGUNA otra petición. Producción corre un único worker de uvicorn
(`entrypoint.sh`), así que un login congelaba la API entera para todo el mundo, y la
comprobación del historial de contraseñas —hasta 5 verificaciones seguidas— la congelaba
más de un segundo.

La corrección tiene dos mitades, y la segunda importa tanto como la primera:

1. Saltar a un hilo libera el event loop. bcrypt suelta el GIL mientras trabaja (la parte
   cara es C), así que el loop sigue despachando el resto de peticiones.
2. Un pool PROPIO y pequeño limita cuántos hashes corren a la vez, y un semáforo del
   mismo tamaño limita cuántos ESPERAN. Sin el primero, N logins simultáneos lanzarían N
   hashes contra el medio núcleo del contenedor y lo dejarían de rodillas (OWASP A04,
   agotamiento de recursos). Sin el segundo, la cola del `ThreadPoolExecutor` —que no
   tiene tope— acumularía una tarea por petición, cada una reteniendo sus argumentos
   (contraseñas en claro incluidas) hasta que le tocara el turno. Con el semáforo la
   espera ocurre en el event loop, que es barato y no guarda nada.
   `BCRYPT_MAX_CONCURRENCY` ajusta los dos si algún día crece la CPU del plan.

NO usar con `token_hash` (SHA-256): son microsegundos y el salto de hilo costaría más que
la propia operación.
"""

import asyncio
import contextvars
import functools
import weakref
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import ParamSpec, TypeVar

from src.shared.infrastructure.env import env_int

P = ParamSpec("P")
T = TypeVar("T")

# Con el medio núcleo del plan actual, más de dos hashes a la vez no acaban antes: solo
# se estorban entre ellos y se llevan por delante la CPU del resto de peticiones.
MAX_CONCURRENCY = env_int("BCRYPT_MAX_CONCURRENCY", default=2)

# Pool propio, no el del runtime: así el límite es real y los hashes no compiten por los
# hilos que FastAPI usa para los endpoints síncronos.
_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENCY, thread_name_prefix="bcrypt")

# Un semáforo por event loop. `asyncio.Semaphore` se ata al loop en el que se usa por
# primera vez, así que uno global rompería en cuanto hubiera más de uno (los tests crean
# uno por test). El diccionario es débil para que un loop cerrado no se quede retenido.
_admission_gates: weakref.WeakKeyDictionary[
    asyncio.AbstractEventLoop, asyncio.Semaphore
] = weakref.WeakKeyDictionary()


def _admission_gate(loop: asyncio.AbstractEventLoop) -> asyncio.Semaphore:
    """Devuelve el semáforo de admisión de este loop, creándolo la primera vez."""
    gate = _admission_gates.get(loop)
    if gate is None:
        gate = asyncio.Semaphore(MAX_CONCURRENCY)
        _admission_gates[loop] = gate
    return gate


async def run_bcrypt(func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    """
    Ejecuta en un hilo aparte una operación que hashea o verifica un password.

    Args:
        func: Operación síncrona que usa bcrypt (por ejemplo `user.verify_password`)
        *args: Argumentos posicionales que se pasan tal cual a `func`
        **kwargs: Argumentos con nombre que se pasan tal cual a `func`

    Returns:
        Lo que devuelva `func`. Las excepciones se propagan sin envolver, sin añadir los
        argumentos al mensaje: por ahí pasan contraseñas en claro.

    Examples:
        >>> if not await run_bcrypt(user.verify_password, plain_password):
        ...     raise InvalidCredentialsError()
    """
    loop = asyncio.get_running_loop()
    # Se copia el contexto igual que hace `asyncio.to_thread`, para que el correlation-id
    # y demás contextvars sigan estando en los logs que salgan desde el hilo.
    context = contextvars.copy_context()
    call = functools.partial(context.run, functools.partial(func, *args, **kwargs))
    # Hay tantos permisos como hilos, así que nada llega al executor sin un hilo libre
    # esperándolo: la cola de dentro no crece, y quien espera lo hace aquí.
    async with _admission_gate(loop):
        return await loop.run_in_executor(_executor, call)
