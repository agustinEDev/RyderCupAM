"""
Errores de dominio de competición que la API traduce en un solo sitio.

`TournamentTypeError` (#251): pedir equipos, capitanes, draft, sobres o la
clasificación por equipos a un torneo que no los tiene. Lo pueden lanzar nueve
rutas de la Ryder Cup, y la mayoría no traduce ValueError: sin esto saldría un
500. Es un error de quien pide, con un motivo que se le puede enseñar: 400.

`StrokePlaySettingsError` (#251): unos ajustes de stroke play sin sentido. Lo
lanza la pieza al crear, al cambiarla y al mover las fechas del torneo, así
que también puede salir de rutas que no lo esperan.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from src.modules.competition.domain.entities.competition import TournamentTypeError
from src.modules.competition.domain.value_objects.stroke_play_setup import (
    StrokePlaySettingsError,
)


async def _tournament_type_error(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})


def register_competition_exception_handlers(app: FastAPI) -> None:
    """Registra en la app los errores de competición que se traducen aquí."""
    app.add_exception_handler(TournamentTypeError, _tournament_type_error)
    app.add_exception_handler(StrokePlaySettingsError, _tournament_type_error)
