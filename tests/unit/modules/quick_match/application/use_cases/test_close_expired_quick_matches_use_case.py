"""
El cierre de las partidas rápidas que nadie termina (Agustín, 23 oct 2026).

| Caso | Partida                                      | Resultado                                |
|------|----------------------------------------------|------------------------------------------|
| B1   | En juego con golpes, pasado su plazo         | COMPLETED y se publica en Actividad      |
|      | En juego, antes de su plazo                  | Sigue en juego                           |
| B6   | En juego sin ningún golpe                    | CANCELLED, sin publicar                  |
| B4   | PENDING de más de 7 días                     | CANCELLED                                |
| B4   | PENDING de menos de 7 días                   | Sigue PENDING                            |
| B12  | Cerrada más de 2 días después de su plazo    | COMPLETED sin publicar                   |
| B8   | Campo borrado o sin zona                     | Plazo en UTC                             |
|      | Ya terminada (o cerrada a mano entretanto)   | No se toca                               |
|      | Publicar falla                               | La partida queda cerrada y se sigue      |
"""

import copy
import logging
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.application.use_cases.close_expired_quick_matches_use_case import (
    CloseExpiredQuickMatchesUseCase,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.entities.quick_match_hole_score import QuickMatchHoleScore
from src.modules.quick_match.domain.value_objects.quick_match_hole_score_id import (
    QuickMatchHoleScoreId,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.match_format import MatchFormat
from tests.unit.modules.quick_match.conftest import create_golf_course

pytestmark = pytest.mark.asyncio

T = QuickMatchStatus
# Empezó el sábado 18 a las 7:00 UTC: en un campo sin zona se cierra el lunes 20
# a las 00:00 UTC
EMPEZO = datetime(2026, 10, 18, 7, 0)
PLAZO = datetime(2026, 10, 20, 0, 0)


class _Publicador:
    def __init__(self, falla: bool = False):
        self.publicadas: list[str] = []
        self.fechas: list[datetime | None] = []
        self._falla = falla

    async def publish(self, quick_match_id: str, published_at: datetime | None = None) -> int:
        self.publicadas.append(quick_match_id)
        self.fechas.append(published_at)
        if self._falla:
            raise RuntimeError("Actividad caída")
        return self.devuelve

    devuelve = 1


async def _partida(
    qm_uow,
    *,
    status=T.IN_PROGRESS,
    golpes: int = 1,
    created_at=EMPEZO,
    started_at=EMPEZO,
    golf_course_id=None,
):
    qm = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=UserId(uuid4()),
        golf_course_id=golf_course_id or GolfCourseId(uuid4()),
        match_format=MatchFormat.SINGLES,
    )
    qm.add_participant(QuickMatchParticipant.for_user(UserId(uuid4())))
    if status != T.PENDING:
        qm.start([qm.creator_participant_id])
    if status == T.COMPLETED:
        qm.complete()
    qm._created_at = created_at
    qm._started_at = started_at if status != T.PENDING else None
    async with qm_uow:
        await qm_uow.quick_matches.add(qm)
        for hoyo in range(1, golpes + 1):
            await qm_uow.quick_match_hole_scores.add(
                QuickMatchHoleScore(
                    id=QuickMatchHoleScoreId.generate(),
                    quick_match_id=qm.id,
                    hole_number=hoyo,
                    participant_id=qm.creator_participant_id,
                    score=4,
                    recorded_by_participant_id=qm.creator_participant_id,
                )
            )
    return qm


async def _cierra(qm_uow, golf_course_uow, ahora, publicador=None):
    publicador = publicador or _Publicador()
    resumen = await CloseExpiredQuickMatchesUseCase(
        qm_uow, golf_course_uow, publicador, reloj=lambda: ahora
    ).execute()
    return resumen, publicador


async def _estado(qm_uow, qm):
    async with qm_uow:
        return (await qm_uow.quick_matches.find_by_id(qm.id)).status


class TestInProgress:
    async def test_b1_with_strokes_it_completes_and_publishes(self, qm_uow, golf_course_uow):
        qm = await _partida(qm_uow)

        resumen, publicador = await _cierra(qm_uow, golf_course_uow, PLAZO)

        assert await _estado(qm_uow, qm) == T.COMPLETED
        assert publicador.publicadas == [str(qm.id.value)]
        assert (resumen.completed, resumen.cancelled, resumen.published) == (1, 0, 1)

    async def test_l5_it_is_published_on_the_day_it_was_played(self, qm_uow, golf_course_uow):
        """En Actividad, en su dia y no arriba con «ahora» (Agustin, 24 oct 2026)."""
        await _partida(qm_uow, created_at=EMPEZO - timedelta(days=2))

        _, publicador = await _cierra(qm_uow, golf_course_uow, PLAZO + timedelta(days=1))

        assert publicador.fechas == [EMPEZO]

    async def test_before_its_time_it_is_left_alone(self, qm_uow, golf_course_uow):
        qm = await _partida(qm_uow)

        resumen, publicador = await _cierra(qm_uow, golf_course_uow, PLAZO - timedelta(seconds=1))

        assert await _estado(qm_uow, qm) == T.IN_PROGRESS
        assert publicador.publicadas == []
        assert (resumen.completed, resumen.cancelled) == (0, 0)

    async def test_b6_without_strokes_it_is_cancelled(self, qm_uow, golf_course_uow):
        qm = await _partida(qm_uow, golpes=0)

        resumen, publicador = await _cierra(qm_uow, golf_course_uow, PLAZO)

        assert await _estado(qm_uow, qm) == T.CANCELLED
        assert publicador.publicadas == []
        assert resumen.cancelled == 1

    async def test_b12_more_than_two_days_late_it_is_not_published(self, qm_uow, golf_course_uow):
        qm = await _partida(qm_uow)

        resumen, publicador = await _cierra(
            qm_uow, golf_course_uow, PLAZO + timedelta(days=2, seconds=1)
        )

        assert await _estado(qm_uow, qm) == T.COMPLETED
        assert publicador.publicadas == []
        assert resumen.published == 0

    async def test_b12_two_days_late_it_is_still_published(self, qm_uow, golf_course_uow):
        await _partida(qm_uow)

        resumen, _ = await _cierra(qm_uow, golf_course_uow, PLAZO + timedelta(days=2))

        assert resumen.published == 1

    async def test_the_course_time_zone_decides(self, qm_uow, golf_course_uow):
        """En Madrid (+2 en octubre) el lunes 20 empieza a las 22:00 UTC del domingo."""
        campo = await create_golf_course(golf_course_uow, UserId(uuid4()))
        campo._timezone = "Europe/Madrid"
        async with golf_course_uow:
            await golf_course_uow.golf_courses.save(campo)
        qm = await _partida(qm_uow, golf_course_id=campo.id)

        await _cierra(qm_uow, golf_course_uow, datetime(2026, 10, 19, 22, 0))

        assert await _estado(qm_uow, qm) == T.COMPLETED

    async def test_publishing_failing_leaves_it_closed_and_goes_on(self, qm_uow, golf_course_uow):
        una = await _partida(qm_uow)
        otra = await _partida(qm_uow)

        _, publicador = await _cierra(qm_uow, golf_course_uow, PLAZO, _Publicador(falla=True))

        assert await _estado(qm_uow, una) == T.COMPLETED
        assert await _estado(qm_uow, otra) == T.COMPLETED
        assert len(publicador.publicadas) == 2


class TestPending:
    async def test_b4_after_seven_days_it_is_cancelled(self, qm_uow, golf_course_uow):
        qm = await _partida(qm_uow, status=T.PENDING, golpes=0)

        resumen, publicador = await _cierra(qm_uow, golf_course_uow, EMPEZO + timedelta(days=7))

        assert await _estado(qm_uow, qm) == T.CANCELLED
        assert publicador.publicadas == []
        assert resumen.cancelled == 1

    async def test_b4_before_seven_days_it_waits(self, qm_uow, golf_course_uow):
        qm = await _partida(qm_uow, status=T.PENDING, golpes=0)

        await _cierra(qm_uow, golf_course_uow, EMPEZO + timedelta(days=7, seconds=-1))

        assert await _estado(qm_uow, qm) == T.PENDING


class TestTheFinishedOnes:
    async def test_a_finished_one_is_not_touched(self, qm_uow, golf_course_uow):
        qm = await _partida(qm_uow, status=T.COMPLETED)

        resumen, publicador = await _cierra(qm_uow, golf_course_uow, PLAZO + timedelta(days=30))

        assert await _estado(qm_uow, qm) == T.COMPLETED
        assert publicador.publicadas == []
        assert (resumen.completed, resumen.cancelled) == (0, 0)

    async def test_one_finished_by_hand_meanwhile_is_not_touched(
        self, qm_uow, golf_course_uow, caplog
    ):
        """La lista se lee antes; al cerrar cada una se vuelve a mirar, bloqueada."""
        qm = await _partida(qm_uow)
        caso = CloseExpiredQuickMatchesUseCase(
            qm_uow, golf_course_uow, _Publicador(), reloj=lambda: PLAZO
        )
        abiertas = qm_uow.quick_matches.list_open

        async def y_la_termina_el_creador():
            # Lo leído es una foto: la partida guardada cambia después
            lista = [copy.deepcopy(p) for p in await abiertas()]
            stored = await qm_uow.quick_matches.find_by_id(qm.id)
            stored.complete()
            return lista

        qm_uow.quick_matches.list_open = y_la_termina_el_creador

        with caplog.at_level(logging.WARNING):
            resumen = await caso.execute()

        assert (resumen.completed, resumen.cancelled) == (0, 0)
        assert await _estado(qm_uow, qm) == T.COMPLETED
        # Se salta sin intentarlo, no porque cerrarla fallara
        assert "Could not close" not in caplog.text


class TestTheRaces:
    async def test_one_started_meanwhile_is_judged_by_its_new_deadline(
        self, qm_uow, golf_course_uow
    ):
        """
        Hallazgo 3 del revisor: leída PENDING y vencida, el creador la empieza
        mientras la vuelta va por otras. Bloqueada ya está en juego, sin golpes
        y con el plazo de mañana: no se cancela.
        """
        qm = await _partida(qm_uow, status=T.PENDING, golpes=0)
        ahora = EMPEZO + timedelta(days=7)
        abiertas = qm_uow.quick_matches.list_open

        async def y_la_empieza_el_creador():
            lista = [copy.deepcopy(p) for p in await abiertas()]
            stored = await qm_uow.quick_matches.find_by_id(qm.id)
            stored.start([stored.creator_participant_id])
            stored._started_at = ahora
            return lista

        qm_uow.quick_matches.list_open = y_la_empieza_el_creador

        resumen, _ = await _cierra(qm_uow, golf_course_uow, ahora)

        assert await _estado(qm_uow, qm) == T.IN_PROGRESS
        assert resumen.cancelled == 0


class TestWhatIsCounted:
    async def test_published_counts_only_what_activity_took(self, qm_uow, golf_course_uow):
        """El publicador se traga sus fallos y devuelve cuántos publicó: con 0 no cuenta."""
        await _partida(qm_uow)
        publicador = _Publicador()
        publicador.devuelve = 0

        resumen, _ = await _cierra(qm_uow, golf_course_uow, PLAZO, publicador)

        assert (resumen.completed, resumen.published) == (1, 0)
