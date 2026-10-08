"""El JSONB de participantes guarda y lee el hándicap fijado al empezar (BE #514)."""

from uuid import uuid4

from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.quick_match.infrastructure.persistence.mappers.quick_match_mapper import (
    QuickMatchParticipantsJsonType,
)
from src.modules.user.domain.value_objects.user_id import UserId

TIPO = QuickMatchParticipantsJsonType()


def _ida_y_vuelta(participante):
    return TIPO.process_result_value(TIPO.process_bind_param([participante], None), None)[0]


def test_el_indice_fijado_sobrevive_al_guardado():
    fijado = QuickMatchParticipant.for_user(UserId(uuid4())).frozen_with(18.5)

    leido = _ida_y_vuelta(fijado)

    assert leido.handicap_frozen is True
    assert leido.effective_handicap(profile_handicap=30.0) == 18.5


def test_empezar_sin_handicap_tambien_queda_fijado():
    fijado = QuickMatchParticipant.for_user(UserId(uuid4())).frozen_with(None)

    leido = _ida_y_vuelta(fijado)

    assert leido.handicap_frozen is True
    assert leido.effective_handicap(profile_handicap=30.0) is None


def test_una_partida_guardada_antes_del_cambio_se_lee_sin_fijar():
    """El JSON viejo no trae las claves: sigue mirando el perfil, como hasta ahora."""
    viejo = [
        {
            "participant_id": str(uuid4()),
            "user_id": str(uuid4()),
            "first_name": None,
            "last_name": None,
            "handicap": None,
            "custom_handicap": None,
            "team": None,
            "tee_color": "YELLOW",
            "tee_gender": "MALE",
        }
    ]

    leido = TIPO.process_result_value(viejo, None)[0]

    assert leido.handicap_frozen is False
    assert leido.effective_handicap(profile_handicap=30.0) == 30.0
