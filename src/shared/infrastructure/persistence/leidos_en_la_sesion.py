"""
Lo que una sesión ya leyó entero, para no volver a pedirlo en la misma petición.

Una petición comparte sesión entre todas sus piezas, y varias leían lo mismo:
la consulta devolvía el objeto que la sesión ya tenía, con su estado (BE #375),
y costaba sus sentencias (27 oct 2026, PR 2). El mapa de identidad no sirve:
es débil y suelta el objeto en cuanto nadie lo retiene. Se guardan en `info`,
que dura lo que la sesión: una petición.
"""

from collections.abc import Hashable, Iterable
from typing import TypeVar

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

_LEIDOS = "leidos_enteros"

T = TypeVar("T")


def sin_cargar(objeto: object) -> frozenset[str]:
    """Los atributos de un objeto de la sesión que aún no se han cargado."""
    estado = inspect(objeto)
    return frozenset(estado.unloaded) if estado is not None else frozenset()


def recordar(session: AsyncSession, tipo: type, clave: Hashable, objeto: object) -> None:
    """Lo apunta como leído entero en esta sesión."""
    session.info.setdefault(_LEIDOS, {})[(tipo, clave)] = objeto


def ya_leido(
    session: AsyncSession, tipo: type[T], clave: Hashable, cargados: Iterable[str]
) -> T | None:
    """
    El objeto si la sesión ya lo leyó entero: con `cargados` cargados, ni
    borrado, ni fuera de la sesión, ni caducado. Si no, None, y se lee.
    """
    objeto = session.info.get(_LEIDOS, {}).get((tipo, clave))
    if not isinstance(objeto, tipo):
        return None
    estado = inspect(objeto)
    if estado is None or estado.deleted or estado.was_deleted or estado.detached:
        return None
    if any(atributo in sin_cargar(objeto) for atributo in cargados):
        return None
    return objeto
