"""Las respuestas con código de competición nunca llevan el texto de la excepción (BE #562).

CodeQL (py/stack-trace-exposure) marcaba `detail=str(error)`. El `detail` sale
ahora de un diccionario fijo por código; las claves y la forma no cambian. Cada
excepción se lanza con un mensaje centinela, que no puede aparecer en la respuesta.
"""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.modules.competition.application.exceptions import (
    ActualizacionEnCursoError,
    ActualizacionNoPermitidaError,
    RefrescoDesactivadoError,
)
from src.modules.competition.application.services.franjas_al_cerrar import (
    PlayersWithoutTeeWindowError,
)
from src.modules.competition.application.services.handicaps_al_cerrar import (
    PlayersWithoutHandicapError,
)
from src.modules.competition.domain.exceptions.competition_violations import (
    InvitationNoRoomViolation,
)
from src.modules.competition.domain.services.ventana_de_actualizacion import CodigoDeVentana
from src.modules.competition.domain.value_objects.match_generation_block import BlockedPlayer
from src.modules.competition.infrastructure.api.v1 import (
    competition_state_routes as rutas,
)
from src.modules.competition.infrastructure.api.v1.invitation_routes import (
    RespondInvitationBody,
    respond_to_invitation,
)
from src.modules.competition.infrastructure.api.v1.tee_group_routes import _CON_JUGADORES
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.infrastructure.api.respuesta_con_codigo import DETALLE_GENERICO

CENTINELA = "CENTINELA-de-la-excepcion-7f3a"
NOMBRE = "Nombre Centinela"


def _cuerpo(respuesta) -> dict:
    return json.loads(respuesta.body)


def _jugador() -> BlockedPlayer:
    return BlockedPlayer(user_id=UserId.generate(), name=NOMBRE, missing="TEE_COLOR")


# --- Actualizar hándicaps (#541) -------------------------------------------------

# Los textos de hoy, que eran literales: no cambian
_AL_ACTUALIZAR = {
    CodigoDeVentana.STATUS: (
        "Los hándicaps se actualizan desde que se cierran las inscripciones hasta que "
        "termina la competición."
    ),
    CodigoDeVentana.NO_WINDOWS: "Sin franjas, se actualizan hasta iniciar la competición.",
    CodigoDeVentana.RYDER: "En una Ryder se actualizan hasta iniciar la competición.",
    CodigoDeVentana.DAY_IN_PLAY: "Hay una jornada en marcha: se podrá al acabar el día.",
    CodigoDeVentana.NO_DAYS_LEFT: "Ya no quedan jornadas por jugar.",
    CodigoDeVentana.TOO_CLOSE: (
        "Queda muy poco para la siguiente salida: no daría tiempo a preguntar por todos."
    ),
    CodigoDeVentana.NO_TIMEZONE: "El campo de la franja no tiene zona horaria.",
    CodigoDeVentana.IN_THE_PAST: "Prográmala para un momento en el futuro.",
    CodigoDeVentana.TOO_TIGHT: (
        "Demasiado justo: prográmala con al menos 2 minutos de margen antes de que se "
        "cierre la ventana."
    ),
    CodigoDeVentana.DISABLED: "La actualización con la RFEG solo está encendida en producción.",
    CodigoDeVentana.RUNNING: "Ya se están actualizando los hándicaps.",
}
# Al programar, el motivo de la ventana va tras «A esa hora no se podría: »; estos
# no son de la ventana y van sin él
_SIN_PREFIJO = {
    CodigoDeVentana.IN_THE_PAST,
    CodigoDeVentana.TOO_TIGHT,
    CodigoDeVentana.DISABLED,
    CodigoDeVentana.RUNNING,
}


def test_every_window_code_has_an_expected_text():
    assert set(_AL_ACTUALIZAR) == set(CodigoDeVentana)


@pytest.mark.parametrize("codigo", list(CodigoDeVentana), ids=str)
def test_not_allowed_answers_the_fixed_text_of_its_reason(codigo):
    """
    Given: Una actualización no permitida, con un mensaje centinela
    When: Se responde el 400
    Then: El detail es el texto fijo de su motivo, con las claves de siempre
    """
    cuerpo = _cuerpo(rutas._no_permitida(ActualizacionNoPermitidaError(CENTINELA, codigo)))

    assert cuerpo == {
        "detail": _AL_ACTUALIZAR[codigo],
        "error_code": "HANDICAP_UPDATE_NOT_ALLOWED",
        "reason_code": codigo.value,
    }


@pytest.mark.parametrize("codigo", list(CodigoDeVentana), ids=str)
def test_not_allowed_when_scheduling_keeps_its_prefix(codigo):
    """
    Given: Una programación no permitida, con un mensaje centinela
    When: Se responde el 400
    Then: El motivo de la ventana va con «A esa hora no se podría:», como hoy
    """
    error = ActualizacionNoPermitidaError(CENTINELA, codigo)
    cuerpo = _cuerpo(rutas._no_permitida(error, al_programar=True))

    esperado = _AL_ACTUALIZAR[codigo]
    if codigo not in _SIN_PREFIJO:
        esperado = f"A esa hora no se podría: {esperado}"
    assert cuerpo["detail"] == esperado
    assert CENTINELA not in json.dumps(cuerpo)


def test_not_allowed_without_reason_has_a_generic_text():
    cuerpo = _cuerpo(rutas._no_permitida(ActualizacionNoPermitidaError(CENTINELA)))

    assert cuerpo == {
        "detail": DETALLE_GENERICO,
        "error_code": "HANDICAP_UPDATE_NOT_ALLOWED",
        "reason_code": None,
    }


@pytest.mark.parametrize(
    ("error", "codigo"),
    [
        (ActualizacionEnCursoError(CENTINELA), "RUNNING"),
        (RefrescoDesactivadoError(CENTINELA), "DISABLED"),
    ],
    ids=["running", "disabled"],
)
def test_conflict_answers_the_fixed_text(error, codigo):
    """
    Given: Una actualización en marcha o apagada, con un mensaje centinela
    When: Se responde el 409
    Then: El texto fijo; el de RUNNING, exacto (lo simula un test del frontend)
    """
    respuesta = rutas._conflicto(error)

    assert respuesta.status_code == 409
    assert _cuerpo(respuesta) == {
        "detail": _AL_ACTUALIZAR[CodigoDeVentana(codigo)],
        "error_code": "HANDICAP_UPDATE_NOT_ALLOWED",
        "reason_code": codigo,
    }


def test_running_text_is_exactly_the_one_the_frontend_mocks():
    cuerpo = _cuerpo(rutas._conflicto(ActualizacionEnCursoError(CENTINELA)))

    assert cuerpo["detail"] == "Ya se están actualizando los hándicaps."


# --- Jugadores sin barra, hándicap o franja (C2) ----------------------------------

_CODIGOS_CON_JUGADORES = [
    "PLAYERS_WITHOUT_TEE",
    "PLAYERS_WITHOUT_HANDICAP",
    "PLAYERS_WITHOUT_TEE_WINDOW",
]


def test_tee_group_player_codes_are_covered():
    assert set(_CON_JUGADORES.values()) <= set(_CODIGOS_CON_JUGADORES)


@pytest.mark.parametrize("codigo", _CODIGOS_CON_JUGADORES)
def test_players_response_names_nobody_in_detail(codigo):
    """
    Given: Jugadores bloqueados, con nombre
    When: Se responde el 400 con la lista
    Then: El detail es genérico; los nombres van solo en `players`
    """
    respuesta = rutas.respuesta_con_jugadores(codigo, [_jugador()])
    cuerpo = _cuerpo(respuesta)

    assert respuesta.status_code == 400
    assert list(cuerpo) == ["detail", "error_code", "players"]
    assert cuerpo["error_code"] == codigo
    assert cuerpo["detail"] == rutas._DETALLE_CON_JUGADORES[codigo]
    assert NOMBRE not in cuerpo["detail"]
    assert cuerpo["players"][0]["name"] == NOMBRE


@pytest.mark.parametrize(
    ("respuesta", "error"),
    [
        (rutas.respuesta_sin_franja, PlayersWithoutTeeWindowError),
        (rutas.respuesta_sin_handicap, PlayersWithoutHandicapError),
    ],
    ids=["sin_franja", "sin_handicap"],
)
def test_close_enrollment_errors_do_not_leak_their_message(respuesta, error):
    """
    Given: El error de cerrar inscripciones, cuyo mensaje lleva los nombres
    When: Se responde
    Then: Ni el mensaje ni los nombres en el detail
    """
    excepcion = error([_jugador()])
    cuerpo = _cuerpo(respuesta(excepcion))

    assert str(excepcion) != cuerpo["detail"]
    assert NOMBRE not in cuerpo["detail"]


# --- Invitación sin plaza (#385) ---------------------------------------------------


async def test_no_room_answers_its_fixed_text():
    """
    Given: Una invitación sin plaza cuyo mensaje se ha cambiado por un centinela
    When: Se responde el 409
    Then: El texto de siempre, no el de la excepción
    """
    error = InvitationNoRoomViolation()
    error.args = (CENTINELA,)

    class _SinPlaza:
        async def execute(self, _dto):
            raise error

    respuesta = await respond_to_invitation(
        invitation_id=uuid4(),
        body=RespondInvitationBody(action="ACCEPT"),
        current_user=SimpleNamespace(id=uuid4()),
        use_case=_SinPlaza(),
    )

    assert respuesta.status_code == 409
    assert _cuerpo(respuesta) == {
        "detail": "Esta invitación se quedó sin plaza",
        "error_code": "INVITATION_NO_ROOM",
    }


# --- Un solo texto por motivo: el del dominio (BE #562) ---------------------------


def _dominio():
    # Dentro del test: si falta, falla el test y no la recogida
    from src.modules.competition.domain.services import ventana_de_actualizacion

    return ventana_de_actualizacion


@pytest.mark.parametrize("codigo", list(CodigoDeVentana), ids=str)
def test_route_text_is_the_domain_constant(codigo):
    """
    Given: El texto de cada motivo
    When: Se compara el de la ruta con el del dominio
    Then: Es el mismo, al actualizar y al programar (con el prefijo si es de la ventana)
    """
    dominio = _dominio()
    texto = dominio.MOTIVOS[codigo]

    assert rutas._DETALLE_AL_ACTUALIZAR[codigo] == texto
    if codigo in dominio.MOTIVOS_DE_LA_VENTANA:
        texto = f"{dominio.PREFIJO_A_ESA_HORA}{texto}"
    assert rutas._DETALLE_AL_PROGRAMAR[codigo] == texto


def test_every_code_has_a_domain_text():
    assert set(_dominio().MOTIVOS) == set(CodigoDeVentana)
