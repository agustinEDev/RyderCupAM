"""
El plazo de inscripción llega a cada puerta por la que se entra (15 nov 2026, C2).

Sin él, el caso de uso no lo mira: olvidarlo en un proveedor dejaría esa puerta abierta.
"""

from types import SimpleNamespace

import pytest

from src.config.dependencies import (
    get_direct_enroll_player_use_case,
    get_handle_enrollment_use_case,
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


@pytest.mark.parametrize(
    "construir",
    [
        lambda: get_request_enrollment_use_case(
            uow=UOW, user_uow=USER_UOW, gc_uow=GC_UOW, actividad=object()
        ),
        lambda: get_handle_enrollment_use_case(
            uow=UOW, user_uow=USER_UOW, gc_uow=GC_UOW, actividad=object()
        ),
        lambda: get_send_invitation_by_user_id_use_case(
            uow=UOW, user_uow=USER_UOW, gc_uow=GC_UOW, email_service=object(), actividad=object()
        ),
        lambda: get_send_invitation_by_email_use_case(
            uow=UOW, user_uow=USER_UOW, gc_uow=GC_UOW, email_service=object(), actividad=object()
        ),
        lambda: get_respond_to_invitation_use_case(
            uow=UOW, user_uow=USER_UOW, gc_uow=GC_UOW, actividad=object()
        ),
        lambda: get_direct_enroll_player_use_case(
            uow=UOW, user_uow=USER_UOW, gc_uow=GC_UOW, actividad=object()
        ),
        lambda: get_update_competition_use_case(
            uow=UOW, location_builder=object(), golf_course_uow=GC_UOW, actividad=object()
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
    caso = construir()

    assert isinstance(caso._plazo, PlazoDeInscripcion)
    assert caso._plazo._zonas._golf_courses is GC_UOW.golf_courses
    assert caso._plazo._zonas._competitions is UOW.competitions
