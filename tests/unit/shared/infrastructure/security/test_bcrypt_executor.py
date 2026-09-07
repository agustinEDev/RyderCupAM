"""
Tests de `run_bcrypt`, el ejecutor que saca bcrypt del event loop.

El test que de verdad protege la corrección es
`test_does_not_block_the_event_loop_while_hashing`: si alguien sustituyera el salto
al hilo por una llamada directa, ese test falla. Los demás cubren que el
ejecutor es transparente para quien lo llama.
"""

import asyncio
import contextvars
import threading
import time

import pytest

from src.shared.infrastructure.security.bcrypt_executor import (
    MAX_CONCURRENCY,
    _executor,
    run_bcrypt,
)

_probe_context: contextvars.ContextVar[str] = contextvars.ContextVar("probe_context")


@pytest.mark.asyncio
async def test_returns_the_result_of_the_wrapped_function():
    result = await run_bcrypt(lambda: "computed-hash")

    assert result == "computed-hash"


@pytest.mark.asyncio
async def test_passes_positional_and_keyword_arguments():
    def hash_it(password, *, rounds):
        return f"{password}:{rounds}"

    result = await run_bcrypt(hash_it, "secret", rounds=12)

    assert result == "secret:12"


@pytest.mark.asyncio
async def test_propagates_the_exception_unwrapped():
    def fails():
        raise ValueError("password too short")

    with pytest.raises(ValueError, match="password too short"):
        await run_bcrypt(fails)


@pytest.mark.asyncio
async def test_does_not_block_the_event_loop_while_hashing():
    """
    Mientras `run_bcrypt` trabaja, el loop tiene que seguir atendiendo otras tareas.

    Se compara el contador ANTES y DESPUÉS en vez de exigir un número de vueltas: con el
    loop bloqueado el ticker no avanza ni una sola vez, así que basta con que avance para
    distinguir los dos casos. Exigir «al menos N vueltas en 200 ms» medía de rebote lo
    ocupada que estuviera la máquina, y fallaba en una cargada sin que nada estuviera roto.
    """
    ticks = 0

    async def ticker():
        nonlocal ticks
        while True:
            ticks += 1
            await asyncio.sleep(0.01)

    task = asyncio.create_task(ticker())
    await asyncio.sleep(0)  # cede el control para que el ticker arranque
    ticks_before = ticks

    try:
        await run_bcrypt(time.sleep, 0.2)  # simula el coste de bcrypt con 12 rounds
    finally:
        task.cancel()

    assert ticks > ticks_before, (
        f"el event loop quedó bloqueado: el ticker no avanzó ni una vez "
        f"durante el hash (seguía en {ticks})"
    )


@pytest.mark.asyncio
async def test_limits_how_many_hashes_run_at_once():
    """
    Sin tope, una avalancha de logins lanzaría un hash por petición contra la CPU del
    contenedor. El pool propio tiene que dejar esperando a los que sobran.
    """
    running = 0
    peak = 0
    lock = threading.Lock()

    def work():
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        time.sleep(0.05)
        with lock:
            running -= 1

    await asyncio.gather(*(run_bcrypt(work) for _ in range(MAX_CONCURRENCY * 3)))

    assert peak <= MAX_CONCURRENCY, f"{peak} hashes a la vez, el tope es {MAX_CONCURRENCY}"


@pytest.mark.asyncio
async def test_propagates_the_context_to_the_thread():
    """El correlation-id de los logs vive en un contextvar: tiene que cruzar al hilo."""
    _probe_context.set("correlation-123")

    assert await run_bcrypt(_probe_context.get) == "correlation-123"


@pytest.mark.asyncio
async def test_does_not_let_work_pile_up_in_the_executor_queue():
    """
    El pool limita cuántos hashes CORREN; el semáforo limita cuántos ESPERAN.

    Sin él, `ThreadPoolExecutor` encola una tarea por llamada en una cola sin tope, y
    cada una retiene sus argumentos —contraseñas en claro entre ellos— hasta que le toca
    el turno. Se mira la cola interna del executor a propósito: es la única forma de
    afirmar la invariante desde fuera.
    """
    release = threading.Event()

    def blocked():
        release.wait(timeout=5)

    tasks = [
        asyncio.create_task(run_bcrypt(blocked)) for _ in range(MAX_CONCURRENCY * 10)
    ]
    try:
        await asyncio.sleep(0.2)  # deja que todas intenten entrar
        queued = _executor._work_queue.qsize()
    finally:
        release.set()
        await asyncio.gather(*tasks)

    assert queued <= MAX_CONCURRENCY, f"{queued} tareas esperando dentro del executor"
