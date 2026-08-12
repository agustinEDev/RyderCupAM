#!/usr/bin/env python3
"""
Importa a la base de datos los campos de golf federados.

Da de alta los campos **llamando a los casos de uso**, no escribiendo en las
tablas: así los 802 recorridos pasan por las mismas invariantes que un alta
hecha a mano, y un dato imposible se rechaza aquí en vez de quedarse guardado.

Sin argumentos hace una pasada en seco: no toca nada y explica qué haría. Para
aplicar de verdad hay que pedirlo con --apply.

Uso:
    python scripts/import_golf_courses.py                 # pasada en seco
    python scripts/import_golf_courses.py --apply         # crea los campos nuevos
    python scripts/import_golf_courses.py --apply --confirm-merges
    python scripts/import_golf_courses.py --limit 20 --apply
"""

import argparse
import asyncio
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, text

from src.config.database import async_session_maker
from src.modules.golf_course.application.dtos.golf_course_dtos import (
    UpdateGolfCourseRequestDTO,
)
from src.modules.golf_course.application.use_cases.create_direct_golf_course_use_case import (
    CreateDirectGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.update_golf_course_use_case import (
    UpdateGolfCourseUseCase,
)
from src.modules.golf_course.domain.value_objects.course_source import CourseSource
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.infrastructure.importers.matching import (
    ExistingCourse,
    Match,
    MatchKind,
    find_match,
)
from src.modules.golf_course.infrastructure.importers.rfeg_dataset import (
    clubs_with_courses,
    load_dataset,
)
from src.modules.golf_course.infrastructure.importers.rfeg_mapper import (
    MappedCourse,
    RfegMappingError,
    map_club,
)
from src.modules.golf_course.infrastructure.persistence.mappers.golf_course_mapper import (
    golf_courses_table,
    start_golf_course_mappers,
)
from src.modules.golf_course.infrastructure.persistence.sqlalchemy.golf_course_unit_of_work import (
    SQLAlchemyGolfCourseUnitOfWork,
)
from src.modules.user.application.use_cases.ensure_system_user_use_case import (
    EnsureSystemUserUseCase,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.mappers import (
    start_mappers as start_user_mappers,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork as SQLAlchemyUserUnitOfWork,
)
from src.shared.infrastructure.persistence.sqlalchemy.country_mappers import (
    start_mappers as start_country_mappers,
)

SYSTEM_USER_EMAIL = "course.import@rydercupfriends.com"


def parse_args() -> argparse.Namespace:
    """Lee los argumentos de la línea de órdenes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica los cambios. Sin esta opción solo se informa de lo que haría",
    )
    parser.add_argument(
        "--confirm-merges",
        action="store_true",
        help=(
            "Aplica también las coincidencias que no son exactas (campos renombrados "
            "por la federación o dados de alta a mano). Sin esta opción se listan y "
            "se dejan intactos"
        ),
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
        help="Ruta a otro volcado. Por defecto, el que viaja en el repositorio",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Procesa solo los primeros N recorridos. Útil para probar",
    )
    return parser.parse_args()


async def load_existing_courses(session) -> list[ExistingCourse]:
    """
    Lee de la base de datos lo justo para reconocer los campos.

    Se consulta con SQL directo y no cargando los agregados enteros porque
    hidratar cientos de campos con sus tarjetas para leer cuatro columnas
    tardaría mucho más y no aporta nada.
    """
    columns = golf_courses_table.c
    rows = await session.execute(
        select(
            columns.id,
            columns.name,
            columns.source,
            columns.external_id,
            columns.latitude,
            columns.longitude,
        ).where(columns.original_golf_course_id.is_(None))
    )

    existing: list[ExistingCourse] = []
    for row in rows:
        total_par, tee_count = await _read_shape(session, row.id)
        existing.append(
            ExistingCourse(
                id=str(row.id),
                name=row.name,
                source=CourseSource(row.source),
                external_id=row.external_id,
                latitude=row.latitude,
                longitude=row.longitude,
                total_par=total_par,
                tee_count=tee_count,
            )
        )
    return existing


async def _read_shape(session, golf_course_id) -> tuple[int, int]:
    """Devuelve el par total y el número de salidas de un campo guardado."""
    tee_count = await session.scalar(
        text("SELECT COUNT(*) FROM golf_course_tees WHERE golf_course_id = :id"),
        {"id": str(golf_course_id)},
    )
    total_par = await session.scalar(
        text(
            "SELECT COALESCE(SUM(h.par), 0) FROM golf_course_tee_holes h "
            "WHERE h.tee_id = (SELECT MIN(id) FROM golf_course_tees WHERE golf_course_id = :id)"
        ),
        {"id": str(golf_course_id)},
    )
    return int(total_par or 0), int(tee_count or 0)


def map_all(dataset, limit: int | None) -> tuple[list[MappedCourse], list[str]]:
    """
    Traduce el volcado entero, anotando lo que no se pueda traducir.

    Un recorrido ilegible no detiene la importación: se informa y se sigue, que
    es preferible a dejar 801 campos fuera por culpa de uno.
    """
    imported_at = datetime.now(UTC).replace(tzinfo=None)
    mapped: list[MappedCourse] = []
    problems: list[str] = []

    for club in clubs_with_courses(dataset):
        try:
            mapped.extend(map_club(club, imported_at))
        except (RfegMappingError, KeyError, TypeError) as error:
            problems.append(f"{club.get('name', '?')}: {error}")

        if limit is not None and len(mapped) >= limit:
            return mapped[:limit], problems

    return mapped, problems


def to_update_request(course: MappedCourse) -> UpdateGolfCourseRequestDTO:
    """Convierte un campo mapeado en la peticion de actualizacion equivalente."""
    return UpdateGolfCourseRequestDTO(
        name=course.request.name,
        country_code=course.request.country_code,
        course_type=course.request.course_type,
        tees=course.request.tees,
        holes=course.request.holes,
        location=course.request.location,
    )


def report(
    decisions: list[tuple[MappedCourse, Match]], problems: list[str], *, applying: bool
) -> None:
    """Escribe el informe de lo que se va a hacer, o de lo que se ha hecho."""
    counts = Counter(match.kind for _, match in decisions)

    print()
    print("=" * 72)
    print("IMPORTACION DE CAMPOS FEDERADOS" if applying else "PASADA EN SECO (no se toca nada)")
    print("=" * 72)
    print(f"  Recorridos leidos:        {len(decisions)}")
    print(f"  Campos nuevos:            {counts[MatchKind.NEW]}")
    print(f"  Ya importados:            {counts[MatchKind.EXACT]}")
    print(f"  Posibles renombrados:     {counts[MatchKind.RENAMED]}")
    print(f"  Coinciden con altas manuales: {counts[MatchKind.MANUAL]}")
    if problems:
        print(f"  Recorridos ilegibles:     {len(problems)}")

    to_confirm = [(course, match) for course, match in decisions if match.needs_confirmation]
    if to_confirm:
        print()
        print("-" * 72)
        print("COINCIDENCIAS QUE NECESITAN TU VISTO BUENO")
        print("-" * 72)
        for course, match in to_confirm:
            print(f"  '{course.name}'")
            print(f"      {match.reason}")

    if problems:
        print()
        print("-" * 72)
        print("RECORRIDOS QUE NO SE HAN PODIDO LEER")
        print("-" * 72)
        for problem in problems:
            print(f"  {problem}")

    print()


async def main() -> int:
    """Punto de entrada."""
    args = parse_args()

    start_user_mappers()
    start_country_mappers()
    start_golf_course_mappers()

    dataset = load_dataset(args.dataset)
    mapped, problems = map_all(dataset, args.limit)
    print(f"Leidos {len(mapped)} recorridos del volcado.")

    async with async_session_maker() as session:
        existing = await load_existing_courses(session)
        print(f"Hay {len(existing)} campos en la base de datos.")

        decisions = [(course, find_match(course, existing)) for course in mapped]

        if not args.apply:
            report(decisions, problems, applying=False)
            print("Nada se ha modificado. Repite con --apply para aplicarlo.")
            return 0

        creator_id = await EnsureSystemUserUseCase(SQLAlchemyUserUnitOfWork(session)).execute(
            SYSTEM_USER_EMAIL
        )
        use_case = CreateDirectGolfCourseUseCase(SQLAlchemyGolfCourseUnitOfWork(session))

        update_use_case = UpdateGolfCourseUseCase(SQLAlchemyGolfCourseUnitOfWork(session))

        created = 0
        updated = 0
        skipped = 0
        failures: list[str] = []

        for course, match in decisions:
            if match.needs_confirmation and not args.confirm_merges:
                skipped += 1
                continue

            try:
                if match.kind is MatchKind.NEW:
                    await use_case.execute(
                        course.request,
                        creator_id,
                        provenance=course.provenance,
                        physical_holes=course.physical_holes,
                    )
                    created += 1
                else:
                    # En un campo que ya existe manda la federación, y se
                    # conserva su id para no romper las competiciones y partidas
                    # que lo referencian. Se edita como administrador porque una
                    # edición sin ese privilegio sobre un campo aprobado crearía
                    # una propuesta pendiente en vez de aplicarse.
                    assert match.existing is not None
                    await update_use_case.execute(
                        golf_course_id=GolfCourseId(match.existing.id),
                        request=to_update_request(course),
                        user_id=creator_id,
                        is_admin=True,
                        provenance=course.provenance,
                        physical_holes=course.physical_holes,
                    )
                    updated += 1
            except Exception as error:
                failures.append(f"{course.name}: {error}")

        report(decisions, problems, applying=True)
        print(f"  Campos creados:           {created}")
        print(f"  Campos actualizados:      {updated}")
        print(f"  Omitidos:                 {skipped}")
        if failures:
            print(f"  Fallos al crear:          {len(failures)}")
            for failure in failures[:20]:
                print(f"      {failure}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
