#!/usr/bin/env python3
"""
Importa de OpenStreetMap el mapa de hoyos de los campos (BE #532).

Recorre los campos aprobados con coordenadas de un país, o uno solo, y para cada
uno llama al caso de uso que busca su contorno en OSM, valida los hoyos contra
nuestra tarjeta y crea o reimporta el mapa, pendiente de que un admin lo revise.
Un mapa ya aprobado no se toca.

Sin --apply hace una pasada en seco: calcula y resume, pero no guarda nada.
Entre campo y campo espera unos segundos: Overpass es un servicio público de uso
justo. Los datos de OSM van bajo licencia ODbL.

Uso:
    python scripts/import_hole_maps.py --country ES            # en seco
    python scripts/import_hole_maps.py --country ES --apply    # guarda
    python scripts/import_hole_maps.py --course <id> --apply
    python scripts/import_hole_maps.py --country ES \\
        --overpass-url https://overpass.kumi.systems/api/interpreter
"""

import argparse
import asyncio
import sys
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.database import async_session_maker
from src.config.mappers import start_all_mappers
from src.modules.golf_course.application.dtos.hole_map_import_dtos import (
    ImportHoleMapRequestDTO,
    ImportHoleMapResponseDTO,
    ImportHoleMapStatus,
)
from src.modules.golf_course.application.use_cases.import_hole_map_from_osm_use_case import (
    ImportHoleMapFromOsmUseCase,
)
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.infrastructure.osm.osm_hole_map_source import OsmHoleMapSource
from src.modules.golf_course.infrastructure.osm.overpass_client import (
    DEFAULT_OVERPASS_URL,
    OverpassClient,
)
from src.modules.golf_course.infrastructure.persistence.mappers.golf_course_mapper import (
    golf_courses_table,
)
from src.modules.golf_course.infrastructure.persistence.sqlalchemy.golf_course_unit_of_work import (
    SQLAlchemyGolfCourseUnitOfWork,
)
from src.shared.domain.value_objects.country_code import CountryCode

DEFAULT_PAUSE_S = 5.0
ERROR = "ERROR"
# Resultados a los que se llega sin preguntar a OSM: tras ellos no hace falta pausa
NO_OSM_CALL = frozenset({ImportHoleMapStatus.SKIPPED_APPROVED, ImportHoleMapStatus.NO_COORDINATES})
# Tantos «OSM no disponible» seguidos = Overpass caído o limitándonos: se para
MAX_CONSECUTIVE_UNAVAILABLE = 5

ImportOne = Callable[[str, bool], Awaitable[ImportHoleMapResponseDTO]]


@dataclass
class Summary:
    """Recuento de una pasada."""

    statuses: Counter[str] = field(default_factory=Counter)
    holes_imported: int = 0
    discarded: Counter[str] = field(default_factory=Counter)
    errors: list[tuple[str, str]] = field(default_factory=list)
    aborted: bool = False


def course_id(value: str) -> str:
    """Un id de campo: tiene que ser un UUID."""
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a golf course id") from None


def http_url(value: str) -> str:
    """Una URL http(s) con servidor."""
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise argparse.ArgumentTypeError(f"'{value}' is not an http(s) URL")
    return value


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Lee la línea de órdenes: un país o un campo, y si se guarda."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--country", type=str.upper, help="código ISO del país, p. ej. ES")
    target.add_argument("--course", type=course_id, help="id de un campo")
    parser.add_argument("--apply", action="store_true", help="guarda (sin esto, en seco)")
    parser.add_argument(
        "--pause",
        type=float,
        default=DEFAULT_PAUSE_S,
        help=f"segundos entre campos (por defecto {DEFAULT_PAUSE_S:g})",
    )
    parser.add_argument(
        "--overpass-url",
        type=http_url,
        default=DEFAULT_OVERPASS_URL,
        help="servidor de Overpass; un espejo si el principal está caído",
    )
    return parser.parse_args(argv)


async def select_course_ids(
    session: AsyncSession, *, country: str | None = None, course: str | None = None
) -> list[str]:
    """Los campos aprobados con coordenadas del país, o ese campo si cumple."""
    table = golf_courses_table
    query = (
        select(table.c.id)
        .where(table.c.approval_status == ApprovalStatus.APPROVED)
        .where(table.c.latitude.is_not(None))
        .order_by(table.c.name)
    )
    if country is not None:
        query = query.where(table.c.country_code == CountryCode(country))
    if course is not None:
        query = query.where(table.c.id == GolfCourseId(course))
    result = await session.execute(query)
    return [str(course_id) for course_id in result.scalars()]


async def run(
    course_ids: Sequence[str],
    import_one: ImportOne,
    *,
    apply: bool,
    pause: float,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> Summary:
    """Importa campo a campo; un fallo se cuenta y no para la pasada."""
    summary = Summary()
    asked_osm = False  # si el campo anterior preguntó a OSM, toca esperar
    unavailable_in_a_row = 0
    for course in course_ids:
        if unavailable_in_a_row >= MAX_CONSECUTIVE_UNAVAILABLE:
            summary.aborted = True
            break
        if asked_osm:
            await sleep(pause)
        asked_osm = True  # ante un error no se sabe: se espera por si acaso
        try:
            result = await import_one(course, apply)
        except Exception as error:
            summary.statuses[ERROR] += 1
            summary.errors.append((course, f"{type(error).__name__}: {error}"))
            continue
        asked_osm = result.status not in NO_OSM_CALL
        if result.status is ImportHoleMapStatus.OSM_UNAVAILABLE:
            unavailable_in_a_row += 1
        else:
            unavailable_in_a_row = 0
        summary.statuses[result.status.value] += 1
        summary.holes_imported += result.holes_imported
        summary.discarded.update(result.discarded)
        print(f"  {course}  {result.status.value}  hoyos={result.holes_imported}")
    return summary


def report(summary: Summary, *, apply: bool) -> str:
    """El resumen de la pasada, para la consola."""
    lines = ["", "Resumen" + ("" if apply else " (en seco: no se ha guardado nada)")]
    for status, count in sorted(summary.statuses.items()):
        lines.append(f"  {status:<18} {count}")
    lines.append(f"  Hoyos importados   {summary.holes_imported}")
    if summary.discarded:
        lines.append("  Hoyos descartados:")
        for reason, count in sorted(summary.discarded.items()):
            lines.append(f"    {reason:<16} {count}")
    for course_id, error in summary.errors:
        lines.append(f"  ERROR {course_id}: {error}")
    if summary.aborted:
        lines.append(
            f"  PASADA CORTADA: {MAX_CONSECUTIVE_UNAVAILABLE} campos seguidos sin respuesta de "
            "Overpass (caído o limitándonos). Repítela más tarde."
        )
    return "\n".join(lines)


def exit_code(summary: Summary) -> int:
    """
    0 solo si todo se pudo hacer: sin errores ni campos sin poder consultar a OSM.

    Una pasada cortada siempre tiene campos sin consultar, así que también da 1.
    """
    unavailable = summary.statuses.get(ImportHoleMapStatus.OSM_UNAVAILABLE.value, 0)
    return 1 if summary.errors or unavailable else 0


def nothing_to_import(args: argparse.Namespace, course_ids: Sequence[str]) -> str | None:
    """Por qué un --course no sale en la selección, para no salir callado."""
    if args.course is None or course_ids:
        return None
    return (
        f"El campo {args.course} no se puede importar: no existe, no está aprobado "
        "o no tiene coordenadas."
    )


async def main() -> int:
    """Punto de entrada."""
    args = parse_args()
    start_all_mappers()

    async with async_session_maker() as session:
        course_ids = await select_course_ids(session, country=args.country, course=args.course)
    message = nothing_to_import(args, course_ids)
    if message is not None:
        print(message)
        return 1
    print(f"{len(course_ids)} campos que importar{'' if args.apply else ' (en seco)'}.")

    client = OverpassClient(url=args.overpass_url)
    source = OsmHoleMapSource(client)

    async def import_one(course_id: str, apply: bool) -> ImportHoleMapResponseDTO:
        # Una sesión por campo: el fallo de uno no arrastra a los demás
        async with async_session_maker() as session:
            use_case = ImportHoleMapFromOsmUseCase(SQLAlchemyGolfCourseUnitOfWork(session), source)
            return await use_case.execute(
                ImportHoleMapRequestDTO(golf_course_id=course_id, apply=apply)
            )

    try:
        summary = await run(course_ids, import_one, apply=args.apply, pause=args.pause)
    finally:
        await client.aclose()
    print(report(summary, apply=args.apply))
    return exit_code(summary)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
