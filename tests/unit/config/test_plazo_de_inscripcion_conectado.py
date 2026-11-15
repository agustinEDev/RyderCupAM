"""
El plazo de inscripción llega a cada puerta por la que se entra (15 nov 2026, C2), y sale
de un solo proveedor (16 nov 2026, F9).

Sin él, el caso de uso no lo mira: olvidarlo en un proveedor dejaría esa puerta abierta.
"""

from types import SimpleNamespace

import pytest

from src.config.dependencies import (
    get_activate_competition_use_case,
    get_direct_enroll_player_use_case,
    get_handle_enrollment_use_case,
    get_plazo_de_inscripcion,
    get_request_enrollment_use_case,
    get_respond_to_invitation_use_case,
    get_send_invitation_by_email_use_case,
    get_send_invitation_by_user_id_use_case,
    get_update_competition_use_case,
)
from src.modules.competition.application.services.plazo_de_inscripcion import (
    PlazoDeInscripcion,
)

UOW = SimpleNamespace(competitions=object())
USER_UOW = SimpleNamespace(users=object())
GC_UOW = SimpleNamespace(golf_courses=object())
PLAZO = PlazoDeInscripcion(object())  # type: ignore[arg-type]


def test_el_proveedor_usa_la_zona_del_primer_campo():
    """F9. Given las unidades de trabajo / Then un plazo con la zona de sus campos."""
    plazo = get_plazo_de_inscripcion(uow=UOW, gc_uow=GC_UOW)

    assert isinstance(plazo, PlazoDeInscripcion)
    assert plazo.zonas._golf_courses is GC_UOW.golf_courses
    assert plazo.zonas._competitions is UOW.competitions


@pytest.mark.parametrize(
    "construir",
    [
        lambda: get_request_enrollment_use_case(
            uow=UOW, user_uow=USER_UOW, actividad=object(), plazo=PLAZO
        ),
        lambda: get_handle_enrollment_use_case(
            uow=UOW, user_uow=USER_UOW, actividad=object(), plazo=PLAZO
        ),
        lambda: get_send_invitation_by_user_id_use_case(
            uow=UOW, user_uow=USER_UOW, email_service=object(), actividad=object(), plazo=PLAZO
        ),
        lambda: get_send_invitation_by_email_use_case(
            uow=UOW, user_uow=USER_UOW, email_service=object(), actividad=object(), plazo=PLAZO
        ),
        lambda: get_respond_to_invitation_use_case(
            uow=UOW, user_uow=USER_UOW, actividad=object(), plazo=PLAZO
        ),
        lambda: get_direct_enroll_player_use_case(
            uow=UOW, user_uow=USER_UOW, actividad=object(), plazo=PLAZO
        ),
        lambda: get_update_competition_use_case(
            uow=UOW,
            location_builder=object(),
            golf_course_uow=GC_UOW,
            actividad=object(),
            plazo=PLAZO,
        ),
    ],
    ids=[
        "apuntarse",
        "aprobar",
        "invitar-por-id",
        "invitar-por-correo",
        "aceptar",
        "inscribir-a-mano",
        "mover-una-cerrada",
    ],
)
def test_cada_puerta_lleva_el_plazo(construir):
    """C2. Given el proveedor de la API / When construye el caso de uso / Then lleva el plazo."""
    assert construir()._plazo is PLAZO


def test_apuntarse_reutiliza_la_zona_del_plazo():
    """F9. Given el plazo / Then la apertura programada mira la misma zona."""
    caso = get_request_enrollment_use_case(
        uow=UOW, user_uow=USER_UOW, actividad=object(), plazo=PLAZO
    )

    assert caso._zonas is PLAZO.zonas


def test_activar_abre_a_su_hora_con_la_zona_del_plazo():
    """F7. Given el plazo / Then activar usa su zona para abrir a su hora una programada."""
    caso = get_activate_competition_use_case(uow=UOW, plazo=PLAZO)

    assert caso._zonas is PLAZO.zonas
