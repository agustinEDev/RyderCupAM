"""
Tipos de persistencia de los ids (value objects con un UUID en `value`).

Antes había 35 decoradores de ids (y 3 de país, abajo) casi iguales repartidos por los módulos, con cinco
variantes de lo que aceptaban al guardar: unos guardaban NULL sin avisar si les
llegaba un `uuid.UUID`, otros reventaban con un texto (unificados el 20 nov
2026). Ahora todos salen de aquí y hacen lo mismo:

- Al guardar: el id, un texto o un `uuid.UUID` se guardan; None es NULL; un
  id de otra clase o cualquier otra cosa es un `TypeError`.
- Al leer: el id con su UUID dentro.

La columna es la que ya tenía cada tabla: texto (`CHAR(36)`, la mayoría),
`VARCHAR(36)` (`columna="varchar"`, los refresh tokens) o UUID nativo de
PostgreSQL (`columna="uuid"`).
Cada módulo sigue declarando sus tipos, ahora con una línea:
`CompetitionIdDecorator = tipo_de_id(CompetitionId)`.
"""

import uuid
from typing import Any, Literal

from sqlalchemy import CHAR, UUID, String
from sqlalchemy.types import TypeDecorator, TypeEngine

from src.shared.domain.value_objects.country_code import CountryCode


def tipo_de_id(
    clase: type, *, columna: Literal["texto", "varchar", "uuid"] = "texto"
) -> type[TypeDecorator]:
    """
    Un tipo de persistencia para los ids de `clase`.

    Cada llamada da un tipo nuevo: cada módulo define el suyo con esta fábrica
    (los módulos comparten dominio, no tablas).
    """
    en_texto = columna != "uuid"
    impl_de_la_columna: TypeEngine[Any]
    if columna == "uuid":
        impl_de_la_columna = UUID(as_uuid=True)
    elif columna == "varchar":
        impl_de_la_columna = String(36)
    else:
        impl_de_la_columna = CHAR(36)

    class TipoDeId(TypeDecorator):
        impl = impl_de_la_columna
        cache_ok = True

        def process_bind_param(self, value: Any, dialect: Any) -> str | uuid.UUID | None:
            if value is None:
                return None
            if isinstance(value, clase):
                value = value.value  # type: ignore[attr-defined]
            if isinstance(value, str):
                return value if en_texto else uuid.UUID(value)
            if isinstance(value, uuid.UUID):
                return str(value) if en_texto else value
            raise TypeError(
                f"Un {clase.__name__} se guarda desde el id, un texto o un UUID; "
                f"llegó {type(value).__name__}"
            )

        def process_result_value(self, value: Any, dialect: Any) -> Any:
            if value is None:
                return None
            return clase(uuid.UUID(value) if isinstance(value, str) else value)

    TipoDeId.__name__ = TipoDeId.__qualname__ = f"{clase.__name__}Type"
    return TipoDeId


def tipo_de_codigo_de_pais(
    *, columna: Literal["texto", "varchar"] = "texto"
) -> type[TypeDecorator]:
    """
    Un tipo de persistencia para `CountryCode` en una columna `CHAR(2)` (o
    `VARCHAR(2)` con `columna="varchar"`, la que tenga la tabla).

    Mismas reglas que los ids: el código o un texto se guardan; None es NULL;
    cualquier otra cosa es un `TypeError`. Al leer, el `CountryCode`. Cada
    llamada da un tipo nuevo, uno por módulo (antes había tres escritos a mano,
    y uno guardaba NULL sin avisar).
    """

    class TipoDeCodigoDePais(TypeDecorator):
        impl = CHAR(2) if columna == "texto" else String(2)
        cache_ok = True

        def process_bind_param(self, value: Any, dialect: Any) -> str | None:
            if value is None:
                return None
            if isinstance(value, CountryCode):
                return str(value.value)
            if isinstance(value, str):
                return value
            raise TypeError(
                f"Un CountryCode se guarda desde el código o un texto; llegó {type(value).__name__}"
            )

        def process_result_value(self, value: Any, dialect: Any) -> CountryCode | None:
            return None if value is None else CountryCode(value)

    TipoDeCodigoDePais.__name__ = TipoDeCodigoDePais.__qualname__ = "CountryCodeType"
    return TipoDeCodigoDePais
