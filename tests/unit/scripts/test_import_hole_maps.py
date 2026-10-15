"""
Tests del comando que importa de OpenStreetMap los mapas de hoyos (BE #532).

Cubren la línea de órdenes y la pasada (pausas, recuento, que un fallo no pare
nada). Lo que se hace con cada campo se prueba en su caso de uso, y qué campos
se eligen, contra la base de datos en los tests de integración.
"""

import pytest

from scripts.import_hole_maps import (
    MAX_CONSECUTIVE_UNAVAILABLE,
    exit_code,
    nothing_to_import,
    parse_args,
    report,
    run,
)
from src.modules.golf_course.application.dtos.hole_map_import_dtos import (
    ImportHoleMapResponseDTO,
    ImportHoleMapStatus,
)
from src.modules.golf_course.infrastructure.osm.overpass_client import DEFAULT_OVERPASS_URL

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
    assert args.overpass_url == DEFAULT_OVERPASS_URL


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


def test_s1_malformed_course_id_is_a_usage_error():
    """
    GIVEN: --course con un id que no es un UUID
    WHEN: Se leen los argumentos
    THEN: Error de uso, no una traza
    """
    with pytest.raises(SystemExit):
        parse_args(["--course", "no-es-un-uuid"])


@pytest.mark.asyncio
async def test_s3_no_pause_after_a_course_that_did_not_ask_osm():
    """
    GIVEN: Un campo ya aprobado (no pregunta a OSM), uno sin coordenadas y otro
    WHEN: Se hace la pasada
    THEN: Tras los que no preguntaron a OSM no se espera
    """
    esperas = []

    async def sleep(seconds):
        esperas.append(seconds)

    importador = Importador(
        {
            "a": _resultado(ImportHoleMapStatus.SKIPPED_APPROVED),
            "b": _resultado(ImportHoleMapStatus.NO_COORDINATES),
            "c": _resultado(ImportHoleMapStatus.CREATED, 18),
            "d": _resultado(ImportHoleMapStatus.CREATED, 18),
        }
    )

    await run(list("abcd"), importador, apply=False, pause=5.0, sleep=sleep)

    assert esperas == [5.0]


@pytest.mark.asyncio
async def test_s6_stops_after_5_osm_unavailable_in_a_row():
    """
    GIVEN: Ocho campos y OSM no disponible en todos
    WHEN: Se hace la pasada
    THEN: Para tras 5 seguidos, sin insistir contra un servicio que nos limita
    """
    importador = Importador(
        {c: _resultado(ImportHoleMapStatus.OSM_UNAVAILABLE) for c in "abcdefgh"}
    )

    summary = await run(list("abcdefgh"), importador, apply=True, pause=0, sleep=_sin_espera)

    assert MAX_CONSECUTIVE_UNAVAILABLE == 5
    assert len(importador.llamadas) == 5
    assert summary.aborted is True
    assert "Overpass" in report(summary, apply=True)


@pytest.mark.asyncio
async def test_s6_a_success_resets_the_streak():
    """
    GIVEN: Cuatro «OSM no disponible», uno bueno y otros cuatro
    WHEN: Se hace la pasada
    THEN: No para: la racha se corta con el bueno
    """
    resultados = {c: _resultado(ImportHoleMapStatus.OSM_UNAVAILABLE) for c in "abcdfghi"}
    resultados["e"] = _resultado(ImportHoleMapStatus.CREATED, 18)

    summary = await run(
        list("abcdefghi"), Importador(resultados), apply=True, pause=0, sleep=_sin_espera
    )

    assert summary.aborted is False
    assert summary.statuses == {"OSM_UNAVAILABLE": 8, "CREATED": 1}


@pytest.mark.parametrize(
    ("statuses", "errors", "aborted", "code"),
    [
        ({"CREATED": 3}, [], False, 0),
        ({"CREATED": 3, "OSM_UNAVAILABLE": 1}, [], False, 1),
        ({"CREATED": 2, "ERROR": 1}, [("x", "boom")], False, 1),
        ({"OSM_UNAVAILABLE": 5}, [], True, 1),
    ],
    ids=["todo-bien", "osm-caido-en-uno", "error", "cortada"],
)
def test_s6_exit_code_says_when_something_could_not_be_done(statuses, errors, aborted, code):
    """
    GIVEN: El resumen de una pasada
    WHEN: Se calcula el código de salida
    THEN: 0 solo si no hubo errores, ni campos sin poder consultar a OSM, ni corte
    """
    from collections import Counter

    from scripts.import_hole_maps import Summary

    summary = Summary(statuses=Counter(statuses), errors=errors, aborted=aborted)

    assert exit_code(summary) == code


def test_s7_course_that_cannot_be_imported_is_explained():
    """
    GIVEN: --course de un campo que no sale en la selección
    WHEN: No hay nada que importar
    THEN: Se explica por qué (no existe, no está aprobado o no tiene coordenadas)
    """
    args = parse_args(["--course", "cd995c5f-0aec-4396-994d-380b32540421"])

    message = nothing_to_import(args, [])

    assert message is not None
    assert "aprobado" in message and "coordenadas" in message


def test_s7_nothing_to_explain_when_there_are_courses():
    """
    GIVEN: Una selección con campos, o un país sin campos
    WHEN: Se mira si hay que explicar algo
    THEN: Solo se explica el caso del campo suelto que no sale
    """
    assert (
        nothing_to_import(parse_args(["--course", "cd995c5f-0aec-4396-994d-380b32540421"]), ["x"])
        is None
    )
    assert nothing_to_import(parse_args(["--country", "ES"]), []) is None


def test_s8_another_overpass_server_can_be_used():
    """
    GIVEN: --overpass-url con un espejo de Overpass (el principal, caído)
    WHEN: Se leen los argumentos
    THEN: Se usará ese servidor
    """
    args = parse_args(
        ["--country", "ES", "--overpass-url", "https://overpass.kumi.systems/api/interpreter"]
    )

    assert args.overpass_url == "https://overpass.kumi.systems/api/interpreter"


@pytest.mark.parametrize("url", ["overpass.kumi.systems", "ftp://x/api", "http://"])
def test_s8_overpass_url_must_be_http(url):
    """
    GIVEN: Un --overpass-url que no es una URL http(s) con servidor
    WHEN: Se leen los argumentos
    THEN: Error de uso
    """
    with pytest.raises(SystemExit):
        parse_args(["--country", "ES", "--overpass-url", url])
