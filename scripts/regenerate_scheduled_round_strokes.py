"""
Recalcula el reparto de golpes de las rondas que aun no se han empezado.

POR QUE HACE FALTA
------------------
Los partidos de competicion se generan una vez y se PERSISTEN: el
`strokes_received` de cada jugador queda escrito en la fila del partido. Un
reparto mal calculado no se arregla solo al desplegar el codigo corregido, se
queda congelado en la base de datos.

Las dos correcciones que obligan a pasar esto:

1. Cada barra se valora contra SU par, no contra el del campo. Cambia cuantos
   golpes se reparten.
2. Los golpes se reparten con el stroke index de la barra que juega cada uno, no
   con el de la tarjeta de referencia. Cambia en que hoyos caen.

De los 800 campos federados importados con mas de una barra con tarjeta, 25
tienen par distinto entre barras y 56 stroke index distinto: un 10% esta expuesto
a al menos uno de los dos.

COMO LO HACE
------------
No duplica el calculo: lee los emparejamientos que ya hay, devuelve la ronda a
PENDING_MATCHES (`Round.reopen_for_regeneration`) y vuelve a llamar a
`GenerateMatchesUseCase` con esos mismos emparejamientos como `manual_pairings`.
Asi el reparto sale del codigo corregido y nadie cambia de rival ni de partido.

QUE TOCA Y QUE NO
-----------------
- Solo rondas en SCHEDULED (partidos generados, ninguno empezado). IN_PROGRESS y
  COMPLETED no se tocan: ahi ya hay resultados.
- Solo competiciones en modo HANDICAP. En SCRATCH no hay golpes que repartir.
- Conserva emparejamientos y numero de partido.

USO
---
    source .venv/bin/activate
    PYTHONPATH=. python scripts/regenerate_scheduled_round_strokes.py --dry-run
    PYTHONPATH=. python scripts/regenerate_scheduled_round_strokes.py

`--dry-run` no escribe nada: lista las rondas que se regenerarian. Conviene
mirarlo antes de ejecutarlo en serio, y tener copia de seguridad de la base de
datos: esto borra y recrea filas de `matches`.
"""

import argparse
import asyncio

from src.config.database import async_session_maker
from src.modules.competition.application.dto.round_match_dto import (
    GenerateMatchesRequestDTO,
    ManualPairingDTO,
)
from src.modules.competition.application.use_cases.generate_matches_use_case import (
    GenerateMatchesUseCase,
)
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_unit_of_work import (
    SQLAlchemyCompetitionUnitOfWork,
)
from src.modules.golf_course.infrastructure.persistence.sqlalchemy.golf_course_unit_of_work import (
    SQLAlchemyGolfCourseUnitOfWork,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork,
)

COMPETITIONS_PAGE = 200


async def main(dry_run: bool) -> int:
    regenerated_rounds = 0
    regenerated_matches = 0
    skipped = 0

    async with async_session_maker() as session:
        uow = SQLAlchemyCompetitionUnitOfWork(session)
        # `handicap_service=None` a proposito: en un lote no se sale a pedir
        # handicaps a la RFEG, se recalcula con los que ya hay guardados.
        use_case = GenerateMatchesUseCase(
            uow=uow,
            golf_course_repository=SQLAlchemyGolfCourseUnitOfWork(session).golf_courses,
            user_repository=SQLAlchemyUnitOfWork(session).users,
        )

        async with uow:
            competitions = await uow.competitions.find_all(limit=COMPETITIONS_PAGE, offset=0)

        for competition in competitions:
            if competition.play_mode != PlayMode.HANDICAP:
                continue

            async with uow:
                rounds = await uow.rounds.find_by_competition(competition.id)

            for round_entity in rounds:
                if round_entity.status != RoundStatus.SCHEDULED:
                    continue

                async with uow:
                    matches = await uow.matches.find_by_round(round_entity.id)

                if not matches:
                    continue

                pairings = [
                    ManualPairingDTO(
                        team_a_player_ids=[p.user_id.value for p in match.team_a_players],
                        team_b_player_ids=[p.user_id.value for p in match.team_b_players],
                    )
                    for match in sorted(matches, key=lambda m: m.match_number)
                ]

                print(
                    f"  {competition.name} / ronda {round_entity.id.value}: "
                    f"{len(pairings)} partidos"
                )

                if dry_run:
                    regenerated_rounds += 1
                    regenerated_matches += len(pairings)
                    continue

                try:
                    async with uow:
                        round_entity.reopen_for_regeneration()
                        await uow.rounds.update(round_entity)

                    await use_case.execute(
                        GenerateMatchesRequestDTO(
                            round_id=round_entity.id.value,
                            manual_pairings=pairings,
                        ),
                        user_id=competition.creator_id,
                        is_admin=True,
                    )
                    regenerated_rounds += 1
                    regenerated_matches += len(pairings)
                except Exception as exc:  # se informa y se sigue con las demas
                    skipped += 1
                    print(f"    ERROR, ronda sin tocar: {exc}")

    print(
        f"\n{'(dry-run) ' if dry_run else ''}"
        f"Rondas regeneradas: {regenerated_rounds} | partidos: {regenerated_matches}"
        + (f" | rondas con error: {skipped}" if skipped else "")
    )
    return 1 if skipped else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Recalcula el reparto de golpes de las rondas SCHEDULED"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Lista lo que haria sin escribir nada"
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.dry_run)))
