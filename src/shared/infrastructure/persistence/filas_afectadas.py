"""
Las filas que tocó un UPDATE o un DELETE, con su tipo.

`AsyncSession.execute` de SQLAlchemy 2.1 promete un `Result` para cualquier
sentencia, y `rowcount` solo lo tiene `CursorResult`, que es lo que devuelve de
verdad con un UPDATE o un DELETE. Solo se le dice al tipo: en ejecución se lee
`rowcount` igual que antes, sin una forma nueva de fallar (/code-review).
"""

from typing import Any, cast

from sqlalchemy import CursorResult, Result


def filas_afectadas(result: Result[Any]) -> int:
    """El `rowcount` de la sentencia, tal cual lo da el driver."""
    return cast(CursorResult[Any], result).rowcount
