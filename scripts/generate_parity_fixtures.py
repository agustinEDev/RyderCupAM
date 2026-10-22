"""
Genera los casos de paridad que consume el test del frontend.

El frontend duplica el reparto de golpes a proposito (sin el no hay anotacion
sin conexion), y el riesgo real de esa duplicacion es que las dos
implementaciones se separen sin que nadie se entere. Los tests escritos a mano
en cada lado fijan lo que uno CREE que hacen los dos; esto fija lo que hace el
backend de verdad.

Uso (desde la raiz del repositorio):
    source .venv/bin/activate
    PYTHONPATH=. python scripts/generate_parity_fixtures.py

Escribe el JSON en el repositorio del frontend, donde lo lee
`MatchPlayStrokeAllocator.parity.test.js`. Si ese test falla despues de tocar el
reparto del backend: se regenera este fichero y se arregla el cliente hasta que
vuelva a cuadrar. No al reves.

Tambien escribe `backendStandingsParity.json` (tabla del 22 oct 2026, H): el
ORDEN de la clasificacion de una partida rapida Stableford o Medal, con el
desempate por menor handicap y quien no cuenta por sus hoyos. Sale de ejecutar
de verdad `PublishQuickMatchResultUseCase` (el aviso QUICK_MATCH_FINISHED), con
las unidades de trabajo en memoria: es el puesto que el backend publica.

    PYTHONPATH=. python scripts/generate_parity_fixtures.py                # los dos
    PYTHONPATH=. python scripts/generate_parity_fixtures.py --standings    # solo el orden
"""

import asyncio
import json
import sys
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.entities.quick_match_hole_score import (
    QuickMatchHoleScore,
)
from src.modules.quick_match.domain.services.stroke_allocation_service import (
    StrokeAllocationService,
)
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_hole_score_id import (
    QuickMatchHoleScoreId,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.quick_match.infrastructure.persistence.in_memory.in_memory_quick_match_unit_of_work import (
    InMemoryQuickMatchUnitOfWork,
)
from src.modules.social.application.use_cases.publish_quick_match_result_use_case import (
    PublishQuickMatchResultUseCase,
)
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.shared.domain.services.playing_handicap_calculator import TeeRating
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.play_mode import PlayMode
from src.shared.domain.value_objects.scoring_format import ScoringFormat

OUTPUT = (
    Path(__file__).resolve().parent.parent.parent
    / "RyderCupWeb"
    / "src"
    / "domain"
    / "services"
    / "__fixtures__"
    / "backendParity.json"
)

# Golf de Meis (RFEG 487), recorrido Par 72: el campo donde se detecto el fallo
MEIS_STROKE_INDEX = [7, 1, 13, 5, 15, 9, 3, 11, 17, 16, 2, 14, 12, 8, 18, 6, 4, 10]
MEIS_PAR = [4, 5, 4, 4, 3, 4, 5, 4, 3, 3, 4, 5, 4, 4, 3, 4, 5, 4]

# Un pitch & putt federado: 18 hoyos que suman par 58
SHORT_PAR = [3] * 14 + [4] * 4
SHORT_STROKE_INDEX = list(range(1, 19))

TEES = {
    ("YELLOW", "MALE"): TeeRating(course_rating=Decimal("73.1"), slope_rating=140, par=72),
    ("YELLOW", "FEMALE"): TeeRating(course_rating=Decimal("79.4"), slope_rating=147, par=72),
    ("WHITE", None): TeeRating(course_rating=Decimal("74.0"), slope_rating=142, par=72),
}

service = StrokeAllocationService()
_ids: dict[str, ParticipantId] = {}
scenarios: list[dict] = []


def _pid(name: str) -> ParticipantId:
    """Id estable por nombre, para que el JSON no cambie en cada ejecucion."""
    if name not in _ids:
        _ids[name] = ParticipantId.generate()
    return _ids[name]


def guest(name, handicap, color, gender, team=None) -> QuickMatchParticipant:
    return QuickMatchParticipant(
        participant_id=_pid(name),
        user_id=None,
        first_name=name,
        last_name="T",
        handicap=handicap,
        team=team,
        tee_color=color,
        tee_gender=gender,
    )


def _order(stroke_index_by_hole: list[int]) -> list[int]:
    return sorted(range(1, 19), key=lambda hole: stroke_index_by_hole[hole - 1])


def run(
    name,
    players,
    match_format,
    allowance,
    play_mode,
    tees=None,
    by_tee=None,
    pars=None,
    stroke_index=None,
) -> None:
    # El par y el indice son del campo del escenario, no siempre los de Meis: un
    # pitch & putt tiene par 58, y el cliente deriva el par sumando los hoyos que
    # le llegan aqui. Emitir el par 72 de Meis junto a un TeeRating de par 58
    # compararia dos campos distintos y la paridad no probaria nada.
    pars = MEIS_PAR if pars is None else pars
    stroke_index = MEIS_STROKE_INDEX if stroke_index is None else stroke_index
    tees = TEES if tees is None else tees
    result = service.allocate(
        participants=players,
        handicaps={
            p.participant_id: (None if p.handicap is None else Decimal(str(p.handicap)))
            for p in players
        },
        tee_ratings=tees,
        holes_by_stroke_index=_order(stroke_index),
        match_format=match_format,
        allowance_percentage=allowance,
        play_mode=play_mode,
        holes_by_stroke_index_by_tee=by_tee,
    )
    scenarios.append(
        {
            "name": name,
            "matchFormat": match_format.value if match_format else None,
            "allowancePercentage": allowance,
            "playMode": play_mode.value,
            "holes": [
                {"holeNumber": i + 1, "par": pars[i], "strokeIndex": stroke_index[i]}
                for i in range(18)
            ],
            "tees": [
                {
                    "color": color,
                    "gender": gender,
                    "courseRating": float(rating.course_rating),
                    "slopeRating": rating.slope_rating,
                }
                for (color, gender), rating in tees.items()
            ],
            "teeCards": {
                f"{color}|{gender or ''}": order
                for (color, gender), order in (by_tee or {}).items()
            },
            "participants": [
                {
                    "participantId": str(p.participant_id.value),
                    "handicap": p.handicap,
                    "color": p.tee_color.value if p.tee_color else None,
                    "teeGender": p.tee_gender.value if p.tee_gender else None,
                    "team": p.team,
                }
                for p in players
            ],
            "expected": {
                str(pid.value): {
                    "playingHandicap": strokes.playing_handicap,
                    "strokesByHole": {
                        str(hole): count for hole, count in sorted(strokes.strokes_by_hole.items())
                    },
                }
                for pid, strokes in result.items()
            },
        }
    )


def main() -> None:
    if "--standings" not in sys.argv:
        _allocation()
    asyncio.run(_standings())


def _allocation() -> None:
    yellow, white = TeeColor.YELLOW, TeeColor.WHITE
    male, female = Gender.MALE, Gender.FEMALE
    handicap, scratch = PlayMode.HANDICAP, PlayMode.SCRATCH

    run(
        "singles Meis 18 vs 20.7",
        [guest("a", 18.0, yellow, male), guest("b", 20.7, yellow, male)],
        MatchFormat.SINGLES,
        100,
        handicap,
    )
    run(
        "singles barras distinto genero",
        [guest("c", 18.0, yellow, female), guest("d", 20.7, yellow, male)],
        MatchFormat.SINGLES,
        100,
        handicap,
    )
    run(
        "libre 95%",
        [guest("e", 18.0, yellow, male), guest("f", 20.7, yellow, male)],
        None,
        95,
        handicap,
    )
    run("libre handicap plus", [guest("g", -2.0, yellow, male)], None, 100, handicap)
    run(
        "scratch",
        [guest("h", 5.0, yellow, male), guest("i", 30.0, yellow, male)],
        MatchFormat.SINGLES,
        100,
        scratch,
    )
    run("sin barra valorable 95%", [guest("j", 20.0, yellow, male)], None, 95, handicap, tees={})
    run("handicap .5 sin barra", [guest("k", 20.5, yellow, male)], None, 100, handicap, tees={})
    run("barra sin genero", [guest("l", 18.0, white, male)], None, 100, handicap)
    run(
        "fourball 90%",
        [
            guest("m", 5.0, yellow, male, "A"),
            guest("n", 15.0, yellow, male, "A"),
            guest("o", 20.0, yellow, male, "B"),
            guest("p", 25.0, yellow, male, "B"),
        ],
        MatchFormat.FOURBALL,
        90,
        handicap,
    )
    run(
        "foursomes 50%",
        [
            guest("q", 10.0, yellow, male, "A"),
            guest("r", 12.0, yellow, male, "A"),
            guest("s", 20.0, yellow, male, "B"),
            guest("t", 24.0, yellow, male, "B"),
        ],
        MatchFormat.FOURSOMES,
        50,
        handicap,
    )
    run(
        "tarjeta propia de la barra",
        [guest("u", 20.0, yellow, female)],
        None,
        100,
        handicap,
        by_tee={("YELLOW", "FEMALE"): list(range(18, 0, -1))},
    )
    # Pitch & putt federado: par 58, CR 54.9, SR 91. Hasta RyderCupAm#206 estos
    # campos no se podian valorar y los dos lados jugaban con el Handicap Index
    # a pelo, asi que la paridad no cubria ninguna barra corta. Es justo donde
    # los dos calculos se pueden separar, porque el cliente deriva el par de los
    # hoyos y el backend lo lleva en el TeeRating.
    run(
        "campo corto",
        [
            guest("x", 18.0, TeeColor.ORANGE, male),
            guest("y", 30.0, TeeColor.ORANGE, male),
        ],
        MatchFormat.SINGLES,
        100,
        handicap,
        tees={
            ("ORANGE", "MALE"): TeeRating(course_rating=Decimal("54.9"), slope_rating=91, par=58)
        },
        pars=SHORT_PAR,
        stroke_index=SHORT_STROKE_INDEX,
    )
    # El plus cuenta como negativo en match play (BE #165, decidido el 2 oct
    # 2026). Hasta entonces los dos lados recortaban cada hándicap a 0 antes de
    # restar, así que la paridad no veía la regla: ningún escenario la tocaba.
    run(
        "singles plus contra 10",
        [guest("pa", -2.0, yellow, male), guest("pb", 10.0, yellow, male)],
        MatchFormat.SINGLES,
        100,
        handicap,
    )
    run(
        "fourball con plus 90%",
        [
            guest("pc", -2.0, yellow, male, "A"),
            guest("pd", 10.0, yellow, male, "A"),
            guest("pe", 14.0, yellow, male, "B"),
            guest("pf", 6.0, yellow, male, "B"),
        ],
        MatchFormat.FOURBALL,
        90,
        handicap,
    )
    run(
        "foursomes con plus 50%",
        [
            guest("pg", -2.0, yellow, male, "A"),
            guest("ph", 10.0, yellow, male, "A"),
            guest("pi", 6.0, yellow, male, "B"),
            guest("pj", 8.0, yellow, male, "B"),
        ],
        MatchFormat.FOURSOMES,
        50,
        handicap,
    )
    run(
        "singles plus sin barra",
        [guest("pk", -2.0, yellow, male), guest("pl", 10.0, yellow, male)],
        MatchFormat.SINGLES,
        100,
        handicap,
        tees={},
    )
    run(
        "fourball con plus sin barra",
        [
            guest("po", -2.0, yellow, male, "A"),
            guest("pp", 10.0, yellow, male, "A"),
            guest("pq", 14.0, yellow, male, "B"),
            guest("pr", 6.0, yellow, male, "B"),
        ],
        MatchFormat.FOURBALL,
        100,
        handicap,
        tees={},
    )
    # Un hándicap bajo en un campo con el rating muy por debajo del par también
    # sale negativo: no hace falta ser plus
    run(
        "campo corto handicap bajo",
        [
            guest("pm", 1.0, TeeColor.ORANGE, male),
            guest("pn", 10.0, TeeColor.ORANGE, male),
        ],
        MatchFormat.SINGLES,
        100,
        handicap,
        tees={
            ("ORANGE", "MALE"): TeeRating(course_rating=Decimal("54.9"), slope_rating=91, par=58)
        },
        pars=SHORT_PAR,
        stroke_index=SHORT_STROKE_INDEX,
    )
    run(
        "sin handicap",
        [guest("v", 18.0, yellow, male), guest("w", None, yellow, male)],
        MatchFormat.SINGLES,
        100,
        handicap,
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as handle:
        json.dump(
            {"generatedBy": "RyderCupAm StrokeAllocationService", "scenarios": scenarios},
            handle,
            indent=2,
            ensure_ascii=False,
        )
        handle.write("\n")

    print(f"{len(scenarios)} escenarios escritos en {OUTPUT}")


# ==================== Orden de la clasificacion (H) ====================

STANDINGS_OUTPUT = OUTPUT.with_name("backendStandingsParity.json")

# El campo de los escenarios: par 72 (18 de par 4), indice = numero de hoyo, y
# una barra amarilla de caballeros con CR 72 y slope 113. Asi el handicap de
# juego es el 95 % del indice redondeado: 19.0 recibe 18, uno por hoyo
STANDINGS_PAR = 4
STANDINGS_CR = 72.0
STANDINGS_SLOPE = 113


def _card(golpes: int | None, **excepciones: int | None) -> dict[int, int | None]:
    """Los 18 hoyos con `golpes`, salvo `h3=5` y similares (None, la raya)."""
    tarjeta: dict[int, int | None] = dict.fromkeys(range(1, 19), golpes)
    for clave, valor in excepciones.items():
        tarjeta[int(clave[1:])] = valor
    return tarjeta


def _con(golpes: int, desde: int, hasta: int, base: int = 4) -> dict[int, int | None]:
    """`base` en todos y `golpes` del hoyo `desde` al `hasta`."""
    return {h: (golpes if desde <= h <= hasta else base) for h in range(1, 19)}


def _hoyos(golpes: int, hoyos) -> dict[int, int | None]:
    return dict.fromkeys(hoyos, golpes)


async def _campo_de_paridad(gc, creador) -> GolfCourse:
    """El campo de los escenarios, guardado en memoria."""
    course = GolfCourse.create(
        name="Parity",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creador.id,
        tees=[
            Tee(
                color=TeeColor.YELLOW,
                gender=Gender.MALE,
                identifier="Yellow",
                course_rating=STANDINGS_CR,
                slope_rating=STANDINGS_SLOPE,
            )
        ],
        holes=[Hole(number=i, par=STANDINGS_PAR, stroke_index=i) for i in range(1, 19)],
    )
    course.approve()
    async with gc:
        await gc.golf_courses.save(course)
    return course


async def _esperado(social, formato, jugadores, cuentas) -> dict:
    """Lo que publico el caso de uso para cada uno: su puesto y sus cuentas."""
    esperado = {}
    for (etiqueta, _, _), user in zip(jugadores, cuentas, strict=True):
        async with social:
            eventos = await social.activity_events.find_in(
                [ActivitySlice(user_ids=(user.id,), types=frozenset(ActivityEventType))],
                limit=5,
            )
        (evento,) = [e for e in eventos if e.type == ActivityEventType.QUICK_MATCH_FINISHED]
        p = evento.payload
        fila = {
            "position": p["position"],
            "tied": p["tied"],
            "unfinished": p["unfinished"],
            "totalPlayers": p["total_players"],
            "holesPlayed": p["holes_played"],
            "grossStrokes": p["gross_strokes"],
        }
        if formato == ScoringFormat.MEDAL:
            fila["netStrokes"] = p["net_strokes"]
            fila["toPar"] = p["to_par"]
        else:
            fila["points"] = p["points"]
        esperado[etiqueta] = fila
    return esperado


async def _escenario(
    escenarios: list[dict], name: str, formato, jugadores: list[tuple[str, float | None, dict]]
) -> None:
    """`jugadores`: (etiqueta, indice o None, tarjeta). El primero crea la partida."""
    social, qm, gc, users = (
        InMemorySocialUnitOfWork(),
        InMemoryQuickMatchUnitOfWork(),
        InMemoryGolfCourseUnitOfWork(),
        InMemoryUnitOfWork(),
    )
    cuentas = []
    for etiqueta, _, _ in jugadores:
        user = User.create(
            first_name=etiqueta,
            last_name="Parity",
            email_str=f"parity_{uuid4().hex[:10]}@test.com",
            plain_password="SecureP@ssw0rd123",
        )
        async with users:
            await users.users.save(user)
        cuentas.append(user)
    creador = cuentas[0]
    if jugadores[0][1] is not None:
        creador.update_handicap(jugadores[0][1])
        async with users:
            await users.users.save(creador)

    course = await _campo_de_paridad(gc, creador)

    match = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=creador.id,
        golf_course_id=course.id,
        scoring_format=formato,
        match_format=None,
    )
    for (_, indice, _), user in zip(jugadores[1:], cuentas[1:], strict=True):
        participante = QuickMatchParticipant.for_user(user.id)
        if indice is not None:
            participante = participante.with_handicap(indice)
        match.add_participant(participante)
    anotador = match.participants[0].participant_id
    match.start(scorer_ids=[anotador])
    match.complete()

    etiquetas = {}
    async with qm:
        await qm.quick_matches.add(match)
        for participante, (etiqueta, _, tarjeta) in zip(match.participants, jugadores, strict=True):
            etiquetas[participante.participant_id] = etiqueta
            for hoyo, golpes in tarjeta.items():
                await qm.quick_match_hole_scores.add(
                    QuickMatchHoleScore(
                        id=QuickMatchHoleScoreId.generate(),
                        quick_match_id=match.id,
                        hole_number=hoyo,
                        participant_id=participante.participant_id,
                        score=golpes,
                        recorded_by_participant_id=anotador,
                    )
                )
        await qm.commit()

    await PublishQuickMatchResultUseCase(social, qm, gc, users).execute(str(match.id.value))

    esperado = await _esperado(social, formato, jugadores, cuentas)

    escenarios.append(
        {
            "name": name,
            "scoringFormat": formato.value,
            "playMode": match.play_mode.value,
            "allowancePercentage": match.get_effective_allowance(),
            "holes": [
                {"holeNumber": i, "par": STANDINGS_PAR, "strokeIndex": i} for i in range(1, 19)
            ],
            "tees": [
                {
                    "color": "YELLOW",
                    "gender": "MALE",
                    "courseRating": STANDINGS_CR,
                    "slopeRating": STANDINGS_SLOPE,
                }
            ],
            "participants": [
                {
                    "participantId": etiquetas[p.participant_id],
                    "handicap": indice,
                    "color": p.tee_color.value if p.tee_color else None,
                    "teeGender": p.tee_gender.value if p.tee_gender else None,
                }
                for p, (_, indice, _) in zip(match.participants, jugadores, strict=True)
            ],
            "scores": {
                etiqueta: {str(h): g for h, g in sorted(tarjeta.items())}
                for etiqueta, _, tarjeta in jugadores
            },
            "expected": esperado,
        }
    )


async def _standings() -> None:
    stableford, medal = ScoringFormat.STABLEFORD, ScoringFormat.MEDAL
    escenarios: list[dict] = []

    # --- Stableford ---
    await _escenario(
        escenarios,
        "stableford empate a puntos, delante el de menos handicap",
        stableford,
        [("a", 19.0, _card(5)), ("b", 12.4, _con(5, 1, 12)), ("c", 30.0, _card(6))],
    )
    await _escenario(
        escenarios,
        "stableford empate con el mismo handicap exacto: comparten",
        stableford,
        [("a", 19.0, _card(5)), ("b", 19.0, _card(5)), ("c", 0.0, _card(5))],
    )
    await _escenario(
        escenarios,
        "stableford empate triple con handicaps mezclados",
        stableford,
        [
            ("a", 19.0, _card(5)),
            ("b", 12.4, _con(5, 1, 12)),
            ("c", 19.0, _card(5)),
            ("d", 0.0, _card(5)),
        ],
    )
    await _escenario(
        escenarios,
        "stableford sin handicap cuenta como 0: delante de 19.0",
        stableford,
        [("a", None, _card(4)), ("b", 19.0, _card(5))],
    )
    await _escenario(
        escenarios,
        "stableford sin handicap empata con un 0.0",
        stableford,
        [("a", None, _card(4)), ("b", 0.0, _card(4)), ("c", 30.0, _card(6))],
    )
    await _escenario(
        escenarios,
        "stableford un plus delante de un 0.0",
        stableford,
        [("a", 0.0, _card(4)), ("b", -1.0, _card(4, h18=3))],
    )
    await _escenario(
        escenarios,
        "stableford uno con 17 hoyos no cuenta y no ocupa puesto",
        stableford,
        [
            ("a", 19.0, _card(5)),
            ("b", 12.4, _con(5, 1, 12)),
            ("c", 0.0, dict.fromkeys(range(1, 18), 3)),
        ],
    )
    await _escenario(
        escenarios,
        "stableford solo uno cuenta: sin puesto",
        stableford,
        [("a", 10.0, _card(4)), ("b", 10.0, _hoyos(4, range(1, 10)))],
    )
    await _escenario(
        escenarios,
        "stableford con raya (hoyo recogido)",
        stableford,
        [("a", 19.0, _card(5, h1=None)), ("b", 19.0, _card(5, h1=7))],
    )
    await _escenario(
        escenarios,
        "stableford nueve hoyos: la ida",
        stableford,
        [("a", 19.0, _hoyos(5, range(1, 10))), ("b", 0.0, _hoyos(4, range(1, 10)))],
    )
    await _escenario(
        escenarios,
        "stableford conjuntos distintos de nueve: no cuenta nadie",
        stableford,
        [("a", 10.0, _hoyos(4, range(1, 10))), ("b", 10.0, _hoyos(4, range(10, 19)))],
    )

    # --- Medal ---
    await _escenario(
        escenarios,
        "medal empate a netos, delante el de menos handicap",
        medal,
        [("a", 19.0, _card(5)), ("b", 3.0, _con(5, 1, 3))],
    )
    await _escenario(
        escenarios,
        "medal empate triple con sin handicap y el mismo 0",
        medal,
        [("a", None, _card(4)), ("b", 19.0, _card(5)), ("c", 0.0, _card(4))],
    )
    await _escenario(
        escenarios,
        "medal empate con el mismo handicap exacto",
        medal,
        [("a", 12.4, _con(5, 1, 12)), ("b", 12.4, _con(5, 7, 18)), ("c", 30.0, _card(4))],
    )
    await _escenario(
        escenarios,
        "medal uno con 9 hoyos entre los de 18 no cuenta",
        medal,
        [
            ("a", 19.0, _card(5)),
            ("b", 3.0, _con(5, 1, 3)),
            ("c", 0.0, _hoyos(3, range(1, 10))),
        ],
    )

    STANDINGS_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with STANDINGS_OUTPUT.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "generatedBy": "RyderCupAm PublishQuickMatchResultUseCase",
                "scenarios": escenarios,
            },
            handle,
            indent=2,
            ensure_ascii=False,
        )
        handle.write("\n")

    print(f"{len(escenarios)} escenarios de clasificacion escritos en {STANDINGS_OUTPUT}")


if __name__ == "__main__":
    main()
