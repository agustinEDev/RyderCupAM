"""
Tests del comando que importa de OpenStreetMap los mapas de hoyos (BE #532).

Cubren la línea de órdenes y la pasada (pausas, recuento, que un fallo no pare
nada). Lo que se hace con cada campo se prueba en su caso de uso, y qué campos
se eligen, contra la base de datos en los tests de integración.
"""

import pytest

from scripts.import_hole_maps import parse_args, report, run
from src.modules.golf_course.application.dtos.hole_map_import_dtos import (
    ImportHoleMapResponseDTO,
    ImportHoleMapStatus,
)

# ============================================================================
# S1-S2 — Argumentos
# ============================================================================


def test_s1_by_country():
    """
    GIVEN: --country ES
    WHEN: Se leen los argumentos
    THEN: Se importa ese país, en seco y con pausa de 5 s
    """
    args = parse_args(["--country", "ES"])

    assert args.country == "ES"
    assert args.course is None
    assert args.apply is False
    assert args.pause == 5.0


def test_s1_by_course():
    """
    GIVEN: --course <id> --apply
    WHEN: Se leen los argumentos
    THEN: Se importa ese campo, guardando
    """
    args = parse_args(["--course", "cd995c5f-0aec-4396-994d-380b32540421", "--apply"])

    assert args.course == "cd995c5f-0aec-4396-994d-380b32540421"
    assert args.apply is True


@pytest.mark.parametrize(
    "argv",
    [[], ["--country", "ES", "--course", "x"], ["--apply"]],
    ids=["ninguno", "los-dos", "solo-apply"],
)
def test_s1_country_or_course_is_required(argv):
    """
    GIVEN: Ni país ni campo, o los dos a la vez
    WHEN: Se leen los argumentos
    THEN: Error de uso: hay que decir qué se importa
    """
    with pytest.raises(SystemExit):
        parse_args(argv)


def test_s1_country_is_upper_cased():
    """
    GIVEN: --country es
    WHEN: Se leen los argumentos
    THEN: Se toma como ES
    """
    assert parse_args(["--country", "es"]).country == "ES"


# ============================================================================
# S2-S5 — La pasada
# ============================================================================


def _resultado(status, holes=0, discarded=None):
    return ImportHoleMapResponseDTO(
        status=status, holes_imported=holes, discarded=discarded or {}, osm_reference=None
    )


class Importador:
    """Hace de caso de uso: devuelve lo que toque para cada campo y apunta las llamadas."""

    def __init__(self, resultados):
        self.resultados = resultados
        self.llamadas: list[tuple[str, bool]] = []

    async def __call__(self, course_id: str, apply: bool):
        self.llamadas.append((course_id, apply))
        resultado = self.resultados[course_id]
        if isinstance(resultado, Exception):
            raise resultado
        return resultado


@pytest.mark.asyncio
@pytest.mark.parametrize("apply", [False, True])
async def test_s2_apply_flag_reaches_every_course(apply):
    """
    GIVEN: Dos campos
    WHEN: Se hace la pasada con o sin --apply
    THEN: Cada campo se importa con ese mismo modo
    """
    importador = Importador(
        {
            "a": _resultado(ImportHoleMapStatus.CREATED),
            "b": _resultado(ImportHoleMapStatus.NO_OUTLINE),
        }
    )

    await run(["a", "b"], importador, apply=apply, pause=5.0, sleep=_sin_espera)

    assert importador.llamadas == [("a", apply), ("b", apply)]


async def _sin_espera(_seconds):
    return None


@pytest.mark.asyncio
async def test_s3_pauses_between_courses_not_after_the_last():
    """
    GIVEN: Tres campos y una pausa de 5 s
    WHEN: Se hace la pasada
    THEN: Se espera 5 s entre uno y otro: dos veces, no tras el último
    """
    esperas = []

    async def sleep(seconds):
        esperas.append(seconds)

    importador = Importador({c: _resultado(ImportHoleMapStatus.NO_OUTLINE) for c in "abc"})

    await run(list("abc"), importador, apply=False, pause=5.0, sleep=sleep)

    assert esperas == [5.0, 5.0]


@pytest.mark.asyncio
async def test_s4_summary_counts_statuses_and_discarded_holes():
    """
    GIVEN: Campos con resultados distintos y hoyos descartados
    WHEN: Se hace la pasada
    THEN: El resumen cuenta cada estado, los hoyos importados y los descartados por motivo
    """
    importador = Importador(
        {
            "a": _resultado(ImportHoleMapStatus.CREATED, 18, {"PAR_MISMATCH": 1}),
            "b": _resultado(ImportHoleMapStatus.CREATED, 16, {"PAR_MISMATCH": 2, "AMBIGUOUS": 1}),
            "c": _resultado(ImportHoleMapStatus.SKIPPED_APPROVED),
            "d": _resultado(ImportHoleMapStatus.NO_OUTLINE),
        }
    )

    summary = await run(list("abcd"), importador, apply=True, pause=0, sleep=_sin_espera)

    assert summary.statuses == {"CREATED": 2, "SKIPPED_APPROVED": 1, "NO_OUTLINE": 1}
    assert summary.holes_imported == 34
    assert summary.discarded == {"PAR_MISMATCH": 3, "AMBIGUOUS": 1}
    texto = report(summary, apply=True)
    assert "CREATED" in texto and "34" in texto and "PAR_MISMATCH" in texto


@pytest.mark.asyncio
async def test_s5_a_failing_course_does_not_stop_the_run():
    """
    GIVEN: Tres campos y el segundo revienta
    WHEN: Se hace la pasada
    THEN: Se cuenta como error con su campo y se sigue con el tercero
    """
    importador = Importador(
        {
            "a": _resultado(ImportHoleMapStatus.CREATED, 18),
            "b": RuntimeError("boom"),
            "c": _resultado(ImportHoleMapStatus.CREATED, 18),
        }
    )

    summary = await run(list("abc"), importador, apply=True, pause=0, sleep=_sin_espera)

    assert [c for c, _ in importador.llamadas] == ["a", "b", "c"]
    assert summary.statuses == {"CREATED": 2, "ERROR": 1}
    assert summary.errors == [("b", "RuntimeError: boom")]


def test_s2_report_says_when_it_was_a_dry_run():
    """
    GIVEN: Una pasada en seco
    WHEN: Se escribe el resumen
    THEN: Dice que no se guardó nada
    """
    from scripts.import_hole_maps import Summary

    assert "seco" in report(Summary(), apply=False).lower()
