"""Fechas que salen al JSON en UTC y con «Z»."""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import PlainSerializer, WithJsonSchema


def utc_z(moment: datetime) -> str:
    """En UTC y con «Z»: sin zona, un navegador la tomaría por hora local."""
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC).replace(tzinfo=None)
    return moment.isoformat() + "Z"


# Para las fechas que se guardan en UTC sin zona: al JSON salen con «Z». El
# esquema sigue diciendo `date-time`: el serializador devuelve texto, y sin
# esto el contrato perderia el formato
UtcDatetime = Annotated[
    datetime,
    PlainSerializer(utc_z, return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "format": "date-time"}, mode="serialization"),
]
