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
"""

import json
from decimal import Decimal
from pathlib import Path

from src.modules.competition.domain.services.playing_handicap_calculator import TeeRating
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.quick_match.domain.services.stroke_allocation_service import (
    StrokeAllocationService,
)
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.shared.domain.value_objects.gender import Gender

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


def run(name, players, match_format, allowance, play_mode, tees=None, by_tee=None) -> None:
    tees = TEES if tees is None else tees
    result = service.allocate(
        participants=players,
        handicaps={
            p.participant_id: (None if p.handicap is None else Decimal(str(p.handicap)))
            for p in players
        },
        tee_ratings=tees,
        holes_by_stroke_index=_order(MEIS_STROKE_INDEX),
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
                {"holeNumber": i + 1, "par": MEIS_PAR[i], "strokeIndex": MEIS_STROKE_INDEX[i]}
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
                f"{color}|{gender or ''}": order for (color, gender), order in (by_tee or {}).items()
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
                        str(hole): count
                        for hole, count in sorted(strokes.strokes_by_hole.items())
                    },
                }
                for pid, strokes in result.items()
            },
        }
    )


def main() -> None:
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


if __name__ == "__main__":
    main()
