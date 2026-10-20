"""
Completa el género de la barra en los partidos de Ryder SCRATCH ya generados.

POR QUE HACE FALTA
------------------
Hasta RyderCupAM #579 una Ryder SCRATCH guardaba a todos los jugadores sin el
género de su barra: veían la tarjeta de referencia en vez de la de su barra, y
el mapa del hoyo no sabía de qué barra era cada muestra (RyderCupWeb #880). Los
partidos nuevos ya salen bien; los ya generados se quedan como estaban.

QUE TOCA Y QUE NO
-----------------
- Solo competiciones SCRATCH, y rondas programadas o en juego. Las terminadas
  no: se jugaron con esa tarjeta.
- Solo a quien no tiene género, con la regla de la generación sobre el color
  que ya tiene. No cambia color, golpes, emparejamientos, resultados ni ids:
  repetirlo no hace nada.
- Sin campo en la ronda, nada.

USO
---
    source .venv/bin/activate
    PYTHONPATH=. python scripts/completar_genero_de_las_barras.py --dry-run
    PYTHONPATH=. python scripts/completar_genero_de_las_barras.py

`--dry-run` no escribe nada: dice a cuántos jugadores se lo pondría.
"""

import argparse
import asyncio

from src.config.database import async_session_maker
from src.config.mappers import start_all_mappers
from src.modules.competition.application.use_cases.completar_genero_de_las_barras_use_case import (
    CompletarGeneroDeLasBarrasUseCase,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_unit_of_work import (
    SQLAlchemyCompetitionUnitOfWork,
)
from src.modules.golf_course.infrastructure.persistence.sqlalchemy.golf_course_unit_of_work import (
    SQLAlchemyGolfCourseUnitOfWork,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork,
)


async def main(dry_run: bool) -> int:
    # Fuera de la aplicación nadie registra el mapeo imperativo
    start_all_mappers()

    async with async_session_maker() as session:
        resumen = await CompletarGeneroDeLasBarrasUseCase(
            SQLAlchemyCompetitionUnitOfWork(session),
            SQLAlchemyGolfCourseUnitOfWork(session).golf_courses,
            SQLAlchemyUnitOfWork(session).users,
        ).execute(dry_run=dry_run)

    for ronda in resumen.rondas:
        print(f"  {ronda.competicion} / ronda {ronda.round_id}: {ronda.jugadores} jugadores")
    for error in resumen.errores:
        print(f"  ERROR, la ronda se queda como estaba: {error}")
    print(
        f"\n{'(dry-run) ' if dry_run else ''}"
        f"Jugadores con su género: {resumen.jugadores} en {len(resumen.rondas)} rondas"
        + (f" | rondas con error: {len(resumen.errores)}" if resumen.errores else "")
    )
    return 1 if resumen.errores else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Completa el género de la barra en los partidos de Ryder SCRATCH"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Dice lo que haría sin escribir nada"
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.dry_run)))
