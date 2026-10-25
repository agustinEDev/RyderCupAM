"""
El instante en UTC con su zona, para que el cliente lo ponga en su hora local
(H5, 25 oct 2026). Las fechas de la partida rápida se guardan sin zona (en UTC,
BE #635): sin la zona, `new Date()` del navegador las tomaba como hora local.

| # | entrada                     | sale                         |
|---|-----------------------------|------------------------------|
| I1| sin zona                    | la misma hora, en UTC        |
| I2| con otra zona               | pasada a UTC                 |
| I3| None                        | None                         |
"""

from datetime import UTC, datetime, timedelta, timezone

from src.shared.domain.services.instante_utc import en_utc


def test_i1_sin_zona_es_utc():
    assert en_utc(datetime(2026, 10, 21, 22, 30)) == datetime(2026, 10, 21, 22, 30, tzinfo=UTC)
    assert en_utc(datetime(2026, 10, 21, 22, 30)).tzinfo is UTC


def test_i2_con_otra_zona_se_pasa_a_utc():
    madrid = timezone(timedelta(hours=2))
    resultado = en_utc(datetime(2026, 10, 22, 0, 30, tzinfo=madrid))
    assert resultado == datetime(2026, 10, 21, 22, 30, tzinfo=UTC)
    assert resultado.tzinfo is UTC


def test_i3_none():
    assert en_utc(None) is None


# BE #635 (25 oct 2026): las fechas de la partida rápida se guardan sin zona y se
# leen como UTC (`en_utc`, y el front desde la FE #710). Con `datetime.now()` eran
# la hora LOCAL del servidor: bien en Render (UTC), desplazadas en otra zona
def test_i4_la_partida_rapida_fecha_en_utc_aunque_el_servidor_este_en_otra_zona():
    """Given el proceso en la zona de Tokio / When se crea / Then sus fechas, en UTC."""
    import os
    import time
    from uuid import uuid4

    from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
    from src.modules.quick_match.domain.entities.quick_match import QuickMatch
    from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
    from src.modules.user.domain.value_objects.user_id import UserId
    from src.shared.domain.value_objects.match_format import MatchFormat

    # A mano y no con monkeypatch: este no vuelve a llamar a tzset al restaurar,
    # y los tests siguientes se quedarían con otra zona (CodeRabbit)
    zona_original = os.environ.get("TZ")
    os.environ["TZ"] = "Asia/Tokyo"
    time.tzset()
    try:
        qm = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=UserId(uuid4()),
            golf_course_id=GolfCourseId(uuid4()),
            match_format=MatchFormat.SINGLES,
        )
        ahora_utc = datetime.now(UTC).replace(tzinfo=None)
        assert qm.created_at.tzinfo is None
        assert abs(qm.created_at - ahora_utc) < timedelta(minutes=1)
        assert abs(qm.updated_at - ahora_utc) < timedelta(minutes=1)
    finally:
        if zona_original is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = zona_original
        time.tzset()
