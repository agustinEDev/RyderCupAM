"""
Un candado de Postgres para las tareas periódicas del proceso de la API.

Con dos procesos a la vez —un despliegue a medias, o varios workers— solo uno
hace la vuelta; el otro se la salta. El candado va en una conexión propia, sin
transacción abierta, y se suelta al acabar; si el proceso muere, Postgres lo
suelta solo al cerrarse la conexión.

Salió del vigilante de hándicaps (#251) cuando le hizo falta también al cierre
de las partidas rápidas.
"""

from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

R = TypeVar("R")


async def con_candado(
    motor: AsyncEngine, clave: int, trabajo: Callable[[], Awaitable[R]]
) -> R | None:
    """El resultado de `trabajo`, o None si otro proceso tiene el candado."""
    async with motor.connect() as candado:
        cogido = await candado.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": clave})
        # El candado es de la conexión, no de la transacción: se cierra para no
        # dejarla abierta toda la vuelta
        await candado.commit()
        if not cogido:
            return None
        try:
            return await trabajo()
        finally:
            await soltar(candado, clave)


async def soltar(candado, clave: int) -> None:
    """
    Suelta el candado; si no puede (un error, o la app apagándose a media
    vuelta), cierra la conexión, que es lo que lo suelta de verdad. Devolverla
    al pool con el candado cogido dejaría a todos los procesos sin la tarea.
    """
    try:
        await candado.scalar(text("SELECT pg_advisory_unlock(:k)"), {"k": clave})
        await candado.commit()
    except BaseException:
        await candado.invalidate()
        raise
