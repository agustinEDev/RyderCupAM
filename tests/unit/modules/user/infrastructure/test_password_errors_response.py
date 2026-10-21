"""El 400 de una contraseña o un token de reseteo, sin el texto de la excepción (BE #562).

`detail` sale de un texto fijo por `error_code`; el código no cambia. Cada error
se lanza con un mensaje centinela, que no puede aparecer en la respuesta.
"""

import json

import pytest

from src.modules.user.domain.exceptions.invalid_reset_token_error import InvalidResetTokenError
from src.modules.user.domain.value_objects.password import InvalidPasswordError, Password
from src.modules.user.infrastructure.api.v1.password_errors import _DETALLE, coded_bad_request
from src.shared.infrastructure.api.respuesta_con_codigo import DETALLE_GENERICO

CENTINELA = "CENTINELA-de-la-excepcion-7f3a"

# Una contraseña que rompe cada regla de la política
_POR_REGLA = {
    "PASSWORD_EMPTY": "",
    "PASSWORD_EDGE_SPACES": " Abcdefghij1!",
    "PASSWORD_TOO_SHORT": "Ab1!",
    "PASSWORD_TOO_LONG": "Ab1!" + "x" * 200,
    "PASSWORD_NO_UPPERCASE": "abcdefghij1!",
    "PASSWORD_NO_LOWERCASE": "ABCDEFGHIJ1!",
    "PASSWORD_NO_DIGIT": "Abcdefghijk!",
    "PASSWORD_NO_SYMBOL": "Abcdefghijk1",
    "PASSWORD_TOO_COMMON": "Password123!",
}

# Los textos de hoy; la longitud, sin el «(actualmente: N)» que dependía de lo tecleado
_ESPERADO = {
    "PASSWORD_EMPTY": "La contraseña no puede estar vacía",
    "PASSWORD_EDGE_SPACES": "La contraseña no puede tener espacios al inicio o final",
    "PASSWORD_TOO_SHORT": "La contraseña debe tener al menos 12 caracteres",
    "PASSWORD_TOO_LONG": "La contraseña no puede exceder 128 caracteres",
    "PASSWORD_NO_UPPERCASE": "La contraseña debe contener al menos una letra mayúscula (A-Z)",
    "PASSWORD_NO_LOWERCASE": "La contraseña debe contener al menos una letra minúscula (a-z)",
    "PASSWORD_NO_DIGIT": "La contraseña debe contener al menos un número (0-9)",
    "PASSWORD_NO_SYMBOL": (
        "La contraseña debe contener al menos un carácter especial (!@#$%^&*()_+-=[]{}|;:,.<>?)"
    ),
    "PASSWORD_TOO_COMMON": (
        "Esta contraseña es demasiado común y fácil de adivinar. Por favor, elige una "
        "contraseña más única"
    ),
    "PASSWORD_REUSED": (
        "Cannot reuse any of your last 5 passwords. Please choose a different password."
    ),
    "PASSWORD_INVALID": "La contraseña no es válida",
    "RESET_TOKEN_INVALID": "Token de reseteo inválido o expirado",
}


@pytest.mark.parametrize(("codigo", "password"), list(_POR_REGLA.items()))
def test_every_policy_code_has_a_text(codigo, password):
    """
    Given: Una contraseña que rompe una regla
    When: El dominio la rechaza
    Then: Su código tiene texto fijo en la respuesta
    """
    with pytest.raises(InvalidPasswordError) as error:
        Password.from_plain_text(password)

    assert error.value.error_code == codigo
    assert codigo in _DETALLE


def test_the_dictionary_has_exactly_the_expected_texts():
    assert _DETALLE == _ESPERADO


@pytest.mark.parametrize("codigo", sorted(_ESPERADO.keys() - {"RESET_TOKEN_INVALID"}))
def test_password_error_answers_the_fixed_text(codigo):
    """
    Given: Un error de contraseña con un mensaje centinela
    When: Se responde el 400
    Then: El texto fijo de su código, nunca el de la excepción
    """
    respuesta = coded_bad_request(InvalidPasswordError(CENTINELA, error_code=codigo))

    assert respuesta.status_code == 400
    assert json.loads(respuesta.body) == {"detail": _ESPERADO[codigo], "error_code": codigo}


def test_reset_token_error_answers_the_fixed_text():
    respuesta = coded_bad_request(InvalidResetTokenError(CENTINELA))

    assert json.loads(respuesta.body) == {
        "detail": "Token de reseteo inválido o expirado",
        "error_code": "RESET_TOKEN_INVALID",
    }


def test_unknown_code_gets_a_generic_text_not_the_message():
    cuerpo = json.loads(coded_bad_request(InvalidPasswordError(CENTINELA, "NUEVO")).body)

    assert CENTINELA not in json.dumps(cuerpo)
    assert cuerpo == {"detail": DETALLE_GENERICO, "error_code": "NUEVO"}


# --- Un solo texto: el del dominio (BE #562) -------------------------------------


def _mensajes():
    # Dentro del test: si falta, falla el test y no la recogida
    from src.modules.user.domain.value_objects.password import MENSAJES_DE_LA_CONTRASENA

    return MENSAJES_DE_LA_CONTRASENA


@pytest.mark.parametrize("codigo", sorted(_ESPERADO.keys() - {"RESET_TOKEN_INVALID"}))
def test_route_text_is_the_domain_text(codigo):
    """
    Given: El texto de cada código de contraseña
    When: Se compara el de la ruta con el del dominio
    Then: Es el mismo, así que no pueden divergir
    """
    assert _DETALLE[codigo] == _mensajes()[codigo]


def test_reset_token_route_text_is_the_domain_text():
    assert _DETALLE["RESET_TOKEN_INVALID"] == InvalidResetTokenError.MENSAJE
    assert str(InvalidResetTokenError()) == InvalidResetTokenError.MENSAJE


@pytest.mark.parametrize(("codigo", "password"), list(_POR_REGLA.items()))
def test_domain_raises_with_its_own_text(codigo, password):
    """
    Given: Una contraseña que rompe una regla
    When: El dominio la rechaza
    Then: Su mensaje empieza por el texto del código (la longitud añade lo tecleado)
    """
    with pytest.raises(InvalidPasswordError) as error:
        Password.from_plain_text(password)

    mensaje = str(error.value)
    if codigo in ("PASSWORD_TOO_SHORT", "PASSWORD_TOO_LONG"):
        assert mensaje == f"{_mensajes()[codigo]} (actualmente: {len(password)})"
    else:
        assert mensaje == _mensajes()[codigo]
