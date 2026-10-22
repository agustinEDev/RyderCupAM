"""Tests de ActivityEvent (BE #175)."""

from datetime import UTC, datetime, timedelta
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


class TestPublicacion:
    """
    Cuando se publico, que no es cuando se jugo: un torneo publica al cerrarse
    vueltas de hace dias, y el aviso de novedades y el orden del feed se rigen
    por lo primero.
    """

    def test_sin_fecha_de_publicacion_se_publica_ahora_en_utc(self, user_id):
        """
        Given un evento creado sin `published_at` / When se crea / Then lleva
        el momento actual en UTC y sin zona, como el resto de fechas guardadas.
        """
        antes = datetime.now(UTC).replace(tzinfo=None)

        evento = ActivityEvent.create(
            user_id=user_id,
            type=ActivityEventType.BIRDIE,
            occurred_at=datetime(2026, 8, 1),
            source_match_id="match-1",
        )

        despues = datetime.now(UTC).replace(tzinfo=None)
        assert evento.published_at.tzinfo is None
        assert antes <= evento.published_at <= despues

    def test_respeta_la_fecha_de_publicacion_dada(self, user_id):
        """Given un `published_at` explicito / When se crea / Then se conserva."""
        publicado = datetime(2026, 8, 12, 9, 30)

        evento = ActivityEvent.create(
            user_id=user_id,
            type=ActivityEventType.BIRDIE,
            occurred_at=publicado - timedelta(days=3),
            source_match_id="match-1",
            published_at=publicado,
        )

        assert evento.published_at == publicado
        assert evento.occurred_at == publicado - timedelta(days=3)

    def test_por_defecto_lo_ven_los_amigos(self, user_id):
        """Given un evento sin indicar visibilidad / When se crea / Then es visible a amigos."""
        evento = ActivityEvent.create(
            user_id=user_id,
            type=ActivityEventType.BIRDIE,
            occurred_at=datetime(2026, 8, 1),
            source_match_id="match-1",
        )

        assert evento.visible_to_friends is True

    def test_se_puede_publicar_solo_para_el_autor(self, user_id):
        """
        Given la publicacion apagada / When se crea el evento oculto / Then no
        es visible a los amigos.
        """
        evento = ActivityEvent.create(
            user_id=user_id,
            type=ActivityEventType.BIRDIE,
            occurred_at=datetime(2026, 8, 1),
            source_match_id="match-1",
            visible_to_friends=False,
        )

        assert evento.visible_to_friends is False


class TestTipos:
    def test_reconoce_los_tipos_publicables(self):
        assert ActivityEventType.from_string("HOLE_IN_ONE") == ActivityEventType.HOLE_IN_ONE

    def test_rechaza_un_tipo_inventado(self):
        with pytest.raises(ValueError, match="Unknown activity event type"):
            ActivityEventType.from_string("JUGO_MUY_MAL")

    def test_la_lista_de_tipos_es_la_aprobada(self):
        """
        La lista es corta a proposito: cada tipo nuevo es una decision de
        producto. Los seis logros (BE #175) y los avisos de BE-2 (tabla del 21
        oct 2026). `QUICK_MATCH_FINISHED` publica tambien una vuelta mala —el
        ultimo puesto sale— porque asi lo decidio Agustin: las partidas rapidas
        de los amigos, todas, con puesto y puntos.
        """
        assert {t.value for t in ActivityEventType} == {
            "HOLE_IN_ONE",
            "EAGLE_OR_BETTER",
            "BIRDIE",
            "NEW_COURSE",
            "PERSONAL_BEST",
            "FIRST_TOURNAMENT",
            "ENROLLMENT_APPROVED",
            "INVITED_TO_TOURNAMENT",
            "ENROLLMENT_REQUEST_CLOSED",
            "ENROLLMENT_REJECTED",
            "ENROLLED_IN_TOURNAMENT",
            "TOURNAMENT_MATCH_RESULT",
            "TOURNAMENT_FINAL_STANDING",
            "QUICK_MATCH_FINISHED",
            # Tabla del 22 oct 2026, C
            "ENROLLMENT_CONFIRMED",
            # Aviso de horario (G, tabla del 22 oct 2026)
            "TEE_TIME_ASSIGNED",
        }
