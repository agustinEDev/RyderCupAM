"""Tests de ActivityEvent (BE #175)."""

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.user.domain.value_objects.user_id import UserId


@pytest.fixture
def user_id():
    return UserId(str(uuid4()))


class TestCreacion:
    def test_crea_un_evento_con_su_identidad(self, user_id):
        evento = ActivityEvent.create(
            user_id=user_id,
            type=ActivityEventType.BIRDIE,
            occurred_at=datetime(2026, 8, 10, 12, 0),
            payload={"count": 3, "holes": [1, 5, 9]},
            source_match_id="match-1",
        )

        assert isinstance(evento.id, UUID)
        assert evento.user_id == user_id
        assert evento.type == ActivityEventType.BIRDIE
        assert evento.payload == {"count": 3, "holes": [1, 5, 9]}
        assert evento.source_match_id == "match-1"

    def test_el_payload_no_se_puede_mutar_desde_fuera(self, user_id):
        payload = {"count": 3}
        evento = ActivityEvent.create(
            user_id=user_id,
            type=ActivityEventType.BIRDIE,
            occurred_at=datetime(2026, 8, 10),
            payload=payload,
            source_match_id="match-1",
        )

        payload["count"] = 99
        evento.payload["count"] = 77

        assert evento.payload == {"count": 3}

    def test_un_evento_sin_payload_es_valido(self, user_id):
        """Estrenar campo no necesita detalle: el hecho es el evento."""
        evento = ActivityEvent.create(
            user_id=user_id,
            type=ActivityEventType.NEW_COURSE,
            occurred_at=datetime(2026, 8, 10),
            source_match_id="match-1",
        )

        assert evento.payload == {}

    def test_exige_un_user_id_de_verdad(self):
        with pytest.raises(TypeError, match="user_id"):
            ActivityEvent.create(
                user_id="no-soy-un-user-id",
                type=ActivityEventType.BIRDIE,
                occurred_at=datetime(2026, 8, 10),
                source_match_id="match-1",
            )

    def test_exige_un_tipo_de_evento_conocido(self, user_id):
        with pytest.raises(TypeError, match="type"):
            ActivityEvent.create(
                user_id=user_id,
                type="BIRDIE",
                occurred_at=datetime(2026, 8, 10),
                source_match_id="match-1",
            )


class TestIdentidad:
    def test_dos_eventos_distintos_no_son_iguales(self, user_id):
        comun = {
            "user_id": user_id,
            "type": ActivityEventType.BIRDIE,
            "occurred_at": datetime(2026, 8, 10),
            "source_match_id": "match-1",
        }

        assert ActivityEvent.create(**comun) != ActivityEvent.create(**comun)

    def test_reconstruir_conserva_la_identidad(self, user_id):
        id_ = uuid4()
        evento = ActivityEvent.reconstruct(
            id=id_,
            user_id=user_id,
            type=ActivityEventType.EAGLE_OR_BETTER,
            occurred_at=datetime(2026, 8, 10),
            payload={},
            source_match_id="match-1",
        )

        assert evento.id == id_

    def test_exige_la_partida_de_la_que_sale(self, user_id):
        """
        Sin partida, la clave unica de la tabla no protege: en Postgres un NULL
        no iguala a otro, asi que reprocesar publicaria el logro otra vez.
        """
        with pytest.raises(ValueError, match="source_match_id is required"):
            ActivityEvent.create(
                user_id=user_id,
                type=ActivityEventType.BIRDIE,
                occurred_at=datetime(2026, 8, 10),
                source_match_id="",
            )

    def test_sabe_de_que_partida_viene(self, user_id):
        evento = ActivityEvent.create(
            user_id=user_id,
            type=ActivityEventType.BIRDIE,
            occurred_at=datetime(2026, 8, 10),
            source_match_id="match-1",
        )

        assert evento.is_from("match-1")
        assert not evento.is_from("match-2")


class TestTipos:
    def test_reconoce_los_tipos_publicables(self):
        assert ActivityEventType.from_string("HOLE_IN_ONE") == ActivityEventType.HOLE_IN_ONE

    def test_rechaza_un_tipo_inventado(self):
        with pytest.raises(ValueError, match="Unknown activity event type"):
            ActivityEventType.from_string("JUGO_MUY_MAL")

    def test_no_existe_ningun_tipo_que_delate_una_vuelta_mala(self):
        """
        La lista es corta a proposito. Si alguien anade aqui un ROUND_PLAYED o
        similar, el feed empezara a publicar los dias malos y la gente dejara de
        anotar sus tarjetas (ver BE #173).
        """
        assert {t.value for t in ActivityEventType} == {
            "HOLE_IN_ONE",
            "EAGLE_OR_BETTER",
            "BIRDIE",
            "NEW_COURSE",
            "PERSONAL_BEST",
            "FIRST_TOURNAMENT",
        }
