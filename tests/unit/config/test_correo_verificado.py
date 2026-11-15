"""
Correo verificado para lo que llega a otras personas (B-17 de la auditoría de la fase 6).

    caso                                              | qué pasa
    --------------------------------------------------|----------------------------------
    sin verificar                                     | EmailNotVerifiedError
    verificado                                        | pasa el usuario
    la respuesta                                      | 403 con error_code EMAIL_NOT_VERIFIED
    V1-V3 crear competición, pedir amistad, invitar   | usan esta dependencia
    V4 aceptar una amistad o una invitación           | no la usan
"""

import inspect
import json
from types import SimpleNamespace

import pytest

from src.config.correo_verificado import (
    EmailNotVerifiedError,
    email_not_verified_handler,
    usuario_con_correo_verificado,
)
from src.modules.competition.infrastructure.api.v1 import competition_crud_routes, invitation_routes
from src.modules.social.infrastructure.api.v1 import friend_routes

pytestmark = pytest.mark.asyncio


async def test_an_unverified_user_is_stopped():
    with pytest.raises(EmailNotVerifiedError):
        await usuario_con_correo_verificado(SimpleNamespace(email_verified=False))


async def test_a_verified_user_goes_through():
    usuario = SimpleNamespace(email_verified=True)

    assert await usuario_con_correo_verificado(usuario) is usuario


async def test_the_answer_is_403_with_its_code():
    respuesta = await email_not_verified_handler(None, EmailNotVerifiedError())

    assert respuesta.status_code == 403
    assert json.loads(respuesta.body)["error_code"] == "EMAIL_NOT_VERIFIED"


def _dependencia_del_usuario(funcion) -> object:
    return inspect.signature(funcion).parameters["current_user"].default.dependency


@pytest.mark.parametrize(
    "ruta",
    [
        competition_crud_routes.create_competition,
        friend_routes.send_friend_request,
        invitation_routes.send_invitation_by_user_id,
        invitation_routes.send_invitation_by_email,
    ],
)
async def test_v1_v3_the_outreach_routes_require_it(ruta):
    assert _dependencia_del_usuario(inspect.unwrap(ruta)) is usuario_con_correo_verificado


@pytest.mark.parametrize(
    "ruta",
    [friend_routes.respond_to_friend_request, invitation_routes.respond_to_invitation],
)
async def test_v4_accepting_does_not_require_it(ruta):
    assert _dependencia_del_usuario(inspect.unwrap(ruta)) is not usuario_con_correo_verificado
