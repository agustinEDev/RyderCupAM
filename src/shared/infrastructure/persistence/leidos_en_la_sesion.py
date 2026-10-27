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

from sqlalchemy import event, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

_LEIDOS = "leidos_enteros"
_LISTAS = "listas_leidas"

T = TypeVar("T")


def _usable(objeto: object) -> bool:
    """Si sigue en la sesión, al día: ni borrado, ni fuera, ni caducado."""
    estado = inspect(objeto)
    return not (
        estado is None
        or estado.deleted
        or estado.was_deleted
        or estado.detached
        # Caducado (`session.expire`): tocarlo en asíncrono sería un `MissingGreenlet`
        or estado.expired_attributes
    )


@event.listens_for(Session, "after_soft_rollback")
def _olvidar_al_deshacer(session: Session, previous_transaction: object) -> None:  # noqa: ARG001 - firma del evento
    """
    Deshacer, también un SAVEPOINT, olvida todo lo recordado (revisor de la PR 2).
    Lo que se tocó queda caducado; y una fila insertada y leída dentro, si solo
    la retiene lo recordado, SQLAlchemy la sigue dando por guardada aunque ya
    no esté en la base de datos.
    """
    session.info.pop(_LEIDOS, None)
    session.info.pop(_LISTAS, None)


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
    if not isinstance(objeto, tipo) or not _usable(objeto):
        return None
    if any(atributo in sin_cargar(objeto) for atributo in cargados):
        return None
    return objeto


def recordar_lista(session: AsyncSession, clave: Hashable, lista: list) -> None:
    """Apunta una lista leída (sus objetos son los de la sesión, al día)."""
    session.info.setdefault(_LISTAS, {})[clave] = list(lista)


def lista_leida(session: AsyncSession, clave: Hashable) -> list | None:
    """Una copia de la lista ya leída en esta sesión, o None: quien llama puede tocarla."""
    lista = session.info.get(_LISTAS, {}).get(clave)
    if lista is None or not all(_usable(objeto) for objeto in lista):
        return None
    return list(lista)


def olvidar_listas(session: AsyncSession, tipo: str) -> None:
    """Olvida las listas de ese tipo: quien escribe cambia lo que contienen."""
    listas = session.info.get(_LISTAS, {})
    for clave in [c for c in listas if isinstance(c, tuple) and c and c[0] == tipo]:
        del listas[clave]
